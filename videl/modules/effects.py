# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio
import os

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from videl import LOGGER, bot, call_py
from videl.core.queue import peek_current
from videl.modules.block import group_allowed, user_allowed
from videl.utils.formatters import short
from videl.utils.rich_ui import (
    rich_edit,
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_send,
)

# ── DB helpers using utils.db ──────────────────────────────────────────────────

def _db_save(chat_id: int) -> None:
    try:
        from videl.utils.db import save_chat_effects
        s = _get(chat_id)
        save_chat_effects(chat_id, s["speed"], s["bass"], s["enabled"])
    except Exception as e:
        LOGGER.warning(f"[Effects] DB save failed: {e}")


def _db_load(chat_id: int) -> dict:
    try:
        from videl.utils.db import load_chat_effects
        return load_chat_effects(chat_id)
    except Exception:
        return {"speed": 1.0, "bass": 0, "enabled": False}


# ── In-memory cache ────────────────────────────────────────────────────────────
_cache: dict[int, dict] = {}

SPEED_DEFAULT = 1.0
BASS_DEFAULT  = 0


def _get(chat_id: int) -> dict:
    if chat_id not in _cache:
        _cache[chat_id] = _db_load(chat_id)
    return _cache[chat_id]


def get_effects(chat_id: int) -> dict:
    return _get(chat_id).copy()


def set_speed(chat_id: int, speed: float) -> None:
    _get(chat_id)["speed"] = speed
    _db_save(chat_id)


def set_bass(chat_id: int, bass: int) -> None:
    _get(chat_id)["bass"] = bass
    _db_save(chat_id)


def set_enabled(chat_id: int, val: bool) -> None:
    _get(chat_id)["enabled"] = val
    _db_save(chat_id)


def is_effects_on(chat_id: int) -> bool:
    return _get(chat_id).get("enabled", False)


def clear_effects(chat_id: int) -> None:
    _cache.pop(chat_id, None)
    try:
        from videl.utils.db import delete_chat_effects
        delete_chat_effects(chat_id)
    except Exception:
        pass


# ── ffmpeg filter builder ──────────────────────────────────────────────────────

def _build_af(speed: float, bass: int) -> str | None:
    parts = []

    if bass and bass > 0:
        parts.append(f"equalizer=f=80:t=h:width=200:g={min(bass, 20)}")

    if speed and speed != 1.0:
        speed = round(max(0.25, min(speed, 4.0)), 2)
        if 0.5 <= speed <= 2.0:
            parts.append(f"atempo={speed}")
        elif speed < 0.5:
            parts.append("atempo=0.5,atempo=0.5")
        else:
            chain = []
            rem   = speed
            while rem > 2.0:
                chain.append("atempo=2.0")
                rem /= 2.0
            chain.append(f"atempo={round(rem, 2)}")
            parts.append(",".join(chain))

    return ",".join(parts) if parts else None


# ── Process file with ffmpeg ───────────────────────────────────────────────────

async def _process_file(src: str, speed: float, bass: int) -> str:
    af = _build_af(speed, bass)
    if not af:
        return src

    os.makedirs("downloads/effects", exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0]
    tag  = f"s{str(speed).replace('.', '')}_b{bass}"
    out  = f"downloads/effects/{base}_{tag}.mp3"

    if os.path.exists(out) and os.path.getsize(out) > 0:
        return out

    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-af", af,
        "-vn", "-acodec", "libmp3lame", "-b:a", "192k",
        out,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await asyncio.wait_for(proc.communicate(), timeout=120)

    if proc.returncode != 0 or not os.path.exists(out):
        raise Exception("ffmpeg processing failed")

    return out


# ── Stream helper ──────────────────────────────────────────────────────────────

async def _stream_from(chat_id: int, file_path: str, seek_sec: int = 0) -> None:
    from pytgcalls.types import AudioQuality, MediaStream

    ms_kwargs = dict(
        audio_parameters=AudioQuality.HIGH,
        video_flags=MediaStream.Flags.IGNORE,
    )
    if seek_sec > 0:
        ms_kwargs["ffmpeg_parameters"] = f"-ss {seek_sec}"

    try:
        await call_py.change_stream(chat_id, MediaStream(file_path, **ms_kwargs))
    except Exception:
        await call_py.play(chat_id, MediaStream(file_path, **ms_kwargs))


# ── Apply effects to current song ─────────────────────────────────────────────

async def apply_effects_now(chat_id: int, message: Message, *, seek_sec: int = -1) -> None:
    from videl.utils.youtube import resolve_stream
    from videl.modules.seek import get_current_position, set_seek_state

    song = peek_current(chat_id)
    if not song:
        await rich_send(bot, chat_id, rich_heading("❍ no song is currently playing", level=3))
        return

    state = _get(chat_id)
    speed = state["speed"]
    bass  = state["bass"]

    pm = await rich_send(bot, chat_id, rich_heading("❍ applying effects, please wait...", level=3))

    try:
        src = await resolve_stream(song["url"])
    except Exception as e:
        await rich_edit(
            pm,
            rich_heading("❍ stream resolve failed", level=3)
            + rich_note(f"<code>{rich_esc(e)}</code>"),
        )
        return

    try:
        processed = await _process_file(src, speed, bass)
    except Exception as e:
        await rich_edit(
            pm,
            rich_heading("❍ ffmpeg error", level=3)
            + rich_note(f"<code>{rich_esc(e)}</code>"),
        )
        return

    pos = get_current_position(chat_id) if seek_sec == -1 else seek_sec

    try:
        await _stream_from(chat_id, processed, seek_sec=pos)
    except Exception as e:
        await rich_edit(
            pm,
            rich_heading("❍ playback failed", level=3)
            + rich_note(f"<code>{rich_esc(e)}</code>"),
        )
        return

    set_seek_state(chat_id, pos)

    speed_label = f"{speed}x" if speed != 1.0 else "normal (1.0x)"
    bass_label  = f"{bass} dB boost" if bass > 0 else "off"
    pos_label   = f"{pos // 60}:{pos % 60:02d}"

    await rich_edit(
        pm,
        rich_heading("❍ effects applied ✓", level=3)
        + rich_kv_table([
            ("song", rich_esc(short(song['title']))),
            ("position", f"<code>{pos_label}</code>"),
            ("speed", f"<code>{speed_label}</code>"),
            ("bass", f"<code>{bass_label}</code>"),
        ]),
    )


# ── Auto-apply effects (called from player.py) ────────────────────────────────

async def maybe_apply_effects(chat_id: int, file_path: str) -> str:
    state = _get(chat_id)
    if not state.get("enabled", False):
        return file_path
    speed = state["speed"]
    bass  = state["bass"]
    if speed == 1.0 and bass == 0:
        return file_path
    try:
        return await _process_file(file_path, speed, bass)
    except Exception as e:
        LOGGER.warning(f"[Effects] Auto-apply failed for {chat_id}: {e}")
        return file_path


# ══════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

@bot.on_message(
    filters.group
    & filters.regex(r"^/speed(?:@\w+)?\s+(?P<val>[\d.]+)$")
    & group_allowed & user_allowed
)
async def speed_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    try:
        val = round(float(message.matches[0].group("val")), 2)
    except ValueError:
        await rich_send(
            bot, chat_id,
            rich_heading("❍ invalid value", level=3)
            + rich_kv_table([("usage", "<code>/speed 1.5</code>")]),
        )
        return

    if not (0.25 <= val <= 4.0):
        await rich_send(
            bot, chat_id,
            rich_heading("❍ speed must be between 0.25 and 4.0", level=3),
        )
        return

    set_speed(chat_id, val)
    try:
        await message.delete()
    except Exception:
        pass
    await apply_effects_now(chat_id, message)


@bot.on_message(
    filters.group
    & filters.regex(r"^/speedreset(?:@\w+)?$")
    & group_allowed & user_allowed
)
async def speedreset_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    set_speed(chat_id, SPEED_DEFAULT)
    try:
        await message.delete()
    except Exception:
        pass
    await apply_effects_now(chat_id, message)


@bot.on_message(
    filters.group
    & filters.regex(r"^/bass(?:@\w+)?\s+(?P<val>\d+)$")
    & group_allowed & user_allowed
)
async def bass_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    try:
        val = int(message.matches[0].group("val"))
    except ValueError:
        await rich_send(
            bot, chat_id,
            rich_heading("❍ invalid value", level=3)
            + rich_kv_table([("usage", "<code>/bass 10</code>")]),
        )
        return

    if not (1 <= val <= 20):
        await rich_send(
            bot, chat_id,
            rich_heading("❍ bass must be between 1 and 20", level=3),
        )
        return

    set_bass(chat_id, val)
    try:
        await message.delete()
    except Exception:
        pass
    await apply_effects_now(chat_id, message)


@bot.on_message(
    filters.group
    & filters.regex(r"^/bassoff(?:@\w+)?$")
    & group_allowed & user_allowed
)
async def bassoff_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    set_bass(chat_id, BASS_DEFAULT)
    try:
        await message.delete()
    except Exception:
        pass
    await apply_effects_now(chat_id, message)


@bot.on_message(
    filters.group
    & filters.regex(r"^/effecton(?:@\w+)?$")
    & group_allowed & user_allowed
)
async def effecton_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    set_enabled(chat_id, True)
    state       = _get(chat_id)
    speed_label = f"{state['speed']}x" if state['speed'] != 1.0 else "normal (1.0x)"
    bass_label  = f"{state['bass']} dB" if state['bass'] > 0 else "off"
    await rich_send(
        bot, chat_id,
        rich_heading("❍ effects enabled ✓", level=3)
        + rich_kv_table([("speed", f"<code>{speed_label}</code>"), ("bass", f"<code>{bass_label}</code>")])
        + rich_note("all songs in this group will now play with effects. "
                    "use /effectoff to disable."),
    )


@bot.on_message(
    filters.group
    & filters.regex(r"^/effectoff(?:@\w+)?$")
    & group_allowed & user_allowed
)
async def effectoff_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    set_enabled(chat_id, False)
    await rich_send(
        bot, chat_id,
        rich_heading("❍ effects disabled ✓", level=3)
        + rich_note("songs will now play normally in this group. speed + bass "
                    "settings are kept — use /effecton to re-enable."),
    )


@bot.on_message(
    filters.group
    & filters.regex(r"^/effects(?:@\w+)?$")
    & group_allowed & user_allowed
)
async def effects_status_cmd(_, message: Message) -> None:
    chat_id     = message.chat.id
    state       = _get(chat_id)
    speed       = state["speed"]
    bass        = state["bass"]
    enabled     = state["enabled"]

    speed_label = f"{speed}x" if speed != 1.0 else "normal (1.0x)"
    bass_label  = f"{bass} dB boost" if bass > 0 else "off"
    mode_label  = "on — all songs affected 🟢" if enabled else "off — manual per song 🔴"

    song        = peek_current(chat_id)
    song_label  = rich_esc(short(song["title"])) if song else "nothing playing"

    await rich_send(
        bot, chat_id,
        rich_heading(f"❍ effects status — {rich_esc(message.chat.title)}", level=3)
        + rich_kv_table([
            ("now playing", song_label),
            ("mode", f"<code>{mode_label}</code>"),
            ("speed", f"<code>{speed_label}</code>"),
            ("bass boost", f"<code>{bass_label}</code>"),
        ])
        + rich_kv_table(
            [
                ("/speed 1.5", "set speed (0.25–4.0)"),
                ("/speedreset", "back to normal speed"),
                ("/bass 10", "bass boost (1–20 db)"),
                ("/bassoff", "remove bass boost"),
                ("/effecton", "all songs get effects"),
                ("/effectoff", "manual mode only"),
            ],
            headers=["command", "description"],
        ),
)

    
