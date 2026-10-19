# --------------------------------------------------------------------------------
#  Built-in download API (Eldian-compatible)
#  Inspired by https://github.com/Eldian-Network/eldian-music-api
#  Mounted on Videl's Flask server so the bot can call itself on localhost.
# --------------------------------------------------------------------------------

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from uuid import uuid4

import yt_dlp
from flask import Flask, Response, jsonify, request, send_file

logger = logging.getLogger(__name__)

_API_DIR = Path("downloads") / "api"
_API_KEY = (os.environ.get("ELDIAN_API_KEY") or os.environ.get("API_KEY") or "").strip()


def _extract_id(value: str) -> str | None:
    if not value:
        return None
    value = value.strip()
    if re.fullmatch(r"[\w-]{6,20}", value):
        return value
    m = re.search(r"(?:v=|/shorts/|youtu\.be/)([\w-]{6,20})", value)
    return m.group(1) if m else None


def _cookies_file() -> str | None:
    paths = []
    for key in ("YTDLP_COOKIES", "COOKIES_PATH", "YOUTUBE_COOKIES_FILE"):
        v = os.environ.get(key)
        if v:
            paths.append(v)
    paths.extend(["cookies.txt", "/app/cookies.txt", str(Path("downloads") / "cookies.txt")])

    def _is_real(path: str) -> bool:
        try:
            raw = Path(path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return False
        markers = ("SID", "HSID", "SSID", "LOGIN_INFO", "__Secure-", "SAPISID", "APISID")
        return any(m in raw for m in markers)

    for path in paths:
        if path and os.path.isfile(path) and os.path.getsize(path) > 80 and _is_real(path):
            return path

    url = (os.environ.get("YTDLP_COOKIES_URL") or "").strip()
    if not url:
        return None
    dest = Path("downloads") / "cookies.txt"
    try:
        if dest.is_file() and dest.stat().st_size > 80 and _is_real(str(dest)):
            return str(dest)
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": "VidelBot"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        if len(data) > 80:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return str(dest)
    except Exception as e:
        logger.warning(f"[api] cookies url: {e}")
    return None


def _ydl_download(video_id: str, video: bool = False) -> Path:
    """Sync yt-dlp download → local Path. Raises RuntimeError on failure."""
    _API_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = _API_DIR / uuid4().hex
    out_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(out_dir / f"{video_id}.%(ext)s")
    watch = f"https://www.youtube.com/watch?v={video_id}"

    fmt = (
        "best[height<=720]/best"
        if video
        else "bestaudio[ext=m4a]/bestaudio/best"
    )
    opts: dict = {
        "format": fmt,
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "retries": 3,
        "fragment_retries": 3,
        "extractor_args": {"youtube": {"player_client": ["android", "ios", "web"]}},
    }
    cookies = _cookies_file()
    if cookies:
        opts["cookiefile"] = cookies
    proxy = (os.environ.get("PROXY_URL") or os.environ.get("YOUTUBE_PROXY") or "").strip()
    if proxy:
        if "://" not in proxy:
            proxy = "http://" + proxy
        opts["proxy"] = proxy

    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(watch, download=True)
            if info is None:
                raise RuntimeError("no info")
            for candidate in sorted(out_dir.glob(f"{video_id}.*")):
                if candidate.is_file() and candidate.stat().st_size > 1024:
                    return candidate
            # prepare_filename fallback
            path = Path(ydl.prepare_filename(info))
            if path.is_file() and path.stat().st_size > 1024:
                return path
            raise RuntimeError("file missing after download")
        except Exception as e:
            last_err = e
            logger.warning(f"[api] yt-dlp attempt {attempt}: {e}")
            time.sleep(1)

    raise RuntimeError(str(last_err) if last_err else "download failed")


def _require_key_if_set() -> tuple[bool, str | None]:
    """If ELDIAN_API_KEY is configured, require X-API-Key header."""
    if not _API_KEY:
        return True, None
    got = (
        request.headers.get("X-API-Key")
        or request.args.get("api_key")
        or request.args.get("api")
        or ""
    ).strip()
    if got != _API_KEY:
        return False, "Invalid or missing API key"
    return True, None


def register_eldian_routes(app: Flask) -> None:
    """Attach Eldian-compatible routes to the existing Flask app."""

    @app.get("/api/status")
    def api_status():
        return jsonify(
            {
                "status": "ok",
                "service": "videl-built-in-eldian",
                "cookies": bool(_cookies_file()),
                "auth_required": bool(_API_KEY),
            }
        )

    @app.get("/api/stream_audio")
    def api_stream_audio():
        ok, err = _require_key_if_set()
        if not ok:
            return jsonify({"error": err}), 401

        raw = request.args.get("url") or request.args.get("video_id") or ""
        vid = _extract_id(raw)
        if not vid:
            return jsonify({"error": "url or video_id required"}), 422

        try:
            path = _ydl_download(vid, video=False)
            return send_file(
                path,
                mimetype="audio/mpeg",
                as_attachment=False,
                download_name=path.name,
            )
        except Exception as e:
            logger.error(f"[api] stream_audio: {e}")
            return jsonify({"error": str(e)[:300]}), 502

    @app.get("/api/download")
    def api_download():
        ok, err = _require_key_if_set()
        if not ok:
            return jsonify({"error": err}), 401

        raw = request.args.get("url") or request.args.get("video_id") or ""
        vid = _extract_id(raw)
        if not vid:
            return jsonify({"error": "url or video_id required"}), 422

        try:
            path = _ydl_download(vid, video=True)
            return send_file(
                path,
                mimetype="video/mp4",
                as_attachment=False,
                download_name=path.name,
            )
        except Exception as e:
            logger.error(f"[api] download: {e}")
            return jsonify({"error": str(e)[:300]}), 502

    @app.post("/v1/track/by-video-id")
    def api_v1_track():
        """Official Eldian-Network style endpoint."""
        ok, err = _require_key_if_set()
        if not ok:
            return jsonify({"detail": err}), 401

        data = request.get_json(silent=True) or {}
        vid = _extract_id(str(data.get("video_id") or data.get("url") or ""))
        if not vid:
            return jsonify({"detail": "video_id required"}), 422

        try:
            path = _ydl_download(vid, video=False)
            return send_file(
                path,
                mimetype="application/octet-stream",
                as_attachment=True,
                download_name=path.name,
            )
        except Exception as e:
            logger.error(f"[api] v1 track: {e}")
            return jsonify({"detail": str(e)[:300]}), 502

    logger.info(
        "[api] Eldian-compatible routes registered: "
        "/api/status /api/stream_audio /api/download /v1/track/by-video-id"
    )
