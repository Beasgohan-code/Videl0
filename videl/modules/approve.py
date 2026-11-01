import config
# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Approvals
#  FallenRobot approve.py — bypass locks/blacklist/antiflood
#  Richgram cards and native action keyboards
# --------------------------------------------------------------------------------

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, CallbackQuery
from videl.utils.bot_ui import button as InlineKeyboardButton
from videl import bot
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc, sb
from videl.utils.rich_ui import rich_esc, rich_heading, rich_note, rich_table, rich_kv_table, rich_details, rich_button
from videl.utils.command_ui import rich_send, rich_edit
from videl.utils.db import approve_user, disapprove_user, is_approved, list_approved

try:
    from videl.utils.premium_emojis import pe
except Exception:
    def pe(k, fb=""):
        return fb

def _hdr(t, lvl=3):
    return rich_heading(t, level=lvl)

async def _resolve_target(m):
    if m.reply_to_message and m.reply_to_message.from_user:
        return m.reply_to_message.from_user.id, m.reply_to_message.from_user.first_name
    if len(m.command) > 1:
        arg = m.command[1]
        if arg.isascii() and arg.isdecimal():
            uid = int(arg)
            if 0 < uid <= 9_223_372_036_854_775_807:
                return uid, arg
            return None, None
        try:
            u = await bot.get_users(arg)
            return u.id, u.first_name
        except Exception:
            return None, None
    return None, None

def _uid_link(uid, name):
    return '<a href="tg://user?id=' + str(uid) + '">' + rich_esc(name or str(uid)) + '</a>'


_APPROVED_PAGE_SIZE = 10


def _approved_page(user_ids, page=0):
    users = sorted({int(uid) for uid in user_ids if isinstance(uid, int) and not isinstance(uid, bool) and 0 < uid <= 9_223_372_036_854_775_807})
    pages = max(1, (len(users) + _APPROVED_PAGE_SIZE - 1) // _APPROVED_PAGE_SIZE)
    page = min(max(int(page), 0), pages - 1)
    start = page * _APPROVED_PAGE_SIZE
    return users, users[start:start + _APPROVED_PAGE_SIZE], page, pages


def _approved_list_view(chat_id, page=0):
    users, visible, page, pages = _approved_page(list_approved(chat_id), page)
    if not users:
        text = rich_heading("Approved members", level=3) + rich_note("No members are approved in this group yet. Use <code>/approve</code> to add someone.")
        return text, InlineKeyboardMarkup([[InlineKeyboardButton("Close", callback_data="approve:close", icon="cross")]])
    offset = page * _APPROVED_PAGE_SIZE
    rows = [(f"<code>{offset + i}</code>", f'<a href="tg://user?id={uid}">{uid}</a>')
            for i, uid in enumerate(visible, 1)]
    text = (rich_heading(f"✅ Approved members · {len(users)}", level=2)
            + rich_note("Approved members bypass this group's content locks, blacklist, anti-flood and join verification.")
            + rich_note(f"Showing {offset + 1}–{offset + len(visible)} of {len(users)} · page {page + 1}/{pages}.")
            + rich_table(["No.", "Member ID"], rows)
            + rich_note("Choose Remove to revoke approval; use /approve to add by reply, ID or username."))
    return text, _approved_keyboard(users, allow_clear=True, page=page)


def _approved_keyboard(user_ids, *, allow_clear=False, page=0):
    """Render bounded remove controls and navigation for one stable page."""
    users, visible, page, pages = _approved_page(user_ids, page)
    rows = []
    for index in range(0, len(visible), 2):
        rows.append([
            InlineKeyboardButton(f"Remove {uid}", callback_data=f"approve:rm:{uid}", style="danger", icon="ios_trash")
            for uid in visible[index:index + 2]
        ])
    if pages > 1:
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("← Previous", callback_data=f"approve:page:{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{pages}", callback_data=f"approve:page:{page}"))
        if page + 1 < pages: nav.append(InlineKeyboardButton("Next →", callback_data=f"approve:page:{page + 1}"))
        rows.append(nav)
    if allow_clear and len(users) > 1:
        rows.append([InlineKeyboardButton("Clear all", callback_data="approve:clear", style="danger", icon="ios_trash")])
    rows.append([InlineKeyboardButton("Close", callback_data="approve:close", icon="cross")])
    return InlineKeyboardMarkup(rows)

@bot.on_message(filters.command('approve', prefixes=config.COMMAND_PREFIX_LIST) & filters.group & group_allowed & user_allowed)
async def approve_cmd(_, m):
    if not await is_user_authorized(m):
        return
    uid, name = await _resolve_target(m)
    if not uid:
        body = _hdr(sc("approve user"),3) + rich_note(pe("diamond","") + " " + sc("usage") + ": <code>/approve</code> " + sc("reply to user or id") + " " + pe("small",""))
        body += rich_table([sc("example")], [("<code>/approve</code> — " + sc("reply"),), ("<code>/approve @username</code>",), ("<code>/approve 123456789</code>",)])
        body += "<p>" + rich_button(pe("eyes","👀") + " " + sc("view approved"), callback_data="approve:list") + "</p>"
        return await rich_send(bot, m.chat.id, body)
    if is_approved(m.chat.id, uid):
        body = _hdr(pe("warn","⚠️") + " " + sc("already approved"),3) + rich_kv_table([(pe("target","") + " " + sc("user"), _uid_link(uid, name)), (pe("hex","") + " " + sc("id"), "<code>" + str(uid) + "</code>")])
        body += "<p>" + rich_button(pe("cross","❌") + " " + sc("unapprove"), callback_data="approve:rm:" + str(uid), style="danger") + "</p>"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("cross","❌") + " " + sc("unapprove"), callback_data="approve:rm:" + str(uid))]])
        return await rich_send(bot, m.chat.id, body, reply_markup=kb)
    approve_user(m.chat.id, uid)
    body = _hdr(pe("check","✅") + " " + sc("approved"),3) + rich_kv_table([(pe("target","") + " " + sc("user"), _uid_link(uid, name)), (pe("hex","") + " " + sc("id"), "<code>" + str(uid) + "</code>"), (pe("diamond","") + " " + sc("effect"), sc("bypass locks / blacklist / antiflood / captcha"))])
    body += "<p>" + rich_button(pe("cross","❌") + " " + sc("unapprove"), callback_data="approve:rm:" + str(uid), style="danger") + " " + rich_button(pe("eyes","👀") + " " + sc("view all"), callback_data="approve:list") + "</p>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("cross","❌") + " " + sc("unapprove"), callback_data="approve:rm:" + str(uid)), InlineKeyboardButton(pe("eyes","👀") + " " + sc("view all"), callback_data="approve:list")]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command('unapprove', prefixes=config.COMMAND_PREFIX_LIST) & filters.group & group_allowed & user_allowed)
async def unapprove_cmd(_, m):
    if not await is_user_authorized(m):
        return
    uid, name = await _resolve_target(m)
    if not uid:
        return await rich_send(bot, m.chat.id, _hdr(sc("unapprove"),3) + rich_note("<code>/unapprove</code> " + sc("reply to user to remove approval") + " " + pe("small","")))
    if not is_approved(m.chat.id, uid):
        body = _hdr(pe("warn","⚠️") + " " + sc("not approved"),3) + rich_note("<code>" + str(uid) + "</code> " + sc("is not approved") + " " + pe("diamond",""))
        return await rich_send(bot, m.chat.id, body)
    disapprove_user(m.chat.id, uid)
    body = _hdr(pe("cross","❌") + " " + sc("unapproved"),3) + rich_kv_table([(pe("circle","") + " " + sc("user"), "<code>" + str(uid) + "</code> " + rich_esc(name or ""))])
    body += "<p>" + rich_button(pe("eyes","👀") + " " + sc("view all"), callback_data="approve:list") + "</p>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("eyes","👀") + " " + sc("view all"), callback_data="approve:list")]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command('approved', prefixes=config.COMMAND_PREFIX_LIST) & filters.group & group_allowed & user_allowed)
async def approved_list(_, m):
    if not await is_user_authorized(m):
        return
    body, markup = _approved_list_view(m.chat.id)
    await rich_send(bot, m.chat.id, body, reply_markup=markup)

@bot.on_message(filters.command(["approval"], prefixes=config.COMMAND_PREFIX_LIST) & filters.group & group_allowed & user_allowed)
async def approval_info(_, m):
    if not await is_user_authorized(m):
        return
    if getattr(m, "reply_to_message", None) is not None or len(getattr(m, "command", []) or []) > 1:
        uid, name = await _resolve_target(m)
        if not uid:
            return await rich_send(bot, m.chat.id,
                rich_heading("Check approval status", level=3)
                + rich_note("Reply to a user or send <code>/approval user_id</code> / <code>/approval @username</code>."))
        approved = is_approved(m.chat.id, int(uid))
        status = "Approved" if approved else "Not approved"
        body = (rich_heading("Approved-user status", level=3)
                + rich_kv_table([("User", _uid_link(uid, name)), ("Status", status),
                    ("Group", str(m.chat.id))]))
        if approved:
            body += rich_note("This user bypasses this group's content locks, blacklist, anti-flood and join verification.")
        return await rich_send(bot, m.chat.id, body)
    arr = list_approved(m.chat.id)
    count = len(arr)
    member_word = "member" if count == 1 else "members"
    body = (
        rich_heading("✅ Approved member access", level=2)
        + rich_note(
            f"<b>{count} approved {member_word}.</b> They bypass content locks, "
            "the blacklist, anti-flood, and join verification in this group."
        )
        + rich_kv_table([
            ("View the list", "<code>/approved</code>"),
            ("Add a member", "<code>/approve</code> · reply to them or use a user ID"),
            ("Remove a member", "<code>/unapprove</code> · reply to them or use a user ID"),
        ])
    )
    body += "<p>" + rich_button("👀 View approved members", callback_data="approve:list") + "</p>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👀 View approved members", callback_data="approve:list")]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_callback_query(filters.regex(r"^approve:"))
async def approve_cbs(_, q):
    if not await is_user_authorized(q):
        return await q.answer(sc("admin only"), show_alert=True)
    chat_id = q.message.chat.id if q.message and q.message.chat else 0
    data = q.data or ""
    if data == "approve:list" or data.startswith("approve:page:"):
        page = 0
        if data != "approve:list":
            try:
                page_text = data.split(":", 2)[2]
                if not page_text.isascii() or not page_text.isdecimal() or len(page_text) > 6: raise ValueError
                page = int(page_text)
            except (ValueError, IndexError):
                return await q.answer("Invalid approved-list page.", show_alert=True)
        await q.answer()
        body, markup = _approved_list_view(chat_id, page)
        try:
            await rich_edit(q.message, body, reply_markup=markup)
        except Exception:
            pass
        return
    if data.startswith("approve:rm:"):
        try:
            raw_uid = data.split(":")[2]
            if not raw_uid.isascii() or not raw_uid.isdecimal() or len(raw_uid) > 19: raise ValueError
            uid = int(raw_uid)
            if not 0 < uid <= 9_223_372_036_854_775_807: raise ValueError
        except (ValueError, IndexError):
            return await q.answer(sc("invalid"), show_alert=True)
        if not is_approved(chat_id, uid):
            await q.answer("That user is no longer approved.", show_alert=True)
            body, markup = _approved_list_view(chat_id)
            try: await rich_edit(q.message, body, reply_markup=markup)
            except Exception: pass
            return
        if not disapprove_user(chat_id, uid):
            return await q.answer("Could not update the approved list. Try again.", show_alert=True)
        await q.answer("Member removed from the approved list.")
        body, markup = _approved_list_view(chat_id)
        try: await rich_edit(q.message, body, reply_markup=markup)
        except Exception: pass
        return
    if data == "approve:close":
        try:
            await q.message.delete()
        except Exception:
            pass
        await q.answer()
    if data == "approve:clear":
        from videl.utils.interactive_settings import engine
        from videl.utils.rich_ui import rich_note
        users = sorted({int(uid) for uid in list_approved(chat_id)
                        if isinstance(uid, int) and not isinstance(uid, bool) and 0 < uid <= 9_223_372_036_854_775_807})
        if len(users) < 2:
            return await q.answer("There are not enough approved members to clear.", show_alert=True)
        try:
            session = await engine.begin_preview(
                chat_id=chat_id, actor_id=int(q.from_user.id), target_chat_id=chat_id,
                workflow="approved_clear", values={"users": users}, timeout_seconds=600)
        except RuntimeError:
            return await q.answer("Another settings confirmation is active for this group. Finish or cancel it first.", show_alert=True)
        body = (rich_heading("Review approved-member removal", level=3)
                + rich_note(f"This will remove all {len(users)} currently approved members from this group's exemptions. No other group or setting will change."))
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("Clear approved list", callback_data=f"approve:clear:confirm:{session.token}", style="danger", icon="ios_trash"),
                                        InlineKeyboardButton("Cancel", callback_data=f"approve:clear:cancel:{session.token}", icon="cross")]])
        try:
            await rich_edit(q.message, body, reply_markup=markup)
            await engine.bind_prompt(session.token, chat_id=chat_id, actor_id=int(q.from_user.id), message_id=int(q.message.id))
        except Exception:
            await engine.cancel(session.token, chat_id=chat_id, actor_id=int(q.from_user.id))
            return await q.answer("Could not show the confirmation. No changes were made.", show_alert=True)
        return await q.answer("Review the affected count and confirm to continue.")
    if data.startswith("approve:clear:cancel:"):
        from videl.utils.interactive_settings import engine
        token = data.rsplit(":", 1)[-1]
        cancelled = await engine.cancel(token, chat_id=chat_id, actor_id=int(q.from_user.id))
        await q.answer("Cancelled." if cancelled else "This confirmation expired.")
        if cancelled:
            body, markup = _approved_list_view(chat_id)
            try: await rich_edit(q.message, body, reply_markup=markup)
            except Exception: pass
        return
    if data.startswith("approve:clear:confirm:"):
        from videl.utils.interactive_settings import engine
        token = data.rsplit(":", 1)[-1]
        session = await engine.get(token, chat_id=chat_id, actor_id=int(q.from_user.id), target_chat_id=chat_id)
        if session is None or session.workflow != "approved_clear":
            return await q.answer("This confirmation expired or belongs to another admin.", show_alert=True)

        async def authorize(target_chat_id, actor_id):
            return target_chat_id == chat_id and actor_id == int(q.from_user.id) and await is_user_authorized(q)

        async def save(snapshot):
            expected = sorted(snapshot.values.get("users", []))
            current = sorted({int(uid) for uid in list_approved(chat_id)
                              if isinstance(uid, int) and not isinstance(uid, bool) and 0 < uid <= 9_223_372_036_854_775_807})
            if current != expected:
                return False
            from videl.utils.db import get_db
            database = get_db()
            if database is None:
                return False
            try:
                database["approved"].delete_many({"chat": chat_id, "user": {"$in": expected}})
            except Exception:
                # A write may have reached Mongo before a transport error. Verify
                # the exact reviewed IDs before deciding whether retry is safe.
                pass
            try:
                remaining = database["approved"].count_documents({"chat": chat_id, "user": {"$in": expected}})
                return remaining == 0
            except Exception:
                return False

        outcome, _ = await engine.commit(token, chat_id=chat_id, actor_id=int(q.from_user.id),
            target_chat_id=chat_id, message_id=int(q.message.id), authorize=authorize, save=save)
        if outcome == "saved":
            await q.answer("Approved-member list cleared.")
            try: await rich_edit(q.message, rich_heading("✅ Approved-member list cleared", level=3) + rich_note("No members are currently approved in this group."))
            except Exception: pass
        elif outcome == "permission_denied":
            await q.answer("Current group-admin permission could not be verified. Nothing was changed.", show_alert=True)
        elif outcome == "save_failed":
            await q.answer("The list changed or storage did not confirm the removal. Refresh and review before retrying.", show_alert=True)
        else:
            await q.answer("This confirmation is stale or already being processed.", show_alert=True)
