"""Private owner/sudo voice diagnostics and owner-only process restart."""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys

from pyrogram import filters
from pyrogram.types import Message

import config
from videl import assistant, bot, call_py
from videl.core.audio_quality import LABELS, PRESETS, audio_quality_label, current_quality, set_runtime_quality
from videl.core.playback_state import sessions
from videl.modules.block import owner_or_sudo
from videl.utils.command_ui import rich_reply, rich_send, usage
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
        rows = [("Current", f"<b>{rich_esc(audio_quality_label())}</b>")]
        rows.extend((name.title(), rich_esc(LABELS[name])) for name in PRESETS)
        return await rich_reply(
            message,
            rich_heading("🎚 Voice-chat quality", level=3)
            + rich_kv_table(rows)
            + rich_note("Set a preset with <code>/voicequality medium</code>. It applies to new streams; ask a current group admin to use <code>/replay</code> to restart the current track at the new quality."),
        )

    quality = args[0].casefold()
    persisted = await asyncio.to_thread(set_bot_setting, "voice_audio_quality", quality)
    if not set_runtime_quality(quality):
        return await rich_reply(message, "That voice quality preset is not supported.")
    storage_note = (
        "Saved for future restarts."
        if persisted else "Applied for this process only; MongoDB is unavailable, so it could not be saved."
    )
    await rich_reply(
        message,
        rich_heading("✅ Voice quality updated", level=3)
        + rich_kv_table([("Preset", rich_esc(LABELS[quality])), ("Persistence", storage_note)])
        + rich_note("New voice streams use this preset. The currently playing track keeps its existing stream settings until it is replayed."),
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
