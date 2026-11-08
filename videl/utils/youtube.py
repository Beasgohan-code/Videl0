# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio
import concurrent.futures
import logging
import os
import re
import threading
import time
from collections import Counter, OrderedDict
from typing import Union
from urllib.parse import urlsplit

import aiofiles
import aiohttp
import yt_dlp
from py_yt import Playlist, VideosSearch
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from videl.utils.formatters import sec_to_iso
from videl.utils.downloader_status import downloader_status

logger = logging.getLogger(__name__)


class MediaDownloadError(RuntimeError):
    """Expected, user-safe failure when every configured media provider fails."""


# Eldian Network's authenticated API is hosted by this Render service by default.
# Configure ELDIAN_API_URL to use a separate trusted Eldian deployment.
ELDIAN_API_URL = (os.environ.get("ELDIAN_API_URL") or f"http://127.0.0.1:{os.environ.get('PORT', '10000')}").strip().rstrip("/")
ELDIAN_API_KEY = (os.environ.get("ELDIAN_API_KEY") or "").strip()
# Optional external downloader (Shruti API contract); when
# configured it is attempted before the built-in/local providers.
YT_API_URL = (os.environ.get("YT_API_URL") or "https://api.shrutibots.in").strip().rstrip("/")
YT_API_KEY = (os.environ.get("YT_API_KEY") or "").strip()
YT_API_KEY_FALLBACK = (os.environ.get("YT_API_KEY_FALLBACK") or "").strip()
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "downloads").strip() or "downloads"
MAX_DOWNLOAD_BYTES = 300 * 1024 * 1024

# Cookie jars are optional deployment secrets; never fetch or discover them implicitly.

# Optional proxy configuration for yt-dlp fallback.
_PROXY_URL  = (os.environ.get("PROXY_URL") or os.environ.get("YOUTUBE_PROXY") or "").strip()
_PROXY_LIST = (os.environ.get("PROXY_LIST") or "").strip()
_AUTO_PROXY = (os.environ.get("AUTO_PROXY") or "1").strip().lower() in ("1", "true", "yes", "on")
_proxy_cache: list = []
_proxy_bad: set = set()

# Shared media cache policy. Active files are protected by leases held by the
# playback engine and response/copy consumers; cache cleanup never guesses from
# file age alone that a stream is no longer in use.
CACHE_MAX_BYTES = 1024 * 1024 * 1024
CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
CACHE_RECENT_GRACE_SECONDS = 300
FILE_CACHE_MAX_ENTRIES = 512
_CACHE_MEDIA_EXTENSIONS = {".aac", ".flac", ".m4a", ".mkv", ".mp3", ".mp4", ".mov", ".ogg", ".opus", ".wav", ".webm"}
_CACHE_GUARD = threading.RLock()
_file_cache: OrderedDict[str, str] = OrderedDict()
_cache_files: OrderedDict[str, dict] = OrderedDict()
_cache_by_video_id: dict[str, OrderedDict[str, None]] = {}
_active_cache_files: Counter[str] = Counter()
_cache_root: str | None = None
_cache_signature: tuple | None = None
_cache_total_bytes = 0
_download_flight_guard = threading.Lock()
_download_flights: dict[tuple[str, bool], concurrent.futures.Future] = {}


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


def _cookies_path() -> str | None:
    """Resolve only a validated, explicitly configured external cookie path."""
    from videl.utils.cookie_security import configured_cookie_path
    return configured_cookie_path()


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


def _cache_directories() -> tuple[str, str]:
    root = os.path.realpath(DOWNLOAD_DIR)
    return root, os.path.join(root, "eldian")


def _cache_directory_signature(root: str, eldian: str) -> tuple:
    signature = []
    for directory in (root, eldian):
        try:
            stat = os.stat(directory)
            signature.append((stat.st_mtime_ns, stat.st_ino))
        except OSError:
            signature.append(None)
    return tuple(signature)


def _video_id_from_cache_name(name: str) -> str | None:
    if len(name) < 13 or name[11] not in ".-":
        return None
    video_id = name[:11]
    return video_id if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) else None


def _cache_file_identity(path: str) -> tuple[str, str] | None:
    real_path = os.path.realpath(path)
    root, eldian = _cache_directories()
    if os.path.dirname(real_path) not in {root, eldian}:
        return None
    extension = os.path.splitext(real_path)[1].lower()
    video_id = _video_id_from_cache_name(os.path.basename(real_path))
    if extension not in _CACHE_MEDIA_EXTENSIONS or not video_id:
        return None
    return video_id, real_path


def _index_cache_file_locked(path: str, video_id: str, stat_result, *, accessed=None, accessed_wall=None) -> None:
    global _cache_total_bytes
    previous = _cache_files.pop(path, None)
    if previous:
        _cache_total_bytes -= previous["size"]
        previous_id = previous["video_id"]
        paths = _cache_by_video_id.get(previous_id)
        if paths:
            paths.pop(path, None)
            if not paths:
                _cache_by_video_id.pop(previous_id, None)
    size = int(stat_result.st_size)
    record = {
        "video_id": video_id,
        "size": size,
        "accessed": time.monotonic() if accessed is None else accessed,
        "accessed_wall": time.time() if accessed_wall is None else accessed_wall,
    }
    _cache_files[path] = record
    _cache_total_bytes += size
    paths = _cache_by_video_id.setdefault(video_id, OrderedDict())
    paths[path] = None
    _cache_files.move_to_end(path)
    paths.move_to_end(path)


def _scan_cache_index_locked(root: str, eldian: str) -> None:
    global _cache_root, _cache_signature, _cache_total_bytes
    old_files = _cache_files.copy() if _cache_root == root else {}
    candidates = []
    for directory in (root, eldian):
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    identity = _cache_file_identity(entry.path)
                    if identity is None:
                        continue
                    video_id, path = identity
                    try:
                        stat_result = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if stat_result.st_size <= 1024:
                        continue
                    previous = old_files.get(path)
                    if previous:
                        accessed = previous["accessed"]
                        accessed_wall = previous["accessed_wall"]
                    else:
                        age = max(0.0, time.time() - stat_result.st_mtime)
                        accessed = time.monotonic() - age
                        accessed_wall = stat_result.st_mtime
                    candidates.append((accessed, accessed_wall, path, video_id, stat_result))
        except OSError:
            continue

    _cache_files.clear()
    _cache_by_video_id.clear()
    _cache_total_bytes = 0
    for accessed, accessed_wall, path, video_id, stat_result in sorted(candidates):
        _index_cache_file_locked(
            path, video_id, stat_result, accessed=accessed,
            accessed_wall=accessed_wall,
        )
    _cache_root = root
    _cache_signature = _cache_directory_signature(root, eldian)
    for url, path in list(_file_cache.items()):
        if path not in _cache_files:
            _file_cache.pop(url, None)
    _enforce_cache_limits_locked()


def _ensure_cache_index_locked() -> None:
    root, eldian = _cache_directories()
    signature = _cache_directory_signature(root, eldian)
    if _cache_root != root or _cache_signature != signature:
        _scan_cache_index_locked(root, eldian)


def _remove_cache_entry_locked(path: str, *, delete_file: bool) -> bool:
    global _cache_total_bytes, _cache_signature
    if _active_cache_files.get(path):
        return False
    record = _cache_files.get(path)
    if record is None:
        return True
    if delete_file:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError as error:
            logger.warning("[download-cache] eviction failed (%s)", type(error).__name__)
            return False
    _cache_files.pop(path, None)
    _cache_total_bytes -= record["size"]
    paths = _cache_by_video_id.get(record["video_id"])
    if paths:
        paths.pop(path, None)
        if not paths:
            _cache_by_video_id.pop(record["video_id"], None)
    for url, cached_path in list(_file_cache.items()):
        if cached_path == path:
            _file_cache.pop(url, None)
    _cache_signature = _cache_directory_signature(*_cache_directories())
    return True


def _enforce_cache_limits_locked(
    protected: set[str] | None = None, released: set[str] | None = None,
) -> None:
    global _cache_signature
    protected = protected or set()
    released = released or set()
    now_mono, now_wall = time.monotonic(), time.time()
    for path, record in list(_cache_files.items()):
        expired = now_wall - record["accessed_wall"] > CACHE_MAX_AGE_SECONDS
        over_budget = _cache_total_bytes > CACHE_MAX_BYTES
        if not expired and not over_budget:
            break
        if path in protected or _active_cache_files.get(path):
            continue
        if path not in released and now_mono - record["accessed"] < CACHE_RECENT_GRACE_SECONDS:
            continue
        _remove_cache_entry_locked(path, delete_file=True)
    _cache_signature = _cache_directory_signature(*_cache_directories())


def _enforce_cache_limits() -> None:
    with _CACHE_GUARD:
        _ensure_cache_index_locked()
        _enforce_cache_limits_locked()


def _register_cache_file(path: str, video_id: str | None = None) -> str:
    global _cache_signature
    identity = _cache_file_identity(path)
    if identity is None:
        return path
    inferred_id, real_path = identity
    video_id = video_id if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) else inferred_id
    try:
        stat_result = os.stat(real_path)
    except OSError:
        return path
    if stat_result.st_size <= 1024:
        return path
    with _CACHE_GUARD:
        _ensure_cache_index_locked()
        _index_cache_file_locked(real_path, video_id, stat_result)
        _enforce_cache_limits_locked({real_path})
        _cache_signature = _cache_directory_signature(*_cache_directories())
    return real_path


def _remember_file_url(url: str, path: str) -> None:
    with _CACHE_GUARD:
        _file_cache[url] = path
        _file_cache.move_to_end(url)
        while len(_file_cache) > FILE_CACHE_MAX_ENTRIES:
            _file_cache.popitem(last=False)


def pin_cache_file(path: str) -> bool:
    """Hold a cache file against eviction while a stream/response uses it."""
    identity = _cache_file_identity(path)
    if identity is None:
        return False
    _video_id, real_path = identity
    with _CACHE_GUARD:
        _ensure_cache_index_locked()
        record = _cache_files.get(real_path)
        if record is None:
            return False
        _active_cache_files[real_path] += 1
        record["accessed"] = time.monotonic()
        record["accessed_wall"] = time.time()
        _cache_files.move_to_end(real_path)
        _cache_by_video_id[record["video_id"]].move_to_end(real_path)
        return True


def release_cache_file(path: str | None) -> None:
    if not path:
        return
    identity = _cache_file_identity(path)
    if identity is None:
        return
    _video_id, real_path = identity
    with _CACHE_GUARD:
        count = _active_cache_files.get(real_path, 0)
        if count <= 1:
            _active_cache_files.pop(real_path, None)
        else:
            _active_cache_files[real_path] = count - 1
        _ensure_cache_index_locked()
        _enforce_cache_limits_locked(released={real_path})


def _reset_download_cache() -> None:
    """Reset only in-memory cache metadata for isolated tests."""
    global _cache_root, _cache_signature, _cache_total_bytes
    with _CACHE_GUARD:
        _file_cache.clear()
        _cache_files.clear()
        _cache_by_video_id.clear()
        _active_cache_files.clear()
        _cache_root = None
        _cache_signature = None
        _cache_total_bytes = 0


def _find_file(video_id: str, video: bool | None = None, *, pin: bool = False) -> str | None:
    """Indexed lookup for a cached media file, optionally returning a lease."""
    global _cache_total_bytes
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or ""):
        return None
    video_exts = {".mp4", ".webm", ".mkv", ".mov"}
    audio_exts = {".mp3", ".m4a", ".opus", ".ogg", ".wav", ".aac", ".flac"}
    with _CACHE_GUARD:
        _ensure_cache_index_locked()
        _enforce_cache_limits_locked()
        paths = _cache_by_video_id.get(video_id)
        if not paths:
            return None
        for path in reversed(paths):
            extension = os.path.splitext(path)[1].lower()
            if video is True and extension not in video_exts:
                continue
            if video is False and extension not in audio_exts:
                continue
            try:
                stat_result = os.stat(path)
            except OSError:
                _remove_cache_entry_locked(path, delete_file=False)
                continue
            if stat_result.st_size <= 1024:
                _remove_cache_entry_locked(path, delete_file=False)
                continue
            record = _cache_files[path]
            if stat_result.st_size != record["size"]:
                _cache_total_bytes += stat_result.st_size - record["size"]
                record["size"] = stat_result.st_size
            record["accessed"] = time.monotonic()
            record["accessed_wall"] = time.time()
            _cache_files.move_to_end(path)
            paths.move_to_end(path)
            if pin:
                _active_cache_files[path] += 1
            return path
    return None


def _sync_ytdlp(url: str, video: bool = False) -> str | None:
    """yt-dlp local fallback with bounded proxy and cookie attempts."""
    video_id=_extract_video_id(url)
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}",video_id or ""): return None
    os.makedirs(DOWNLOAD_DIR,exist_ok=True)
    found=_find_file(video_id,video=video)
    if found:return found
    watch=_yt_url(url); cookiefile=_cookies_path(); outtmpl=os.path.join(DOWNLOAD_DIR,f"{video_id}.%(ext)s")
    if cookiefile:
        logger.info("[yt-dlp] validated YouTube cookies are available")
    else:
        logger.warning("[yt-dlp] no valid YouTube auth cookie file found; downloads may hit YouTube's sign-in challenge")
    fmt="best[height<=720]/best" if video else "bestaudio/best"
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
            last_error=exc
            logger.warning("[yt-dlp] extraction failed (%s)", type(exc).__name__)
            if proxy and any(word in str(exc).lower() for word in ("proxy","tunnel","timed out","connection","refused")):
                _mark_proxy_bad(proxy)
    if last_error:
        logger.error("[yt-dlp] final extraction failure (%s)", type(last_error).__name__)
    return None


async def _await_download_flight(flight: concurrent.futures.Future) -> str | None:
    """Await a shared result without leaving callbacks attached to a closed loop."""
    loop = asyncio.get_running_loop()
    waiter = loop.create_future()
    active = threading.Event()
    active.set()

    def transfer_result() -> None:
        if waiter.done():
            return
        try:
            result = flight.result()
        except BaseException as error:
            waiter.set_exception(error)
        else:
            waiter.set_result(result)

    def schedule_transfer(_completed) -> None:
        if not active.is_set() or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(transfer_result)
        except RuntimeError:
            # The waiting request can time out and close its loop while another
            # event loop is still completing the shared provider operation.
            return

    flight.add_done_callback(schedule_transfer)
    try:
        return await asyncio.shield(waiter)
    finally:
        active.clear()
        if not waiter.done():
            waiter.cancel()


async def _run_download_singleflight(video_id: str, video: bool, loader) -> str | None:
    """Share one same-ID operation across callers and event loops in this process."""
    key = (video_id, video)
    with _download_flight_guard:
        flight = _download_flights.get(key)
        leader = flight is None
        if leader:
            flight = concurrent.futures.Future()
            _download_flights[key] = flight

    if not leader:
        try:
            return await _await_download_flight(flight)
        except asyncio.CancelledError:
            # A caller's own cancellation must not affect the shared future.
            # If the producer was cancelled, elect/rejoin a fresh flight instead.
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise
            return await _run_download_singleflight(video_id, video, loader)

    try:
        result = await loader()
    except BaseException as error:
        with _download_flight_guard:
            if _download_flights.get(key) is flight:
                del _download_flights[key]
            flight.set_exception(error)
        raise
    else:
        with _download_flight_guard:
            if _download_flights.get(key) is flight:
                del _download_flights[key]
            flight.set_result(result)
        return result


async def _await_uncancellable_thread(awaitable):
    """Keep a shared flight alive until its non-cancellable worker has stopped."""
    operation = asyncio.ensure_future(awaitable)
    try:
        return await asyncio.shield(operation)
    except asyncio.CancelledError:
        while not operation.done():
            try:
                await asyncio.shield(operation)
            except asyncio.CancelledError:
                # A second cancellation must not release the flight while the
                # worker still writes to its deterministic shared output path.
                continue
            except BaseException:
                break
        raise


async def _download_song_impl(link: str, video_id: str) -> str | None:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    cached = _find_file(video_id, video=False)
    if cached:
        return cached
    path = await _download_via_external_api(video_id, video=False)
    if path:
        return path
    path = await _download_via_eldian(video_id, video=False)
    if path:
        return path
    try:
        from pathlib import Path
        from vendor.eldian_music_api.app.youtube import download_audio
        local_dir = Path(DOWNLOAD_DIR) / "eldian"
        path = await _await_uncancellable_thread(
            asyncio.to_thread(download_audio, video_id, local_dir)
        )
        if path and Path(path).is_file() and Path(path).stat().st_size > 1024:
            return str(path)
    except Exception as exc:
        logger.warning("[eldian-local] download failed: %s", exc)
    return await _await_uncancellable_thread(
        asyncio.get_running_loop().run_in_executor(
            None, lambda: _sync_ytdlp(link, video=False)
        )
    )


async def download_song(link: str) -> str | None:
    """Try providers with per-video single-flight across bot/API event loops."""
    video_id = _extract_video_id(link)
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or ""):
        return None
    path = await _run_download_singleflight(
        video_id, False, lambda: _download_song_impl(link, video_id)
    )
    return _register_cache_file(path, video_id) if path else None


async def _download_video_impl(link: str, video_id: str) -> str | None:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    cached = _find_file(video_id, video=True)
    if cached:
        return cached
    path = await _download_via_external_api(video_id, video=True)
    if path:
        return path
    path = await _download_via_eldian(video_id, video=True)
    if path:
        return path
    return await _await_uncancellable_thread(
        asyncio.get_running_loop().run_in_executor(
            None, lambda: _sync_ytdlp(link, video=True)
        )
    )


async def download_video(link: str) -> str | None:
    """Try providers with per-video single-flight across bot/API event loops."""
    video_id = _extract_video_id(link)
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or ""):
        return None
    path = await _run_download_singleflight(
        video_id, True, lambda: _download_video_impl(link, video_id)
    )
    return _register_cache_file(path, video_id) if path else None


def _shruti_quota_exhausted(status: int, body: str) -> bool:
    """Recognize common quota/rate-limit responses without logging response text."""
    if status == 429:
        return True
    text = str(body or "").casefold()
    quota_terms = ("quota", "rate limit", "too many requests", "daily limit", "limit exceeded", "limit reached")
    return status in {200, 400, 403} and any(term in text for term in quota_terms)


async def _download_via_external_api(video_id: str, video: bool = False) -> str | None:
    """Download a direct media response from the configured external API.

    Contract: GET {YT_API_URL}/download?url=VIDEO_ID&type=audio|video&api_key=KEY.
    The API must be explicitly configured; credentials are never sent to HTTP or
    redirected hosts. Failures are non-fatal so the existing providers still run.
    """
    keys = list(dict.fromkeys(key for key in (YT_API_KEY, YT_API_KEY_FALLBACK) if key))
    if not YT_API_URL or not keys or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or ""):
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
    params = {"url": video_id, "type": "video" if video else "audio"}
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for key_index, key in enumerate(keys):
                request_params = {**params, "api_key": key}
                try:
                    async with session.get(
                        f"{YT_API_URL}/download", params=request_params, allow_redirects=False
                    ) as response:
                        content_type = (response.headers.get("Content-Type") or "").lower()
                        if response.status != 200:
                            error_text = (await response.text())[:2000]
                            if _shruti_quota_exhausted(response.status, error_text) and key_index + 1 < len(keys):
                                logger.info("[external-downloader] key quota exhausted; trying configured fallback key")
                                _cleanup(partial)
                                continue
                            if response.status == 404:
                                logger.warning(
                                    "[external-downloader] Shruti returned HTTP 404; check that YT_API_URL is the base URL "
                                    "https://api.shrutibots.in (without /download) and that the provider route is available"
                                )
                            elif response.status in (401, 403):
                                logger.warning(
                                    "[external-downloader] Shruti rejected the request (HTTP %s); check that the primary API key is active",
                                    response.status,
                                )
                            else:
                                logger.warning("[external-downloader] HTTP %s", response.status)
                            return None
                        if "json" in content_type or "text/" in content_type:
                            error_text = (await response.text())[:2000]
                            if _shruti_quota_exhausted(response.status, error_text) and key_index + 1 < len(keys):
                                logger.info("[external-downloader] API quota exhausted; trying configured fallback key")
                                _cleanup(partial)
                                continue
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
                    _cleanup(partial)
                    logger.warning("[external-downloader] request failed (%s)", type(exc).__name__)
                    return None
        return None
    except BaseException:
        # asyncio cancellation bypasses `except Exception`; never leave a shared
        # provider partial behind when the caller abandons this download.
        _cleanup(partial)
        raise
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
        declared = getattr(response, "content_length", None)
        if declared is not None and declared > MAX_DOWNLOAD_BYTES:
            _cleanup(partial)
            return None
        size = 0
        async with aiofiles.open(partial,"wb") as file:
            async for chunk in response.content.iter_chunked(131072):
                size += len(chunk)
                if size > MAX_DOWNLOAD_BYTES:
                    raise ValueError("provider response exceeds configured size limit")
                await file.write(chunk)
        if size<=1024:
            _cleanup(partial);return None
        os.replace(partial,out)
        logger.info("[eldian-api] downloaded %s KB",os.path.getsize(out)//1024)
        return out
    except BaseException:
        # Cancellation is a BaseException in supported Python versions; clean
        # the partial before propagating it to the caller.
        _cleanup(partial)
        raise


async def resolve_stream(url: str, video: bool = False) -> str:
    """Resolve media and return a leased cache path; callers must release it."""
    if url and os.path.isfile(url):
        pin_cache_file(url)
        return url
    with _CACHE_GUARD:
        _ensure_cache_index_locked()
        _enforce_cache_limits_locked()
        cached = _file_cache.get(url)
        if cached and cached in _cache_files and os.path.isfile(cached):
            record = _cache_files[cached]
            record["accessed"] = time.monotonic()
            record["accessed_wall"] = time.time()
            _cache_files.move_to_end(cached)
            _cache_by_video_id[record["video_id"]].move_to_end(cached)
            _active_cache_files[cached] += 1
            _file_cache.move_to_end(url)
            return cached
        _file_cache.pop(url, None)

    video_id = _extract_video_id(url)
    cached = _find_file(video_id, video=video, pin=True)
    if cached:
        _remember_file_url(url, cached)
        return cached
    path = await (download_video(url) if video else download_song(url))
    if path and os.path.isfile(path):
        pin_cache_file(path)
        _remember_file_url(url, path)
        return path
    status = downloader_status()
    if status["shruti"]["state"] == "needs_api_key":
        raise MediaDownloadError(
            "Shruti needs an API key, and the backup download methods could not retrieve this track. "
            "Ask the bot owner to configure YT_API_KEY or try another track."
        )
    raise MediaDownloadError(
        "Shruti and the backup download methods could not retrieve this track. "
        "Try again later or choose another track."
    )


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


def _parse_search_duration(value: object) -> int:
    """Parse provider duration text, returning zero for unknown/malformed values."""
    if not isinstance(value, str) or not value or len(value) > 32:
        return 0
    parts = value.split(":")
    if not 1 <= len(parts) <= 3 or any(not re.fullmatch(r"[0-9]+", part) for part in parts):
        return 0
    try:
        numbers = [int(part) for part in parts]
    except (TypeError, ValueError):
        return 0
    if len(numbers) == 3:
        hours, minutes, seconds = numbers
        if minutes >= 60 or seconds >= 60:
            return 0
        return hours * 3600 + minutes * 60 + seconds
    if len(numbers) == 2:
        minutes, seconds = numbers
        if seconds >= 60:
            return 0
        return minutes * 60 + seconds
    return numbers[0]


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

        secs = _parse_search_duration(dur)

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
