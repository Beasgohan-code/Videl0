#  Videl © 2026 | Beasgohan-code
"""Shared plumbing for Videl's command plugins.

Every file in :mod:`videl.plugins` owns its commands, its validation and the
MongoDB collections it writes. This module only holds the pieces that must
behave identically everywhere: chat settings, target resolution, duration
parsing, permission checks and the small-caps heading style.
"""
from __future__ import annotations

import asyncio
import html
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

from pyrogram.enums import ChatMemberStatus

import config
from videl.utils.db import get_db
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note

# Small caps for authored titles only. User names, arguments and message
# bodies are never transliterated.
_SMALL_CAPS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz", "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)


def small_caps(text: str) -> str:
    """Transliterate Latin letters outside HTML tags and <code> blocks."""
    parts = re.split(r"(<[^>]+>)", str(text))
    return "".join(
        part if part.startswith("<") else part.translate(_SMALL_CAPS) for part in parts
    )


_PLAIN_CAPS = str.maketrans(
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ", "abcdefghijklmnopqrstuvwxyz"
)


def plain(text: str) -> str:
    """Undo small caps — used by logs, tests and search."""
    return str(text).translate(_PLAIN_CAPS)


def heading(text: str, level: int = 2) -> str:
    return rich_heading(small_caps(text), level=level)


def body(text: str) -> str:
    return rich_note(text)


def escape(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def studio_url() -> str:
    """The public studio origin, validated before it is put in a button."""
    from urllib.parse import urlsplit

    value = (getattr(config, "WEBAPP_URL", "") or "https://videl-studio.vercel.app").rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password:
        return value
    return "https://videl-studio.vercel.app"


def guide_url() -> str:
    return studio_url() + "/?tab=guide"


def table(rows: Iterable[tuple]) -> str:
    return rich_kv_table(list(rows))


# ── Storage ──────────────────────────────────────────────────────────────────

SETTINGS_COLLECTION = "mgmt_chat_settings"


def db():
    return get_db()


def collection(name: str):
    database = db()
    return database[name] if database is not None else None


def get_setting(chat_id: int, key: str, default=None):
    try:
        document = collection(SETTINGS_COLLECTION).find_one({"chat_id": chat_id})
    except Exception:
        return default
    return document.get(key, default) if document else default


def get_settings(chat_id: int) -> dict:
    try:
        document = collection(SETTINGS_COLLECTION).find_one({"chat_id": chat_id})
    except Exception:
        return {}
    return dict(document or {})


def set_settings(chat_id: int, values: dict, *, expected_revision=None) -> bool:
    try:
        if collection(SETTINGS_COLLECTION) is None:
            return False
        # Telegram and the web panel share one CAS revision so an old keyboard
        # cannot silently overwrite a newer group configuration.
        from videl.utils import settings_store

        settings_store.write(chat_id, values, expected=expected_revision)
        return True
    except Exception:
        return False


def set_setting(chat_id: int, key: str, value, *, expected_revision=None) -> bool:
    return set_settings(chat_id, {key: value}, expected_revision=expected_revision)


# ── Chats and roles ──────────────────────────────────────────────────────────


def chat_kind(message) -> str:
    value = getattr(getattr(message, "chat", None), "type", "")
    return str(getattr(value, "value", value))


def is_group(message) -> bool:
    return chat_kind(message) in {"group", "supergroup"}


def is_private(message) -> bool:
    return chat_kind(message) == "private"


def is_owner(user_id: int) -> bool:
    return int(user_id or 0) == int(getattr(config, "OWNER_ID", 0) or 6265999542)


async def is_admin(client, chat_id: int, user_id: int) -> bool:
    if is_owner(user_id) or user_id in getattr(config, "ADMIN_IDS", set()):
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}
    except Exception:
        return False


async def bot_rights(client, chat_id: int) -> dict:
    """Return the bot's effective administrator rights as a plain dict."""
    try:
        me = getattr(client, "me", None) or await client.get_me()
        member = await client.get_chat_member(chat_id, me.id)
    except Exception:
        return {}
    if member.status == ChatMemberStatus.OWNER:
        return {"owner": True}
    privileges = getattr(member, "privileges", None)
    if member.status != ChatMemberStatus.ADMINISTRATOR or privileges is None:
        return {}
    names = (
        "can_delete_messages",
        "can_restrict_members",
        "can_pin_messages",
        "can_promote_members",
        "can_manage_video_chats",
        "can_change_info",
        "can_invite_users",
    )
    return {name: bool(getattr(privileges, name, False)) for name in names}


def missing_rights(rights: dict, needed: Iterable[str]) -> list[str]:
    if rights.get("owner"):
        return []
    return [name for name in needed if not rights.get(name)]


SETTING_LABELS = {
    "can_delete_messages": "Delete messages",
    "can_restrict_members": "Restrict members",
    "can_pin_messages": "Pin messages",
    "can_promote_members": "Promote members",
    "can_manage_video_chats": "Manage voice chats",
    "can_change_info": "Change group info",
    "can_invite_users": "Invite users",
}


# ── Arguments ────────────────────────────────────────────────────────────────

_DURATION = re.compile(r"^([1-9][0-9]{0,7})([smhdw])$", re.I)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_duration(token: str) -> int | None:
    match = _DURATION.fullmatch((token or "").strip())
    if not match:
        return None
    seconds = int(match[1]) * _UNIT_SECONDS[match[2].lower()]
    return seconds if 60 <= seconds <= 365 * 86400 else None


def human_duration(seconds: int) -> str:
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size and seconds % size == 0:
            return f"{seconds // size}{unit}"
    return f"{seconds}s"


def until(seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


async def resolve_target(client, message, tokens: list[str]):
    """Return ``(user, remaining_tokens)``; user is None when no reply/token."""
    reply = getattr(message, "reply_to_message", None)
    user = getattr(reply, "from_user", None) if reply else None
    tokens = list(tokens)
    if user is not None:
        return user, tokens
    if not tokens:
        return None, tokens
    identifier = tokens.pop(0)
    if not identifier.startswith("@") and not identifier.isdecimal():
        return None, [identifier, *tokens]
    try:
        target = await client.get_users(int(identifier) if identifier.isdecimal() else identifier)
    except Exception:
        return None, tokens
    return target, tokens


def authority(message) -> tuple[int, int]:
    """(chat_id, actor_id) for audit records."""
    chat = getattr(message, "chat", None)
    actor = getattr(message, "from_user", None)
    return int(getattr(chat, "id", 0) or 0), int(getattr(actor, "id", 0) or 0)


# ── Presentation ─────────────────────────────────────────────────────────────


def target_label(user) -> str:
    if user is None:
        return "Unknown user"
    name = getattr(user, "first_name", None) or getattr(user, "title", None) or "User"
    return escape(name)


def target_link(user) -> str:
    if user is None:
        return "Unknown user"
    return f'<a href="tg://user?id={int(user.id)}">{target_label(user)}</a>'


def settings_block(chat_id: int, keys: dict[str, tuple[str, object]]) -> list[tuple[str, str]]:
    """Build table rows for feature toggles from ``{key: (label, default)}``."""
    rows = []
    for key, (label, default) in keys.items():
        value = get_setting(chat_id, key, default)
        if isinstance(value, bool):
            text = "ᴏɴ" if value else "ᴏғғ"
        else:
            text = escape(value)
        rows.append((label, text))
    return rows
