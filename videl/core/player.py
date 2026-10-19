# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio
import random
import time

from pyrogram.enums import ParseMode
from pyrogram.raw.functions.phone import CreateGroupCall
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from pytgcalls import PyTgCalls
from pytgcalls import filters as fl
from ntgcalls import TelegramServerError
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import (
    AudioQuality,
    MediaStream,
    VideoQuality,
    ChatUpdate,
    StreamEnded,
    GroupCallConfig,
    GroupCallParticipant,
    UpdatedGroupCallParticipant,
)

import config

from videl import (
    LOGGER,
    assistant,
    bot,
    call_py,
)

from videl.core.queue import (
    remove_from_queue,
)

from videl.utils.formatters import (
    parse_dur,
    progress_bar,
    short,
)

from videl.utils.rich_ui import (
    rich_edit,
    rich_esc,
    rich_heading,
    rich_img,
    rich_kv_table,
    rich_note,
    rich_send,
)

from videl.utils.youtube import (
    resolve_stream,
)

def _support_updates_pills() -> str:
    return (
        "<p>"
        f'<tg-button type="url" style="primary" url="{config.SUPPORT_GROUP}">'
        "🍬 sᴜᴘᴘᴏʀᴛ</tg-button> "
        f'<tg-button type="url" style="success" url="{config.UPDATES_CHANNEL}">'
        "🍹 ᴜᴘᴅᴀᴛᴇs</tg-button>"
        "</p>"
    )


# ─────────────────────────────────────────────
# NOW PLAYING CONTENT
# ─────────────────────────────────────────────


def _thumb_url(song: dict) -> str:
    """Best-effort thumbnail URL (ytimg CDN preferred)."""
    thumb = (song.get("thumbnail") or "").strip()
    vid = (song.get("video_id") or "").strip()
    if not vid and song.get("url"):
        u = str(song["url"])
        if "v=" in u:
            vid = u.split("v=")[-1].split("&")[0]
        elif "youtu.be/" in u:
            vid = u.split("youtu.be/")[-1].split("?")[0]
    if vid and ("ytimg" not in thumb or not thumb):
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    if thumb.startswith("http"):
        return thumb.split("?")[0]
    if vid:
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return ""


# Per-chat UI state for dynamic buttons
_paused: dict[int, bool] = {}
_loop_mode: dict[int, str] = {}  # off | one | all
_np_msg: dict[int, Message] = {}  # last now-playing message
_np_song: dict[int, dict] = {}
_np_start: dict[int, float] = {}
_np_total: dict[int, float] = {}


def get_loop(chat_id: int) -> str:
    return _loop_mode.get(chat_id, "off")


def set_loop(chat_id: int, mode: str) -> str:
    if mode not in ("off", "one", "all"):
        mode = "off"
    _loop_mode[chat_id] = mode
    return mode


def cycle_loop(chat_id: int) -> str:
    order = ("off", "one", "all")
    cur = get_loop(chat_id)
    nxt = order[(order.index(cur) + 1) % len(order)]
    return set_loop(chat_id, nxt)


def is_paused(chat_id: int) -> bool:
    return bool(_paused.get(chat_id, False))


def set_paused(chat_id: int, value: bool) -> None:
    _paused[chat_id] = value


def _dot_progress(elapsed: float, total: float) -> str:
    """Screenshot-style: 2:32 ———●——— 3:44"""
    from videl.utils.formatters import fmt_time
    if total <= 0:
        return "0:00  ———●———  0:00"
    left = fmt_time(elapsed)
    right = fmt_time(total)
    slots = 10
    pos = int((elapsed / total) * slots) if total else 0
    pos = max(0, min(slots - 1, pos))
    bar = "—" * pos + "●" + "—" * (slots - pos - 1)
    return f"{left}  {bar}  {right}"


def _now_playing_caption(song: dict, elapsed: float = 0, total: float = 0, chat_id: int | None = None) -> str:
    """Clean photo-caption UI with up-next strip (small-caps)."""
    from videl.utils.formatters import sc
    from videl.core.queue import peek_next, queue_size

    title = short(song.get("title", "?"), 48)
    requester = song.get("requester", "?")
    kind = "VIDEO" if song.get("video") else "AUDIO"
    dur = song.get("duration", "?")
    if total <= 0:
        total = parse_dur(str(dur)) if dur else 0
        if not total and song.get("duration_seconds"):
            total = float(song["duration_seconds"])

    bar = _dot_progress(elapsed, total) if total > 0 else f"0:00  ———●———  {dur}"
    loop = get_loop(chat_id) if chat_id is not None else "off"
    loop_tag = {"off": "", "one": f"  🔁 {sc('loop one')}", "all": f"  🔁 {sc('loop queue')}"}.get(loop, "")
    paused_tag = f"  ⏸ {sc('paused')}" if (chat_id is not None and is_paused(chat_id)) else ""

    lines = [
        f"<b>{rich_esc(title)}</b>",
        f"<code>{kind}</code>  •  <code>{rich_esc(str(dur))}</code>{loop_tag}{paused_tag}",
        f"{sc('requested by')} <b>{rich_esc(requester)}</b> 🤍",
        "",
        f"<code>{bar}</code>",
    ]

    if chat_id is not None:
        nxt = peek_next(chat_id)
        qn = max(queue_size(chat_id) - 1, 0)
        if nxt:
            lines.append("")
            lines.append(f"⏭ {sc('up next')}: <b>{rich_esc(short(nxt.get('title', '?'), 36))}</b>")
            if qn > 1:
                lines.append(f"📋 {sc('queue')}: <code>{qn}</code>")
        elif qn == 0:
            lines.append("")
            lines.append(f"📋 {sc('queue')}: <code>0</code>")

    return "\n".join(lines)


def _now_playing_kb(
    chat_id: int | None = None,
    elapsed: float = 0,
    total: float = 0,
    votes: int = 0,
    votes_needed: int = 0,
) -> InlineKeyboardMarkup:
    """
    Visual controls like premium music bots:
      [ ↻ Replay ] [ II Pause / ▷ Resume ] [ ‣‣ Skip ]
      [ 🔁 Loop ]  [ ⏹ Stop ]
    """
    from videl.utils.formatters import sc

    paused = is_paused(chat_id) if chat_id is not None else False
    loop = get_loop(chat_id) if chat_id is not None else "off"

    mid = (
        InlineKeyboardButton(f"▷ {sc('resume')}", callback_data="resume")
        if paused
        else InlineKeyboardButton(f"II {sc('pause')}", callback_data="pause")
    )
    row1 = [
        InlineKeyboardButton(f"↻ {sc('replay')}", callback_data="replay"),
        mid,
        InlineKeyboardButton(f"‣‣ {sc('skip')}", callback_data="skip"),
    ]

    loop_label = {
        "off": f"🔁 {sc('loop off')}",
        "one": f"🔁 {sc('loop one')}",
        "all": f"🔁 {sc('loop all')}",
    }.get(loop, f"🔁 {sc('loop off')}")

    row2 = [
        InlineKeyboardButton(loop_label, callback_data="cycle_loop"),
        InlineKeyboardButton(f"⏹ {sc('stop')}", callback_data="stop"),
    ]

    rows = [row1, row2]
    if votes_needed > 0:
        rows.append([
            InlineKeyboardButton(
                f"⏭ {sc('vote')} {votes}/{votes_needed}",
                callback_data="vote_skip",
            )
        ])
    return InlineKeyboardMarkup(rows)


async def refresh_np_ui(chat_id: int) -> None:
    """Re-render now-playing caption + buttons after pause/loop changes."""
    msg = _np_msg.get(chat_id)
    song = _np_song.get(chat_id)
    if not msg or not song:
        return
    start_t = _np_start.get(chat_id, time.time())
    total = _np_total.get(chat_id, 0) or 0
    # freeze elapsed while paused
    if is_paused(chat_id):
        elapsed = min(time.time() - start_t, total) if total else 0
        # keep same visual position
    else:
        elapsed = min(time.time() - start_t, total) if total else 0
    caption = _now_playing_caption(song, elapsed, total, chat_id=chat_id)
    kb = _now_playing_kb(chat_id)
    try:
        if getattr(msg, "photo", None):
            await bot.edit_message_caption(
                chat_id, msg.id, caption=caption, reply_markup=kb
            )
        else:
            await rich_edit(msg, caption, reply_markup=kb)
    except Exception:
        pass


# ─────────────────────────────────────────────
# PROGRESS UPDATER
# ─────────────────────────────────────────────

async def _update_progress(
    chat_id: int,
    msg: Message,
    start_t: float,
    total: float,
    song: dict,
) -> None:
    """Update caption progress; skips ticks while paused."""
    _np_msg[chat_id] = msg
    _np_song[chat_id] = song
    _np_start[chat_id] = start_t
    _np_total[chat_id] = total
    set_paused(chat_id, False)

    paused_accum = 0.0
    pause_began = None

    while True:
        if is_paused(chat_id):
            if pause_began is None:
                pause_began = time.time()
            await asyncio.sleep(2)
            continue
        if pause_began is not None:
            paused_accum += time.time() - pause_began
            pause_began = None
            _np_start[chat_id] = start_t + paused_accum

        elapsed = min(time.time() - start_t - paused_accum, total) if total else 0
        caption = _now_playing_caption(song, elapsed, total, chat_id=chat_id)
        kb = _now_playing_kb(chat_id)

        try:
            if getattr(msg, "photo", None):
                await bot.edit_message_caption(
                    chat_id, msg.id, caption=caption, reply_markup=kb
                )
            else:
                await rich_edit(msg, caption, reply_markup=kb)
        except Exception as e:
            if "MESSAGE_NOT_MODIFIED" not in str(e):
                break

        if total and elapsed >= total:
            break

        await asyncio.sleep(12)


# ─────────────────────────────────────────────
# AUTO START VC
# ─────────────────────────────────────────────

async def _try_create_group_call(client, chat_id: int, who: str) -> bool:
    """CreateGroupCall via assistant or bot. True if created or already running."""
    try:
        peer = await client.resolve_peer(chat_id)
        await client.invoke(
            CreateGroupCall(
                peer=peer,
                random_id=random.randint(10_000, 999_999),
            )
        )
        LOGGER.info(f"[VC] Created by {who} in {chat_id}")
        await asyncio.sleep(1.5)
        return True
    except Exception as e:
        err = str(e).lower()
        if (
            "already" in err
            or "groupcall_already_started" in err
            or "group_call_already_started" in err
        ):
            LOGGER.info(f"[VC] Already active ({who}) in {chat_id}")
            return True
        LOGGER.warning(f"[VC] {who} CreateGroupCall failed: {e}")
        return False


async def _try_promote_assistant(chat_id: int) -> bool:
    """
    If the bot can promote members, give the assistant
    manage_video_chats (+ invite users) so it can start VC.
    """
    try:
        from pyrogram.types import ChatPrivileges

        me_asst = await assistant.get_me()
        await bot.promote_chat_member(
            chat_id,
            me_asst.id,
            privileges=ChatPrivileges(
                can_manage_video_chats=True,
                can_invite_users=True,
            ),
        )
        LOGGER.info(f"[VC] Promoted assistant in {chat_id} (manage video chats)")
        await asyncio.sleep(1)
        return True
    except Exception as e:
        LOGGER.warning(f"[VC] promote assistant failed: {e}")
        return False


async def _ensure_vc(chat_id: int) -> bool:
    """
    Make sure a group voice chat exists.

    Order:
      1) Assistant CreateGroupCall
      2) Bot CreateGroupCall (if bot has Manage Video Chats)
      3) Auto-promote assistant (if bot can promote) → retry assistant
      4) If already running → OK

    Note: Telegram does NOT allow starting VC with only «Add members».
    That right only lets the bot invite the assistant into the group.
    """
    chat_id = int(chat_id)

    # 1) Assistant
    if await _try_create_group_call(assistant, chat_id, "assistant"):
        return True

    # 2) Bot account as fallback (many groups give rights only to the bot)
    if await _try_create_group_call(bot, chat_id, "bot"):
        return True

    # 3) Promote assistant with manage_video_chats, then retry
    if await _try_promote_assistant(chat_id):
        if await _try_create_group_call(assistant, chat_id, "assistant-after-promote"):
            return True
        if await _try_create_group_call(bot, chat_id, "bot-after-promote"):
            return True

    await rich_send(
        bot,
        chat_id,
        rich_heading("❌ Need VC admin rights", level=3)
        + rich_note(
            "Telegram needs <b>Manage Video Chats</b> to <b>start</b> a call.\n"
            "«Add members» only invites the assistant — it cannot start VC.\n\n"
            "<b>Fix (pick one):</b>\n"
            "• Promote <b>bot + assistant</b> → Manage Video Chats\n"
            "• Or start Voice Chat manually once, then /play again"
        ),
    )
    return False


# ─────────────────────────────────────────────
# MAIN PLAY FUNCTION
# ─────────────────────────────────────────────

async def play_song(
    chat_id: int,
    message: Message,
    song: dict,
) -> None:

    chat_id = int(chat_id)
    url = song.get("url")

    if not url:
        return

    loading_text = (
        rich_heading("⏳ Loading...", level=3)
        + rich_kv_table([("sᴏɴɢ", rich_esc(short(song['title'])))])
    )

    try:
        await rich_edit(message, loading_text)

    except Exception:
        message = await rich_send(bot, chat_id, loading_text)

    # ─────────────────────────────────────────
    # RESOLVE STREAM
    # ─────────────────────────────────────────

    try:
        want_video = bool(song.get("video", False))
        media_path = await resolve_stream(url, video=want_video)

    except Exception as e:
        try:
            remove_from_queue(chat_id, 0)
        except Exception:
            pass

        await rich_send(
            bot, chat_id,
            rich_heading("❌ Download failed", level=3)
            + rich_note(f"<code>{rich_esc(str(e)[:400])}</code>"),
        )
        return

    is_video = song.get("video", False)
    # Local file path → detect video by extension (mkv, mp4, webm, …)
    _vid_exts = (".mkv", ".mp4", ".webm", ".avi", ".mov", ".m4v", ".flv", ".wmv", ".mpeg", ".mpg", ".3gp")
    try:
        path_l = str(media_path or song.get("url") or "").lower()
        if any(path_l.endswith(ext) for ext in _vid_exts):
            is_video = True
            song["video"] = True
    except Exception:
        pass

    # ─────────────────────────────────────────
    # AUTO EFFECTS
    # ─────────────────────────────────────────

    if not is_video:
        try:
            from videl.modules.effects import maybe_apply_effects
            media_path = await maybe_apply_effects(chat_id, media_path)

        except Exception as fx_err:
            LOGGER.warning(f"[Effects] Skipped: {fx_err}")

    # ─────────────────────────────────────────
    # PLAY STREAM
    # ─────────────────────────────────────────

    played = False

    for attempt in range(2):

        try:

            if is_video:
                await call_py.play(
                    chat_id,
                    MediaStream(
                        media_path,
                        audio_parameters=AudioQuality.HIGH,
                        video_parameters=VideoQuality.HD_720p,
                    ),
                )
            else:
                await call_py.play(
                    chat_id,
                    MediaStream(
                        media_path,
                        audio_parameters=AudioQuality.HIGH,
                        video_flags=MediaStream.Flags.IGNORE,
                    ),
                )

            played = True
            break

        except NoActiveGroupCall:

            if attempt == 0:
                LOGGER.info(f"[VC] NoActiveGroupCall — Creating VC in {chat_id}")
                ok = await _ensure_vc(chat_id)

                if ok:
                    continue

                try:
                    remove_from_queue(chat_id, 0)
                except Exception:
                    pass

                return

        except TelegramServerError as e:
            LOGGER.error(f"[PLAY] TelegramServerError: {e}")

            try:
                remove_from_queue(chat_id, 0)
            except Exception:
                pass

            await rich_send(
                bot, chat_id,
                rich_heading("❍ ᴘʟᴀʏʙᴀᴄᴋ ғᴀɪʟᴇᴅ (Telegram Server)", level=3)
                + rich_note(f"<code>{rich_esc(e)}</code>"),
            )
            return

        except Exception as e:

            err = str(e).lower()

            vc_missing = any(
                x in err
                for x in (
                    "groupcallnotfound",
                    "not_in_group_call",
                    "groupcall_forbidden",
                    "not in group call",
                    "no active group call",
                )
            )

            # auto create vc (string-based fallback)
            if vc_missing and attempt == 0:
                LOGGER.info(f"[VC] Creating VC in {chat_id}")
                ok = await _ensure_vc(chat_id)

                if ok:
                    continue

                try:
                    remove_from_queue(chat_id, 0)
                except Exception:
                    pass

                return

            # admin permission error — try auto VC create / promote once
            if "chat_admin_required" in err or ("admin" in err and "user" not in err):
                LOGGER.error(f"[ADMIN ERROR] {e}")
                ok = await _ensure_vc(chat_id)
                if ok:
                    continue
                try:
                    remove_from_queue(chat_id, 0)
                except Exception:
                    pass
                return

            # generic error
            try:
                remove_from_queue(chat_id, 0)
            except Exception:
                pass

            await rich_send(
                bot, chat_id,
                rich_heading("❍ ᴘʟᴀʏʙᴀᴄᴋ ғᴀɪʟᴇᴅ", level=3)
                + rich_note(f"<code>{rich_esc(e)}</code>"),
            )
            LOGGER.error(f"[PLAY ERROR] {e}")
            return

    if not played:
        return

    # ─────────────────────────────────────────
    # RESET SEEK
    # ─────────────────────────────────────────

    try:
        from videl.modules.seek import set_seek_state
        set_seek_state(chat_id, 0)
    except Exception:
        pass

    # ─────────────────────────────────────────
    # DATABASE TRACKING
    # ─────────────────────────────────────────

    try:
        from videl.database import (
            add_served_chat,
            add_served_user,
            increment_play_count,
        )

        add_served_chat(chat_id)
        requester_id = song.get("requester_id")

        if requester_id:
            add_served_user(requester_id)

        increment_play_count(chat_id)

    except Exception as db_err:
        LOGGER.warning(f"[DB ERROR] {db_err}")

    # ─────────────────────────────────────────
    # NOW PLAYING UI — photo + caption (thumbnail always loads via ytimg)
    # ─────────────────────────────────────────

    total = parse_dur(str(song.get("duration", "0:00")))
    if not total and song.get("duration_seconds"):
        total = float(song["duration_seconds"])
    set_paused(chat_id, False)
    caption = _now_playing_caption(song, 0, total, chat_id=chat_id)
    kb = _now_playing_kb(chat_id)
    thumb = _thumb_url(song)

    pmsg = None
    if thumb:
        try:
            # Prefer sending as real photo so art always shows
            pmsg = await bot.send_photo(
                chat_id,
                photo=thumb,
                caption=caption,
                reply_markup=kb,
            )
            # Delete the old "loading" message if any
            try:
                if message and getattr(message, "id", None):
                    await message.delete()
            except Exception:
                pass
        except Exception as e:
            LOGGER.warning(f"[NP] photo send failed ({e}) — trying download")
            # Fallback: download thumb then upload
            try:
                import aiohttp
                import tempfile
                import os as _os
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(thumb, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                            tmp.write(data)
                            tmp.close()
                            pmsg = await bot.send_photo(
                                chat_id,
                                photo=tmp.name,
                                caption=caption,
                                reply_markup=kb,
                            )
                            try:
                                _os.unlink(tmp.name)
                            except Exception:
                                pass
                            try:
                                if message and getattr(message, "id", None):
                                    await message.delete()
                            except Exception:
                                pass
            except Exception as e2:
                LOGGER.warning(f"[NP] thumb download failed: {e2}")

    if pmsg is None:
        # Text-only fallback
        try:
            pmsg = await rich_edit(message, caption, reply_markup=kb)
            if pmsg is None:
                pmsg = message
        except Exception:
            pmsg = await rich_send(bot, chat_id, caption, reply_markup=kb)

    asyncio.create_task(
        _update_progress(
            chat_id,
            pmsg,
            time.time(),
            total,
            song,
        )
    )

    # ─────────────────────────────────────────
    # LOGGER
    # ─────────────────────────────────────────

    if config.LOGGER_ID:
        logger_content = (
            rich_heading(
                "🎧 #ɴᴏᴡᴘʟᴀʏɪɴɢ",
                level=3
            )
            + rich_kv_table([
                ("ᴛɪᴛʟᴇ", rich_esc(song.get("title", "?"))),
                ("ᴅᴜʀᴀᴛɪᴏɴ", rich_esc(song.get("duration", "?"))),
                ("ʙʏ", rich_esc(song.get("requester", "?"))),
            ])
        )

        asyncio.create_task(
            rich_send(
                bot,
                config.LOGGER_ID,
                logger_content,
            )
        )
