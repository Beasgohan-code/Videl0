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
        if arg.isdigit():
            return int(arg), arg
        try:
            u = await bot.get_users(arg)
            return u.id, u.first_name
        except Exception:
            return None, None
    return None, None

def _uid_link(uid, name):
    return '<a href="tg://user?id=' + str(uid) + '">' + rich_esc(name or str(uid)) + '</a>'


def _approved_keyboard(user_ids, *, allow_clear=False):
    """Action keyboard mirrors the visible members without mutating callback data."""
    rows = []
    visible = list(user_ids[:28])
    for index in range(0, len(visible), 2):
        rows.append([
            InlineKeyboardButton(
                f"Remove {uid}", callback_data=f"approve:rm:{uid}",
                style="danger", icon="ios_trash",
            )
            for uid in visible[index:index + 2]
        ])
    if allow_clear and len(user_ids) > 1:
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
    arr = list_approved(m.chat.id)
    if not arr:
        body = (
            rich_heading("Approved members", level=3)
            + rich_note("No members are approved in this group yet. Use <code>/approve</code> to add someone.")
            + rich_details(
                "What approval changes",
                "Approved members bypass this group’s content locks, blacklist, anti-flood, and join verification.",
            )
        )
        return await rich_send(bot, m.chat.id, body)
    visible = arr[:28]
    rows = [
        (f"<code>{i}</code>", '<a href="tg://user?id=' + str(uid) + '">' + str(uid) + '</a>')
        for i, uid in enumerate(visible, 1)
    ]
    body = (
        rich_heading(f"✅ Approved members · {len(arr)}", level=2)
        + rich_note("Approved members bypass this group’s content locks, blacklist, anti-flood and join verification.")
        + rich_table(["No.", "Member ID"], rows)
    )
    if len(arr) > len(visible):
        body += rich_note(f"Showing {len(visible)} of {len(arr)} members. Use <code>/unapprove</code> by reply or user ID for someone not shown.")
    body += rich_note("Use a Remove button below to revoke approval, or reply to the member with <code>/unapprove</code>.")
    await rich_send(bot, m.chat.id, body, reply_markup=_approved_keyboard(arr, allow_clear=True))

@bot.on_message(filters.command(["approval"], prefixes=config.COMMAND_PREFIX_LIST) & filters.group & group_allowed & user_allowed)
async def approval_info(_, m):
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
    if data == "approve:list":
        await q.answer()
        arr = list_approved(chat_id)
        if not arr:
            try:
                await rich_edit(q.message, rich_heading("Approved members", level=3) + rich_note("No members are approved in this group yet. Use <code>/approve</code> to add someone."))
            except Exception:
                pass
            return
        visible = arr[:28]
        rows = [
            (f"<code>{i}</code>", '<a href="tg://user?id=' + str(uid) + '">' + str(uid) + '</a>')
            for i, uid in enumerate(visible, 1)
        ]
        body = (
            rich_heading(f"✅ Approved members · {len(arr)}", level=2)
            + rich_note("Choose a Remove button below to revoke approval.")
            + rich_table(["No.", "Member ID"], rows)
        )
        if len(arr) > len(visible):
            body += rich_note(f"Showing {len(visible)} of {len(arr)} members. Use <code>/unapprove</code> for someone not shown.")
        try:
            await rich_edit(q.message, body, reply_markup=_approved_keyboard(arr, allow_clear=True))
        except Exception:
            pass
        return
    if data.startswith("approve:rm:"):
        try:
            uid = int(data.split(":")[2])
        except Exception:
            return await q.answer(sc("invalid"), show_alert=True)
        disapprove_user(chat_id, uid)
        await q.answer("Member removed from the approved list.")
        arr = list_approved(chat_id)
        if not arr:
            try:
                await rich_edit(q.message, rich_heading("Approved members", level=3) + rich_note("No members are approved in this group yet. Use <code>/approve</code> to add someone."))
            except Exception:
                pass
            return
        visible = arr[:28]
        rows = [
            (f"<code>{i}</code>", '<a href="tg://user?id=' + str(uid) + '">' + str(uid) + '</a>')
            for i, uid in enumerate(visible, 1)
        ]
        body = (
            rich_heading(f"✅ Approved members · {len(arr)}", level=2)
            + rich_note("Updated approval list. Use a Remove button below to change another member’s access.")
            + rich_table(["No.", "Member ID"], rows)
        )
        if len(arr) > len(visible):
            body += rich_note(f"Showing {len(visible)} of {len(arr)} members. Use <code>/unapprove</code> for someone not shown.")
        try:
            await rich_edit(q.message, body, reply_markup=_approved_keyboard(arr, allow_clear=True))
        except Exception:
            pass
        return
    if data == "approve:close":
        try:
            await q.message.delete()
        except Exception:
            pass
        await q.answer()
    if data == "approve:clear":
        arr = list_approved(chat_id)
        for uid in arr:
            disapprove_user(chat_id, uid)
        await q.answer("Approved-member list cleared.")
        try:
            await rich_edit(q.message, rich_heading("✅ Approved-member list cleared", level=3) + rich_note("No members are currently approved in this group."))
        except Exception:
            pass
