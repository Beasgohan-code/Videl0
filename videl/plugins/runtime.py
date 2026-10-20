"""Small MongoDB-backed AFK and reminder service; no entertainment adapters."""
from __future__ import annotations
import asyncio
import html
import logging
import re
from datetime import datetime, timedelta, timezone
from pymongo import ReturnDocument
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup
from videl import bot
from videl.utils.db import get_db
from videl.utils.rich_ui import rich_heading, rich_note
from videl.utils.command_ui import rich_reply
from videl.utils.bot_ui import visual_call
log = logging.getLogger("videl.plugins.runtime")
_TASKS = {}

def _db():
    return get_db()

def _col(name):
    db = _db()
    return db[name] if db is not None else None

def _args(message: Message) -> str:
    return " ".join((message.text or "").split()[1:]).strip()

def _who(message: Message) -> int:
    return message.from_user.id if message.from_user else 0

def _esc(value) -> str:
    return html.escape(str(value or ""), quote=True)

async def _send(message: Message, title: str, body: str, *, photo: str = "", buttons=None):
    text = rich_heading(_esc(title), level=2) + rich_note(body)
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    if photo:
        from pyrogram.errors import BadRequest
        from videl.utils.rich_ui import rich_caption
        try:
            return await visual_call(bot.send_photo, message.chat.id, photo, caption=rich_caption(text), reply_markup=markup)
        except BadRequest:
            pass  # Definite rejection: a text-only reply is safe.
        except Exception as exc:
            log.warning("Plugin photo delivery unconfirmed (%s); not resending", type(exc).__name__)
            return None
    return await rich_reply(message, text, reply_markup=markup)

@bot.on_message(filters.incoming & ~filters.service, group=8)
async def _afk_watcher(_, message: Message):
    if not message.from_user or not message.text or message.text.startswith("/"): return
    col=_col("videl_afk")
    if col is None:return
    uid=message.from_user.id
    own=col.find_one({"user_id":uid})
    if own:
        col.delete_one({"_id":own["_id"]})
        try: await rich_reply(message, rich_heading("Welcome back", level=3) + rich_note(f"{_esc(message.from_user.first_name)}, your AFK status is cleared."))
        except Exception: pass
    seen=set()
    if message.reply_to_message and message.reply_to_message.from_user:seen.add(message.reply_to_message.from_user.id)
    for entity in message.entities or []:
        if getattr(entity,"type",None) and str(entity.type).endswith("TEXT_MENTION") and entity.user:seen.add(entity.user.id)
    for target in seen:
        item=col.find_one({"user_id":target})
        if item:
            try: await rich_reply(message, rich_heading("Currently away", level=3) + rich_note(_esc(item.get("reason", "Away"))))
            except Exception: pass


async def run_plugin(slug: str, message: Message):
    uid = _who(message)
    if not uid:
        return await _send(message, "User account required", "Anonymous/channel senders cannot save personal state.")
    arg = _args(message)
    if slug == "afk":
        col = _col("videl_afk")
        if col is None:
            return await _send(message, "AFK unavailable", "MongoDB is unavailable; nothing was saved.")
        await asyncio.to_thread(col.update_one, {"user_id": uid}, {"$set": {"reason": arg[:300] or "Away", "since": datetime.now(timezone.utc)}}, upsert=True)
        return await _send(message, "AFK enabled", f"Your status: {_esc(arg[:300] or 'Away')}")
    if slug != "reminder":
        return await _send(message, "Command retired", "Use /help for the supported music and group tools.")
    match = re.fullmatch(r"(?:in\s+)?(\d{1,5})([smh])\s+(.{1,300})", arg, re.I | re.S)
    if not match:
        return await _send(message, "Reminder", "Usage: <code>/remind 10m take a break</code>. Maximum delay: 24 hours.")
    seconds = int(match[1]) * {"s": 1, "m": 60, "h": 3600}[match[2].lower()]
    if not 1 <= seconds <= 86400:
        return await _send(message, "Invalid delay", "Choose between 1 second and 24 hours.")
    col = _col("plugin_reminders")
    if col is None:
        return await _send(message, "Reminder unavailable", "MongoDB is unavailable; nothing was scheduled.")
    if await asyncio.to_thread(col.count_documents, {"user_id": uid, "status": "pending"}) >= 20:
        return await _send(message, "Reminder limit", "You already have 20 pending reminders.")
    reminder = {"user_id": uid, "chat_id": message.chat.id, "message_thread_id": getattr(message, "message_thread_id", None), "text": match[3], "due_at": datetime.now(timezone.utc) + timedelta(seconds=seconds), "status": "pending"}
    result = await asyncio.to_thread(col.insert_one, reminder)
    reminder["_id"] = result.inserted_id
    _schedule_reminder(col, reminder)
    return await _send(message, "Reminder saved", f"Due in {seconds} seconds: {_esc(match[3])}")


def _schedule_reminder(col, reminder):
    key = str(reminder["_id"])
    if key in _TASKS and not _TASKS[key].done():
        return
    due = reminder.get("due_at")
    if not isinstance(due, datetime):
        return
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)

    async def deliver():
        await asyncio.sleep(max(0, (due - datetime.now(timezone.utc)).total_seconds()))
        # Atomic claim prevents duplicate dispatch by restored tasks/processes.
        pending = await asyncio.to_thread(col.find_one_and_update, {"_id": reminder["_id"], "status": "pending"}, {"$set": {"status": "sending"}}, return_document=ReturnDocument.AFTER)
        if not pending:
            return
        try:
            options = {"message_thread_id": pending["message_thread_id"]} if pending.get("message_thread_id") else {}
            await bot.send_message(pending["chat_id"], f"<b>Reminder</b> · <a href='tg://user?id={pending['user_id']}'>For you</a>\n{_esc(pending.get('text', ''))}", **options)
        except Exception as exc:
            await asyncio.to_thread(col.update_one, {"_id": pending["_id"], "status": "sending"}, {"$set": {"status": "unconfirmed"}})
            log.warning("Reminder delivery unconfirmed (%s); not resending", type(exc).__name__)
        else:
            await asyncio.to_thread(col.update_one, {"_id": pending["_id"], "status": "sending"}, {"$set": {"status": "sent", "sent_at": datetime.now(timezone.utc)}})

    task = asyncio.create_task(deliver(), name=f"reminder-{key}")
    _TASKS[key] = task
    def finish(done):
        if _TASKS.get(key) is done:
            _TASKS.pop(key, None)
        if not done.cancelled() and done.exception():
            log.warning("Reminder task failed (%s)", type(done.exception()).__name__)
    task.add_done_callback(finish)


async def restore_pending_reminders():
    col = _col("plugin_reminders")
    if col is None:
        return 0
    reminders = await asyncio.to_thread(lambda: list(col.find({"status": "pending"}).sort("due_at", 1).limit(500)))
    for reminder in reminders:
        _schedule_reminder(col, reminder)
    return len(reminders)
