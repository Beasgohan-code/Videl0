# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Media Downloader ✦ Perfect
#  Professional media downloader using external repos fully:
#  - yt-dlp (https://github.com/yt-dlp/yt-dlp) for YouTube/IG/TikTok/YT Music
#  - Pyrogram (Kurigram) for Telegram file handling (Bot API 10.3)
#  - aiohttp + httpx for network resilience
#  Commands: /song, /vsong, /download
#  Features: search picker, progress bar, thumbnail, metadata, auto-cleanup, proxy & cookies support
# --------------------------------------------------------------------------------
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlsplit

import aiofiles
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, CallbackQuery
from videl.utils.bot_ui import button as InlineKeyboardButton, visual_call

import config
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.formatters import sc, sb, short
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note, rich_table, rich_details, rich_button, rich_img, rich_send_blocks
from videl.utils.command_ui import navigation_markup, rich_send, rich_edit

try:
    from videl.utils.premium_emojis import pe
except Exception:
    def pe(k, fb=""):
        return fb

# ── Professional Logger ───────────────────────────────────────────────────────
log = logging.getLogger("videl.downloader")

DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── yt-dlp options — professional, uses all external features ────────────────
def _get_yt_dlp_opts(audio_only: bool = True, out_path: Optional[str] = None) -> dict:
    """Build professional yt-dlp options with cookies, proxy, external downloader support."""
    cookies = None
    # Never pass the repository's placeholder cookies.txt to yt-dlp. Only
    # accept an exported Netscape cookie jar containing YouTube auth cookies.
    candidates = [
        os.getenv("YTDLP_COOKIES"), os.getenv("YT_COOKIES_FILE"),
        os.getenv("COOKIES_PATH"), os.getenv("YOUTUBE_COOKIES_FILE"),
        "/app/cookies.txt", "cookies.txt",
    ]
    markers = ("\tSID\t", "\tHSID\t", "\tSSID\t", "\tLOGIN_INFO\t",
               "\tSAPISID\t", "\tAPISID\t", "\t__Secure-3PSID\t")
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            raw = Path(candidate).read_text(encoding="utf-8", errors="ignore")
            if any(marker in raw for marker in markers):
                cookies = candidate
                break
        except OSError:
            continue

    proxy = (os.getenv("PROXY_URL") or os.getenv("YOUTUBE_PROXY") or "").strip()
    if proxy and "://" not in proxy:
        proxy = "http://" + proxy

    # External downloader: aria2c if available for faster downloads
    external_downloader = None
    if shutil.which("aria2c"):
        external_downloader = "aria2c"
        log.info("Using aria2c as external downloader")

    fmt = "bestaudio[ext=m4a]/bestaudio/best" if audio_only else "best[height<=1080][ext=mp4]/best"

    opts = {
        "format": fmt,
        "outtmpl": out_path or str(DOWNLOAD_DIR / "%(title).80s-%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "retries": 5,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 5,
        "postprocessors": [],
        "prefer_ffmpeg": True,
        "keepvideo": False,
    }
    if cookies:
        opts["cookiefile"] = cookies
        log.debug(f"Using cookies: {cookies}")
    if proxy:
        opts["proxy"] = proxy
    if external_downloader:
        opts["external_downloader"] = external_downloader
        opts["external_downloader_args"] = ["--min-split-size=1M", "--max-connection-per-server=4"]

    # Audio extraction via FFmpeg for audio_only
    if audio_only:
        opts["postprocessors"].append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        })

    return opts


def _extract_video_id(text: str) -> Optional[str]:
    """Extract YouTube video ID from URL or raw ID using professional regex (all variants)."""
    text = text.strip()
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
        r"youtube\.com.*[?&]v=([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


def _is_url(text: str) -> bool:
    return text.startswith(("http://", "https://", "www.")) or bool(re.match(r"^[A-Za-z0-9_-]{11}$", text.strip()))


async def _search_youtube(query: str, limit: int = 5) -> list[dict]:
    """Professional YouTube search using VideosSearch (py-yt-search) + yt-dlp fallback."""
    results = []
    # Primary: youtubesearchpython
    try:
        from py_yt import VideosSearch
        search = VideosSearch(query, limit=limit)
        data = await asyncio.to_thread(search.result)
        for item in data.get("result", [])[:limit]:
            results.append({
                "id": item.get("id"),
                "title": item.get("title", "Unknown"),
                "duration": item.get("duration", "?"),
                "channel": item.get("channel", {}).get("name", "?") if isinstance(item.get("channel"), dict) else str(item.get("channel", "?")),
                "views": item.get("viewCount", {}).get("short", "?") if isinstance(item.get("viewCount"), dict) else "?",
                "link": item.get("link") or f"https://www.youtube.com/watch?v={item.get('id')}",
                "thumbnail": (item.get("thumbnails") or [{}])[0].get("url") if item.get("thumbnails") else "",
            })
        if results:
            log.info(f"Search '{query}' → {len(results)} results via VideosSearch")
            return results
    except Exception as e:
        log.warning(f"VideosSearch failed for '{query}': {e}")

    # Fallback: yt-dlp search
    try:
        import yt_dlp
        ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "default_search": f"ytsearch{limit}"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, f"ytsearch{limit}:{query}", download=False)
            for entry in (info.get("entries") or [])[:limit]:
                results.append({
                    "id": entry.get("id"),
                    "title": entry.get("title", "Unknown"),
                    "duration": entry.get("duration_string") or str(entry.get("duration") or "?"),
                    "channel": entry.get("uploader", "?"),
                    "views": str(entry.get("view_count") or "?"),
                    "link": entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry.get('id')}",
                    "thumbnail": entry.get("thumbnail", ""),
                })
        if results:
            log.info(f"Search '{query}' → {len(results)} via yt-dlp fallback")
    except Exception as e:
        log.error(f"yt-dlp search failed: {e}")

    return results


async def _download_media(source: str, audio_only: bool = True, status_msg: Optional[Message] = None) -> Optional[Path]:
    """Professional download with progress, retries, and cleanup."""
    tmpdir = Path(tempfile.mkdtemp(dir=str(DOWNLOAD_DIR)))
    outtmpl = str(tmpdir / "%(title).80s-%(id)s.%(ext)s")
    opts = _get_yt_dlp_opts(audio_only=audio_only, out_path=outtmpl)

    # Resolve source: if not URL, search first
    if not _is_url(source):
        log.info(f"Searching for: {source}")
        if status_msg:
            try:
                await rich_edit(
                    status_msg,
                    rich_heading("🔎 Searching for your track", level=3)
                    + rich_note("Looking for a playable match…"),
                )
            except Exception:
                pass
        results = await _search_youtube(source, limit=1)
        if not results:
            raise ValueError(f"No results for '{source}'")
        source = results[0]["link"]
        log.info(f"Resolved '{source}' → {results[0]['title']}")

    url = source.strip()
    if re.match(r"^[A-Za-z0-9_-]{11}$", url):
        url = f"https://www.youtube.com/watch?v={url}"
    elif url.startswith("www."):
        url = "https://" + url

    if status_msg:
        try:
            media_label = "MP3 · 192 kbps audio" if audio_only else "MP4 · up to 1080p video"
            status_text = (
                rich_heading("⬇️ Preparing your download", level=3)
                + rich_note(
                    f"<b>Source</b> · {rich_esc(_source_summary(url))}<br>"
                    f"<b>Format</b> · {media_label}<br>"
                    "<i>This may take a few moments.</i>"
                )
            )
            await rich_edit(status_msg, status_text, navigation=False)
        except Exception:
            pass

    def _run():
        import yt_dlp
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError("yt-dlp returned no info")
            # Find downloaded file
            for ext in (".mp3", ".m4a", ".mp4", ".mkv", ".webm", ".opus"):
                for p in tmpdir.rglob(f"*{ext}"):
                    if p.is_file() and p.stat().st_size > 1024:
                        return p, info
            # Fallback via prepare_filename
            try:
                guessed = Path(ydl.prepare_filename(info))
                if guessed.exists():
                    return guessed, info
            except Exception:
                pass
            raise RuntimeError("Downloaded file not found")

    try:
        path, info = await asyncio.to_thread(_run)
        if not path.exists() or path.stat().st_size < 1024:
            raise RuntimeError(f"File too small: {path}")
        log.info(f"Downloaded {path.name} ({path.stat().st_size/1024/1024:.2f} MB) — {info.get('title')}")
        return path
    except Exception as e:
        log.error(f"Download failed for {url}: {e}", exc_info=True)
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


def _hdr(t: str, lvl: int = 3):
    return rich_heading(t, level=lvl)


def _source_summary(source: str) -> str:
    """Describe a media source without echoing tracking/auth query parameters."""
    try:
        parsed = urlsplit(str(source).strip())
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if not host:
            return "Search result"
        if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
            video_id = (parse_qs(parsed.query).get("v") or [""])[0]
            if not video_id and parsed.path.startswith("/shorts/"):
                video_id = parsed.path.split("/", 2)[2]
            return "YouTube" + (f" · {video_id[:11]}" if video_id else "")
        if host == "youtu.be":
            video_id = parsed.path.strip("/").split("/", 1)[0]
            return "YouTube" + (f" · {video_id[:11]}" if video_id else "")
        return host
    except Exception:
        return "Provided link"


def _friendly_download_error(error: Exception) -> str:
    """Map noisy extractor/network details to actionable, non-leaking copy."""
    detail = str(error or "").casefold()
    if "failed to extract any player response" in detail or "player response" in detail:
        return "YouTube couldn’t prepare a stream for this video right now. Please try again later or use another link."
    if "no results" in detail or "no matching" in detail:
        return "No playable result was found. Try a different title or link."
    if "unsupported url" in detail or "unsupported site" in detail:
        return "That link format isn’t supported. Try a direct video link or search by title."
    if any(term in detail for term in ("private video", "video unavailable", "members-only", "age-restricted", "sign in to confirm")):
        return "This video may be private, age-restricted, or unavailable to the bot. Try another link."
    if any(term in detail for term in ("http error 403", "http error 429", "too many requests", "rate limit")):
        return "The media source is temporarily limiting downloads. Please wait a little and try again."
    return "The download couldn’t be completed. Check the link and try again in a moment."


def _hero_img(url: Optional[str] = None):
    if url and url.startswith("http"):
        return rich_img(url)
    return rich_img("https://files.catbox.moe/f084wg.png")

# ── /song — download audio (like ShizuMusic /song) ────────────────────────────

@bot.on_message(filters.command('song', prefixes=config.COMMAND_PREFIXES) & (filters.group | filters.private))
async def song_cmd(_, m: Message):
    query = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not query and m.reply_to_message and m.reply_to_message.text:
        query = m.reply_to_message.text.strip()
    if not query:
        body = (
            rich_heading("🎵 Audio downloader", level=2)
            + rich_note(
                "Send a track name or a direct link to get a high-quality MP3. "
                "You can also reply to a message containing a title or link."
            )
            + rich_table(
                ["Command", "What it does"],
                [
                    ("<code>/song</code>", "Download audio · MP3, 192 kbps"),
                    ("<code>/vsong</code>", "Download video · MP4, up to 1080p"),
                    ("<code>/download</code>", "Choose audio or video automatically"),
                ],
            )
            + rich_details(
                "Supported sources",
                "YouTube, YouTube Music, SoundCloud, Instagram, TikTok, and more.",
            )
        )
        body += "<p>" + rich_button("🎵 Play in voice chat", callback_data="help_play") + " " + rich_button("🔎 Search", callback_data="song_search") + "</p>"
        return await rich_send(bot, m.chat.id, body)

    # Check banned words professionally
    blocked = getattr(config, "BLOCKED_WORDS", []) or ["porn", "xxx", "xnxx", "sex"]
    low = query.lower()
    if any(w in low for w in blocked):
        return await rich_send(
            bot, m.chat.id,
            rich_heading("⚠️ Request not allowed", level=3)
            + rich_note("This search request isn’t permitted. Try a different title or link."),
        )

    status = await rich_send(
        bot, m.chat.id,
        rich_heading("🎵 Preparing your audio", level=3)
        + rich_note("Finding the track and preparing a high-quality audio file…"),
        navigation=False,
    )

    path = None
    try:
        start = time.time()
        path = await _download_media(query, audio_only=True, status_msg=status)
        elapsed = time.time() - start

        # Extract metadata via yt-dlp info if available, else dummy
        title = path.stem[:80].replace("_", " ")
        duration = "?"
        # Try to get real metadata from filename or via probe
        try:
            import yt_dlp
            # Quick probe for thumbnail via search
            search_res = await _search_youtube(query, limit=1)
            if search_res:
                title = search_res[0].get("title", title)[:80]
                duration = search_res[0].get("duration", "?")
                thumb = search_res[0].get("thumbnail", "")
            else:
                thumb = ""
        except Exception:
            thumb = ""

        size_mb = path.stat().st_size / 1024 / 1024
        if size_mb > 50:
            await rich_edit(
                status,
                rich_heading("⚠️ Audio file is too large", level=3)
                + rich_note(
                    f"This file is {size_mb:.1f} MB; Telegram bots can send up to 50 MB. "
                    "Try a shorter track."
                ),
            )
            path.unlink(missing_ok=True)
            shutil.rmtree(path.parent, ignore_errors=True)
            return

        # Build caption with rich metadata
        cap = _hdr(pe("music","🎵") + " " + rich_esc(title[:60]), 2)
        cap += _hero_img(thumb) if thumb else ""
        cap += rich_kv_table([
            ("Title", rich_esc(title[:60])),
            ("Duration", f"<code>{rich_esc(duration)}</code>"),
            ("File size", f"<code>{size_mb:.2f} MB</code>"),
            ("Ready in", f"<code>{elapsed:.1f} seconds</code>"),
            ("Requested by", f"<a href=\"tg://user?id={m.from_user.id}\">{rich_esc(m.from_user.first_name or 'User')}</a>" if m.from_user else "User"),
        ], headers=["Audio download", ""])
        cap += rich_note("Audio prepared as an MP3 · 192 kbps")

        # Send audio with professional metadata
        try:
            await visual_call(
                bot.send_audio,
                chat_id=m.chat.id,
                audio=str(path),
                caption=cap,
                parse_mode=ParseMode.HTML,
                title=title[:60],
                performer="Videl • Beasgohan-code",
                reply_to_message_id=m.id,
                reply_markup=navigation_markup(),
            )
            await rich_edit(
                status,
                rich_heading("✅ Audio sent", level=3)
                + rich_note(
                    f"<b>{rich_esc(title[:60])}</b><br>"
                    f"{size_mb:.2f} MB · ready in {elapsed:.1f} seconds"
                ),
                navigation=False,
            )
            log.info(f"/song by {m.from_user.id} in {m.chat.id}: {title} ({size_mb:.2f} MB, {elapsed:.1f}s)")
        except Exception as e:
            log.error(f"send_audio fail: {e}", exc_info=True)
            await bot.send_document(
                m.chat.id, document=str(path), caption=rich_esc(title),
                reply_to_message_id=m.id, reply_markup=navigation_markup(),
            )
            try:
                await status.delete()
            except Exception:
                pass
        finally:
            # Cleanup
            try:
                path.unlink(missing_ok=True)
                shutil.rmtree(path.parent, ignore_errors=True)
            except Exception as e:
                log.debug(f"Cleanup fail: {e}")

    except ValueError as e:
        log.info("/song could not find a playable result for %r: %s", query[:160], e)
        await rich_edit(
            status,
            rich_heading("🔎 No playable result found", level=3)
            + rich_note("Try another title or paste a direct audio/video link."),
        )
    except Exception as e:
        log.error(f"/song error for '{query}': {e}", exc_info=True)
        await rich_edit(
            status,
            rich_heading("⚠️ Download couldn’t be completed", level=3)
            + rich_note(_friendly_download_error(e)),
        )
        if path and path.exists():
            try:
                path.unlink(missing_ok=True)
                shutil.rmtree(path.parent, ignore_errors=True)
            except Exception:
                pass


@bot.on_message(filters.command('vsong', prefixes=config.COMMAND_PREFIXES) & (filters.group | filters.private))
async def vsong_cmd(_, m: Message):
    query = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not query and m.reply_to_message and m.reply_to_message.text:
        query = m.reply_to_message.text.strip()
    if not query:
        body = (
            rich_heading("🎥 Video downloader", level=2)
            + rich_note(
                "Send a video title or direct link to download an MP4 (up to 1080p). "
                "You can also reply to a message containing a title or link."
            )
            + rich_details("Example", "<code>/vsong nature documentary</code>")
        )
        return await rich_send(bot, m.chat.id, body)

    status = await rich_send(
        bot, m.chat.id,
        rich_heading("🎥 Preparing your video", level=3)
        + rich_note("Checking the source and preparing an MP4 download…"),
        navigation=False,
    )

    path = None
    try:
        start = time.time()
        path = await _download_media(query, audio_only=False, status_msg=status)
        elapsed = time.time() - start
        size_mb = path.stat().st_size / 1024 / 1024
        if size_mb > 50:
            # Try compress or send as document with warning
            log.warning(f"Video too large: {size_mb:.1f} MB")
            await rich_edit(
                status,
                rich_heading("⚠️ Video file is too large", level=3)
                + rich_note(
                    f"This file is {size_mb:.1f} MB; Telegram bots can send up to 50 MB. "
                    "Try a shorter video."
                ),
            )
            path.unlink(missing_ok=True)
            shutil.rmtree(path.parent, ignore_errors=True)
            return

        title = path.stem[:60]
        cap = (
            rich_heading(f"🎥 {rich_esc(title)}", level=2)
            + rich_kv_table([
                ("File size", f"<code>{size_mb:.2f} MB</code>"),
                ("Ready in", f"<code>{elapsed:.1f} seconds</code>"),
            ], headers=["Video download", ""])
        )
        await visual_call(
            bot.send_video,
            chat_id=m.chat.id,
            video=str(path),
            caption=cap,
            parse_mode=ParseMode.HTML,
            reply_to_message_id=m.id,
            supports_streaming=True,
        )
        await status.delete()
        path.unlink(missing_ok=True)
        shutil.rmtree(path.parent, ignore_errors=True)
        log.info(f"/vsong {m.from_user.id} → {title} {size_mb:.2f} MB")
    except Exception as e:
        log.error(f"/vsong error: {e}", exc_info=True)
        await rich_edit(
            status,
            rich_heading("⚠️ Video download couldn’t be completed", level=3)
            + rich_note(_friendly_download_error(e)),
        )
        if path:
            try:
                path.unlink(missing_ok=True)
                shutil.rmtree(path.parent, ignore_errors=True)
            except Exception:
                pass


@bot.on_message(filters.command('download', prefixes=config.COMMAND_PREFIXES) & (filters.group | filters.private))
async def download_cmd(_, m: Message):
    query = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not query:
        body = (
            rich_heading("⬇️ Media downloader", level=2)
            + rich_note(
                "Send a title or link and I’ll prepare audio or video automatically. "
                "Use <code>/song</code> or <code>/vsong</code> to choose a format yourself."
            )
            + rich_details(
                "Supported sources",
                "YouTube, TikTok, Instagram, SoundCloud, X, Facebook, and many more.",
            )
        )
        body += "<p>" + rich_button("🎵 Audio help", callback_data="dl:song") + " " + rich_button("📹 Video help", callback_data="dl:video") + "</p>"
        return await rich_send(bot, m.chat.id, body)
    # Auto-detect: if query contains video keywords, use video, else audio
    is_video = any(x in query.lower() for x in (".mp4", "video", "tiktok", "instagram", "reel"))
    if is_video:
        m.command = ["vsong"] + query.split()
        return await vsong_cmd(bot, m)
    else:
        m.command = ["song"] + query.split()
        return await song_cmd(bot, m)


# ── Callbacks for download pills ─────────────────────────────────────────────
@bot.on_callback_query(filters.regex(r"^dl:"))
async def dl_cbs(_, q: CallbackQuery):
    data = (q.data or "").split(":")[1] if ":" in (q.data or "") else ""
    if data == "song":
        await q.answer("Use /song followed by a title or link")
        try:
            await rich_edit(
                q.message,
                rich_heading("🎵 Download audio", level=3)
                + rich_note("Example: <code>/song Believer</code> · MP3, 192 kbps"),
            )
        except Exception:
            pass
    elif data == "video":
        await q.answer("Use /vsong followed by a title or link")
        try:
            await rich_edit(
                q.message,
                rich_heading("🎥 Download video", level=3)
                + rich_note("Example: <code>/vsong nature documentary</code> · MP4, up to 1080p"),
            )
        except Exception:
            pass

log.info(" downloader — perfect ")
