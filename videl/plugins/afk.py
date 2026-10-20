#  Videl © 2026 | Beasgohan-code
"""``/afk`` — away status with real auto-replies.

Owns its command handlers (registered through the router manifest), its MongoDB
collection and its message watcher. People who mention or reply to an away
member get one quiet reply; writing anything clears the status automatically.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardMarkup

from videl import LOGGER, bot
from videl.app.router import Command, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.bot_ui import button
from videl.utils.command_ui import rich_reply

COLLECTION = "videl_afk"
NOTICE_COOLDOWN = 300  # seconds between notices for the same person in a chat


def _store():
    return base.collection(COLLECTION)


def _since(timestamp) -> str:
    if isinstance(timestamp, datetime):
        moment = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        seconds = max(0, int((datetime.now(timezone.utc) - moment).total_seconds()))
    else:
        seconds = 0
    if seconds >= 3600:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    if seconds >= 60:
        return f"{seconds // 60}m"
    return "just now"


def _autoclear(user_id: int) -> dict | None:
    store = _store()
    if store is None:
        return None
    document = store.find_one_and_delete({"user_id": user_id})
    return document


def _mention(user) -> str:
    return f'<a href="tg://user?id={int(user.id)}">{escape(getattr(user, "first_name", "Someone"))}</a>'


@bot.on_message(filters.incoming & ~filters.service, group=7)
async def _afk_presence(_, message) -> None:
    """Clear the sender's own status, then answer mentions of away members."""
    user = getattr(message, "from_user", None)
    if user is None or getattr(user, "is_bot", False):
        return
    text = message.text or message.caption or ""
    store = _store()
    if store is None:
        return
    if not text.startswith("/"):
        cleared = await asyncio.to_thread(_autoclear, user.id)
        if cleared:
            try:
                await rich_reply(
                    message,
                    heading("Welcome back", 3)
                    + body(f"{_mention(user)}, your away status is cleared."),
                )
            except Exception:
                LOGGER.debug("AFK welcome-back reply failed", exc_info=True)

    targets: set[int] = set()
    reply = getattr(message, "reply_to_message", None)
    if reply is not None and getattr(reply, "from_user", None):
        targets.add(reply.from_user.id)
    for entity in (message.entities or []) + (message.caption_entities or []):
        entity_user = getattr(entity, "user", None)
        if entity_user is not None:
            targets.add(entity_user.id)
    targets.discard(user.id)
    if not targets:
        return
    now = time.time()
    for target in list(targets)[:4]:
        try:
            document = await asyncio.to_thread(store.find_one, {"user_id": target})
        except Exception:
            return
        if not document:
            continue
        seen = document.get("last_notice") or {}
        if now - float(seen.get(str(message.chat.id), 0) or 0) < NOTICE_COOLDOWN:
            continue
        try:
            await asyncio.to_thread(
                store.update_one,
                {"user_id": target},
                {"$set": {f"last_notice.{message.chat.id}": now}},
            )
            await rich_reply(
                message,
                heading("Currently away", 3)
                + body(f"<b>{escape(document.get('reason', 'Away'))}</b> · {_since(document.get('since'))}"),
            )
        except Exception:
            LOGGER.debug("AFK notice failed", exc_info=True)


async def afk(ctx) -> Screen:
    actor = getattr(ctx.message, "from_user", None)
    store = _store()
    if actor is None:
        return Screen(heading("Away status", 3) + body("Anonymous senders cannot save a personal status."))
    if store is None:
        return Screen(heading("AFK unavailable", 3) + body("MongoDB is not connected, so nothing was saved."))
    reason = (ctx.command.arguments or "").strip()[:300] or "Away"
    await asyncio.to_thread(
        store.update_one,
        {"user_id": actor.id},
        {
            "$set": {
                "user_id": actor.id,
                "reason": reason,
                "since": datetime.now(timezone.utc),
                "name": getattr(actor, "first_name", "Someone"),
            },
            "$unset": {"last_notice": ""},
        },
        upsert=True,
    )
    return Screen(
        heading("Away mode on", 3)
        + table([("Reason", escape(reason)), ("Clears", "when you send your next message or /back")])
        + body("Mentions and replies will get one quiet note per chat every five minutes."),
        InlineKeyboardMarkup([[button("Back", callback_data="help:tools")]]),
    )


async def back(ctx) -> Screen:
    actor = getattr(ctx.message, "from_user", None)
    if actor is None:
        return Screen(heading("Away status", 3) + body("Nothing to clear."))
    cleared = await asyncio.to_thread(_autoclear, actor.id) if _store() is not None else None
    if cleared:
        return Screen(heading("You are back", 3) + body("Away status cleared."))
    return Screen(heading("You are here already", 3) + body("No away status was saved."))


async def afk_list(ctx) -> Screen:
    store = _store()
    if store is None:
        return Screen(heading("Away members", 3) + body("MongoDB is not connected."))
    documents = await asyncio.to_thread(lambda: list(store.find({}).sort("since", 1).limit(20)))
    if not documents:
        return Screen(heading("Away members", 3) + body("Nobody is away right now."))
    rows = [(escape(item.get("name", "User")), f"{escape(item.get('reason', 'Away'))} · {_since(item.get('since'))}")
            for item in documents]
    return Screen(heading("Away members", 3) + table(rows))


COMMANDS = (
    Command("afk", afk, "Set an away status with automatic replies", category="tools"),
    Command("back", back, "Clear your away status", category="tools"),
    Command("afklist", afk_list, "List members currently away", category="tools", policy="group"),
)
