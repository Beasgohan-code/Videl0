# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio
import logging
import os
import re
from typing import Union
from urllib.parse import urlsplit

import aiofiles
import aiohttp
import yt_dlp
from py_yt import Playlist, VideosSearch
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from videl.utils.formatters import sec_to_iso

logger = logging.getLogger(__name__)

# Eldian Network's authenticated API is hosted by this Render service by default.
# Configure ELDIAN_API_URL to use a separate trusted Eldian deployment.
ELDIAN_API_URL = (os.environ.get("ELDIAN_API_URL") or f"http://127.0.0.1:{os.environ.get('PORT', '10000')}").strip().rstrip("/")
ELDIAN_API_KEY = (os.environ.get("ELDIAN_API_KEY") or os.environ.get("WEBAPP_SECRET") or "").strip()
# ShizuMusic-compatible external downloader (Shruti API contract). Optional; when
# configured it is attempted before the built-in/local providers.
YT_API_URL = (os.environ.get("YT_API_URL") or "").strip().rstrip("/")
YT_API_KEY = (os.environ.get("YT_API_KEY") or "").strip()
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "downloads").strip() or "downloads"

# Cookies — YTDLP_COOKIES path or YTDLP_COOKIES_URL (auto-downloaded & saved)
_COOKIES_FILE = os.environ.get("YTDLP_COOKIES") or os.environ.get("YT_COOKIES_FILE") or os.environ.get("COOKIES_PATH") or ""
_COOKIES_URL  = (os.environ.get("YTDLP_COOKIES_URL") or "").strip()

# Optional proxy configuration for yt-dlp fallback.
_PROXY_URL  = (os.environ.get("PROXY_URL") or os.environ.get("YOUTUBE_PROXY") or "").strip()
_PROXY_LIST = (os.environ.get("PROXY_LIST") or "").strip()
_AUTO_PROXY = (os.environ.get("AUTO_PROXY") or "1").strip().lower() in ("1", "true", "yes", "on")
_proxy_cache: list = []
_proxy_bad: set = set()

_file_cache: dict[str, str] = {}


# ═════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _extract_video_id(url: str) -> str:
    """Extract raw video ID from any YouTube URL format."""
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0]
    return url


def _cleanup(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _cookies_save_path() -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    env = os.environ.get("YTDLP_COOKIES") or os.environ.get("YT_COOKIES_FILE") or os.environ.get("COOKIES_PATH")
    if env:
        parent = os.path.dirname(env) or "."
        os.makedirs(parent, exist_ok=True)
        return env
    return os.path.join(DOWNLOAD_DIR, "cookies.txt")


def _is_real_cookies(raw: str) -> bool:
    markers = ("SID", "HSID", "SSID", "LOGIN_INFO", "__Secure-", "SAPISID", "APISID")
    return any(x in raw for x in markers)


def _save_cookies_bytes(data: bytes, dest: str | None = None) -> str | None:
    global _COOKIES_FILE
    if not data or len(data) < 80:
        return None
    dest = dest or _cookies_save_path()
    try:
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        if _is_real_cookies(data.decode("utf-8", errors="ignore")):
            _COOKIES_FILE = dest
            logger.info(f"[cookies] saved {len(data)} bytes → {dest}")
            return dest
    except Exception as e:
        logger.warning(f"[cookies] save failed: {e}")
    return None


def _cookies_path() -> str | None:
    global _COOKIES_FILE
    candidates = [_COOKIES_FILE, "cookies.txt", "/app/cookies.txt", os.path.join(DOWNLOAD_DIR, "cookies.txt"), _cookies_save_path()]
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                with open(path, encoding="utf-8", errors="ignore") as f:
                    raw = f.read()
                if _is_real_cookies(raw):
                    _COOKIES_FILE = path
                    return path
            except Exception:
                pass
    if _COOKIES_URL:
        try:
            import urllib.request
            request = urllib.request.Request(_COOKIES_URL, headers={"User-Agent": "Mozilla/5.0 VidelBot"})
            with urllib.request.urlopen(request, timeout=20) as response:
                return _save_cookies_bytes(response.read())
        except Exception as e:
            logger.warning(f"[cookies] URL fetch failed: {e}")
    return None


def _load_proxy_list() -> list:
    global _proxy_cache
    if _proxy_cache:
        return [p for p in _proxy_cache if p not in _proxy_bad]
    proxies = []
    if _PROXY_URL:
        proxies.append(_PROXY_URL)
    if _PROXY_LIST:
        for part in _PROXY_LIST.replace(";", ",").split(","):
            if part.strip(): proxies.append(part.strip())
    for fname in ("proxies.txt", os.path.join(DOWNLOAD_DIR, "proxies.txt"), "/app/proxies.txt"):
        if not os.path.isfile(fname): continue
        try:
            with open(fname, encoding="utf-8", errors="ignore") as f:
                proxies.extend(line.strip() for line in f if line.strip() and not line.lstrip().startswith("#"))
        except Exception:
            pass
    normalized=[]
    for proxy in proxies:
        if "://" not in proxy: proxy="http://"+proxy
        if proxy not in normalized: normalized.append(proxy)
    _proxy_cache=normalized
    return [p for p in normalized if p not in _proxy_bad]


def _mark_proxy_bad(proxy: str) -> None:
    _proxy_bad.add(proxy)


def _yt_url(link: str) -> str:
    video_id = _extract_video_id(link)
    if not video_id: return link
    if "youtube.com" in str(link) or "youtu.be" in str(link): return link
    return f"https://www.youtube.com/watch?v={video_id}"


def _find_file(video_id: str, video: bool | None = None) -> str | None:
    """Find a downloaded file, optionally constrained to audio or video media."""
    if not video_id or not os.path.isdir(DOWNLOAD_DIR): return None
    video_exts={".mp4",".webm",".mkv",".mov"}; audio_exts={".mp3",".m4a",".opus",".ogg",".wav",".aac",".flac"}
    try:
        for name in os.listdir(DOWNLOAD_DIR):
            if not (name.startswith(video_id+".") or name.startswith(video_id+"-")): continue
            ext=os.path.splitext(name)[1].lower()
            if video is True and ext not in video_exts: continue
            if video is False and ext not in audio_exts: continue
            path=os.path.join(DOWNLOAD_DIR,name)
            if os.path.isfile(path) and os.path.getsize(path)>1024: return path
    except Exception: pass
    return None


def _sync_ytdlp(url: str, video: bool = False) -> str | None:
    """yt-dlp local fallback with bounded proxy and cookie attempts."""
    video_id=_extract_video_id(url)
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}",video_id or ""): return None
    os.makedirs(DOWNLOAD_DIR,exist_ok=True)
    found=_find_file(video_id,video=video)
    if found:return found
    watch=_yt_url(url); cookiefile=_cookies_path(); outtmpl=os.path.join(DOWNLOAD_DIR,f"{video_id}.%(ext)s")
    fmt="best[height<=720]/best" if video else "bestaudio[ext=m4a]/bestaudio/best"
    base={"format":fmt,"outtmpl":outtmpl,"noplaylist":True,"quiet":True,"no_warnings":True,"noprogress":True,"geo_bypass":True,"nocheckcertificate":True,"retries":2,"fragment_retries":2,"socket_timeout":20}
    if cookiefile:base["cookiefile"]=cookiefile
    proxies=_load_proxy_list()[:3]
    last_error=None
    for proxy in [None,*proxies]:
        options={**base}
        if proxy:options["proxy"]=proxy
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info=ydl.extract_info(watch,download=True)
                if info:
                    result=ydl.prepare_filename(info)
                    if os.path.isfile(result) and os.path.getsize(result)>1024:return result
                    stem=os.path.splitext(result)[0]
                    for ext in ((".mp4",".webm",".mkv") if video else (".m4a",".mp3",".opus",".webm")):
                        if os.path.isfile(stem+ext) and os.path.getsize(stem+ext)>1024:return stem+ext
            found=_find_file(video_id,video=video)
            if found:return found
        except Exception as exc:
            last_error=exc; logger.warning("[yt-dlp] %s",exc)
            if proxy and any(word in str(exc).lower() for word in ("proxy","tunnel","timed out","connection","refused")):
                _mark_proxy_bad(proxy)
    if last_error:logger.error("[yt-dlp] final error: %s",last_error)
    return None


async def download_song(link: str) -> str | None:
    """Download audio through Eldian first, then the local yt-dlp fallback."""
    video_id=_extract_video_id(link)
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}",video_id or ""):return None
    os.makedirs(DOWNLOAD_DIR,exist_ok=True)
    cached=_find_file(video_id,video=False)
    if cached:return cached
    path=await _download_via_external_api(video_id,video=False)
    if path:return path
    path=await _download_via_eldian(video_id,video=False)
    if path:return path
    try:
        from pathlib import Path
        from vendor.eldian_music_api.app.youtube import download_audio
        local_dir=Path(DOWNLOAD_DIR)/"eldian"
        path=await asyncio.to_thread(download_audio,video_id,local_dir)
        if path and Path(path).is_file() and Path(path).stat().st_size>1024:return str(path)
    except Exception as exc:
        logger.warning("[eldian-local] download failed: %s",exc)
    return await asyncio.get_running_loop().run_in_executor(None,lambda:_sync_ytdlp(link,video=False))


async def download_video(link: str) -> str | None:
    """Download video through Eldian's built-in endpoint, then yt-dlp."""
    video_id=_extract_video_id(link)
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}",video_id or ""):return None
    os.makedirs(DOWNLOAD_DIR,exist_ok=True)
    cached=_find_file(video_id,video=True)
    if cached:return cached
    path=await _download_via_external_api(video_id,video=True)
    if path:return path
    path=await _download_via_eldian(video_id,video=True)
    if path:return path
    return await asyncio.get_running_loop().run_in_executor(None,lambda:_sync_ytdlp(link,video=True))


async def _download_via_external_api(video_id: str, video: bool = False) -> str | None:
    """Download a direct media response from the ShizuMusic-compatible API.

    Contract: GET {YT_API_URL}/download?url=VIDEO_ID&type=audio|video&api_key=KEY.
    The API must be explicitly configured; credentials are never sent to HTTP or
    redirected hosts. Failures are non-fatal so the existing providers still run.
    """
    if not YT_API_URL or not YT_API_KEY or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or ""):
        return None
    try:
        parsed = urlsplit(YT_API_URL)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            logger.warning("[external-downloader] URL must be a clean HTTPS base URL")
            return None
    except ValueError:
        logger.warning("[external-downloader] invalid configured URL")
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    ext = ".mp4" if video else ".mp3"
    target = os.path.join(DOWNLOAD_DIR, f"{video_id}.external{ext}")
    partial = target + ".part"
    timeout = aiohttp.ClientTimeout(total=300, connect=20)
    params = {"url": video_id, "type": "video" if video else "audio", "api_key": YT_API_KEY}
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{YT_API_URL}/download", params=params, allow_redirects=False) as response:
                if response.status != 200:
                    logger.warning("[external-downloader] HTTP %s", response.status)
                    return None
                content_type = (response.headers.get("Content-Type") or "").lower()
                if "json" in content_type or "text/" in content_type:
                    logger.warning("[external-downloader] API returned non-media content (%s)", content_type)
                    return None
                declared = response.content_length
                max_bytes = 300 * 1024 * 1024
                if declared is not None and declared > max_bytes:
                    logger.warning("[external-downloader] response exceeds size limit")
                    return None
                size = 0
                async with aiofiles.open(partial, "wb") as output:
                    async for chunk in response.content.iter_chunked(131072):
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError("response exceeds size limit")
                        await output.write(chunk)
        if size <= 1024:
            _cleanup(partial)
            return None
        os.replace(partial, target)
        logger.info("[external-downloader] downloaded %s KB", size // 1024)
        return target
    except Exception as exc:
        logger.warning("[external-downloader] request failed (%s)", type(exc).__name__)
        _cleanup(partial)
        return None


async def _download_via_eldian(video_id: str, video: bool = False) -> str | None:
    """Use Eldian's authenticated audio API or the local API's video route."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}",video_id or "") or not ELDIAN_API_KEY:return None
    os.makedirs(DOWNLOAD_DIR,exist_ok=True)
    target=os.path.join(DOWNLOAD_DIR,f"{video_id}.eldian")
    partial=target+".part"
    timeout=aiohttp.ClientTimeout(total=300,connect=20)
    headers={"X-API-Key":ELDIAN_API_KEY}
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            if video:
                async with session.get(f"{ELDIAN_API_URL}/api/download",params={"video_id":video_id},headers=headers,allow_redirects=False) as response:
                    return await _save_eldian_response(response,partial,target,video=True)
            headers["Content-Type"]="application/json"
            async with session.post(f"{ELDIAN_API_URL}/v1/track/by-video-id",headers=headers,json={"video_id":video_id},allow_redirects=False) as response:
                return await _save_eldian_response(response,partial,target,video=False)
    except Exception as exc:
        logger.warning("[eldian-api] request failed: %s",exc)
        _cleanup(partial)
        return None


async def _save_eldian_response(response, partial: str, target: str, *, video: bool) -> str | None:
    if response.status!=200:
        detail=(await response.text())[:200]
        logger.warning("[eldian-api] HTTP %s: %s",response.status,detail)
        return None
    content_type=(response.headers.get("Content-Type") or "").lower()
    if "json" in content_type or "text/" in content_type:
        logger.warning("[eldian-api] unexpected response type: %s",content_type)
        return None
    if video: ext=".mp4"
    elif "mpeg" in content_type: ext=".mp3"
    elif "ogg" in content_type: ext=".ogg"
    elif "aac" in content_type: ext=".aac"
    else: ext=".m4a"
    out=target+ext
    try:
        async with aiofiles.open(partial,"wb") as file:
            async for chunk in response.content.iter_chunked(131072):await file.write(chunk)
        if os.path.getsize(partial)<=1024:
            _cleanup(partial);return None
        os.replace(partial,out)
        logger.info("[eldian-api] downloaded %s KB",os.path.getsize(out)//1024)
        return out
    except Exception:
        _cleanup(partial)
        raise


async def resolve_stream(url: str, video: bool = False) -> str:
    """Resolve audio/video via Eldian first, with local yt-dlp fallback."""
    if url and os.path.isfile(url):return url
    if url in _file_cache and os.path.isfile(_file_cache[url]):return _file_cache[url]
    video_id=_extract_video_id(url)
    cached=_find_file(video_id,video=video)
    if cached:
        _file_cache[url]=cached;return cached
    path=await (download_video(url) if video else download_song(url))
    if path and os.path.isfile(path):
        _file_cache[url]=path;return path
    raise RuntimeError("Eldian API and yt-dlp could not resolve this media item")


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC — YOUTUBE SEARCH / METADATA
# ═════════════════════════════════════════════════════════════════════════════

async def search_yt(query: str):
    """Search YouTube for a video or playlist. Returns metadata tuple or playlist dict."""

    # ── Playlist ──────────────────────────────────────────────────────────────
    if "playlist?list=" in query or "&list=" in query:
        pl   = await Playlist.get(query)
        vids = pl.get("videos") or []
        if not vids:
            raise Exception("ᴩʟᴀʏʟɪsᴛ ɪs ᴇᴍᴩᴛʏ")

        items = []
        for v in vids:
            raw = v.get("duration", {})
            if isinstance(raw, dict):
                try:
                    secs = int(raw.get("secondsText", 0))
                except Exception:
                    secs = 0
            else:
                try:
                    secs = int(raw)
                except Exception:
                    secs = 0

            thumbs = v.get("thumbnails") or []
            thumb  = thumbs[0].get("url", "").split("?")[0] if thumbs else ""
            items.append({
                "link":      f"https://www.youtube.com/watch?v={v['id']}",
                "title":     v.get("title", "Unknown"),
                "duration":  sec_to_iso(secs),
                "thumbnail": thumb,
            })
        return {"playlist": items}

    # ── Single video search (first result — backward compatible) ──────────────
    items = await search_yt_multi(query, limit=1)
    if not items:
        raise Exception("ɴᴏ ʀᴇsᴜʟᴛs ғᴏᴜɴᴅ")
    r = items[0]
    return (r["url"], r["title"], r["duration_iso"], r["thumbnail"])


async def search_yt_multi(query: str, limit: int = 5) -> list:
    """
    Search YouTube and return up to `limit` results.
    Each item: {url, title, duration, duration_iso, thumbnail, channel}
    """
    if "playlist?list=" in query or "&list=" in query:
        # keep playlist behaviour in search_yt
        return []

    search = VideosSearch(query, limit=min(max(limit, 1), 10))
    results = await search.next()
    lst = results.get("result", [])
    if not lst:
        return []

    out = []
    for r in lst:
        url = r.get("link") or f"https://www.youtube.com/watch?v={r['id']}"
        title = r.get("title", "Unknown")
        vid = r.get("id") or ""
        # Prefer stable ytimg CDN (avoids broken/expired search-result thumbs)
        thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""
        if not thumb:
            raw = (r.get("thumbnails") or [{}])[0].get("url", "")
            thumb = raw.split("?")[0] if raw else ""
        dur = r.get("duration") or "0:00"
        channel = ""
        try:
            channel = (r.get("channel") or {}).get("name", "") or r.get("channelName", "")
        except Exception:
            pass

        parts = [int(x) for x in dur.split(":") if x.isdigit() or x]
        try:
            parts = [int(x) for x in dur.split(":")]
            secs = (
                parts[0] * 3600 + parts[1] * 60 + parts[2]
                if len(parts) == 3
                else (parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0])
            )
        except Exception:
            secs = 0

        out.append({
            "url": url,
            "title": title,
            "duration": dur,
            "duration_iso": sec_to_iso(secs),
            "thumbnail": thumb,
            "channel": channel,
            "video_id": r.get("id", ""),
        })
    return out


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC — YouTubeAPI CLASS (full-featured, from Youtube5 style)
# ═════════════════════════════════════════════════════════════════════════════

class YouTubeAPI:
    def __init__(self):
        self.base     = "https://www.youtube.com/watch?v="
        self.regex    = r"(?:youtube\.com|youtu\.be)"
        self.status   = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg      = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_link(self, link: str, videoid) -> str:
        return (self.base + link) if videoid else link

    def _strip_extra(self, link: str) -> str:
        return link.split("&")[0] if "&" in link else link

    # ── Public methods ────────────────────────────────────────────────────────

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        link = self._strip_extra(self._build_link(link, videoid))
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title        = result["title"]
            duration_min = result["duration"]
            thumbnail    = result["thumbnails"][0]["url"].split("?")[0]
            vidid        = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        link = self._strip_extra(self._build_link(link, videoid))
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str:
        link = self._strip_extra(self._build_link(link, videoid))
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        link = self._strip_extra(self._build_link(link, videoid))
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        link = self._strip_extra(self._build_link(link, videoid))
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(
        self, link: str, limit: int, user_id, videoid: Union[bool, str] = None
    ) -> list:
        if videoid:
            link = self.listbase + link
        link = self._strip_extra(link)
        try:
            plist = await Playlist.get(link)
        except Exception:
            return []
        videos = plist.get("videos") or []
        ids = []
        for data in videos[:limit]:
            if not data:
                continue
            vid = data.get("id")
            if not vid:
                continue
            ids.append(vid)
        return ids

    async def track(self, link: str, videoid: Union[bool, str] = None):
        link = self._strip_extra(self._build_link(link, videoid))
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title        = result["title"]
            duration_min = result["duration"]
            vidid        = result["id"]
            yturl        = result["link"]
            thumbnail    = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title":        title,
            "link":         yturl,
            "vidid":        vidid,
            "duration_min": duration_min,
            "thumb":        thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        link = self._strip_extra(self._build_link(link, videoid))
        ytdl_opts = {"quiet": True}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for fmt in r["formats"]:
                try:
                    if "dash" not in str(fmt["format"]).lower():
                        formats_available.append(
                            {
                                "format":      fmt["format"],
                                "filesize":    fmt.get("filesize"),
                                "format_id":   fmt["format_id"],
                                "ext":         fmt["ext"],
                                "format_note": fmt["format_note"],
                                "yturl":       link,
                            }
                        )
                except Exception:
                    continue
        return formats_available, link

    async def slider(
        self, link: str, query_type: int, videoid: Union[bool, str] = None
    ):
        link = self._strip_extra(self._build_link(link, videoid))
        a      = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title        = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid        = result[query_type]["id"]
        thumbnail    = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video:     Union[bool, str] = None,
        videoid:   Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title:     Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        try:
            if video or songvideo:
                downloaded_file = await download_video(link)
            else:
                downloaded_file = await download_song(link)
            if downloaded_file:
                return downloaded_file, True
            return None, False
        except Exception:
            return None, False
