"""Premium (custom) emoji artwork, resolved server-side and cached.

Browsers can never see the bot token, so custom emoji images are streamed
through this owner-only proxy. Telegram's ``getCustomEmojiStickers`` gives a
sticker object, ``getFile`` gives a short-lived path, and the bytes are cached
so a chat full of premium emoji costs one Telegram round-trip per emoji.
"""
from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from urllib.parse import quote

import requests

import config

_EMOJI_ID = re.compile(r"^[0-9]{1,20}$")
_MEMORY_LIMIT = 192
_TTL_OK = 24 * 3600
_TTL_FAIL = 300
_MAX_BYTES = 512 * 1024
_ALLOWED_MIME = {"image/webp", "image/png", "image/jpeg", "image/gif", "application/x-tgsticker", "video/webm"}

_cache: "OrderedDict[str, tuple[float, bytes | None, str, str | None]]" = OrderedDict()
_lock = threading.Lock()


class EmojiError(ValueError):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _cached(key: str):
    with _lock:
        row = _cache.get(key)
        if row is None:
            return None
        expires, payload, mime, error = row
        if expires < time.time():
            _cache.pop(key, None)
            return None
        _cache.move_to_end(key)
        return payload, mime, error


def _remember(key: str, payload: bytes | None, mime: str, error: str | None):
    with _lock:
        _cache[key] = (time.time() + (_TTL_OK if payload else _TTL_FAIL), payload, mime, error)
        _cache.move_to_end(key)
        while len(_cache) > _MEMORY_LIMIT:
            _cache.popitem(last=False)


def _telegram_path(api, emoji_id: str) -> str:
    """Resolve a custom emoji id to a Telegram file path using the Bot API."""
    status, body = api("getCustomEmojiStickers", {"custom_emoji_ids": [emoji_id]})
    result = body.get("result") if isinstance(body, dict) and body.get("ok") else None
    if not isinstance(result, list) or not result or not isinstance(result[0], dict):
        description = body.get("description") if isinstance(body, dict) else ""
        raise EmojiError("This premium emoji is not available to the bot." + (f" {description}" if description else ""), 404)
    sticker = result[0]
    thumbnail = sticker.get("thumbnail") if isinstance(sticker.get("thumbnail"), dict) else None
    file_id = (thumbnail or {}).get("file_id") or sticker.get("file_id")
    if not file_id:
        raise EmojiError("Telegram did not return artwork for this premium emoji.", 502)
    status, body = api("getFile", {"file_id": file_id})
    result = body.get("result") if isinstance(body, dict) and body.get("ok") else None
    path = (result or {}).get("file_path") if isinstance(result, dict) else None
    if not path or not str(path).startswith("documents/"):
        raise EmojiError("Telegram did not return a downloadable emoji file.", 502)
    if str(path).lower().endswith((".webm", ".tgs")):
        # Animated stickers have no still image the browser can paint; the
        # fallback character is the correct rendering rather than a broken box.
        raise EmojiError("This animated premium emoji has no still artwork.", 404)
    return str(path)


def fetch_emoji(api, emoji_id: str) -> tuple[str, bytes]:
    """Return (mime, bytes) for one premium emoji id, using a bounded cache."""
    emoji_id = str(emoji_id or "").strip()
    if not _EMOJI_ID.fullmatch(emoji_id):
        raise EmojiError("A numeric premium emoji ID is required.", 400)
    hit = _cached(emoji_id)
    if hit is not None:
        payload, mime, error = hit
        if payload is None:
            raise EmojiError(error or "Premium emoji artwork is unavailable.", 404)
        return mime, payload
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token:
        raise EmojiError("The bot token is not configured on the backend.", 503)
    try:
        path = _telegram_path(api, emoji_id)
        with requests.get(f"https://api.telegram.org/file/bot{token}/{quote(path, safe='/')}", stream=True, timeout=(5, 15)) as upstream:
            if upstream.status_code != 200:
                raise EmojiError("Telegram emoji artwork is unavailable.", 502)
            mime = (upstream.headers.get("Content-Type") or "image/webp").split(";")[0].strip().lower()
            chunks = []
            size = 0
            for chunk in upstream.iter_content(32768):
                size += len(chunk)
                if size > _MAX_BYTES:
                    raise EmojiError("Premium emoji artwork is larger than the viewer limit.", 413)
                chunks.append(chunk)
        payload = b"".join(chunks)
        if not payload:
            raise EmojiError("Telegram returned an empty emoji image.", 502)
        if mime not in _ALLOWED_MIME:
            mime = "image/webp"
    except EmojiError as error:
        _remember(emoji_id, None, "image/webp", str(error))
        raise
    except Exception:
        _remember(emoji_id, None, "image/webp", "Premium emoji artwork could not be loaded.")
        raise EmojiError("Premium emoji artwork could not be loaded.", 502) from None
    _remember(emoji_id, payload, mime, None)
    return mime, payload


def clear_cache():
    with _lock:
        _cache.clear()
