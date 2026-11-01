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
from pymongo import ReturnDocument

from videl import LOGGER, bot
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.bot_ui import button
from videl.utils.command_ui import rich_edit, rich_reply, usage

COLLECTION = "videl_afk"
NOTICE_COOLDOWN = 300  # seconds between notices for the same person in a chat
AFK_LIST_PAGE_SIZE = 10


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
        path = f"last_notice.{int(message.chat.id)}"
        selector = {
            "user_id": target,
            "$or": [
                {path: {"$exists": False}},
                {path: {"$lte": now - NOTICE_COOLDOWN}},
            ],
        }
        try:
            # The cooldown claim is one atomic database operation. Concurrent
            # workers cannot both pass a read-then-write notice check.
            document = await asyncio.to_thread(
                store.find_one_and_update,
                selector,
                {"$set": {path: now}},
                return_document=ReturnDocument.BEFORE,
            )
        except Exception:
            LOGGER.debug("AFK notice cooldown claim failed", exc_info=True)
            continue
        if not document:
            continue
        try:
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


async def _afk_list_page(store, page: int) -> Screen:
    try:
        total = await asyncio.to_thread(store.count_documents, {})
        if not total:
            return Screen(heading("Away members", 3) + body("Nobody is away right now."))
        pages = max(1, (int(total) + AFK_LIST_PAGE_SIZE - 1) // AFK_LIST_PAGE_SIZE)
        page = max(0, min(int(page), pages - 1))
        documents = await asyncio.to_thread(
            lambda: list(store.find({}).sort("since", 1)
                         .skip(page * AFK_LIST_PAGE_SIZE).limit(AFK_LIST_PAGE_SIZE))
        )
    except Exception as error:
        LOGGER.warning("AFK list query failed (%s)", type(error).__name__)
        raise CommandError("The away list is temporarily unavailable. Try again shortly.") from None
    if not documents:
        return Screen(heading("Away members", 3) + body("Nobody is away right now."))
    rows = [(escape(item.get("name", "User")), f"{escape(item.get('reason', 'Away'))} · {_since(item.get('since'))}")
            for item in documents]
    start = page * AFK_LIST_PAGE_SIZE + 1
    end = start + len(documents) - 1
    content = (heading("Away members", 3) + table(rows)
               + body(f"Showing {start}–{end} of {total} active Videl away statuses · page {page + 1} of {pages}.")
               + body("This is a bot-wide list across chats. Only each status owner can clear their own status with /back."))
    controls = []
    if page > 0:
        controls.append(button("Previous", callback_data=f"afklist:{page - 1}"))
    if page + 1 < pages:
        controls.append(button("Next", callback_data=f"afklist:{page + 1}", style="primary"))
    keyboard = InlineKeyboardMarkup([controls]) if controls else None
    return Screen(content, keyboard)


async def afk_list(ctx) -> Screen:
    argument = str(getattr(ctx.command, "arguments", "") or "").strip()
    if argument and (len(argument.split()) != 1 or not argument.isdecimal()
                     or len(argument) > 6 or int(argument) < 1 or int(argument) > 100_000):
        return Screen(usage("/afklist [page]", "Use a positive page number, for example /afklist 2."))
    store = _store()
    if store is None:
        return Screen(heading("Away members", 3) + body("MongoDB is not connected."))
    return await _afk_list_page(store, int(argument) - 1 if argument else 0)


@bot.on_callback_query(filters.regex(r"^afklist:[0-9]{1,5}$"))
async def afk_list_callback(client, query) -> None:
    """Rebuild one bounded read-only page in the same group context."""
    message = getattr(query, "message", None)
    actor = getattr(query, "from_user", None)
    chat = getattr(message, "chat", None) if message is not None else None
    chat_type = getattr(chat, "type", "")
    chat_type = str(getattr(chat_type, "value", chat_type))
    if (message is None or actor is None or chat is None
            or chat_type not in {"group", "supergroup"}):
        return await query.answer("Open the away list in a group chat.", show_alert=True)
    try:
        bot_user = getattr(client, "me", None) or await client.get_me()
    except Exception:
        return await query.answer("I could not verify this away-list message.", show_alert=True)
    if int(getattr(getattr(message, "from_user", None), "id", 0) or 0) != int(getattr(bot_user, "id", 0) or 0):
        return await query.answer("This is not a Videl away-list panel.", show_alert=True)
    try:
        _prefix, raw_page = str(query.data).split(":", 1)
        if _prefix != "afklist" or not raw_page.isdecimal() or len(raw_page) > 5:
            raise ValueError
        store = _store()
        if store is None:
            raise CommandError("The away list is temporarily unavailable. Try again shortly.")
        screen = await _afk_list_page(store, int(raw_page))
    except (ValueError, TypeError):
        return await query.answer("That page is no longer available. Reopen /afklist.", show_alert=True)
    except CommandError as error:
        return await query.answer(str(error), show_alert=True)
    await query.answer()
    await rich_edit(message, screen.html, reply_markup=screen.keyboard)



COMMANDS = (
    Command("afk", afk, "Set an away status with automatic replies", category="tools"),
    Command("back", back, "Clear your away status", category="tools"),
    Command("afklist", afk_list, "Browse members currently away across Videl chats", category="tools", policy="group"),
)
