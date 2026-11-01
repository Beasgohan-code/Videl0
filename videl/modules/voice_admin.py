"""Private owner/sudo voice diagnostics and owner-only process restart."""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys
from types import SimpleNamespace as NS

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from videl import assistant, bot, call_py
from videl.core.audio_quality import LABELS, PRESETS, audio_quality_label, current_quality, set_runtime_quality
from videl.core.playback_state import sessions
from videl.modules.block import owner_or_sudo
from videl.utils.bot_ui import button
from videl.utils.command_ui import rich_edit, rich_reply, rich_send, usage
from videl.utils.db import is_sudo_user, set_bot_setting
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note

LOGGER = logging.getLogger(__name__)


def _private_self_chat(message: Message) -> bool:
    user = getattr(message, "from_user", None)
    chat = getattr(message, "chat", None)
    chat_type = getattr(getattr(chat, "type", None), "value", getattr(chat, "type", None))
    return bool(
        user and chat and str(chat_type).casefold() == "private"
        and int(getattr(user, "id", 0) or 0) == int(getattr(chat, "id", 0) or 0)
    )


async def _can_manage_voice_settings(message: Message) -> bool:
    if not _private_self_chat(message):
        return False
    user_id = int(message.from_user.id)
    if user_id == int(config.OWNER_ID):
        return True
    try:
        return bool(await asyncio.to_thread(is_sudo_user, user_id))
    except Exception:
        return False


def _quality_keyboard() -> InlineKeyboardMarkup:
    selected = current_quality()
    names = tuple(PRESETS)
    rows = []
    for start in range(0, len(names), 2):
        row = []
        for name in names[start:start + 2]:
            label = f"✓ {name.title()}" if name == selected else name.title()
            row.append(button(
                label,
                callback_data=f"voicequality:{name}",
                style="success" if name == selected else "default",
            ))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def _quality_panel(*, persistence: str | None = None) -> str:
    body = (
        rich_heading("🎚 Voice-chat quality", level=3)
        + rich_kv_table([("Current", f"<b>{rich_esc(audio_quality_label())}</b>")])
        + rich_kv_table([(name.title(), rich_esc(LABELS[name])) for name in PRESETS])
        + rich_note("Choose a preset below. It applies to new streams; use <code>/replay</code> to restart a current track at the selected quality.")
    )
    if persistence:
        body += rich_note(rich_esc(persistence))
    return body


async def _apply_quality(quality: str) -> bool:
    """Persist when possible, then apply now for new streams in this process."""
    try:
        persisted = await asyncio.to_thread(set_bot_setting, "voice_audio_quality", quality)
    except Exception as error:
        LOGGER.warning("Could not persist voice quality (%s); applying for this process", type(error).__name__)
        persisted = False
    # `quality` has already been checked against PRESETS by the caller.
    set_runtime_quality(quality)
    return bool(persisted)


@bot.on_message(
    filters.command("voicequality", prefixes=config.COMMAND_PREFIX_LIST)
    & filters.private & owner_or_sudo
)
async def voice_quality_command(_, message: Message) -> None:
    """Inspect/change global voice uplink quality; sudo is private-chat only."""
    if not await _can_manage_voice_settings(message):
        return await rich_reply(message, "Only the owner or an active bot sudo operator can change voice quality in private chat.")
    args = list(getattr(message, "command", []) or [])[1:]
    if len(args) > 1 or (args and args[0].casefold() not in PRESETS):
        return await rich_reply(
            message,
            usage(
                "/voicequality [studio|high|medium|low]",
                "Choose Studio 96 kbps stereo, High 48 kbps stereo, Medium 36 kbps mono, or Low 24 kbps mono.",
            ),
        )
    if not args:
        return await rich_reply(
            message,
            _quality_panel(),
            reply_markup=_quality_keyboard(),
        )

    quality = args[0].casefold()
    persisted = await _apply_quality(quality)
    storage_note = (
        "Saved for future restarts."
        if persisted else "Applied for this process only; MongoDB is unavailable, so it could not be saved."
    )
    await rich_reply(
        message,
        rich_heading("✅ Voice quality updated", level=3)
        + rich_kv_table([("Preset", rich_esc(LABELS[quality])), ("Persistence", storage_note)])
        + rich_note("New streams use this preset; the current stream is unchanged. Use <code>/replay</code> to restart the current track."),
        reply_markup=_quality_keyboard(),
    )


@bot.on_callback_query(filters.regex(r"^voicequality:(?:studio|high|medium|low)$"))
async def voice_quality_callback(client, query) -> None:
    """Apply a preset from the owner/sudo private panel after fresh auth checks."""
    message = getattr(query, "message", None)
    actor = getattr(query, "from_user", None)
    chat = getattr(message, "chat", None) if message is not None else None
    if (message is None or actor is None or chat is None
            or str(getattr(getattr(chat, "type", None), "value", getattr(chat, "type", None))).casefold() != "private"
            or int(getattr(chat, "id", 0) or 0) != int(getattr(actor, "id", 0) or 0)):
        return await query.answer("Open voice quality settings in your own private chat.", show_alert=True)

    try:
        bot_user = getattr(client, "me", None) or await client.get_me()
    except Exception:
        return await query.answer("I could not verify this settings panel.", show_alert=True)
    if int(getattr(getattr(message, "from_user", None), "id", 0) or 0) != int(getattr(bot_user, "id", 0) or 0):
        return await query.answer("This is not a Videl voice-quality panel.", show_alert=True)

    if not await _can_manage_voice_settings(NS(from_user=actor, chat=chat)):
        return await query.answer("Only the owner or an active sudo operator can change voice quality.", show_alert=True)

    data = str(getattr(query, "data", "") or "")
    quality = data.partition(":")[2]
    if data != f"voicequality:{quality}" or quality not in PRESETS:
        return await query.answer("That voice-quality preset is invalid.", show_alert=True)

    persisted = await _apply_quality(quality)
    persistence = (
        "Saved for future restarts."
        if persisted else "Applied for this process only; MongoDB is unavailable, so it could not be saved."
    )
    await query.answer(f"{quality.title()} quality applied")
    await rich_edit(
        message,
        _quality_panel(persistence=persistence),
        reply_markup=_quality_keyboard(),
    )


@bot.on_message(
    filters.command("voicehealth", prefixes=config.COMMAND_PREFIX_LIST)
    & filters.private & owner_or_sudo
)
async def voice_health_command(_, message: Message) -> None:
    """Show safe voice-stack diagnostics without probing or exposing credentials."""
    if not await _can_manage_voice_settings(message):
        return await rich_reply(message, "Voice diagnostics are private to the owner and active bot sudo operators.")
    from videl.utils.assistant import assistant_status
    from videl.utils.downloader_status import downloader_status

    assistant_info = assistant_status()
    downloader_info = downloader_status()
    quality = rich_esc(audio_quality_label())
    assistant_state = "Connected" if assistant_info["ready"] else assistant_info["state"].replace("_", " ").title()
    engine_state = "Available" if call_py is not None and assistant_info["ready"] else "Not ready"
    ffmpeg_state = "Installed" if shutil.which("ffmpeg") else "Missing"
    api_state = downloader_info["shruti"]["state"].replace("_", " ").title()
    rows = [
        ("Voice quality", quality),
        ("Assistant session", rich_esc(assistant_state)),
        ("PyTgCalls engine", engine_state),
        ("FFmpeg", ffmpeg_state),
        ("Active streams", str(len(sessions))),
        ("Primary media API", rich_esc(api_state)),
    ]
    body = rich_heading("🔎 Voice diagnostics", level=3) + rich_kv_table(rows)
    if not assistant_info["ready"]:
        body += rich_note("Check the assistant session and startup logs. Voice playback requires the assistant client and PyTgCalls to start successfully.")
    else:
        body += rich_note("If audio stutters for all tracks, try <code>/voicequality medium</code>. If only one source fails, check its downloader logs instead.")
    await rich_reply(message, body)


@bot.on_message(
    filters.command("restart", prefixes=config.COMMAND_PREFIX_LIST)
    & filters.private & filters.user(config.OWNER_ID)
)
async def restart_command(_, message: Message) -> None:
    """Replace the running backend process after owner confirmation."""
    if not _private_self_chat(message) or int(message.from_user.id) != int(config.OWNER_ID):
        return await rich_reply(message, "Only the owner can restart Videl from a private chat.")

    await rich_reply(
        message,
        rich_heading("🔄 Restarting Videl", level=3)
        + rich_note("The bot and active voice chats will briefly disconnect while the service starts again."),
    )
    await asyncio.sleep(1.0)
    argv = [sys.executable, "-m", "videl", *sys.argv[1:]]
    LOGGER.warning("Owner requested process restart")
    try:
        os.execv(sys.executable, argv)
    except OSError as error:
        LOGGER.error("Process restart failed (%s)", type(error).__name__)
        await rich_send(bot, message.chat.id, "Automatic restart failed; restart the service from Render instead.")
