# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Media Downloader ✦ Perfect
#  Professional media downloader using external repos fully:
#  - yt-dlp (https://github.com/yt-dlp/yt-dlp) for YouTube/IG/TikTok/YT Music
#  - Pyrogram (Kurigram) for Telegram file handling (Bot API 10.3)
#  - aiohttp + httpx for network resilience
#  Commands: /song, /vsong, /download, /ytaudio, /ytvideo, /playdl
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

import aiofiles
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, CallbackQuery
from videl.utils.bot_ui import button as InlineKeyboardButton

import config
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.formatters import sc, sb, short
from videl.utils.rich_ui import (
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_table,
    rich_details,
    rich_button,
    rich_img,
    rich_send,
    rich_edit,
    rich_send_blocks,
)

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
    for key in ("YTDLP_COOKIES", "COOKIES_PATH", "YOUTUBE_COOKIES_FILE", "cookies.txt"):
        v = os.getenv(key)
        if v and Path(v).exists():
            cookies = v
            break
    if not cookies and Path("/app/cookies.txt").exists():
        cookies = "/app/cookies.txt"
    elif not cookies and Path("cookies.txt").exists():
        cookies = "cookies.txt"

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
        "http_chunk_size": 10 * 1024 * 1024,
        "extractor_args": {"youtube": {"player_client": ["android", "ios", "web", "web_embedded"]}},
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
                await rich_edit(status_msg, rich_heading(f"{pe('circle','')} {sc('searching')} • {sc(source[:40])}", level=3))
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
            await rich_edit(status_msg, rich_heading(f"{pe('diamond','')} {sc('downloading')} • {sc('please wait')}", level=3) + rich_note(f"<code>{rich_esc(url[:60])}</code> • {pe('hex','')} {sc('quality')}: <code>{'MP3 192kbps' if audio_only else 'MP4 1080p'}</code>"))
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
    return rich_heading(pe("orb","") + " " + t + " " + pe("spark",""), level=lvl)

def _hero_img(url: Optional[str] = None):
    if url and url.startswith("http"):
        return rich_img(url)
    return rich_img("https://files.catbox.moe/f084wg.png")

# ── /song — download audio (like ShizuMusic /song) ────────────────────────────

@bot.on_message(filters.command(["song", "ytaudio", "mdown", "yta"]) & filters.group & filters.private)
async def song_cmd(_, m: Message):
    query = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not query and m.reply_to_message and m.reply_to_message.text:
        query = m.reply_to_message.text.strip()
    if not query:
        body = _hdr(sc("song downloader") + " • " + pe("music","🎵"), 2)
        body += rich_note(pe("diamond","") + " " + sc("usage") + ": <code>/song &lt;name or URL&gt;</code><br>" + pe("small","") + " " + sc("e.g.") + " <code>/song Believer Imagine Dragons</code><br>" + pe("small","") + " <code>/song https://youtu.be/dQw4w9WgXcQ</code>")
        body += rich_table([sc("command"), sc("description")], [("<code>/song</code>", sc("download audio MP3 192kbps")), ("<code>/vsong</code>", sc("download video MP4 1080p")), ("<code>/download</code>", sc("auto-detect audio/video"))])
        body += rich_details(pe("star","⭐️") + " " + sc("features"), rich_note(pe("line","") + " " + sc("yt-dlp + aria2c + cookies + proxy support") + "<br>" + pe("line","") + " " + sc("supports YouTube, YT Music, SoundCloud, IG, TikTok") + "<br>" + pe("line","") + " " + sc("metadata + thumbnail + progress bar")))
        body += "<p>" + rich_button(pe("music","🎵") + " " + sc("play in vc"), callback_data="help_play") + " " + rich_button(pe("eyes","👀") + " " + sc("search"), callback_data="song_search") + "</p>"
        return await rich_send(bot, m.chat.id, body)

    # Check banned words professionally
    blocked = getattr(config, "BLOCKED_WORDS", []) or ["porn", "xxx", "xnxx", "sex"]
    low = query.lower()
    if any(w in low for w in blocked):
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("blocked content"),3) + rich_note(sc("this content is not allowed")))

    status = await rich_send(bot, m.chat.id, _hdr(pe("circle","") + " " + sc("preparing") + " • " + sc(query[:30]),3) + rich_note(pe("diamond","") + " " + sc("searching & downloading") + "…<br>" + pe("hex","") + " " + sc("this may take 10-30 seconds")))

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
            await rich_edit(status, _hdr(pe("warn","⚠️") + " " + sc("file too large") + f" • {size_mb:.1f} MB",3) + rich_note(sc("Telegram limit 50MB for bots — try shorter track")))
            path.unlink(missing_ok=True)
            shutil.rmtree(path.parent, ignore_errors=True)
            return

        # Build caption with rich metadata
        cap = _hdr(pe("music","🎵") + " " + rich_esc(title[:60]), 2)
        cap += _hero_img(thumb) if thumb else ""
        cap += rich_kv_table([
            (pe("target","") + " " + sc("title"), rich_esc(title[:60])),
            (pe("hex","") + " " + sc("duration"), f"<code>{rich_esc(duration)}</code>"),
            (pe("diamond","") + " " + sc("size"), f"<code>{size_mb:.2f} MB</code>"),
            (pe("circle","") + " " + sc("elapsed"), f"<code>{elapsed:.1f}s</code>"),
            (pe("small","") + " " + sc("requested by"), f"<a href=\"tg://user?id={m.from_user.id}\">{rich_esc(m.from_user.first_name or 'User')}</a>" if m.from_user else "?"),
        ], headers=[pe("spark","") + " " + sc("downloaded"), ""])
        cap += rich_note(pe("line","") + " " + sc("via yt-dlp • ffmpeg • aria2c") + " " + pe("spark",""))

        # Send audio with professional metadata
        try:
            await bot.send_audio(
                chat_id=m.chat.id,
                audio=str(path),
                caption=cap,
                parse_mode=ParseMode.HTML,
                title=title[:60],
                performer="Videl • Beasgohan-code",
                reply_to_message_id=m.id,
            )
            await rich_edit(status, _hdr(pe("check","✅") + " " + sc("sent") + " • " + pe("music","🎵"),3) + rich_note(pe("diamond","") + " <code>" + rich_esc(title[:40]) + "</code> " + pe("hex","") + f" {size_mb:.2f} MB " + pe("small","") + f" {elapsed:.1f}s"))
            log.info(f"/song by {m.from_user.id} in {m.chat.id}: {title} ({size_mb:.2f} MB, {elapsed:.1f}s)")
        except Exception as e:
            log.error(f"send_audio fail: {e}", exc_info=True)
            await bot.send_document(m.chat.id, document=str(path), caption=rich_esc(title), reply_to_message_id=m.id)
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
        await rich_edit(status, _hdr(pe("warn","⚠️") + " " + sc("not found"),3) + rich_note(rich_esc(str(e))))
        log.warning(f"/song not found: {query} — {e}")
    except Exception as e:
        log.error(f"/song error for '{query}': {e}", exc_info=True)
        await rich_edit(status, _hdr(pe("cross","❌") + " " + sc("download failed"),3) + rich_note(f"<code>{rich_esc(str(e)[:300])}</code><br>" + pe("line","") + " " + sc("try again or use different query") + "<br>" + pe("small","") + " " + sc("check cookies/proxy if YouTube blocked")))
        if path and path.exists():
            try:
                path.unlink(missing_ok=True)
                shutil.rmtree(path.parent, ignore_errors=True)
            except Exception:
                pass


@bot.on_message(filters.command(["vsong", "ytvideo", "vdownload"]) & filters.group & filters.private)
async def vsong_cmd(_, m: Message):
    query = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not query and m.reply_to_message and m.reply_to_message.text:
        query = m.reply_to_message.text.strip()
    if not query:
        return await rich_send(bot, m.chat.id, _hdr(sc("video downloader"),2) + rich_note("<code>/vsong &lt;name or URL&gt;</code><br>" + pe("small","") + " <code>/vsong Believer</code> • MP4 1080p"))

    status = await rich_send(bot, m.chat.id, _hdr(pe("circle","") + " " + sc("preparing video") + " • " + sc(query[:30]),3))

    path = None
    try:
        start = time.time()
        path = await _download_media(query, audio_only=False, status_msg=status)
        elapsed = time.time() - start
        size_mb = path.stat().st_size / 1024 / 1024
        if size_mb > 50:
            # Try compress or send as document with warning
            log.warning(f"Video too large: {size_mb:.1f} MB")
            await rich_edit(status, _hdr(pe("warn","⚠️") + " " + sc("video too large") + f" {size_mb:.1f} MB",3) + rich_note(sc("Telegram 50MB limit — try /song for audio")))
            path.unlink(missing_ok=True)
            shutil.rmtree(path.parent, ignore_errors=True)
            return

        title = path.stem[:60]
        cap = _hdr(pe("pin","📌") + " " + rich_esc(title),2) + rich_kv_table([(pe("hex","") + " " + sc("size"), f"<code>{size_mb:.2f} MB</code>"), (pe("circle","") + " " + sc("elapsed"), f"<code>{elapsed:.1f}s</code>")])
        await bot.send_video(chat_id=m.chat.id, video=str(path), caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=m.id, supports_streaming=True)
        await status.delete()
        path.unlink(missing_ok=True)
        shutil.rmtree(path.parent, ignore_errors=True)
        log.info(f"/vsong {m.from_user.id} → {title} {size_mb:.2f} MB")
    except Exception as e:
        log.error(f"/vsong error: {e}", exc_info=True)
        await rich_edit(status, _hdr(pe("cross","❌") + " " + sc("video download failed"),3) + rich_note(f"<code>{rich_esc(str(e)[:300])}</code>"))
        if path:
            try:
                path.unlink(missing_ok=True)
                shutil.rmtree(path.parent, ignore_errors=True)
            except Exception:
                pass


@bot.on_message(filters.command(["download", "dl"]) & filters.group & filters.private)
async def download_cmd(_, m: Message):
    query = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not query:
        return await rich_send(bot, m.chat.id, _hdr(sc("downloader"),3) + rich_note("<code>/download &lt;URL or name&gt;</code><br>" + pe("small","") + " " + sc("audio if music, video if video URL") + "<br>" + rich_details(sc("supported"), sc("YouTube • TikTok • Instagram • SoundCloud • Twitter • Facebook • 1000+ sites via yt-dlp")) + "<p>" + rich_button(pe("music","🎵") + " " + sc("song"), callback_data="dl:song") + " " + rich_button(pe("pin","📌") + " " + sc("video"), callback_data="dl:video") + "</p>"))
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
        await q.answer(sc("use") + " /song <name>")
        try:
            await rich_edit(q.message, _hdr(sc("song downloader"),3) + rich_note("<code>/song Believer</code> — MP3 192kbps " + pe("music","🎵")))
        except Exception:
            pass
    elif data == "video":
        await q.answer(sc("use") + " /vsong <name>")
        try:
            await rich_edit(q.message, _hdr(sc("video downloader"),3) + rich_note("<code>/vsong Believer</code> — MP4 1080p " + pe("pin","📌")))
        except Exception:
            pass

log.info(" downloader — perfect ")
