# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio
import re
import time

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from videl import bot
from videl.core.player import play_song
from videl.core.queue import add_to_queue, peek_current, queue_size
from videl.modules.block import group_allowed, user_allowed
from videl.utils.assistant import is_assistant_in, try_join_assistant
from videl.utils.db import add_served_chat, add_served_user
from videl.utils.formatters import fmt_time, iso_to_human, iso_to_sec, sc, short
from videl.utils.rich_ui import (
    rich_edit,
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_send,
)
from videl.utils.youtube import search_yt

# ── Blocked words ──────────────────────────────────────────────────────────────
BLOCKED_WORDS = [
    "porn", "xxx", "xnxx", "xvideos",
    "sex", "fuck", "lund",
    "drug", "cocaine", "weed", "charas",
]

# ── Per-chat state ─────────────────────────────────────────────────────────────
_last_cmd: dict[int, float] = {}
_pending:  dict[int, tuple] = {}
# search picker cache: "chat_id:user_id" -> {results, video, requester, ...}
_search_cache: dict[str, dict] = {}


# ── DB helper ──────────────────────────────────────────────────────────────────

def _db_track(chat_id: int, user_id: int) -> None:
    try:
        add_served_chat(chat_id)
        if user_id:
            add_served_user(user_id)
        from videl.utils.db import touch_chat_activity, touch_user_activity
        touch_chat_activity(chat_id)
        if user_id:
            touch_user_activity(user_id)
    except Exception:
        pass


# ── Cooldown handler ───────────────────────────────────────────────────────────

async def _run_pending(chat_id: int, delay: int) -> None:
    await asyncio.sleep(delay)
    if chat_id in _pending:
        msg, reply = _pending.pop(chat_id)
        try:
            await reply.delete()
        except Exception:
            pass
        await play_handler(bot, msg)


# Video / audio file extensions we accept from documents
_VIDEO_EXTS = {".mkv", ".mp4", ".webm", ".avi", ".mov", ".m4v", ".flv", ".wmv", ".mpeg", ".mpg", ".3gp"}
_AUDIO_EXTS = {".mp3", ".m4a", ".ogg", ".opus", ".flac", ".wav", ".aac", ".wma"}
_MAX_FILE_MB = 200  # Telegram bot download practical limit


def _is_playable_document(doc) -> tuple[bool, bool]:
    """
    Returns (is_playable, is_video).
    Accepts video/audio mime types and common file extensions (mkv, mp4, …).
    """
    if not doc:
        return False, False
    mime = (getattr(doc, "mime_type", None) or "").lower()
    name = (getattr(doc, "file_name", None) or "").lower()
    ext = ""
    if "." in name:
        ext = "." + name.rsplit(".", 1)[-1]

    if mime.startswith("video/") or ext in _VIDEO_EXTS:
        return True, True
    if mime.startswith("audio/") or ext in _AUDIO_EXTS:
        return True, False
    # Some clients send mkv as application/octet-stream
    if ext in _VIDEO_EXTS or ext in _AUDIO_EXTS:
        return True, ext in _VIDEO_EXTS
    return False, False


async def _play_local_media(message: Message, chat_id: int, user_id: int, force_video: bool = False) -> bool:
    """
    Handle reply-to audio / video / document (mkv, mp4, …).
    Returns True if handled.
    """
    reply = message.reply_to_message
    if not reply:
        return False

    media = None
    is_video = force_video
    title = "Media"
    duration = 0
    file_size = 0

    if reply.video:
        media = reply.video
        is_video = True
        title = getattr(media, "file_name", None) or "Video"
        duration = media.duration or 0
        file_size = media.file_size or 0
    elif reply.audio:
        media = reply.audio
        is_video = False
        title = getattr(media, "file_name", None) or getattr(media, "title", None) or "Audio"
        duration = media.duration or 0
        file_size = media.file_size or 0
    elif reply.voice:
        media = reply.voice
        is_video = False
        title = "Voice message"
        duration = media.duration or 0
        file_size = media.file_size or 0
    elif reply.video_note:
        media = reply.video_note
        is_video = True
        title = "Video note"
        duration = media.duration or 0
        file_size = media.file_size or 0
    elif reply.document:
        ok, doc_video = _is_playable_document(reply.document)
        if not ok:
            return False
        media = reply.document
        is_video = force_video or doc_video
        title = getattr(media, "file_name", None) or "Document"
        duration = 0
        file_size = media.file_size or 0
    else:
        return False

    pm = await rich_send(bot, chat_id, rich_heading("⏳ Processing media...", level=3))

    if file_size and file_size > _MAX_FILE_MB * 1024 * 1024:
        await rich_edit(
            pm,
            rich_heading("❌ File too large", level=3)
            + rich_kv_table([("Max", f"<code>{_MAX_FILE_MB} MB</code>")]),
        )
        return True

    await rich_edit(pm, rich_heading("⬇️ Downloading...", level=3))

    try:
        # Re-fetch for stable file ref
        fresh = await bot.get_messages(reply.chat.id, reply.id)
        target = (
            fresh.video or fresh.audio or fresh.voice
            or fresh.video_note or fresh.document or media
        )
        fp = await bot.download_media(target)
    except Exception as e:
        await rich_edit(
            pm,
            rich_heading("❌ Download failed", level=3)
            + rich_note(f"<code>{rich_esc(e)}</code>"),
        )
        return True

    if not fp:
        await rich_edit(pm, rich_heading("❌ Download failed", level=3))
        return True

    # Infer video from extension if still unclear
    lower = str(fp).lower()
    if any(lower.endswith(ext) for ext in _VIDEO_EXTS):
        is_video = True

    thumb = None
    try:
        src = fresh.video or fresh.audio or fresh.document
        if src and getattr(src, "thumbs", None):
            thumb = await bot.download_media(src.thumbs[0])
    except Exception:
        pass

    song = {
        "url": fp,
        "title": title,
        "duration": fmt_time(duration) if duration else "?",
        "duration_seconds": duration or 0,
        "requester": message.from_user.first_name if message.from_user else "Unknown",
        "requester_id": user_id,
        "thumbnail": thumb,
        "video": is_video,
        "local_file": True,
    }

    pos = add_to_queue(chat_id, song)
    if pos == 1:
        await play_song(chat_id, pm, song)
    else:
        await rich_edit(
            pm,
            rich_heading("➕ Added to queue", level=3)
            + rich_kv_table([
                ("Title", f"<code>{rich_esc(short(title))}</code>"),
                ("Type", "Video" if is_video else "Audio"),
                ("Pos", f"<code>#{pos - 1}</code>"),
            ]),
        )
    return True


# ── /play & /vplay command ─────────────────────────────────────────────────────

@bot.on_message(
    filters.group
    & filters.regex(r"^/(?P<cmd>v?play)(?:@\w+)?(?:\s+(?P<q>.+))?$")
    & group_allowed
    & user_allowed
)
async def play_handler(_, message: Message) -> None:

    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0

    _db_track(chat_id, user_id)

    cmd_match = message.matches[0] if message.matches else None
    cmd = (cmd_match.group("cmd") if cmd_match else "play") or "play"
    force_video = cmd == "vplay"

    # ── Replied audio / video / document (mkv, mp4, …) ─────────────────────────
    if message.reply_to_message:
        handled = await _play_local_media(message, chat_id, user_id, force_video=force_video)
        if handled:
            return

    # ── Text query ─────────────────────────────────────────────────────────────
    match = message.matches[0] if message.matches else None
    query = (match.group("q") or "").strip() if match else ""

    try:
        await message.delete()
    except Exception:
        pass

    # Blocked words check
    if query and any(x in query.lower() for x in BLOCKED_WORDS):
        await rich_send(bot, chat_id, rich_heading("🚫 Song blocked", level=3))
        return

    # Cooldown check
    now = time.time()
    if chat_id in _last_cmd and (now - _last_cmd[chat_id]) < config.COOLDOWN:
        rem = int(config.COOLDOWN - (now - _last_cmd[chat_id]))
        if chat_id not in _pending:
            rep = await rich_send(
                bot, chat_id,
                rich_heading("⏳ Cooldown active", level=3)
                + rich_kv_table([("Processing in", f"<code>{rem}s</code>")]),
            )
            _pending[chat_id] = (message, rep)
            asyncio.create_task(_run_pending(chat_id, rem))
        return

    _last_cmd[chat_id] = now

    if not query:
        await rich_send(
            bot, chat_id,
            rich_heading("ℹ️ Usage", level=3)
            + rich_kv_table([
                ("Audio", "<code>/play song name</code>"),
                ("Video", "<code>/vplay song name</code>"),
                ("Channel", "<code>/cplay song name</code>"),
                ("File", "Reply to audio/video/mkv/mp4 with /play or /vplay"),
                ("URL", "<code>/play youtube url</code>"),
            ]),
        )
        return

    await _process_play(message, query, video=force_video)


# ── Process play ───────────────────────────────────────────────────────────────

async def _process_play(message: Message, query: str, video: bool = False) -> None:
    chat_id = message.chat.id

    pm = await rich_send(bot, chat_id, rich_heading("⏳ Processing...", level=3))

    # Assistant check — uses utils/assistant.py
    status = await is_assistant_in(chat_id)

    if status == "banned":
        await rich_edit(
            pm,
            rich_heading("🚫 Assistant is banned", level=3)
            + rich_note("Unban the assistant and try again."),
        )
        return

    if not status:
        await rich_edit(pm, rich_heading("👤 Assistant is joining...", level=3))
        ok = await try_join_assistant(chat_id, pm)
        if not ok:
            return
        await rich_edit(
            pm,
            rich_heading("✅ Assistant joined", level=3)
            + rich_note("Processing..."),
        )

    # Normalise short YouTube URL
    if "youtu.be" in query:
        m = re.search(r"youtu\.be/([^?&]+)", query)
        if m:
            query = f"https://www.youtube.com/watch?v={m.group(1)}"

    is_url = any(x in query for x in ("youtube.com", "youtu.be", "playlist?list="))

    # Text search → show multiple results for user to pick
    if not is_url:
        try:
            from videl.utils.youtube import search_yt_multi
            results = await search_yt_multi(query, limit=5)
        except Exception as e:
            await rich_edit(
                pm,
                rich_heading("❌ Search failed", level=3)
                + rich_note(f"<code>{rich_esc(e)}</code>"),
            )
            return

        if not results:
            await rich_edit(pm, rich_heading("❌ No results found", level=3))
            return

        # Store pending results for callback (chat_id + user_id keyed)
        key = f"{chat_id}:{message.from_user.id if message.from_user else 0}"
        _search_cache[key] = {
            "results": results,
            "video": video,
            "requester": message.from_user.first_name if message.from_user else "Unknown",
            "requester_id": message.from_user.id if message.from_user else 0,
            "ts": time.time(),
        }

        buttons = []
        for i, r in enumerate(results):
            label = f"{i+1}. {short(r['title'], 32)} [{r.get('duration', '?')}]"
            buttons.append([InlineKeyboardButton(label, callback_data=f"ytpick:{i}:{key}")])
        buttons.append([InlineKeyboardButton("✕ Cancel", callback_data=f"ytpick:cancel:{key}")])

        lines = []
        for i, r in enumerate(results):
            ch = f" — {rich_esc(r['channel'])}" if r.get("channel") else ""
            lines.append(f"<b>{i+1}.</b> {rich_esc(short(r['title'], 45))} <i>({rich_esc(r.get('duration', '?'))})</i>{ch}")

        await rich_edit(
            pm,
            rich_heading(f"🔍 {sc('choose a track')}", level=3)
            + rich_note("\n".join(lines)),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    # URL / playlist path — existing search_yt
    try:
        result = await search_yt(query)
    except Exception as e:
        await rich_edit(
            pm,
            rich_heading("❌ Search failed", level=3)
            + rich_note(f"<code>{rich_esc(e)}</code>"),
        )
        return

    # Playlist
    if isinstance(result, dict) and "playlist" in result:
        items = result["playlist"]
        if not items:
            await rich_edit(pm, rich_heading("ℹ️ Playlist empty", level=3))
            return

        req    = message.from_user.first_name if message.from_user else "Unknown"
        req_id = message.from_user.id         if message.from_user else 0

        first_was_empty = queue_size(chat_id) == 0

        for item in items:
            add_to_queue(chat_id, {
                "url":              item["link"],
                "title":            item["title"],
                "duration":         iso_to_human(item["duration"]),
                "duration_seconds": iso_to_sec(item["duration"]),
                "requester":        req,
                "requester_id":     req_id,
                "thumbnail":        item["thumbnail"],
            })

        rows = [
            ("sᴏɴɢs", f"<code>{len(items)}</code>"),
            ("ғɪʀsᴛ", f"<code>{rich_esc(short(items[0]['title']))}</code>"),
        ]
        if len(items) > 1:
            rows.append(("ɴᴇxᴛ", f"<code>{rich_esc(short(items[1]['title']))}</code>"))

        await rich_send(
            bot, chat_id,
            rich_heading("❍ ᴘʟᴀʏʟɪsᴛ ᴀᴅᴅᴇᴅ", level=3) + rich_kv_table(rows),
        )

        if first_was_empty:
            first_song = peek_current(chat_id)
            if first_song:
                await play_song(chat_id, pm, first_song)
        else:
            await pm.delete()
        return

    # Single track
    url, title, dur_iso, thumb = result

    if not url:
        await rich_edit(pm, rich_heading("❍ sᴏɴɢ ɴᴏᴛ ғᴏᴜɴᴅ", level=3))
        return

    secs = iso_to_sec(dur_iso)

    if secs > config.MAX_DURATION_SECONDS:
        await rich_edit(
            pm,
            rich_heading("❍ sᴏɴɢ ᴛᴏᴏ ʟᴏɴɢ", level=3)
            + rich_kv_table([
                ("ᴅᴜʀ", f"<code>{iso_to_human(dur_iso)}</code>"),
                ("ᴍᴀx", f"<code>{config.MAX_DURATION_SECONDS // 60} min</code>"),
            ]),
        )
        return

    req    = message.from_user.first_name if message.from_user else "Unknown"
    req_id = message.from_user.id         if message.from_user else 0

    vid = ""
    if "v=" in str(url):
        vid = str(url).split("v=")[-1].split("&")[0]
    elif "youtu.be/" in str(url):
        vid = str(url).split("youtu.be/")[-1].split("?")[0]
    if vid and (not thumb or "ytimg" not in str(thumb)):
        thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"

    song = {
        "url":              url,
        "title":            title,
        "duration":         iso_to_human(dur_iso),
        "duration_seconds": secs,
        "requester":        req,
        "requester_id":     req_id,
        "thumbnail":        thumb,
        "video":            video,
        "video_id":         vid,
    }

    pos = add_to_queue(chat_id, song)

    if pos == 1:
        await play_song(chat_id, pm, song)
    else:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⌯ sᴋɪᴘ ⌯",  callback_data="skip"),
            InlineKeyboardButton("⌯ ᴄʟᴇᴀʀ ⌯", callback_data="clear"),
        ]])
        await rich_send(
            bot, chat_id,
            rich_heading("➕ Added to queue", level=3)
            + rich_kv_table([
                ("ᴛɪᴛʟᴇ", f"<code>{rich_esc(short(title))}</code>"),
                ("ᴅᴜʀ", f"<code>{iso_to_human(dur_iso)}</code>"),
                ("ʙʏ", f"<code>{rich_esc(req)}</code>"),
                ("ᴘᴏs", f"<code>#{pos - 1}</code>"),
            ]),
            reply_markup=kb,
        )
        await pm.delete()


# ── Search result picker callback ──────────────────────────────────────────────

from pyrogram.types import CallbackQuery


@bot.on_callback_query(filters.regex(r"^ytpick:"))
async def ytpick_callback(_, cq: CallbackQuery) -> None:
    data = cq.data or ""
    parts = data.split(":", 2)
    if len(parts) < 3:
        await cq.answer()
        return

    _, choice, key = parts
    cache = _search_cache.get(key)

    if choice == "cancel":
        _search_cache.pop(key, None)
        await cq.answer("Cancelled")
        try:
            await cq.message.delete()
        except Exception:
            pass
        return

    if not cache or time.time() - cache.get("ts", 0) > 120:
        _search_cache.pop(key, None)
        await cq.answer("Search expired — search again", show_alert=True)
        try:
            await cq.message.delete()
        except Exception:
            pass
        return

    # Only the requester can pick
    expected_uid = int(key.split(":")[-1]) if ":" in key else 0
    if cq.from_user and expected_uid and cq.from_user.id != expected_uid:
        if cq.from_user.id != config.OWNER_ID:
            await cq.answer("Only the requester can choose", show_alert=True)
            return

    try:
        idx = int(choice)
    except ValueError:
        await cq.answer()
        return

    results = cache.get("results") or []
    if idx < 0 or idx >= len(results):
        await cq.answer("Invalid choice", show_alert=True)
        return

    r = results[idx]
    _search_cache.pop(key, None)
    await cq.answer(f"Selected: {short(r['title'], 30)}")

    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    secs = iso_to_sec(r.get("duration_iso", "PT0S"))
    if secs > config.MAX_DURATION_SECONDS:
        await rich_edit(
            cq.message,
            rich_heading("❍ Song too long", level=3)
            + rich_kv_table([
                ("Dur", r.get("duration", "?")),
                ("Max", f"{config.MAX_DURATION_SECONDS // 60} min"),
            ]),
        )
        return

    song = {
        "url": r["url"],
        "title": r["title"],
        "duration": iso_to_human(r.get("duration_iso", "PT0S")),
        "duration_seconds": secs,
        "requester": cache.get("requester", "Unknown"),
        "requester_id": cache.get("requester_id", 0),
        "thumbnail": r.get("thumbnail", ""),
        "video": cache.get("video", False),
        "video_id": r.get("video_id", ""),
    }

    pos = add_to_queue(chat_id, song)

    if pos == 1:
        await play_song(chat_id, cq.message, song)
    else:
        await rich_edit(
            cq.message,
            rich_heading("➕ Added to queue", level=3)
            + rich_kv_table([
                ("Title", f"<code>{rich_esc(short(r['title']))}</code>"),
                ("Dur", f"<code>{r.get('duration', '?')}</code>"),
                ("Pos", f"<code>#{pos - 1}</code>"),
            ]),
        )

