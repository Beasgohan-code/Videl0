"""Explicitly confirmed Business profile edits through Aiogram's Bot API client.

Kurigram exposes Business Connections and business message routing, but not the
Bot API's Business profile setters. This small adapter uses Aiogram only for
those Bot API calls; it does not poll updates, start a user session, or manage
child-bot tokens.
"""
from __future__ import annotations

import re
import secrets
import time
from collections import OrderedDict, deque

import config
from videl.app.router import Command, CommandError, Screen
from videl.plugins.base import body, escape, heading, table

_PENDING: dict[str, dict] = {}
_APPLY_TIMES: dict[str, deque[float]] = {}
_PENDING_TTL = 300
_MAX_PENDING = 32
_MAX_CONNECTIONS = 64
_CONNECTION_ID = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_USERNAME = re.compile(r"^[A-Za-z0-9_]{5,32}$")
_FIELDS = {
    "name": ("can_edit_name", "set_business_account_name"),
    "bio": ("can_edit_bio", "set_business_account_bio"),
    "username": ("can_edit_username", "set_business_account_username"),
}
_CONNECTIONS: "OrderedDict[str, dict]" = OrderedDict()
_CONNECTION_TTL = 86400.0
_MAX_REMEMBERED_CONNECTIONS = 20


def remember_business_connection(connection) -> None:
    """Keep only the verified owner's active connection ID in process memory."""
    owner_id = int(getattr(getattr(connection, "user", None), "id", 0) or 0)
    connection_id = str(getattr(connection, "id", "") or "")
    if owner_id != int(config.OWNER_ID) or not _CONNECTION_ID.fullmatch(connection_id):
        return
    for reference, entry in list(_CONNECTIONS.items()):
        if entry["connection_id"] == connection_id:
            _CONNECTIONS.pop(reference, None)
            if not getattr(connection, "is_enabled", False):
                return
            _CONNECTIONS[reference] = {"connection_id": connection_id, "updated": time.monotonic()}
            return
    if not getattr(connection, "is_enabled", False):
        return
    now = time.monotonic()
    _clean_connections(now)
    reference = secrets.token_urlsafe(6)
    _CONNECTIONS[reference] = {"connection_id": connection_id, "updated": now}
    while len(_CONNECTIONS) > _MAX_REMEMBERED_CONNECTIONS:
        _CONNECTIONS.popitem(last=False)


def _clean_connections(now: float) -> None:
    for reference, entry in list(_CONNECTIONS.items()):
        if now - entry["updated"] > _CONNECTION_TTL:
            _CONNECTIONS.pop(reference, None)


def _resolve_connection(reference: str) -> str:
    now = time.monotonic()
    _clean_connections(now)
    entry = _CONNECTIONS.get(str(reference or ""))
    if entry is None:
        raise CommandError("That Business Connection is not available in this process. Reconnect the business account and try again.")
    _CONNECTIONS.move_to_end(str(reference))
    return entry["connection_id"]


def _aiogram_methods_available() -> bool:
    try:
        from aiogram import Bot
        return all(callable(getattr(Bot, name, None)) for name in (
            "get_business_connection", "set_business_account_name",
            "set_business_account_bio", "set_business_account_username",
        ))
    except Exception:
        return False


async def _bot_api(method: str, **payload):
    """One-shot Aiogram Bot API call; the token/session are never persisted."""
    if not _aiogram_methods_available():
        raise RuntimeError("Aiogram Business profile methods are unavailable")
    token = str(getattr(config, "BOT_TOKEN", "") or "").strip()
    if not token:
        raise RuntimeError("Bot API credentials are not configured")
    from aiogram import Bot
    client = Bot(token=token)
    try:
        return await getattr(client, method)(**payload)
    finally:
        await client.session.close()


def _clean_pending(now: float) -> None:
    for nonce, item in list(_PENDING.items()):
        if now - item["created"] > _PENDING_TTL:
            _PENDING.pop(nonce, None)
    while len(_PENDING) > _MAX_PENDING:
        _PENDING.pop(next(iter(_PENDING)))


def _connection_ref(value: str) -> str:
    value = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8}", value):
        raise CommandError("Use a short connection reference from <code>/businessprofile connections</code>.")
    return _resolve_connection(value)


def _profile_value(field: str, raw_value: str) -> dict:
    value = str(raw_value or "").strip()
    if field == "name":
        pieces = value.split(maxsplit=1)
        first_name = pieces[0] if pieces else ""
        last_name = pieces[1] if len(pieces) == 2 else ""
        if not 1 <= len(first_name) <= 64 or len(last_name) > 64:
            raise CommandError("Name must have a first name of 1–64 characters and an optional last name up to 64 characters.")
        return {"first_name": first_name, "last_name": last_name}
    if field == "bio":
        if not 1 <= len(value) <= 140:
            raise CommandError("Bio must be 1–140 characters; nothing changed.")
        return {"bio": value}
    if field == "username":
        value = value.removeprefix("@").strip()
        if not _USERNAME.fullmatch(value):
            raise CommandError("Username must contain 5–32 letters, digits or underscores, without @.")
        return {"username": value}
    raise CommandError("Choose name, bio or username.")


async def _verify_connection(connection_id: str, actor_id: int, field: str | None = None):
    try:
        connection = await _bot_api("get_business_connection", business_connection_id=connection_id)
    except Exception:
        raise CommandError("The Business Connection could not be verified. Check that it is active and try again.") from None
    user = getattr(connection, "user", None)
    if not getattr(connection, "is_enabled", False) or int(getattr(user, "id", 0) or 0) != int(actor_id):
        raise CommandError("This is not an active Business Connection owned by the signed-in bot owner.")
    rights = getattr(connection, "rights", None)
    if field:
        right = _FIELDS[field][0]
        if rights is None or getattr(rights, right, False) is not True:
            raise CommandError("The connected account has not granted the required profile-edit right. Nothing changed.")
    return connection


def _rate_limit(connection_id: str, now: float) -> bool:
    bucket = _APPLY_TIMES.get(connection_id)
    if bucket is None:
        if len(_APPLY_TIMES) >= _MAX_CONNECTIONS:
            oldest = min(_APPLY_TIMES, key=lambda key: _APPLY_TIMES[key][-1] if _APPLY_TIMES[key] else 0)
            _APPLY_TIMES.pop(oldest, None)
        bucket = _APPLY_TIMES[connection_id] = deque()
    while bucket and now - bucket[0] >= 3600:
        bucket.popleft()
    if len(bucket) >= 5 or (bucket and now - bucket[-1] < 60):
        return False
    bucket.append(now)
    return True


async def business_profile(ctx) -> Screen:
    """Preview and separately confirm one scoped, consent-backed profile edit."""
    args = str(ctx.command.arguments or "").strip()
    parts = args.split(maxsplit=3)
    actor = ctx.user
    actor_id = int(getattr(actor, "id", 0) or 0)
    if actor_id != int(getattr(config, "OWNER_ID", 6265999542)):
        raise CommandError("Business profile changes are limited to the verified bot owner.")
    if not parts:
        return Screen(
            heading("Business profile · explicit confirmation", 3)
            + body("Use <code>/businessprofile connections</code> for active connections, then <code>/businessprofile status REFERENCE</code> to inspect granted rights or <code>/businessprofile preview REFERENCE name|bio|username VALUE</code> to review one change. Confirm separately with <code>/businessprofile confirm CODE</code>. References are temporary, owner-scoped, and kept only in process memory.")
        )

    action = parts[0].casefold()
    if action == "connections" and len(parts) == 1:
        _clean_connections(time.monotonic())
        rows = [(reference, "Active · temporary reference") for reference in _CONNECTIONS]
        if not rows:
            return Screen(heading("Business Connections", 3) + body("No active owner connection is currently remembered. Enable the bot in Telegram Business and retry after its connection update arrives."))
        return Screen(heading("Business Connections", 3) + table(rows))

    if action == "status" and len(parts) == 2:
        connection_id = _connection_ref(parts[1])
        connection = await _verify_connection(connection_id, actor_id)
        rights = getattr(connection, "rights", None)
        rows = [("Connection", "Active and owned by the signed-in bot owner")]
        rows.extend((label, "Granted" if rights is not None and getattr(rights, key, False) is True else "Not granted")
                    for label, key in (("Change name", "can_edit_name"),
                                       ("Change bio", "can_edit_bio"),
                                       ("Change username", "can_edit_username")))
        return Screen(heading("Business profile connection status", 3) + table(rows))

    if action == "preview" and len(parts) == 4:
        connection_id = _connection_ref(parts[1])
        field = parts[2].casefold()
        if field not in _FIELDS:
            raise CommandError("Choose one field: name, bio or username.")
        values = _profile_value(field, parts[3])
        await _verify_connection(connection_id, actor_id, field)
        now = time.monotonic()
        _clean_pending(now)
        if len(_PENDING) >= _MAX_PENDING:
            raise CommandError("Too many profile previews are pending. Confirm or wait for an earlier preview to expire.")
        nonce = secrets.token_urlsafe(9)
        _PENDING[nonce] = {"connection_id": connection_id, "field": field,
                           "values": values, "actor_id": actor_id, "created": now}
        display = " ".join(values.values())
        return Screen(
            heading("Review Business profile change", 3)
            + table([("Field", field.capitalize()), ("New value", escape(display)), ("Expiry", "5 minutes")])
            + body(f"This edits only the connected account owned by you. Re-enter <code>/businessprofile confirm {escape(nonce)}</code> to apply; no profile change has happened yet.")
        )

    if action == "confirm" and len(parts) == 2:
        nonce = parts[1]
        now = time.monotonic()
        _clean_pending(now)
        pending = _PENDING.get(nonce)
        if pending is None or pending["actor_id"] != actor_id:
            raise CommandError("That preview is expired or belongs to another account. Nothing changed.")
        # Consume before any network call so concurrent/replayed confirms cannot
        # apply the same profile update twice.
        _PENDING.pop(nonce, None)
        connection_id = pending["connection_id"]
        field = pending["field"]
        await _verify_connection(connection_id, actor_id, field)
        if not _rate_limit(connection_id, now):
            raise CommandError("Profile edits are rate-limited to one per minute and five per hour. Nothing changed.")
        method = _FIELDS[field][1]
        try:
            applied = await _bot_api(method, business_connection_id=connection_id, **pending["values"])
        except Exception:
            raise CommandError("Telegram did not confirm the Business profile edit. Check the connected account before retrying.") from None
        if applied is not True:
            raise CommandError("Telegram did not confirm the Business profile edit. Check the connected account before retrying.")
        return Screen(heading("Business profile updated", 3)
                      + body(f"Telegram confirmed the {escape(field)} update for your connected account."))

    raise CommandError("Use connections, status REFERENCE, preview REFERENCE name|bio|username VALUE, or confirm CODE.")


COMMANDS = (
    Command("businessprofile", business_profile,
            "Preview and confirm a consented Business profile edit", category="owner", policy="owner"),
)
