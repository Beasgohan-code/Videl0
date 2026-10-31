#  Videl © 2026 | Beasgohan-code
"""``/remind`` — durable reminders stored in MongoDB.

A reminder survives a redeploy: pending documents are re-scheduled at startup and
claimed atomically before delivery so a restart cannot send one twice.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone

from pyrogram.types import InlineKeyboardMarkup
from pymongo import ReturnDocument

from videl import LOGGER, bot
from videl.app.router import Command, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.bot_ui import button
from videl.utils.command_ui import usage

COLLECTION = "plugin_reminders"
MAX_PENDING = 20
MAX_SECONDS = 7 * 86400
_TASKS: dict[str, asyncio.Task] = {}
_ARGUMENT = re.compile(r"(?:in\s+)?(\d{1,6})\s*([smhdw])\s+(.{1,300})", re.I | re.S)
UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def _store():
    return base.collection(COLLECTION)


def parse(text: str):
    match = _ARGUMENT.fullmatch((text or "").strip())
    if not match:
        return None
    seconds = int(match[1]) * UNITS[match[2].lower()]
    if not 10 <= seconds <= MAX_SECONDS:
        return None
    return seconds, match[3].strip()


def _schedule(store, reminder: dict) -> None:
    key = str(reminder["_id"])
    if key in _TASKS and not _TASKS[key].done():
        return
    due = reminder.get("due_at")
    if not isinstance(due, datetime):
        return
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)

    async def deliver() -> None:
        # Re-check at most every five minutes so turning quiet hours off (or
        # changing the window) takes effect promptly without cancelling a task.
        while True:
            now = datetime.now(timezone.utc)
            remaining = (due - now).total_seconds()
            if remaining > 0:
                await asyncio.sleep(min(remaining, 300))
                continue
            if int(reminder["chat_id"]) == int(reminder["user_id"]):
                from videl.utils.db import get_db
                from videl.utils.member_preferences import read
                preferences = await asyncio.to_thread(read, get_db(), int(reminder["user_id"]))
                quiet_hours = preferences["quiet_hours"]
            else:
                quiet_hours = {"enabled": False}
            from videl.utils.member_preferences import next_allowed_delivery
            allowed_at = next_allowed_delivery(datetime.now(timezone.utc), quiet_hours)
            delay = (allowed_at - datetime.now(timezone.utc)).total_seconds()
            if delay <= 0:
                break
            await asyncio.sleep(min(delay, 300))
        pending = await asyncio.to_thread(
            store.find_one_and_update,
            {"_id": reminder["_id"], "status": "pending"},
            {"$set": {"status": "sending"}},
            return_document=ReturnDocument.AFTER,
        )
        if not pending:
            return
        options = {"message_thread_id": pending["message_thread_id"]} if pending.get("message_thread_id") else {}
        text = (
            heading("Reminder", 3)
            + body(f"<a href=\"tg://user?id={pending['user_id']}\">For you</a> · {escape(pending.get('text', ''))}")
        )
        try:
            await bot.send_message(pending["chat_id"], text, **options)
        except Exception as exc:
            await asyncio.to_thread(store.update_one, {"_id": pending["_id"]}, {"$set": {"status": "unconfirmed"}})
            LOGGER.warning("Reminder delivery unconfirmed (%s); not resending", type(exc).__name__)
        else:
            await asyncio.to_thread(
                store.update_one,
                {"_id": pending["_id"]},
                {"$set": {"status": "sent", "sent_at": datetime.now(timezone.utc)}},
            )

    task = asyncio.create_task(deliver(), name=f"reminder-{key}")
    _TASKS[key] = task

    def finish(done):
        if _TASKS.get(key) is done:
            _TASKS.pop(key, None)
        if not done.cancelled() and done.exception():
            LOGGER.warning("Reminder task failed (%s)", type(done.exception()).__name__)

    task.add_done_callback(finish)


async def restore_pending_reminders() -> int:
    store = _store()
    if store is None:
        return 0
    reminders = await asyncio.to_thread(
        lambda: list(store.find({"status": "pending"}).sort("due_at", 1).limit(500))
    )
    for reminder in reminders:
        _schedule(store, reminder)
    return len(reminders)


async def remind(ctx) -> Screen:
    actor = getattr(ctx.message, "from_user", None)
    if actor is None:
        return Screen(heading("Reminder", 3) + body("Anonymous senders cannot schedule reminders."))
    store = _store()
    if store is None:
        return Screen(heading("Reminder unavailable", 3) + body("MongoDB is not connected; nothing was scheduled."))
    parsed = parse(ctx.command.arguments)
    if parsed is None:
        return Screen(usage("/remind 10m take a break", "Accepts s, m, h, d and w from 10 seconds to 7 days."))
    seconds, text = parsed
    pending = await asyncio.to_thread(store.count_documents, {"user_id": actor.id, "status": "pending"})
    if pending >= MAX_PENDING:
        return Screen(heading("Reminder limit", 3) + body(f"You already have {MAX_PENDING} pending reminders."))
    reminder = {
        "user_id": actor.id,
        "chat_id": ctx.message.chat.id,
        "message_thread_id": getattr(ctx.message, "message_thread_id", None),
        "text": text,
        "due_at": datetime.now(timezone.utc) + timedelta(seconds=seconds),
        "status": "pending",
    }
    inserted = await asyncio.to_thread(store.insert_one, reminder)
    reminder["_id"] = inserted.inserted_id
    _schedule(store, reminder)
    return Screen(
        heading("Reminder saved", 3)
        + table([("In", base.human_duration(seconds)), ("Text", escape(text))])
        + body("I will message this chat when the time is up.")
    )


async def reminders(ctx) -> Screen:
    actor = getattr(ctx.message, "from_user", None)
    store = _store()
    if actor is None or store is None:
        return Screen(heading("Reminders", 3) + body("Reminders are unavailable right now."))
    documents = await asyncio.to_thread(
        lambda: list(store.find({"user_id": actor.id, "status": "pending"}).sort("due_at", 1).limit(MAX_PENDING))
    )
    if not documents:
        return Screen(heading("No reminders", 3) + body("Create one with <code>/remind 15m stretch</code>."))
    rows = []
    for item in documents:
        due = item.get("due_at")
        when = due.strftime("%d %b %H:%M UTC") if isinstance(due, datetime) else "pending"
        rows.append((when, escape(item.get("text", ""))))
    return Screen(
        heading("Your reminders", 3) + table(rows) + body("Use <code>/forget all</code> to clear them."),
        InlineKeyboardMarkup([[button("Clear all", callback_data="help:tools")]]),
    )


async def forget(ctx) -> Screen:
    actor = getattr(ctx.message, "from_user", None)
    store = _store()
    if actor is None or store is None:
        return Screen(heading("Reminders", 3) + body("Reminders are unavailable right now."))
    argument = (ctx.command.arguments or "").strip().casefold()
    if argument not in {"all"}:
        return Screen(usage("/forget all", "Cancels every pending reminder you created."))
    result = await asyncio.to_thread(store.delete_many, {"user_id": actor.id, "status": "pending"})
    return Screen(heading("Reminders cleared", 3) + body(f"Cancelled {escape(result.deleted_count)} pending reminders."))


COMMANDS = (
    Command("remind", remind, "Schedule a reminder such as 10m or 2h", category="tools"),
    Command("reminders", reminders, "List your pending reminders", category="tools"),
    Command("forget", forget, "Cancel every pending reminder you created", category="tools"),
)
