"""Authenticated Eldian-compatible media API on Videl's existing Render port.

Audio uses the MIT-licensed Eldian Network downloader, not a second bot process.
No endpoint accepts arbitrary hosts, cookie uploads, proxies or shell commands.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import mimetypes
import os
import re
import shutil
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from flask import Flask, jsonify, request, send_file
import yt_dlp

logger = logging.getLogger(__name__)
_API_DIR = Path("downloads") / "api"
_SLOTS = threading.BoundedSemaphore(2)
_ACTIVE: set[Path] = set()
_LOCK = threading.Lock()
_WINDOWS: OrderedDict = OrderedDict()
MAX_BYTES = 300 * 1024 * 1024


def _extract_id(value: str) -> str | None:
    value = str(value or "").strip()
    if len(value) > 2048:
        return None
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    try:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            return None
        host = (parsed.hostname or "").lower()
        if host == "youtu.be":
            candidate = parsed.path.strip("/").split("/")[0]
        elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
            candidate = parse_qs(parsed.query).get("v", [""])[0]
            if parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
                candidate = parsed.path.split("/")[2]
        else:
            return None
        return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None
    except (ValueError, IndexError):
        return None


def _require_key_if_set() -> tuple[bool, str | None]:
    # Fail closed even on loopback: reverse proxies can also use loopback addresses.
    key = (os.environ.get("ELDIAN_API_KEY") or os.environ.get("WEBAPP_SECRET") or "").strip()
    supplied = request.headers.get("X-API-Key", "")
    if not key:
        return False, "Media API credentials are not configured"
    return (True, None) if hmac.compare_digest(supplied, key) else (False, "Invalid or missing X-API-Key")


def _rate_allowed() -> bool:
    now = time.monotonic()
    # Bounded per-source accounting. The semaphore separately bounds total work.
    source = request.remote_addr or "unknown"
    with _LOCK:
        window = _WINDOWS.setdefault(source, deque())
        _WINDOWS.move_to_end(source)
        while window and now - window[0] >= 60:
            window.popleft()
        while len(_WINDOWS) > 2048:
            _WINDOWS.popitem(last=False)
        if len(window) >= 12:
            return False
        window.append(now)
        return True


def _cleanup_stale() -> None:
    _API_DIR.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        active = set(_ACTIVE)
    for directory in _API_DIR.iterdir():
        try:
            if directory.is_dir() and directory not in active and directory.stat().st_mtime < time.time() - 3600:
                shutil.rmtree(directory, ignore_errors=True)
        except FileNotFoundError:
            pass


def _download(video_id: str, video: bool, directory: Path) -> Path:
    if not video:
        from vendor.eldian_music_api.app.youtube import download_audio
        return download_audio(video_id, directory)
    options = {
        "format": "best[height<=720][ext=mp4]/best[height<=720]",
        "outtmpl": str(directory / f"{video_id}.%(ext)s"),
        "noplaylist": True, "quiet": True, "no_warnings": True,
        "socket_timeout": 20, "retries": 2, "fragment_retries": 2,
        "max_filesize": MAX_BYTES,
    }
    cookie = (os.getenv("YTDLP_COOKIES") or os.getenv("YT_COOKIES_FILE") or "").strip()
    if cookie and Path(cookie).is_file():
        options["cookiefile"] = cookie
    with yt_dlp.YoutubeDL(options) as client:
        info = client.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
        if not info:
            raise RuntimeError("No media returned")
        return Path(client.prepare_filename(info))


def register_eldian_routes(app: Flask) -> None:
    def internal_authorized() -> bool:
        expected = (os.environ.get("WEBAPP_SECRET") or "").strip()
        supplied = request.headers.get("X-Videl-Internal", "")
        return bool(expected) and hmac.compare_digest(supplied, expected)

    @app.get("/internal/music/search")
    def internal_music_search():
        if not internal_authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        query = str(request.args.get("q", "")).strip()
        if not query or len(query) > 120:
            return jsonify({"ok": False, "error": "Enter a search up to 120 characters"}), 400
        try:
            limit = max(1, min(8, int(request.args.get("limit", "8"))))
            from videl.utils.youtube import search_yt_multi
            tracks = asyncio.run(asyncio.wait_for(search_yt_multi(query, limit), timeout=20))
            safe_tracks = [
                {
                    "video_id": str(item.get("video_id", "")),
                    "title": str(item.get("title", ""))[:240],
                    "channel": str(item.get("channel", ""))[:120],
                    "duration": str(item.get("duration", ""))[:20],
                    "thumbnail": str(item.get("thumbnail", "")),
                }
                for item in tracks
                if re.fullmatch(r"[A-Za-z0-9_-]{11}", str(item.get("video_id", "")))
            ]
            return jsonify({"ok": True, "tracks": safe_tracks}), 200
        except Exception as exc:
            logger.warning("Music search failed (%s)", type(exc).__name__)
            return jsonify({"ok": False, "error": "Search is temporarily unavailable; try again shortly"}), 503

    @app.get("/internal/music/track/<video_id>")
    def internal_music_track(video_id: str):
        if not internal_authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or ""):
            return jsonify({"ok": False, "error": "Invalid track ID"}), 400
        try:
            from videl.utils.youtube import download_song
            path = asyncio.run(asyncio.wait_for(download_song(video_id), timeout=300))
            if not path or not Path(path).is_file():
                return jsonify({"ok": False, "error": "Track could not be prepared"}), 502
            response = send_file(
                path,
                mimetype=mimetypes.guess_type(path)[0] or "audio/mpeg",
                as_attachment=False,
                conditional=True,
                max_age=0,
            )
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        except Exception as exc:
            logger.warning("Music track preparation failed (%s)", type(exc).__name__)
            return jsonify({"ok": False, "error": "Track could not be prepared; check the downloader status"}), 502

    @app.get("/api/music")
    def music_contract():
        return jsonify({"service": "Videl music API", "version": 1,
            "authentication": "X-API-Key header (server-to-server only)",
            "audio": {"method": "POST", "path": "/v1/track/by-video-id", "json": {"video_id": "11-character YouTube video ID"}},
            "video": {"method": "GET", "path": "/api/download?video_id=VIDEO_ID"},
            "limits": {"concurrent_requests": 2, "requests_per_source_per_minute": 12, "maximum_file_bytes": MAX_BYTES},
            "upstream": "https://github.com/Eldian-Network/eldian-music-api"})

    @app.get("/api/status")
    def api_status():
        ok, error = _require_key_if_set()
        if not ok:
            return jsonify({"ok": False, "error": error}), 401
        return jsonify({"ok": True, "service": "videl-eldian", "auth_required": True})

    def serve(video: bool = False):
        ok, error = _require_key_if_set()
        if not ok:
            return jsonify({"detail": error}), 401
        data = request.get_json(silent=True) if request.method == "POST" else request.args
        if not data or not isinstance(data, dict) and request.method == "POST":
            return jsonify({"detail": "A JSON object with video_id is required"}), 422
        video_id = _extract_id(data.get("video_id") or data.get("url") or "")
        if not video_id:
            return jsonify({"detail": "Use an 11-character video ID or an HTTPS YouTube URL"}), 422
        if not _rate_allowed():
            return jsonify({"detail": "Media request limit reached"}), 429, {"Retry-After": "60"}
        if not _SLOTS.acquire(blocking=False):
            return jsonify({"detail": "Both media workers are busy; retry later"}), 503, {"Retry-After": "5"}
        directory = _API_DIR / uuid4().hex
        with _LOCK:
            _ACTIVE.add(directory)
        released = False

        def cleanup():
            nonlocal released
            if released:
                return
            released = True
            shutil.rmtree(directory, ignore_errors=True)
            with _LOCK:
                _ACTIVE.discard(directory)
            _SLOTS.release()

        try:
            _cleanup_stale()
            directory.mkdir(parents=True, exist_ok=True)
            path = _download(video_id, video, directory).resolve()
            if directory.resolve() not in path.parents or not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
                raise RuntimeError("Downloader did not return a bounded media file")
            response = send_file(path, mimetype=mimetypes.guess_type(path.name)[0] or "application/octet-stream", as_attachment=True, download_name=path.name, max_age=0)
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.direct_passthrough = False
            response.call_on_close(cleanup)
            return response
        except Exception as exc:
            # Downloader exceptions can contain proxy credentials or private paths.
            logger.warning("Media request failed (%s)", type(exc).__name__)
            cleanup()
            return jsonify({"detail": "Media download failed. Check server-side downloader credentials and availability."}), 502

    app.add_url_rule("/v1/track/by-video-id", "eldian_audio", lambda: serve(False), methods=["POST"])
    app.add_url_rule("/api/stream_audio", "eldian_stream", lambda: serve(False), methods=["GET"])
    app.add_url_rule("/api/download", "eldian_video", lambda: serve(True), methods=["GET"])
    logger.info("Authenticated Eldian media API mounted on the existing Render server")
