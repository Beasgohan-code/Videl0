#  Videl © 2026 | Beasgohan-code
"""Saved notes and keyword filters.

``/save`` stores text or replied media, ``#name`` recalls it, and ``/filter``
answers keywords automatically. Both stores live in MongoDB per chat.
"""
from __future__ import annotations

import asyncio
import re
import secrets
import time
from collections import OrderedDict

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup

import config
from videl import LOGGER, bot
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.audit import record_bot
from videl.utils.bot_ui import button
from videl.utils.command_ui import rich_edit, rich_send, usage
from videl.utils.premium_emojis import pe

NOTES = "mgmt_notes"
FILTERS = "mgmt_filters"
_FILTER_DELETE_ACTIONS: OrderedDict[str, tuple[int, str, int, float]] = OrderedDict()
_FILTER_ACTION_TTL = 900
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
    try:
        if kind == "text":
            await bot.send_message(chat_id, content, reply_to_message_id=reply_to)
        elif kind == "photo":
            await bot.send_photo(chat_id, content, caption=caption, reply_to_message_id=reply_to)
        elif kind == "document":
            await bot.send_document(chat_id, content, caption=caption, reply_to_message_id=reply_to)
        elif kind == "video":
            await bot.send_video(chat_id, content, caption=caption, reply_to_message_id=reply_to)
        elif kind == "audio":
            await bot.send_audio(chat_id, content, caption=caption, reply_to_message_id=reply_to)
        elif kind == "sticker":
            await bot.send_sticker(chat_id, content, reply_to_message_id=reply_to)
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
    reply = reply[:400]
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


FILTER_PAGE_SIZE = 8


def _remember_filter_delete(chat_id: int, keyword: str, page: int) -> str:
    now = time.monotonic()
    for token, value in list(_FILTER_DELETE_ACTIONS.items()):
        if now - value[3] > _FILTER_ACTION_TTL:
            _FILTER_DELETE_ACTIONS.pop(token, None)
    token = secrets.token_urlsafe(6)
    _FILTER_DELETE_ACTIONS[token] = (chat_id, keyword, page, now)
    _FILTER_DELETE_ACTIONS.move_to_end(token)
    while len(_FILTER_DELETE_ACTIONS) > 4096:
        _FILTER_DELETE_ACTIONS.popitem(last=False)
    return token


def _filter_markup(documents, page: int, total: int, *, chat_id: int, can_manage: bool):
    rows = []
    if can_manage:
        for index, item in enumerate(documents):
            keyword = str(item.get("keyword", ""))
            label = re.sub(r"\s+", " ", keyword).strip()[:30] or "unnamed filter"
            token = _remember_filter_delete(chat_id, keyword, page)
            rows.append([button(f"🗑 Remove · {label}", callback_data=f"mgmt_filter:delete:{token}", style="danger")])
    pages = max(1, (total + FILTER_PAGE_SIZE - 1) // FILTER_PAGE_SIZE)
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(button("‹ Previous", callback_data=f"mgmt_filter:page:{page - 1}"))
        nav.append(button(f"{page + 1}/{pages}", callback_data="mgmt_filter:noop"))
        if page + 1 < pages:
            nav.append(button("Next ›", callback_data=f"mgmt_filter:page:{page + 1}"))
        rows.append(nav)
    if rows:
        rows.append([button("Close", callback_data="mgmt_filter:close")])
    return InlineKeyboardMarkup(rows) if rows else None


async def _filter_page(store, chat_id: int, page: int):
    def load():
        total = store.count_documents({"chat_id": chat_id})
        pages = max(1, (total + FILTER_PAGE_SIZE - 1) // FILTER_PAGE_SIZE)
        safe_page = min(max(0, page), pages - 1)
        documents = list(
            store.find({"chat_id": chat_id})
            .sort("keyword", 1)
            .skip(safe_page * FILTER_PAGE_SIZE)
            .limit(FILTER_PAGE_SIZE)
        )
        return total, safe_page, documents
    return await asyncio.to_thread(load)


async def _live_group_admin(client, chat_id: int, user_id: int) -> bool:
    if not user_id:
        return False
    try:
        member = await client.get_chat_member(chat_id, user_id)
    except Exception:
        return False
    return getattr(member, "status", None) in {
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR,
    }


def _filter_page_text(total: int, documents, page: int, can_manage: bool) -> str:
    if not total:
        return heading("📝 No automatic filters yet", 3) + body("Create one with <code>/filter keyword response</code>.")
    rows = [
        (f"{pe('ios_symbols')} <code>{escape(str(item.get('keyword', '')))}</code>", escape((item.get("reply") or "")[:72]))
        for item in documents
    ]
    pages = max(1, (total + FILTER_PAGE_SIZE - 1) // FILTER_PAGE_SIZE)
    text = (
        heading("📝 Automatic filters", 3)
        + body(f"{total} filter{'s' if total != 1 else ''} in this group · page {page + 1}/{pages}.")
        + table(rows)
    )
    text += body("Tap a filter button below to remove it." if can_manage else "Only a current group admin can remove filters; use <code>/stopfilter keyword</code>.")
    return text


async def list_filters(ctx) -> Screen:
    store = _filters()
    if store is None:
        raise CommandError("MongoDB is not connected.")
    chat_id = ctx.message.chat.id
    total, page, documents = await _filter_page(store, chat_id, 0)
    user = ctx.user
    can_manage = await _live_group_admin(ctx.client, chat_id, getattr(user, "id", 0))
    return Screen(
        _filter_page_text(total, documents, page, can_manage),
        _filter_markup(documents, page, total, chat_id=chat_id, can_manage=can_manage),
    )


@bot.on_callback_query(filters.regex(r"^mgmt_filter:"))
async def filter_management_callback(client, query: CallbackQuery) -> None:
    message = getattr(query, "message", None)
    if message is None or base.chat_kind(message) not in {"group", "supergroup"}:
        await query.answer("Open this panel in the group.", show_alert=True)
        return
    parts = (query.data or "").split(":")
    if len(parts) < 2 or parts[0] != "mgmt_filter":
        await query.answer("This filter action is invalid.", show_alert=True)
        return
    action = parts[1]
    if action == "close":
        await query.answer("Panel closed")
        await rich_edit(message, heading("Filter panel closed", 3) + body("Run <code>/filters</code> to open it again."), navigation=False, reply_markup=None)
        return
    if action == "noop":
        await query.answer()
        return
    if action not in {"page", "delete"} or len(parts) != 3:
        await query.answer("This filter action is invalid.", show_alert=True)
        return
    try:
        if not parts[2].isdigit() or len(parts[2]) > 6:
            if action != "delete" or not re.fullmatch(r"[A-Za-z0-9_-]{6,12}", parts[2]):
                raise ValueError
        page = int(parts[2]) if action == "page" else 0
        token = parts[2] if action == "delete" else ""
    except ValueError:
        await query.answer("This filter action is invalid.", show_alert=True)
        return

    chat_id = message.chat.id
    actor_id = getattr(getattr(query, "from_user", None), "id", 0)
    can_manage = await _live_group_admin(client, chat_id, actor_id)
    if action == "delete" and not can_manage:
        await query.answer("A current group admin is required to remove filters.", show_alert=True)
        return
    store = _filters()
    if store is None:
        await query.answer("The filters database is unavailable.", show_alert=True)
        return

    if action == "delete":
        token_entry = _FILTER_DELETE_ACTIONS.get(token)
        if token_entry is None or time.monotonic() - token_entry[3] > _FILTER_ACTION_TTL:
            _FILTER_DELETE_ACTIONS.pop(token, None)
            await query.answer("This button expired. Reopen /filters and try again.", show_alert=True)
            return
        token_chat_id, keyword, page, _created = token_entry
        if token_chat_id != chat_id:
            await query.answer("This filter button belongs to another group.", show_alert=True)
            return
        _FILTER_DELETE_ACTIONS.pop(token, None)
        result = await asyncio.to_thread(store.delete_one, {"chat_id": chat_id, "keyword": keyword})
        if result.deleted_count:
            await asyncio.to_thread(
                record_bot, chat_id, "filter", action="filter_delete",
                detail=f"keyword: {keyword}"[:80], actor=actor_id,
            )
            await query.answer("Filter removed")
        else:
            await query.answer("That filter was already removed")
    else:
        await query.answer()

    total, page, documents = await _filter_page(store, chat_id, page)
    can_manage = await _live_group_admin(client, chat_id, actor_id)
    await rich_edit(
        message,
        _filter_page_text(total, documents, page, can_manage),
        reply_markup=_filter_markup(documents, page, total, chat_id=chat_id, can_manage=can_manage),
    )

@bot.on_message(filters.group, group=17)
async def filter_watcher(_, message) -> None:
    raw_text = message.text or ""
    text = raw_text.casefold().strip()
    user = getattr(message, "from_user", None)
    if not text or user is None or getattr(user, "is_bot", False):
        return
    # Filters answer conversation, not bot commands. This prevents a keyword
    # such as "ban" or "rules" from adding noise to management actions.
    if re.match(rf"^{config.COMMAND_PREFIX_PATTERN}\w+", text):
        return
    store = _filters()
    if store is None:
        return
    documents = await asyncio.to_thread(lambda: list(store.find({"chat_id": message.chat.id}).limit(100)))
    matches = [
        item for item in documents
        if isinstance(item.get("keyword"), str)
        and item["keyword"].strip()
        and item["keyword"].casefold() in text
        and isinstance(item.get("reply"), str)
        and item["reply"]
    ]
    if not matches:
        return
    # Prefer the most specific phrase; storage order must not change which
    # automatic answer wins when filters overlap (e.g. "hello" / "hello all").
    selected = max(matches, key=lambda item: len(item["keyword"].strip()))
    try:
        await message.reply_text(selected["reply"], parse_mode=None)
    except Exception:
        LOGGER.debug("Filter reply failed", exc_info=True)


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
