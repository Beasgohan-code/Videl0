"""Telegram profile photos, fetched by the backend and cached for the table.

A browser never sees a Telegram file URL and never sees the bot token: the
panel asks for a player id, this module resolves the photo that Telegram
published to the bot, and the bytes are served from our own proxy.

Two sources, in order:

1. ``photo_url`` from the signed Mini App payload — a direct CDN link, already
   proven to belong to this Telegram account.
2. ``getUserProfilePhotos`` through the Bot API, for players whose photo was
   not present in the payload (the Login Widget omits it, for example).

Only a small, image-typed response is accepted, and a miss is cached too so a
player without a photo does not cost a Telegram round-trip on every poll.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

import config

MAX_BYTES = 400 * 1024
TTL = 12 * 3600
MISS_TTL = 1800
IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
HOSTS = {"t.me", "telegram.me", "telegram.org"}


class AvatarError(ValueError):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def _now():
    return datetime.now(timezone.utc)


def _db():
    from videl.utils.db import get_db
    return get_db()


def _allowed(url):
    try:
        parsed = urlparse(str(url or ""))
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return False
    return (host in HOSTS
            or host.endswith(".telegram.org")
            or host.endswith(".telegram-cdn.org")
            or host.endswith(".cdn-telegram.org"))


def _download(url):
    try:
        with requests.get(url, stream=True, timeout=(4, 10)) as upstream:
            if upstream.status_code != 200:
                raise AvatarError("Telegram did not return that photo", 502)
            mime = (upstream.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip().lower()
            if mime not in IMAGE_TYPES:
                mime = "image/jpeg"
            chunks, size = [], 0
            for chunk in upstream.iter_content(16384):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise AvatarError("That profile photo is too large", 413)
                chunks.append(chunk)
    except AvatarError:
        raise
    except Exception:
        raise AvatarError("Telegram profile photo could not be loaded", 502) from None
    if not chunks:
        raise AvatarError("Telegram returned an empty profile photo", 502)
    return mime, b"".join(chunks)


def _from_bot(api, user_id):
    """Ask the Bot API for the newest profile photo."""
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token or api is None:
        raise AvatarError("Telegram profile photos are not configured", 503)
    status, body = api("getUserProfilePhotos", {"user_id": int(user_id), "limit": 1})
    result = body.get("result") if isinstance(body, dict) and body.get("ok") else None
    photos = (result or {}).get("photos") if isinstance(result, dict) else None
    if not photos or not isinstance(photos[0], list) or not photos[0]:
        raise AvatarError("That player has no Telegram photo", 404)
    sizes = photos[0]
    file_id = max(sizes, key=lambda row: int((row or {}).get("width") or 0)).get("file_id")
    if not file_id:
        raise AvatarError("That player has no Telegram photo", 404)
    status, body = api("getFile", {"file_id": file_id})
    result = body.get("result") if isinstance(body, dict) and body.get("ok") else None
    path = str((result or {}).get("file_path") or "")
    if not path.startswith(("photos/", "profile_photos/")):
        raise AvatarError("Telegram did not return a downloadable photo", 502)
    return _download(f"https://api.telegram.org/file/bot{token}/{path}")


def _cached(doc):
    database = _db()
    if database is None:
        return None
    row = database["player_avatars"].find_one({"_id": int(doc["_id"])})
    if not row or not isinstance(row.get("at"), datetime):
        return None
    stamp = row["at"] if row["at"].tzinfo else row["at"].replace(tzinfo=timezone.utc)
    age = (_now() - stamp).total_seconds()
    limit = MISS_TTL if row.get("missing") else TTL
    if age > limit:
        return None
    if row.get("missing"):
        raise AvatarError("That player has no Telegram photo", 404)
    return row.get("mime") or "image/jpeg", base64.b64decode(row.get("data") or "")


def _remember(doc, mime=None, payload=None):
    database = _db()
    if database is None:
        return
    row = {"_id": int(doc["_id"]), "at": _now(),
           "missing": payload is None, "mime": mime,
           "data": base64.b64encode(payload).decode() if payload else None}
    try:
        database["player_avatars"].replace_one({"_id": row["_id"]}, row, upsert=True)
    except Exception:
        pass


def fetch(doc, api=None):
    """Return ``(mime, bytes)`` for one player's Telegram photo."""
    hit = _cached(doc)
    if hit is not None:
        return hit
    url = doc.get("photo_url")
    try:
        if url and _allowed(url):
            mime, payload = _download(url)
        else:
            mime, payload = _from_bot(api, doc["_id"])
    except AvatarError:
        _remember(doc)
        raise
    _remember(doc, mime, payload)
    return mime, payload


def clear(user_id):
    """Forget a cached photo (used when a player changes their picture)."""
    database = _db()
    if database is None:
        return
    database["player_avatars"].delete_one({"_id": int(user_id)})


__all__ = ["AvatarError", "fetch", "clear", "MAX_BYTES"]
