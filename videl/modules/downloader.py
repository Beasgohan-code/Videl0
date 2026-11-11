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
import ipaddress
import socket
import time
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlsplit

import aiofiles
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.errors import BadRequest
from pyrogram.types import Message, InlineKeyboardMarkup, CallbackQuery
from videl.utils.bot_ui import button as InlineKeyboardButton, visual_call

import config
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.formatters import sc, sb, short
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note, rich_table, rich_details, rich_button
from videl.utils.command_ui import (
    rich_send, rich_edit, section, transfer_progress_callback,
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
    """Build yt-dlp options using cookies only from an explicitly configured path."""
    # Cookie jars are credentials: accept only explicitly configured absolute
    # paths outside the checkout and never log the path or cookie contents.
    from videl.utils.cookie_security import configured_cookie_path
    cookies = configured_cookie_path()

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
        log.debug("Using explicitly configured YouTube authentication cookies")
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


_URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_LOCAL_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa")


def _is_url(text: str) -> bool:
    value = str(text or "").strip()
    return bool(
        re.match(r"(?i)^https?://", value)
        or value.lower().startswith("www.")
        or _YOUTUBE_ID_RE.fullmatch(value)
    )


def _normalize_direct_url(source: str) -> str:
    """Normalize HTTP(S) media URLs and reject obvious local/private targets."""
    value = str(source or "").strip()
    if _YOUTUBE_ID_RE.fullmatch(value):
        return f"https://www.youtube.com/watch?v={value}"
    if value.lower().startswith("www."):
        value = "https://" + value

    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public HTTP(S) media links are supported")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Credentials in media URLs are not supported")
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid media URL port") from None
    if port not in {None, 80, 443}:
        raise ValueError("Only standard public web ports are supported")

    host = parsed.hostname.rstrip(".").lower()
    if "." not in host:
        raise ValueError("Single-label media hosts are not supported")
    if host == "localhost" or host.endswith(_LOCAL_HOST_SUFFIXES):
        raise ValueError("Local media hosts are not supported")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        # inet_aton also recognizes legacy numeric IPv4 spellings such as
        # decimal or abbreviated loopback addresses that ip_address rejects.
        try:
            address = ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            address = None
    if address is not None and not address.is_global:
        raise ValueError("Private or reserved media addresses are not supported")
    return value


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
            log.info("YouTube title search returned %d results", len(results))
            return results
    except Exception as error:
        log.warning("VideosSearch provider failed (%s)", type(error).__name__)

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
            log.info("yt-dlp title search returned %d results", len(results))
    except Exception as e:
        log.error("yt-dlp search provider failed (%s)", type(e).__name__)

    return results


async def _fallback_youtube_audio(url: str, tmpdir: Path, requested_label: str) -> tuple[Path, dict] | None:
    """Use the configured playback providers if yt-dlp cannot extract YouTube audio."""
    if not _extract_video_id(url):
        return None
    from videl.utils.youtube import release_cache_file, resolve_stream

    downloaded = await resolve_stream(url)
    if not downloaded:
        return None
    try:
        original = Path(downloaded)
        if not original.is_file() or original.stat().st_size <= 1024:
            return None
        # Playback providers store their cache in the shared download directory.
        # Copy into this request's temp folder so normal cleanup cannot delete the
        # shared cache or another request's files.
        extension = original.suffix if original.suffix.lower() in {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".webm"} else ".mp3"
        copied = tmpdir / f"fallback-audio{extension}"
        await asyncio.to_thread(shutil.copy2, original, copied)
        title = requested_label if not _is_url(requested_label) else original.stem
        return copied, {"title": title[:180] or "YouTube audio", "duration": None}
    finally:
        release_cache_file(downloaded)


def _yt_dlp_progress_hook(status_msg, title="Downloading media"):
    """Bridge yt-dlp's worker-thread byte events into throttled Telegram edits."""
    if status_msg is None:
        return None
    loop = asyncio.get_running_loop()

    async def update(text):
        await rich_edit(status_msg, text, navigation=False)

    report = transfer_progress_callback(update, title, interval=2.0)
    state = {"at": 0.0, "bucket": -1, "latest": None}
    pending = []

    def hook(data):
        if not isinstance(data, dict) or data.get("status") != "downloading":
            return None
        try:
            current = int(data.get("downloaded_bytes") or 0)
            total = int(data.get("total_bytes") or data.get("total_bytes_estimate") or 0)
        except (TypeError, ValueError, OverflowError):
            return None
        if current < 0 or total <= 0:
            return None
        state["latest"] = (current, total)
        bucket = int(min(current, total) * 100 / total) // 10
        now = time.monotonic()
        if bucket == state["bucket"] and now - state["at"] < 2.0:
            return None
        state.update(at=now, bucket=bucket)
        try:
            future = asyncio.run_coroutine_threadsafe(report(current, total), loop)
            pending.append(future)
            return future
        except RuntimeError:
            return None

    async def drain(*, complete=False):
        latest = state["latest"]
        if latest:
            current, total = latest
            if complete:
                current = total
            future = asyncio.run_coroutine_threadsafe(report(current, total), loop)
            pending.append(future)
        for future in list(pending):
            try:
                await asyncio.wrap_future(future)
            except Exception:
                pass
        pending.clear()

    hook.drain = drain
    return hook


async def _download_media(
    source: str,
    audio_only: bool = True,
    status_msg: Optional[Message] = None,
    *,
    include_info: bool = False,
) -> Path | tuple[Path, dict]:
    """Professional download with progress, retries, and cleanup."""
    source = str(source or "").strip()
    if _is_url(source) or _URL_SCHEME_RE.match(source):
        source = _normalize_direct_url(source)

    tmpdir = Path(tempfile.mkdtemp(dir=str(DOWNLOAD_DIR)))
    outtmpl = str(tmpdir / "%(title).80s-%(id)s.%(ext)s")
    try:
        opts = _get_yt_dlp_opts(audio_only=audio_only, out_path=outtmpl)
    except BaseException:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise

    requested_label = source.strip()

    # Resolve source: if not URL, search first
    if not _is_url(source):
        log.info("Searching for media title (%d characters)", len(source))
        if status_msg:
            try:
                await rich_edit(
                    status_msg,
                    section("Searching for a track", rich_note("Looking for a playable match…"), level=3),
                )
            except Exception:
                pass
        try:
            results = await _search_youtube(source, limit=1)
            if not results:
                raise ValueError("No matching media result")
            source = _normalize_direct_url(results[0]["link"])
        except BaseException:
            # Includes cancellation while the provider is resolving a title.
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise
        log.info("Resolved a media title to a supported source")

    url = source.strip()
    if re.match(r"^[A-Za-z0-9_-]{11}$", url):
        url = f"https://www.youtube.com/watch?v={url}"
    elif url.startswith("www."):
        url = "https://" + url

    if status_msg:
        try:
            media_label = "MP3 · 192 kbps audio" if audio_only else "MP4 · up to 1080p video"
            status_text = section(
                "Preparing download",
                rich_note(
                    f"<b>Source</b> · {rich_esc(_source_summary(url))}<br>"
                    f"<b>Format</b> · {media_label}<br>"
                    "<i>Waiting for the source to report transfer size.</i>"
                ),
                level=3,
            )
            await rich_edit(status_msg, status_text, navigation=False)
        except Exception:
            pass

    progress_hook = None
    if status_msg is not None:
        media_kind = "Downloading audio" if audio_only else "Downloading video"
        progress_hook = _yt_dlp_progress_hook(status_msg, media_kind)
        opts["progress_hooks"] = [progress_hook]

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
        try:
            path, info = await asyncio.to_thread(_run)
            if progress_hook is not None:
                await progress_hook.drain(complete=True)
        except Exception as extractor_error:
            if progress_hook is not None:
                await progress_hook.drain()
            if not audio_only or not _extract_video_id(url):
                raise
            if status_msg is not None:
                try:
                    await rich_edit(
                        status_msg,
                        section("Switching audio source", rich_note("The first source did not return a playable file. Trying the configured fallback…"), level=3),
                        navigation=False,
                    )
                except Exception:
                    pass
            log.warning("yt-dlp audio extraction failed for YouTube; trying configured provider fallback (%s)", type(extractor_error).__name__)
            try:
                fallback = await _fallback_youtube_audio(url, tmpdir, requested_label)
            except Exception as fallback_error:
                log.warning("Configured YouTube audio fallback failed (%s)", type(fallback_error).__name__)
                from videl.utils.youtube import MediaDownloadError
                if isinstance(fallback_error, MediaDownloadError):
                    raise fallback_error from extractor_error
                raise extractor_error from fallback_error
            if fallback is None:
                raise
            path, info = fallback
        if not path.exists() or path.stat().st_size < 1024:
            raise RuntimeError(f"File too small: {path}")
        log.info("Media download completed (%.2f MB)", path.stat().st_size / 1024 / 1024)
        return (path, info) if include_info else path
    except Exception as e:
        log.error("Media download failed for %s (%s)", _source_summary(url), type(e).__name__)
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


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
    if "configure yt_api_key" in detail or "needs an api key" in detail:
        return "The backup audio provider isn’t configured. Ask the bot owner to set its download API key, or try another link."
    if "no results" in detail or "no matching" in detail:
        return "No playable result was found. Try a different title or link."
    if "unsupported url" in detail or "unsupported site" in detail:
        return "That link format isn’t supported. Try a direct video link or search by title."
    if any(term in detail for term in ("private video", "video unavailable", "members-only", "age-restricted", "sign in to confirm")):
        return "This video may be private, age-restricted, or unavailable to the bot. Try another link."
    if any(term in detail for term in ("http error 403", "http error 429", "too many requests", "rate limit")):
        return "The media source is temporarily limiting downloads. Please wait a little and try again."
    return "The download couldn’t be completed. Check the link and try again in a moment."


def _duration_label(value) -> str:
    try:
        seconds = max(0, int(float(value)))
    except (TypeError, ValueError, OverflowError):
        return "Unknown"
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def _media_title(info: dict, path: Path, limit: int = 80) -> str:
    raw = str(info.get("track") or info.get("title") or path.stem).strip()
    return raw.replace("\x00", "")[:limit] or "Media download"


def _cleanup_download(path: Optional[Path]) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
        shutil.rmtree(path.parent, ignore_errors=True)
    except OSError as error:
        log.warning("Could not clean temporary media %s (%s)", path.name, type(error).__name__)


def _upload_progress_callback(status_msg, title):
    if status_msg is None:
        return None

    async def update(text):
        await rich_edit(status_msg, text, navigation=False)

    return transfer_progress_callback(update, title, interval=2.0)


def _blocked_request(query: str, words) -> bool:
    """Match configured blocked terms as words/phrases, not accidental substrings."""
    for item in words:
        term = str(item or "").strip()
        if not term:
            continue
        parts = re.findall(r"[\w]+", term)
        if not parts:
            continue
        pattern = r"(?<!\w)" + r"\s+".join(map(re.escape, parts)) + r"(?!\w)"
        if re.search(pattern, query, re.IGNORECASE):
            return True
    return False


# ── /song — download audio ────────────────────────────────────────────────────

@bot.on_message(filters.command('song', prefixes=config.COMMAND_PREFIX_LIST) & (filters.group | filters.private) & group_allowed & user_allowed)
async def song_cmd(_, m: Message):
    query = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    reply = m.reply_to_message
    if not query and reply:
        query = str(getattr(reply, "text", None) or getattr(reply, "caption", None) or "").strip()
    if not query:
        body = section(
            "🎵 Audio downloader",
            rich_note(
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
            ),
            level=2,
        )
        body += "<p>" + rich_button("Play in voice chat", callback_data="help_play") + " " + rich_button("Download video", callback_data="dl:video") + "</p>"
        return await rich_send(bot, m.chat.id, body)

    # Check banned words professionally
    blocked = getattr(config, "BLOCKED_WORDS", []) or ["porn", "xxx", "xnxx", "sex"]
    if _blocked_request(query, blocked):
        return await rich_send(
            bot, m.chat.id,
            section("⚠️ Request not allowed", rich_note("This search request isn’t permitted. Try a different title or link."), level=3),
        )

    status = await rich_send(
        bot, m.chat.id,
        section("🎵 Preparing your audio", rich_note("Finding the track and preparing a high-quality audio file…"), level=3),
        navigation=False,
    )

    path = None
    try:
        start = time.time()
        path, info = await _download_media(query, audio_only=True, status_msg=status, include_info=True)
        elapsed = time.time() - start
        title = _media_title(info, path)
        duration_seconds = info.get("duration")
        duration = _duration_label(duration_seconds)
        artist = str(info.get("artist") or info.get("album_artist") or info.get("creator") or "").strip()[:64]

        size_mb = path.stat().st_size / 1024 / 1024
        if size_mb > 50:
            await rich_edit(
                status,
                section(
                    "⚠️ Audio file is too large",
                    rich_note(
                        f"This file is {size_mb:.1f} MB; Telegram bots can send up to 50 MB. "
                        "Try a shorter track."
                    ),
                    level=3,
                ),
            )
            _cleanup_download(path)
            return

        # Build caption with rich metadata
        fields = [
            ("Title", rich_esc(title[:60])),
            ("Duration", f"<code>{rich_esc(duration)}</code>"),
        ]
        if artist:
            fields.append(("Artist", rich_esc(artist)))
        fields.extend([
            ("File size", f"<code>{size_mb:.2f} MB</code>"),
            ("Ready in", f"<code>{elapsed:.1f} seconds</code>"),
            ("Requested by", f"<a href=\"tg://user?id={m.from_user.id}\">{rich_esc(m.from_user.first_name or 'User')}</a>" if m.from_user else "User"),
        ])
        cap = section(
            pe("music", "🎵") + " " + rich_esc(title[:60]),
            rich_kv_table(fields, headers=["Audio download", ""])
            + rich_note("MP3 · 192 kbps"),
            level=2,
        )

        # Send audio with professional metadata
        try:
            audio_duration = max(0, int(float(duration_seconds))) if duration_seconds is not None else None
        except (TypeError, ValueError, OverflowError):
            audio_duration = None
        audio_options = {
            "chat_id": m.chat.id,
            "audio": str(path),
            "caption": cap,
            "parse_mode": ParseMode.HTML,
            "title": title[:60],
            "duration": audio_duration,
            "reply_to_message_id": m.id,
        }
        if artist:
            audio_options["performer"] = artist
        if status is not None:
            await rich_edit(
                status,
                section("Uploading audio", rich_note("Sending the prepared file to Telegram…"), level=3),
                navigation=False,
            )
            audio_options["progress"] = _upload_progress_callback(status, "Uploading audio")
        try:
            try:
                await visual_call(bot.send_audio, **audio_options)
            except BadRequest as error:
                # Telegram definitively rejected the audio payload; a document
                # fallback is safe here. Never retry after an ambiguous timeout.
                log.warning("Telegram rejected audio metadata for %s (%s); trying document", title[:80], type(error).__name__)
                fallback_caption = rich_esc(title[:60]) + (f" · {rich_esc(artist)}" if artist else "")
                await bot.send_document(
                    m.chat.id, document=str(path), caption=fallback_caption,
                    reply_to_message_id=m.id, progress=audio_options.get("progress"),
                )
            try:
                await status.delete()
            except Exception:
                pass
            log.info(f"/song by {m.from_user.id if m.from_user else 0} in {m.chat.id}: {title} ({size_mb:.2f} MB, {elapsed:.1f}s)")
        except Exception as e:
            log.error("send_audio failed (%s)", type(e).__name__)
            raise
        finally:
            # Cleanup
            _cleanup_download(path)

    except ValueError as e:
        log.info("/song had no playable result for query length %d (%s)", len(query), type(e).__name__)
        await rich_edit(
            status,
            section("🔎 No playable result found", rich_note("Try another title or paste a direct audio/video link."), level=3),
        )
    except Exception as e:
        log.error("/song failed for query length %d (%s)", len(query), type(e).__name__)
        await rich_edit(
            status,
            section("⚠️ Download couldn’t be completed", rich_note(_friendly_download_error(e)), level=3),
        )
        _cleanup_download(path)


@bot.on_message(filters.command('vsong', prefixes=config.COMMAND_PREFIX_LIST) & (filters.group | filters.private) & group_allowed & user_allowed)
async def vsong_cmd(_, m: Message):
    query = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    reply = m.reply_to_message
    if not query and reply:
        query = str(getattr(reply, "text", None) or getattr(reply, "caption", None) or "").strip()
    if not query:
        body = section(
            "🎥 Video downloader",
            rich_note(
                "Send a video title or direct link to download an MP4 (up to 1080p). "
                "You can also reply to a message containing a title or link."
            )
            + rich_details("Example", "<code>/vsong nature documentary</code>"),
            level=2,
        )
        body += "<p>" + rich_button("Download audio", callback_data="dl:song") + "</p>"
        return await rich_send(bot, m.chat.id, body)

    blocked = getattr(config, "BLOCKED_WORDS", []) or ["porn", "xxx", "xnxx", "sex"]
    if _blocked_request(query, blocked):
        return await rich_send(bot, m.chat.id, section("⚠️ Request not allowed", rich_note("This search request isn’t permitted. Try another title or link."), level=3))

    status = await rich_send(
        bot, m.chat.id,
        section("🎥 Preparing your video", rich_note("Checking the source and preparing an MP4 download…"), level=3),
        navigation=False,
    )

    path = None
    try:
        start = time.time()
        path, info = await _download_media(query, audio_only=False, status_msg=status, include_info=True)
        elapsed = time.time() - start
        size_mb = path.stat().st_size / 1024 / 1024
        if size_mb > 50:
            # Try compress or send as document with warning
            log.warning(f"Video too large: {size_mb:.1f} MB")
            await rich_edit(
                status,
                section(
                    "⚠️ Video file is too large",
                    rich_note(
                        f"This file is {size_mb:.1f} MB; Telegram bots can send up to 50 MB. "
                        "Try a shorter video."
                    ),
                    level=3,
                ),
            )
            _cleanup_download(path)
            return

        title = _media_title(info, path, limit=60)
        duration_seconds = info.get("duration")
        try:
            dimensions = (int(info.get("width") or 0), int(info.get("height") or 0))
            if min(dimensions) <= 0:
                dimensions = None
        except (TypeError, ValueError, OverflowError):
            dimensions = None
        video_fields = [("Duration", f"<code>{rich_esc(_duration_label(duration_seconds))}</code>")]
        if dimensions:
            video_fields.append(("Resolution", f"<code>{dimensions[0]} × {dimensions[1]}</code>"))
        video_fields.extend([
            ("File size", f"<code>{size_mb:.2f} MB</code>"),
            ("Ready in", f"<code>{elapsed:.1f} seconds</code>"),
        ])
        video_options = {
            "chat_id": m.chat.id,
            "video": str(path),
            "caption": section(
                f"🎥 {rich_esc(title)}",
                rich_kv_table(video_fields, headers=["Video download", ""]),
                level=2,
            ),
            "parse_mode": ParseMode.HTML,
            "reply_to_message_id": m.id,
            "supports_streaming": True,
        }
        if status is not None:
            await rich_edit(
                status,
                section("Uploading video", rich_note("Sending the prepared file to Telegram…"), level=3),
                navigation=False,
            )
            video_options["progress"] = _upload_progress_callback(status, "Uploading video")
        try:
            video_duration = max(0, int(float(duration_seconds))) if duration_seconds is not None else None
        except (TypeError, ValueError, OverflowError):
            video_duration = None
        if video_duration is not None:
            video_options["duration"] = video_duration
        if dimensions:
            video_options["width"], video_options["height"] = dimensions
        await visual_call(bot.send_video, **video_options)
        try:
            await status.delete()
        except Exception:
            pass
        _cleanup_download(path)
        log.info(f"/vsong {m.from_user.id if m.from_user else 0} → {title} {size_mb:.2f} MB")
    except Exception as e:
        log.error("/vsong failed (%s)", type(e).__name__)
        await rich_edit(
            status,
            section("⚠️ Video download couldn’t be completed", rich_note(_friendly_download_error(e)), level=3),
        )
        _cleanup_download(path)


@bot.on_message(filters.command('download', prefixes=config.COMMAND_PREFIX_LIST) & (filters.group | filters.private) & group_allowed & user_allowed)
async def download_cmd(_, m: Message):
    query = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not query:
        body = section(
            "⬇️ Media downloader",
            rich_note(
                "Send a title or link and I’ll prepare audio or video automatically. "
                "Use <code>/song</code> or <code>/vsong</code> to choose a format yourself."
            )
            + rich_details(
                "Supported sources",
                "YouTube, TikTok, Instagram, SoundCloud, X, Facebook, and many more.",
            ),
            level=2,
        )
        body += "<p>" + rich_button("Audio help", callback_data="dl:song") + " " + rich_button("Video help", callback_data="dl:video") + "</p>"
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
    callback_data = str(getattr(q, "data", "") or "")
    if callback_data not in {"dl:song", "dl:video"}:
        await q.answer("This download help action is no longer available.", show_alert=False)
        return
    data = callback_data.partition(":")[2]
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
