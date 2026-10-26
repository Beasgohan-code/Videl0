#  Videl © 2026 | Beasgohan-code
"""Saved notes and keyword filters.

``/save`` stores text or replied media, ``#name`` recalls it, and ``/filter``
answers keywords automatically. Both stores live in MongoDB per chat.
"""
from __future__ import annotations

import asyncio
import re

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup

from videl import LOGGER, bot
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.audit import record_bot
from videl.utils.bot_ui import button
from videl.utils.command_ui import navigation_markup, rich_send, usage
from videl.utils.premium_emojis import pe

NOTES = "mgmt_notes"
FILTERS = "mgmt_filters"
HASHTAG = re.compile(r"^#([A-Za-z0-9_]{1,32})")


def _notes():
    return base.collection(NOTES)


def _filters():
    return base.collection(FILTERS)


async def save(ctx) -> Screen:
    chat_id = ctx.message.chat.id
    tokens = ctx.command.arguments.split()
    if not tokens:
        return Screen(usage("/save rules be nice", "Reply to any message to save media instead."))
    name = tokens[0].casefold()[:32]
    content = " ".join(tokens[1:]).strip()
    note_type, caption = "text", ""
    reply = getattr(ctx.message, "reply_to_message", None)
    if reply is not None:
        for field, kind in (("text", "text"), ("photo", "photo"), ("document", "document"),
                            ("video", "video"), ("audio", "audio"), ("sticker", "sticker")):
            media = getattr(reply, field, None)
            if media is None:
                continue
            content = getattr(media, "file_id", None) or content
            note_type = kind
            caption = reply.caption or ""
            break
    if not content:
        raise CommandError("Add content or reply to a message.")
    store = _notes()
    if store is None:
        raise CommandError("MongoDB is not connected, so the note was not saved.")
    document = {"chat_id": chat_id, "name": name, "content": content, "type": note_type}
    if caption:
        document["caption"] = caption
    await asyncio.to_thread(
        store.update_one, {"chat_id": chat_id, "name": name}, {"$set": document}, upsert=True
    )
    return Screen(
        heading("Note saved", 3)
        + table([("Name", f"#{escape(name)}"), ("Type", escape(note_type))])
        + body(f"Recall it with <code>#{escape(name)}</code> or <code>/get {escape(name)}</code>.")
    )


async def get(ctx) -> Screen | None:
    name = ctx.command.arguments.split()[0].casefold() if ctx.command.arguments.strip() else ""
    if not name:
        return Screen(usage("/get rules", "Use the name you saved with /save."))
    await send_note(ctx.message.chat.id, name, reply_to=ctx.message.id)
    return None


async def send_note(chat_id: int, name: str, reply_to=None) -> None:
    store = _notes()
    if store is None:
        await rich_send(
            bot, chat_id,
            heading("⚠️ Saved note unavailable", 3) + body("The notes database is not connected, so I couldn’t look up this item."),
            reply_to_message_id=reply_to,
        )
        return
    document = await asyncio.to_thread(store.find_one, {"chat_id": chat_id, "name": name.casefold()})
    if not document:
        await rich_send(
            bot, chat_id,
            heading("Note not found", 3) + body(f"No saved note named <code>{escape(name)}</code>."),
            reply_to_message_id=reply_to,
        )
        return
    kind, content, caption = document.get("type", "text"), document["content"], document.get("caption", "")
    markup = navigation_markup()
    try:
        if kind == "text":
            await bot.send_message(chat_id, content, reply_to_message_id=reply_to, reply_markup=markup)
        elif kind == "photo":
            await bot.send_photo(chat_id, content, caption=caption, reply_to_message_id=reply_to, reply_markup=markup)
        elif kind == "document":
            await bot.send_document(chat_id, content, caption=caption, reply_to_message_id=reply_to, reply_markup=markup)
        elif kind == "video":
            await bot.send_video(chat_id, content, caption=caption, reply_to_message_id=reply_to, reply_markup=markup)
        elif kind == "audio":
            await bot.send_audio(chat_id, content, caption=caption, reply_to_message_id=reply_to, reply_markup=markup)
        elif kind == "sticker":
            await bot.send_sticker(chat_id, content, reply_to_message_id=reply_to, reply_markup=markup)
    except Exception:
        LOGGER.exception("Saved note delivery failed for chat %s, name %s", chat_id, name)
        await rich_send(
            bot, chat_id,
            heading("⚠️ Saved note could not be delivered", 3)
            + body("Telegram did not confirm delivery. Check the chat permissions and try again only if the note did not arrive."),
            reply_to_message_id=reply_to,
        )


async def delete_note(ctx) -> Screen:
    name = ctx.command.arguments.split()[0].casefold() if ctx.command.arguments.strip() else ""
    if not name:
        return Screen(usage("/delnote rules", "Removes one saved note."))
    store = _notes()
    if store is None:
        raise CommandError("MongoDB is not connected.")
    result = await asyncio.to_thread(store.delete_one, {"chat_id": ctx.message.chat.id, "name": name})
    if not result.deleted_count:
        return Screen(heading("No such note", 3) + body(f"<code>#{escape(name)}</code> does not exist."))
    return Screen(heading("Note deleted", 3) + body(f"Removed <code>#{escape(name)}</code>."))


async def list_notes(ctx) -> Screen:
    store = _notes()
    if store is None:
        raise CommandError("MongoDB is not connected.")
    chat_id = ctx.message.chat.id
    def load_names():
        total = store.count_documents({"chat_id": chat_id})
        cursor = store.find({"chat_id": chat_id}, {"name": 1}).sort("name", 1).limit(31)
        return total, list(cursor)
    total, documents = await asyncio.to_thread(load_names)
    if not total:
        return Screen(heading("📝 No saved notes yet", 3) + body("Save text or replied media with <code>/save name text</code>, then retrieve it with <code>/get name</code>."))
    names = sorted({str(document.get("name", "")) for document in documents if document.get("name")})
    shown = names[:30]
    rows = [
        (f"{pe('ios_memo')} <code>#{escape(name)}</code>", f"Open with <code>/get {escape(name)}</code>")
        for name in shown
    ]
    text = (
        heading("📝 Saved notes", 3)
        + body(f"{total} saved note{'s' if total != 1 else ''} in this group.")
        + table(rows)
    )
    if total > len(shown):
        text += body(f"Showing the first {len(shown)}. Use <code>/get name</code> to open a note directly.")
    return Screen(text)


# ── Filters ─────────────────────────────────────────────────────────────────


async def add_filter(ctx) -> Screen:
    tokens = ctx.command.arguments.split()
    if len(tokens) < 2:
        return Screen(usage("/filter hello Hi there!", "Reply to a message to reuse it as the answer."))
    keyword = tokens[0].casefold()[:64]
    reply = " ".join(tokens[1:])[:400]
    replied = getattr(ctx.message, "reply_to_message", None)
    if replied is not None and replied.text:
        reply = replied.text
    store = _filters()
    if store is None:
        raise CommandError("MongoDB is not connected.")
    await asyncio.to_thread(
        store.update_one,
        {"chat_id": ctx.message.chat.id, "keyword": keyword},
        {"$set": {"reply": reply}},
        upsert=True,
    )
    await asyncio.to_thread(
        record_bot, ctx.message.chat.id, "filter", action="filter_add",
        detail=f"keyword: {keyword}"[:80],
        actor=getattr(getattr(ctx.message, "from_user", None), "id", None),
    )
    return Screen(heading("Filter saved", 3) + body(f"<code>{escape(keyword)}</code> → {escape(reply[:120])}"))


async def remove_filter(ctx) -> Screen:
    tokens = ctx.command.arguments.split()
    if not tokens:
        return Screen(usage("/stopfilter hello", "Stops one automatic answer."))
    keyword = tokens[0].casefold()
    store = _filters()
    if store is None:
        raise CommandError("MongoDB is not connected.")
    result = await asyncio.to_thread(
        store.delete_one, {"chat_id": ctx.message.chat.id, "keyword": keyword}
    )
    if not result.deleted_count:
        return Screen(heading("Filter not found", 3) + body(f"No filter named <code>{escape(keyword)}</code>."))
    await asyncio.to_thread(
        record_bot, ctx.message.chat.id, "filter", action="filter_delete",
        detail=f"keyword: {keyword}"[:80],
        actor=getattr(getattr(ctx.message, "from_user", None), "id", None),
    )
    return Screen(heading("Filter removed", 3) + body(f"<code>{escape(keyword)}</code> is silent again."))


async def list_filters(ctx) -> Screen:
    store = _filters()
    if store is None:
        raise CommandError("MongoDB is not connected.")
    chat_id = ctx.message.chat.id
    def load_filters():
        total = store.count_documents({"chat_id": chat_id})
        cursor = store.find({"chat_id": chat_id}).sort("keyword", 1).limit(21)
        return total, list(cursor)
    total, documents = await asyncio.to_thread(load_filters)
    if not total:
        return Screen(heading("📝 No automatic filters yet", 3) + body("Create one with <code>/filter keyword response</code>."))
    shown = documents[:20]
    rows = [(f"{pe('ios_symbols')} <code>{escape(item['keyword'])}</code>", escape((item.get("reply") or "")[:72])) for item in shown]
    text = heading("📝 Automatic filters", 3) + body(f"{total} filter{'s' if total != 1 else ''} in this group.") + table(rows)
    if total > len(shown):
        text += body("Showing the first 20 alphabetically. Remove one with <code>/stopfilter keyword</code>.")
    return Screen(text)


@bot.on_message(filters.group, group=17)
async def filter_watcher(_, message) -> None:
    text = (message.text or "").casefold()
    if not text:
        return
    store = _filters()
    if store is None:
        return
    documents = await asyncio.to_thread(lambda: list(store.find({"chat_id": message.chat.id}).limit(50)))
    for document in documents:
        if document["keyword"] in text:
            try:
                await message.reply_text(document["reply"])
            except Exception:
                LOGGER.debug("Filter reply failed", exc_info=True)
            return


@bot.on_message(filters.group, group=18)
async def note_watcher(_, message) -> None:
    text = message.text or ""
    if not text.startswith("#"):
        return
    match = HASHTAG.match(text)
    if match:
        await send_note(message.chat.id, match.group(1), reply_to=message.id)


COMMANDS = (
    Command("save", save, "Save a note (text or replied media)", category="manage", policy="admin"),
    Command("get", get, "Send a saved note", category="manage", policy="group"),
    Command("delnote", delete_note, "Delete a saved note", category="manage", policy="admin"),
    Command("notes", list_notes, "List saved notes", category="manage", policy="group"),
    Command("filter", add_filter, "Answer a keyword automatically", category="manage", policy="admin"),
    Command("stopfilter", remove_filter, "Remove an automatic answer", category="manage", policy="admin"),
    Command("filters", list_filters, "List automatic answers", category="manage", policy="group"),
)
