"""Verify what Telegram says about a person, and what the panel says about them.

Two different proofs live here:

* **Who you are** — a Mini App ``initData`` string or a Login Widget payload,
  both HMAC-signed with the bot token. Telegram's own algorithm, unchanged.
* **What the panel is allowed to ask for** — the Vercel frontend signs a short
  actor assertion with the shared secret, so the backend can attribute an
  action without trusting a bare user id in a header.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

MAX_AGE = 86400
CLOCK_SKEW = 60
ACTOR_TTL = 60


class AuthError(ValueError):
    """A proof that does not hold. Never carries the reason to the browser."""


def _hex(value, length=64):
    text = str(value or "")
    return len(text) == length and all(character in "0123456789abcdefABCDEF" for character in text)


def verify_init_data(init_data, bot_token, *, now=None):
    """Return the Telegram user from a Mini App launch, or raise ``AuthError``."""
    if not isinstance(init_data, str) or not init_data or len(init_data) > 8192:
        raise AuthError("Telegram authentication data is required")
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        raise AuthError("Invalid Telegram authentication data") from None
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise AuthError("Invalid Telegram authentication data")
    received = fields.pop("hash", "")
    if not _hex(received):
        raise AuthError("Invalid Telegram authentication data")
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    key = hmac.new(b"WebAppData", str(bot_token or "").encode(), "sha256").digest()
    expected = hmac.new(key, check.encode(), "sha256").hexdigest()
    if not hmac.compare_digest(received.lower(), expected):
        raise AuthError("Invalid Mini App signature")
    try:
        auth_date = int(fields.get("auth_date", "0"))
        user = json.loads(fields.get("user", "{}"))
    except (TypeError, ValueError):
        raise AuthError("Invalid Telegram authentication data") from None
    _fresh(auth_date, now)
    if not isinstance(user, dict) or not str(user.get("id", "")).isdigit():
        raise AuthError("Telegram did not include a user")
    return user


def verify_login_widget(payload, bot_token, *, now=None):
    """Return the Telegram user from a Login Widget callback."""
    if not isinstance(payload, dict) or len(payload) > 20:
        raise AuthError("Telegram authentication data is required")
    fields = {str(key): str(value) for key, value in payload.items()
              if key != "hash" and value is not None}
    received = str(payload.get("hash", ""))
    if not _hex(received):
        raise AuthError("Invalid Telegram authentication data")
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    key = hashlib.sha256(str(bot_token or "").encode()).digest()
    expected = hmac.new(key, check.encode(), "sha256").hexdigest()
    if not hmac.compare_digest(received.lower(), expected):
        raise AuthError("Invalid Login Widget signature")
    try:
        auth_date = int(fields.get("auth_date", "0"))
    except (TypeError, ValueError):
        raise AuthError("Invalid Telegram authentication data") from None
    _fresh(auth_date, now)
    if not str(payload.get("id", "")).isdigit():
        raise AuthError("Telegram did not include a user")
    return {key: payload.get(key) for key in ("id", "first_name", "last_name", "username", "photo_url")
            if payload.get(key) is not None}


def _fresh(auth_date, now=None):
    stamp = int(time.time()) if now is None else int(now)
    if not auth_date or auth_date > stamp + CLOCK_SKEW or stamp - auth_date > MAX_AGE:
        raise AuthError("Telegram authentication data is expired")


def public_user(user):
    """Only the fields the panel may keep. No phone number, no language code."""
    return {"id": int(user["id"]),
            "name": " ".join(part for part in (str(user.get("first_name") or "").strip(),
                                               str(user.get("last_name") or "").strip()) if part)[:64]
            or str(user.get("username") or "Player")[:64],
            "username": str(user.get("username") or "")[:32] or None,
            "photo_url": str(user.get("photo_url") or "")[:512] or None}


def sign_actor(actor, secret, *, expires=None, now=None):
    """The assertion the panel sends so the backend can name the actor."""
    stamp = int(time.time()) if now is None else int(now)
    expires = stamp + ACTOR_TTL if expires is None else int(expires)
    message = f"{int(actor)}|{expires}"
    digest = hmac.new(str(secret or "").encode(), message.encode(), "sha256").hexdigest()
    return {"actor": int(actor), "expires": expires, "signature": digest}


def verify_actor(actor, expires, signature, secret, *, now=None):
    try:
        actor, expires = int(actor), int(expires)
    except (TypeError, ValueError):
        raise AuthError("An actor is required") from None
    stamp = int(time.time()) if now is None else int(now)
    if expires < stamp - CLOCK_SKEW or expires > stamp + ACTOR_TTL + CLOCK_SKEW:
        raise AuthError("The actor assertion expired")
    expected = hmac.new(str(secret or "").encode(), f"{actor}|{expires}".encode(), "sha256").hexdigest()
    if not _hex(str(signature or "")) or not hmac.compare_digest(str(signature).lower(), expected):
        raise AuthError("The actor assertion is not valid")
    return actor
