# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import time

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, Message
from videl.utils.bot_ui import button as InlineKeyboardButton

from videl import bot, call_py, LOGGER
from videl.core.queue import peek_current
from videl.modules.block import group_allowed, user_allowed
from videl.utils.formatters import fmt_time, parse_dur, progress_bar, short
from videl.utils.rich_ui import rich_esc, rich_heading, rich_img, rich_kv_table, rich_note
from videl.utils.command_ui import rich_edit, rich_send
from videl.utils.youtube import resolve_stream

# ── Seek state tracker ─────────────────────────────────────────────────────────
_seek_state: dict[int, dict] = {}


def set_seek_state(chat_id: int, offset: int) -> None:
    _seek_state[chat_id] = {"start_ts": time.time(), "offset": offset}


def get_current_position(chat_id: int) -> int:
    from videl.core.player import current_position
    return int(current_position(chat_id))


def clear_seek_state(chat_id: int) -> None:
    _seek_state.pop(chat_id, None)


# ── Internal seek ──────────────────────────────────────────────────────────────

async def _seek_to(chat_id: int, target_sec: int, message: Message) -> None:
    from pytgcalls.types import AudioQuality, MediaStream

    song = peek_current(chat_id)
    if not song:
        await rich_send(bot, chat_id, rich_heading("❍ nothing is playing right now", level=3))
        return

    total_sec  = parse_dur(song.get("duration", "0:00"))
    target_sec = max(0, min(target_sec, total_sec - 1))

    pm = await rich_send(
        bot, chat_id,
        rich_heading("⏩ seeking...", level=3)
        + rich_kv_table([("to", f"<code>{fmt_time(target_sec)}</code>")]),
    )

    try:
        media_path = await resolve_stream(song["url"])
    except Exception as e:
        await rich_edit(
            pm,
            rich_heading("❍ seek failed — could not resolve stream", level=3)
            + rich_note(f"<code>{rich_esc(e)}</code>"),
        )
        return

    try:
        await call_py.change_stream(
            chat_id,
            MediaStream(
                media_path,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
                ffmpeg_parameters=f"-ss {target_sec}",
            ),
        )
    except Exception:
        try:
            await call_py.play(
                chat_id,
                MediaStream(
                    media_path,
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MediaStream.Flags.IGNORE,
                    ffmpeg_parameters=f"-ss {target_sec}",
                ),
            )
        except Exception as e2:
            await rich_edit(
                pm,
                rich_heading("❍ seek failed", level=3)
                + rich_note(f"<code>{rich_esc(e2)}</code>"),
            )
            return

    set_seek_state(chat_id, target_sec)
    from videl.core.player import _np_start, _pause_started, set_paused
    _np_start[chat_id] = time.time() - target_sec
    _pause_started.pop(chat_id, None)
    set_paused(chat_id, False)

    # True rich card — same pattern as the now-playing message in player.py
    # (embedded thumbnail via rich_img, real heading + table), not a caption.
    content = (
        rich_heading(" Now Playing", level=3)
        + (rich_img(song["thumbnail"]) if song.get("thumbnail") else "")
        + rich_kv_table([
            ("title", rich_esc(short(song["title"]))),
            ("duration", rich_esc(song.get("duration", "?"))),
            ("by", rich_esc(song["requester"])),
            ("seeked to", f"<code>{fmt_time(target_sec)}</code>"),
        ])
    )
    btns = [
        InlineKeyboardButton("▷",   callback_data="resume"),
        InlineKeyboardButton("II",  callback_data="pause"),
        InlineKeyboardButton("‣‣I", callback_data="skip"),
        InlineKeyboardButton("▢",   callback_data="stop"),
    ]
    bar = progress_bar(target_sec, total_sec)
    kb  = InlineKeyboardMarkup([
        [InlineKeyboardButton(bar, callback_data="noop")],
        btns,
    ])
    try:
        await pm.delete()
    except Exception:
        pass
    await rich_send(bot, chat_id, content, reply_markup=kb)


# ── /seek ──────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.group
    & filters.regex(r"^/seek(?:@\w+)?\s+(?P<sec>\d+)$")
    & group_allowed
    & user_allowed
)
async def seek_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    song    = peek_current(chat_id)

    if not song:
        await rich_send(bot, chat_id, rich_heading("❍ no song is currently playing", level=3))
        return

    sec = int(message.matches[0].group("sec"))
    if sec < 1:
        await rich_send(
            bot, chat_id,
            rich_heading("❍ please provide a number of seconds greater than 0", level=3)
            + rich_kv_table([("usage", "<code>/seek 30</code>")]),
        )
        return

    current_pos = get_current_position(chat_id)
    target      = current_pos + sec
    total_sec   = parse_dur(song.get("duration", "0:00"))

    if current_pos >= total_sec - 1:
        await rich_send(bot, chat_id, rich_heading("❍ song is almost finished, cannot seek forward", level=3))
        return

    if target >= total_sec:
        await rich_send(
            bot, chat_id,
            rich_heading("❍ cannot seek that far forward", level=3)
            + rich_kv_table([
                ("current position", f"<code>{fmt_time(current_pos)}</code>"),
                ("song duration", f"<code>{fmt_time(total_sec)}</code>"),
            ]),
        )
        return

    try:
        await message.delete()
    except Exception:
        pass

    await _seek_to(chat_id, target, message)


# ── /seekback ──────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.group
    & filters.regex(r"^/seekback(?:@\w+)?\s+(?P<sec>\d+)$")
    & group_allowed
    & user_allowed
)
async def seekback_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    song    = peek_current(chat_id)

    if not song:
        await rich_send(bot, chat_id, rich_heading("❍ no song is currently playing", level=3))
        return

    sec = int(message.matches[0].group("sec"))
    if sec < 1:
        await rich_send(
            bot, chat_id,
            rich_heading("❍ please provide a number of seconds greater than 0", level=3)
            + rich_kv_table([("usage", "<code>/seekback 30</code>")]),
        )
        return

    target = max(0, get_current_position(chat_id) - sec)

    try:
        await message.delete()
    except Exception:
        pass

    await _seek_to(chat_id, target, message)


# ── /seek (no args) ────────────────────────────────────────────────────────────

@bot.on_message(
    filters.group
    & filters.regex(r"^/seek(?:@\w+)?$")
    & group_allowed
    & user_allowed
)
async def seek_usage(_, message: Message) -> None:
    chat_id = message.chat.id
    song    = peek_current(chat_id)

    usage_rows = [
        ("/seek 30", "forward 30 seconds"),
        ("/seekback 30", "backward 30 seconds"),
    ]

    if song:
        pos       = get_current_position(chat_id)
        total_sec = parse_dur(song.get("duration", "0:00"))
        await rich_send(
            bot, chat_id,
            rich_heading("❍ seek usage", level=3)
            + rich_kv_table([("current position",
                              f"<code>{fmt_time(pos)}</code> / <code>{fmt_time(total_sec)}</code>")])
            + rich_kv_table(usage_rows, headers=["command", "description"]),
        )
    else:
        await rich_send(
            bot, chat_id,
            rich_heading("❍ seek usage", level=3)
            + rich_kv_table(usage_rows, headers=["command", "description"]),
        )

