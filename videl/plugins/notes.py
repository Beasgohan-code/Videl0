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
from types import SimpleNamespace

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import CallbackQuery, ForceReply, InlineKeyboardMarkup

import config
from videl import LOGGER, bot
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.audit import record_bot
from videl.utils.bot_ui import button
from videl.utils.command_ui import rich_edit, rich_send, usage
from videl.utils.premium_emojis import pe
from videl.utils.interactive_settings import Step, engine
from videl.utils import filter_store

NOTES = "mgmt_notes"
FILTERS = "mgmt_filters"
_FILTER_ACTIONS: OrderedDict[str, tuple[str, int, dict, int, float]] = OrderedDict()
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
    keyword = tokens[0][:filter_store.MAX_KEYWORD]
    reply = " ".join(tokens[1:])[:filter_store.MAX_REPLY]
    replied = getattr(ctx.message, "reply_to_message", None)
    if replied is not None and getattr(replied, "text", None):
        reply = replied.text[:filter_store.MAX_REPLY]
    database = base.db()
    if database is None:
        raise CommandError("MongoDB is not connected; the filter was not saved.")
    try:
        saved, outcome = await asyncio.to_thread(
            filter_store.put_filter, database, ctx.message.chat.id, keyword, reply, mode="upsert")
    except (filter_store.FilterStoreConflict, filter_store.FilterStoreError, ValueError) as error:
        raise CommandError(str(error)) from None
    await asyncio.to_thread(
        record_bot, ctx.message.chat.id, "filter",
        action="filter_add" if outcome == "created" else "filter_update",
        detail=f"text filter {outcome}",
        actor=getattr(getattr(ctx.message, "from_user", None), "id", None),
    )
    return Screen(heading("Filter saved", 3)
                  + body(f"<code>{escape(saved['keyword'])}</code> → {escape(saved['reply'][:120])}"))


async def remove_filter(ctx) -> Screen:
    tokens = ctx.command.arguments.split()
    if not tokens:
        return Screen(usage("/stopfilter hello", "Stops one automatic answer."))
    try:
        keyword = filter_store.normalize_keyword(tokens[0])
    except ValueError as error:
        raise CommandError(str(error)) from None
    database = base.db()
    if database is None:
        raise CommandError("MongoDB is not connected; no filter was removed.")
    try:
        removed = await asyncio.to_thread(filter_store.delete_filter_by_keyword,
                                          database, ctx.message.chat.id, keyword)
    except (filter_store.FilterStoreConflict, filter_store.FilterStoreError, ValueError) as error:
        raise CommandError(str(error)) from None
    if not removed:
        return Screen(heading("Filter not found", 3) + body(f"No filter named <code>{escape(keyword)}</code>."))
    await asyncio.to_thread(
        record_bot, ctx.message.chat.id, "filter", action="filter_delete",
        detail="text filter removed",
        actor=getattr(getattr(ctx.message, "from_user", None), "id", None),
    )
    return Screen(heading("Filter removed", 3) + body(f"<code>{escape(keyword)}</code> is silent again."))


FILTER_PAGE_SIZE = 8


def _remember_filter_action(action: str, chat_id: int, item: dict, page: int) -> str:
    now = time.monotonic()
    for token, value in list(_FILTER_ACTIONS.items()):
        if now - value[4] > _FILTER_ACTION_TTL:
            _FILTER_ACTIONS.pop(token, None)
    token = secrets.token_urlsafe(6)
    snapshot = {key: item.get(key) for key in ("_id", "keyword", "reply")}
    _FILTER_ACTIONS[token] = (action, int(chat_id), snapshot, int(page), now)
    _FILTER_ACTIONS.move_to_end(token)
    while len(_FILTER_ACTIONS) > 4096:
        _FILTER_ACTIONS.popitem(last=False)
    return token


def _filter_markup(documents, page: int, total: int, *, chat_id: int, can_manage: bool):
    rows = []
    if can_manage:
        for item in documents:
            keyword = str(item.get("keyword", ""))
            label = re.sub(r"\s+", " ", keyword).strip()[:24] or "unnamed filter"
            edit_token = _remember_filter_action("edit", chat_id, item, page)
            delete_token = _remember_filter_action("delete", chat_id, item, page)
            rows.append([button(f"Edit · {label}", callback_data=f"mgmt_filter:edit:{edit_token}"),
                         button(f"Remove · {label}", callback_data=f"mgmt_filter:delete:{delete_token}", style="danger")])
        rows.append([button("＋ Add filter", callback_data="mgmt_filter:add", style="primary")])
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
    text += body("Edit or remove a filter below, or add a new filter." if can_manage else "Only a current group admin can edit or remove filters; use <code>/stopfilter keyword</code>.")
    return text


def _filter_preview(session):
    original = session.values.get("original")
    keyword = session.values["keyword"]
    reply = session.values["reply"]
    mode = "Edit existing filter" if original else "Add new filter"
    rows = [("Trigger keyword", f"<code>{escape(keyword)}</code>")]
    if original:
        rows.extend([("Current keyword", f"<code>{escape(str(original.get('keyword') or ''))}</code>"),
                     ("Current response", f"<pre>{escape(str(original.get('reply') or ''))}</pre>")])
    rows.append(("New response", f"<pre>{escape(reply)}</pre>"))
    text = (heading(mode + " preview", 3) + table(rows)
            + body("This is a plain-text response. Nothing has changed until you confirm Save."))
    keyboard = InlineKeyboardMarkup([
        [button("Save", callback_data=f"filter_edit:{session.token}:save", style="primary"),
         button("Edit Again", callback_data=f"filter_edit:{session.token}:edit")],
        [button("Cancel", callback_data=f"filter_edit:{session.token}:cancel", style="danger"),
         button("Back to filters", callback_data=f"filter_edit:{session.token}:back")],
    ])
    return text, keyboard


async def _send_filter_prompt(client, session, error: str | None = None):
    step = session.current_step
    if step is None:
        return None
    original = session.values.get("original") or {}
    current = ""
    if step.key == "keyword" and original.get("keyword"):
        current = f" Current keyword: <code>{escape(original['keyword'])}</code>."
    elif step.key == "reply" and original.get("reply"):
        current = f" Current response: <code>{escape(str(original['reply'])[:120])}</code>."
    prompt = (heading("Filter editor", 3)
              + body((escape(error) + " ") if error else "")
              + body(f"{escape(step.prompt)}{current} Reply to this prompt. Use /cancel to discard the draft."))
    sent = await client.send_message(session.chat_id, prompt,
                                     reply_markup=ForceReply(selective=True))
    await engine.bind_prompt(session.token, chat_id=session.chat_id,
                             actor_id=session.actor_id, message_id=int(sent.id))
    return sent


async def start_filter_editor(client, panel, chat_id: int, actor_id: int, *, mode="add", original=None, interaction_chat_id=None):
    if mode not in {"add", "edit"}:
        raise ValueError("Unknown filter editor mode.")
    if _filters() is None:
        raise filter_store.FilterStoreError("The filters database is unavailable; nothing changed.")
    original_snapshot = None
    if mode == "edit":
        if not isinstance(original, dict) or "_id" not in original:
            raise filter_store.FilterStoreConflict("This filter is no longer available. Reopen /filters.")
        original_snapshot = {key: original.get(key) for key in ("_id", "keyword", "reply")}
    interaction_chat_id = int(chat_id if interaction_chat_id is None else interaction_chat_id)
    session = await engine.begin(
        chat_id=interaction_chat_id, actor_id=int(actor_id), target_chat_id=int(chat_id),
        workflow=f"filter_{mode}",
        steps=(Step("keyword", "Send a trigger keyword (1–64 characters).", max_length=64),
               Step("reply", "Send the plain-text response (1–400 characters).", max_length=400)),
        timeout_seconds=600,
    )
    if original_snapshot is not None:
        session.values["original"] = original_snapshot
    try:
        await rich_edit(panel,
                        heading("Filter editor started", 3)
                        + body("Reply to each prompt. Your existing filter remains unchanged until you save the preview."),
                        reply_markup=None)
        await _send_filter_prompt(client, session)
    except Exception:
        await engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=int(actor_id))
        raise filter_store.FilterStoreError("Could not start the filter editor; nothing changed.") from None
    return session


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
    actor = getattr(query, "from_user", None)
    if message is None or actor is None or base.chat_kind(message) not in {"group", "supergroup"}:
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
    if action == "add":
        if len(parts) != 2 or not await _live_group_admin(client, message.chat.id, actor.id):
            await query.answer("A current group admin is required to add filters.", show_alert=True)
            return
        try:
            await start_filter_editor(client, message, message.chat.id, actor.id, mode="add")
        except (filter_store.FilterStoreConflict, filter_store.FilterStoreError, RuntimeError) as error:
            await query.answer(str(error), show_alert=True)
            return
        await query.answer("Reply to the prompts; nothing is saved until you confirm.")
        return
    if action not in {"page", "delete", "edit"} or len(parts) != 3:
        await query.answer("This filter action is invalid.", show_alert=True)
        return
    if action == "page":
        if not parts[2].isdigit() or len(parts[2]) > 6:
            await query.answer("This filter page is invalid.", show_alert=True)
            return
        page, token = int(parts[2]), ""
    else:
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,12}", parts[2]):
            await query.answer("This filter action is invalid.", show_alert=True)
            return
        page, token = 0, parts[2]

    chat_id, actor_id = int(message.chat.id), int(actor.id)
    can_manage = await _live_group_admin(client, chat_id, actor_id)
    if action in {"delete", "edit"} and not can_manage:
        await query.answer("A current group admin is required to change filters.", show_alert=True)
        return
    store = _filters()
    if store is None:
        await query.answer("The filters database is unavailable.", show_alert=True)
        return

    if action in {"delete", "edit"}:
        token_entry = _FILTER_ACTIONS.get(token)
        if token_entry is None or time.monotonic() - token_entry[4] > _FILTER_ACTION_TTL:
            _FILTER_ACTIONS.pop(token, None)
            await query.answer("This button expired. Reopen /filters and try again.", show_alert=True)
            return
        token_action, token_chat_id, original, page, _created = token_entry
        if token_action != action or token_chat_id != chat_id:
            await query.answer("This filter button belongs to another action or group.", show_alert=True)
            return
        _FILTER_ACTIONS.pop(token, None)
        if action == "edit":
            try:
                current = await asyncio.to_thread(store.find_one,
                                                  {"_id": original["_id"], "chat_id": chat_id})
            except Exception:
                await query.answer("Could not verify this filter; reopen /filters and try again.", show_alert=True)
                return
            if current is None or current.get("keyword") != original.get("keyword") or current.get("reply") != original.get("reply"):
                await query.answer("This filter changed or was removed. Refresh the filter list.", show_alert=True)
                return
            try:
                await start_filter_editor(client, message, chat_id, actor_id,
                                          mode="edit", original=original)
            except (filter_store.FilterStoreConflict, filter_store.FilterStoreError, RuntimeError) as error:
                await query.answer(str(error), show_alert=True)
                return
            await query.answer("Reply to the prompts; the existing filter stays unchanged until Save.")
            return
        try:
            await asyncio.to_thread(filter_store.delete_filter_by_id, base.db(), chat_id, original)
        except (filter_store.FilterStoreConflict, filter_store.FilterStoreError) as error:
            await query.answer(str(error), show_alert=True)
        else:
            await asyncio.to_thread(record_bot, chat_id, "filter", action="filter_delete",
                                    detail="text filter removed", actor=actor_id)
            await query.answer("Filter removed")
    else:
        await query.answer()

    total, page, documents = await _filter_page(store, chat_id, page)
    can_manage = await _live_group_admin(client, chat_id, actor_id)
    await rich_edit(
        message,
        _filter_page_text(total, documents, page, can_manage),
        reply_markup=_filter_markup(documents, page, total, chat_id=chat_id, can_manage=can_manage),
    )

async def _filter_session_authorized(client, session) -> bool:
    interaction_chat_id = int(session.chat_id)
    target_chat_id = int(session.target_chat_id)
    actor_id = int(session.actor_id)
    if interaction_chat_id == target_chat_id:
        return await _live_group_admin(client, target_chat_id, actor_id)
    if interaction_chat_id != actor_id:
        return False
    from videl.app.connections import connected_target
    group, error = await connected_target(client, actor_id, expected_chat_id=target_chat_id)
    return group is not None and error is None


@bot.on_message((filters.group | filters.private) & filters.incoming & (filters.text | filters.media), group=3)
async def filter_editor_message(client, message) -> None:
    user = getattr(message, "from_user", None)
    if user is None:
        return
    interaction_chat_id, actor_id = int(message.chat.id), int(user.id)
    if base.chat_kind(message) == "private" and interaction_chat_id != actor_id:
        return
    session = await engine.for_owner(chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow not in {"filter_add", "filter_edit"}:
        return
    chat_id = int(session.target_chat_id)
    if not await _filter_session_authorized(client, session):
        await engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        return await client.send_message(interaction_chat_id, "Connection or current group-admin access changed. Filter draft discarded; nothing was saved.")
    raw_text = getattr(message, "text", None)
    text = str(raw_text or "")
    tokens = text.strip().split(maxsplit=1)
    if tokens and tokens[0].split("@", 1)[0].casefold() == "/cancel":
        await engine.cancel(session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        await client.send_message(interaction_chat_id, "Filter editing cancelled. Nothing was saved.")
        return
    reply = getattr(message, "reply_to_message", None)
    if getattr(reply, "id", None) != session.expected_message_id:
        return
    if raw_text is None:
        await _send_filter_prompt(client, session, "Only plain-text keywords and responses are supported.")
        return
    if tokens and tokens[0].startswith("/"):
        return
    step = session.current_step
    value = text
    normalized_keyword = None
    if step and step.key == "keyword":
        try:
            normalized_keyword = filter_store.normalize_keyword(text)
        except ValueError as error:
            await _send_filter_prompt(client, session, str(error))
            return
        value = normalized_keyword
    result = await engine.capture(session.token, chat_id=interaction_chat_id, actor_id=actor_id,
                                  target_chat_id=chat_id,
                                  reply_to_message_id=getattr(reply, "id", None), value=value)
    if result.status == "invalid":
        await _send_filter_prompt(client, result.session, result.error or "That value is invalid.")
        return
    if result.status in {"stale", "expired", "unauthorized"}:
        return
    if normalized_keyword is not None:
        result.session.values["keyword"] = normalized_keyword
    if result.status == "accepted":
        await _send_filter_prompt(client, result.session)
        return
    if result.status != "preview":
        return
    text_preview, keyboard = _filter_preview(result.session)
    try:
        preview = await client.send_message(interaction_chat_id, text_preview, reply_markup=keyboard)
        await engine.bind_prompt(result.session.token, chat_id=interaction_chat_id, actor_id=actor_id,
                                 message_id=int(preview.id))
    except Exception:
        await engine.cancel(result.session.token, chat_id=interaction_chat_id, actor_id=actor_id)
        LOGGER.debug("Filter preview could not be delivered", exc_info=True)


@bot.on_callback_query(filters.regex(r"^filter_edit:[A-Za-z0-9_-]{1,24}:(?:save|edit|cancel|back)$"))
async def filter_editor_callback(client, query: CallbackQuery) -> None:
    message = getattr(query, "message", None)
    actor = getattr(query, "from_user", None)
    if message is None or actor is None:
        return await query.answer("Open the filter editor from a valid Telegram account.", show_alert=True)
    interaction_kind = base.chat_kind(message)
    connected_dm = interaction_kind == "private" and int(message.chat.id) == int(actor.id)
    if interaction_kind not in {"group", "supergroup"} and not connected_dm:
        return await query.answer("This filter editor is unavailable in this chat.", show_alert=True)
    try:
        _, token, action = str(query.data).split(":")
    except ValueError:
        return await query.answer("This filter action is invalid.", show_alert=True)
    interaction_chat_id, actor_id = int(message.chat.id), int(actor.id)
    session = await engine.get(token, chat_id=interaction_chat_id, actor_id=actor_id)
    if session is None or session.workflow not in {"filter_add", "filter_edit"}:
        return await query.answer("This filter edit expired or belongs to another admin.", show_alert=True)
    chat_id = int(session.target_chat_id)
    if connected_dm and interaction_chat_id != int(session.actor_id):
        return await query.answer("This private filter action is unavailable.", show_alert=True)
    if not connected_dm and chat_id != interaction_chat_id:
        return await query.answer("This filter editor belongs to another group.", show_alert=True)
    if action not in {"cancel", "back"} and not await _filter_session_authorized(client, session):
        await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        denial = ("Connection or current group-admin access changed. Nothing was saved." if connected_dm
                  else "Current group-admin status could not be verified. Nothing was saved.")
        return await query.answer(denial, show_alert=True)

    async def show_list():
        if connected_dm:
            from videl.plugins.settings import _screen
            screen = _screen(chat_id, "automations", connected_dm=True)
        else:
            context = SimpleNamespace(message=message, user=actor, client=client)
            screen = await list_filters(context)
        return await rich_edit(message, screen.html, reply_markup=screen.keyboard)

    if action in {"cancel", "back"}:
        await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Cancelled; nothing was saved." if action == "cancel" else "Back to filters.")
        return await show_list()
    if action == "edit":
        original = session.values.get("original")
        edited = await engine.edit_again(token, chat_id=interaction_chat_id, actor_id=actor_id,
                                         message_id=int(message.id))
        if edited is None:
            return await query.answer("This preview is no longer active.", show_alert=True)
        if original is not None:
            edited.values["original"] = original
        await rich_edit(message, heading("Edit filter again", 3)
                        + body("Reply to the keyword and response prompts. Nothing is saved yet."),
                        reply_markup=None)
        try:
            await _send_filter_prompt(client, edited)
        except Exception:
            await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
            return await query.answer("Could not restart the filter editor; nothing changed.", show_alert=True)
        return await query.answer("Reply to the prompts to revise the filter.")
    if action != "save":
        return await query.answer("This filter action is invalid.", show_alert=True)

    async def authorize(target_chat_id: int, user_id: int) -> bool:
        return await _filter_session_authorized(client, session)

    save_error = {"conflict": None, "storage": False}

    async def save(snapshot) -> bool:
        try:
            database = base.db()
            if snapshot.workflow == "filter_add":
                await asyncio.to_thread(filter_store.put_filter, database, snapshot.target_chat_id,
                                        snapshot.values["keyword"], snapshot.values["reply"], mode="create")
            else:
                await asyncio.to_thread(filter_store.edit_filter, database, snapshot.target_chat_id,
                                        snapshot.values["original"], snapshot.values["keyword"],
                                        snapshot.values["reply"])
            return True
        except filter_store.FilterStoreConflict as error:
            save_error["conflict"] = str(error)
            return False
        except (filter_store.FilterStoreError, ValueError):
            save_error["storage"] = True
            return False
        except Exception:
            save_error["storage"] = True
            return False

    outcome, _ = await engine.commit(token, chat_id=interaction_chat_id, actor_id=actor_id,
                                     target_chat_id=chat_id, message_id=int(message.id),
                                     authorize=authorize, save=save)
    if outcome == "saved":
        await asyncio.to_thread(
            record_bot, chat_id, "filter",
            action="filter_add" if session.workflow == "filter_add" else "filter_edit",
            detail="text filter added" if session.workflow == "filter_add" else "text filter edited",
            actor=actor_id,
        )
        await query.answer("Filter saved.")
        return await show_list()
    if outcome == "permission_denied":
        await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer("Current group-admin status could not be verified. Nothing was saved.", show_alert=True)
        return await show_list()
    if outcome == "save_failed" and save_error["conflict"]:
        await engine.cancel(token, chat_id=interaction_chat_id, actor_id=actor_id)
        await query.answer(save_error["conflict"], show_alert=True)
        return await show_list()
    if outcome == "save_failed":
        await query.answer("Could not save the filter. Nothing was reported as saved; retry from this preview.", show_alert=True)
        return
    if outcome == "expired":
        return await query.answer("This filter edit expired. Nothing was saved.", show_alert=True)
    return await query.answer("This filter preview is no longer active.", show_alert=True)


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


@bot.on_message(filters.group, group=19)
async def custom_command_watcher(client, message) -> None:
    raw = message.text or ""
    if not raw or raw[0] not in config.COMMAND_PREFIX_LIST:
        return
    user = getattr(message, "from_user", None)
    if user is None or getattr(user, "is_bot", False):
        return
    parts = raw.split(maxsplit=1)
    token = parts[0]
    match = re.fullmatch(rf"({config.COMMAND_PREFIX_PATTERN})([a-zA-Z][a-zA-Z0-9_]{{1,31}})(?:@([a-zA-Z0-9_]+))?", token)
    if not match:
        return
    name = match.group(2).lower()
    mention_bot = match.group(3)
    if mention_bot:
        me = await client.get_me()
        if mention_bot.casefold() != str(getattr(me, "username", "") or "").casefold():
            return
    database = base.db()
    if database is None:
        return
    from videl.utils.db import is_disabled
    if await asyncio.to_thread(is_disabled, message.chat.id, name):
        return
    try:
        row = await asyncio.to_thread(database["mgmt_custom_commands"].find_one,
                                      {"chat_id": message.chat.id, "name": name})
        if not row or not isinstance(row.get("response"), str):
            return
        first_name = str(getattr(user, "first_name", "") or "Guest")
        last_name = str(getattr(user, "last_name", "") or "")
        display = (first_name + (" " + last_name if last_name else "")).strip()
        username = str(getattr(user, "username", "") or "")
        values = {
            "name": display, "mention": "@" + username if username else display,
            "id": str(user.id), "chat": str(getattr(message.chat, "title", "") or "this chat"),
            "username": ("@" + username) if username else "",
            "args": parts[1] if len(parts) > 1 else "",
        }
        from videl.utils.custom_commands import allow_use, is_native, render
        if is_native(name):
            return
        allowed, _retry_after = allow_use(message.chat.id, name, user.id, row.get("cooldown_seconds", 0))
        if not allowed:
            return
        response = render(row["response"], values)
        if len(response.encode("utf-16-le")) // 2 > 4096:
            await message.reply_text("That custom command's reply is too long to send.", parse_mode=None)
            return
        await message.reply_text(response, parse_mode=None)
    except Exception:
        LOGGER.debug("Custom command reply failed", exc_info=True)


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
