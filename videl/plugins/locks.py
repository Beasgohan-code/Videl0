#  Videl © 2026 | Beasgohan-code
"""Content locks and anti-flood enforcement.

Admins and approved members are exempt. Enforcement deletes the offending
message; it never restricts a member automatically, so a false positive cannot
lock someone out of the group.
"""
from __future__ import annotations

import logging
import re
import time
from collections import OrderedDict, deque

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup

from videl import LOGGER, bot
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.bot_ui import button
from videl.utils.db import is_approved
from videl.utils.moderation import LOCK_TYPES, locked_message_reason
from videl.utils.rich_ui import rich_reply

logger = LOGGER

LOCK_CHOICES = LOCK_TYPES
_LOCK_TYPES = LOCK_TYPES + ("all",)
_FLOOD_WINDOWS: "OrderedDict[tuple[int, int], deque]" = OrderedDict()
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
FLOOD_LIMIT = 7
FLOOD_WINDOW = 8


def _locked(chat_id: int, kind: str) -> bool:
    if base.get_setting(chat_id, f"lock_{kind}", False):
        return True
    return kind == "forward" and bool(base.get_setting(chat_id, "lock_forwards", False))


@bot.on_message(filters.group, group=15)
async def mgmt_content_checker(_, message) -> None:
    """Delete messages that break an active lock; also enforce anti-flood."""
    if not getattr(message, "chat", None):
        return
    if base.chat_kind(message) not in {"group", "supergroup"}:
        return
    if message.from_user and await base.is_admin(bot, message.chat.id, message.from_user.id):
        return
    if message.from_user and is_approved(message.chat.id, message.from_user.id):
        return
    if base.get_setting(message.chat.id, "antispam", False) and message.from_user:
        key = (message.chat.id, message.from_user.id)
        now = time.monotonic()
        window = _FLOOD_WINDOWS.setdefault(key, deque(maxlen=32))
        _FLOOD_WINDOWS.move_to_end(key)
        while window and now - window[0] > FLOOD_WINDOW:
            window.popleft()
        window.append(now)
        while len(_FLOOD_WINDOWS) > 10000:
            _FLOOD_WINDOWS.popitem(last=False)
        if len(window) > FLOOD_LIMIT:
            try:
                await message.delete()
            except Exception:
                logger.debug("Anti-flood deletion failed", exc_info=True)
            return
    reason = locked_message_reason(message, lambda kind: _locked(message.chat.id, kind))
    if reason:
        try:
            await message.delete()
            logger.info("Lock %s removed a message in %s", reason, message.chat.id)
        except Exception:
            logger.debug("Lock deletion failed", exc_info=True)


async def change_lock(ctx, enabled: bool) -> Screen:
    selected = ctx.command.arguments.strip().casefold()
    if selected not in _LOCK_TYPES:
        return Screen(
            heading("Choose a lock", 3)
            + body("Available: <code>" + " | ".join(_LOCK_TYPES) + "</code>")
        )
    kinds = LOCK_TYPES if selected == "all" else (selected,)
    updates = {f"lock_{kind}": enabled for kind in kinds}
    if "forward" in kinds:
        updates["lock_forwards"] = enabled
    if not base.set_settings(ctx.message.chat.id, updates):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(
        heading("Locks updated", 3)
        + table([("Type", escape(selected)), ("State", "locked" if enabled else "open")])
        + body("Administrators and approved members are exempt.")
    )


async def lock(ctx) -> Screen:
    return await change_lock(ctx, True)


async def unlock(ctx) -> Screen:
    return await change_lock(ctx, False)


async def locks(ctx) -> Screen:
    chat_id = ctx.message.chat.id
    rows = [(kind.capitalize(), "locked" if _locked(chat_id, kind) else "open") for kind in LOCK_TYPES]
    antispam = "on" if base.get_setting(chat_id, "antispam", False) else "off"
    rows.append(("Anti-flood", f"{antispam} · {FLOOD_LIMIT + 1} messages / {FLOOD_WINDOW}s"))
    return Screen(
        heading("Lock status", 3)
        + table(rows)
        + body("Toggle with <code>/lock links</code> or <code>/unlock links</code>."),
        InlineKeyboardMarkup([[button("Anti-flood", callback_data="help:manage")]]),
    )


async def antispam(ctx) -> Screen:
    chat_id = ctx.message.chat.id
    argument = ctx.command.arguments.strip().casefold()
    if argument not in {"on", "off"}:
        return Screen(heading("Anti-flood", 3) + body("Usage: <code>/antispam on</code> or <code>/antispam off</code>."))
    if not base.set_setting(chat_id, "antispam", argument == "on"):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("Anti-flood", 3) + body(f"Anti-flood is now <b>{argument}</b>."))


COMMANDS = (
    Command("lock", lock, "Block a content type in this group", category="manage", policy="admin"),
    Command("unlock", unlock, "Allow a content type again", category="manage", policy="admin"),
    Command("locks", locks, "Show every lock state", category="manage", policy="group"),
    Command("antispam", antispam, "Toggle anti-flood protection", category="manage", policy="admin"),
)
