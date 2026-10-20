# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Approvals ✦ Perfect
#  FallenRobot approve.py — bypass locks/blacklist/antiflood — better than Rose
#  Richgram perfect: premium costume + rich_button + rich_table + rich_details
# --------------------------------------------------------------------------------

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from videl import bot
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc, sb
from videl.utils.rich_ui import (
    rich_esc, rich_heading, rich_note, rich_table, rich_kv_table,
    rich_details, rich_button, rich_send, rich_edit
)
from videl.utils.db import approve_user, disapprove_user, is_approved, list_approved

try:
    from videl.utils.premium_emojis import pe
except Exception:
    def pe(k, fb=""):
        return fb

def _hdr(t, lvl=3):
    return rich_heading(pe("orb","") + " " + t + " " + pe("spark",""), level=lvl)

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

@bot.on_message(filters.command(["approve","addapprove"]) & filters.group & group_allowed & user_allowed)
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

@bot.on_message(filters.command(["unapprove","rmapprove","disapprove"]) & filters.group & group_allowed & user_allowed)
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

@bot.on_message(filters.command(["approved","approvelist"]) & filters.group & group_allowed & user_allowed)
async def approved_list(_, m):
    arr = list_approved(m.chat.id)
    if not arr:
        body = _hdr(pe("circle","") + " " + sc("approved users") + " — 0",3) + rich_note(pe("line","") + " " + sc("no approved users yet") + " • " + pe("diamond","") + " <code>/approve</code> " + sc("to add one"))
        body += rich_details(pe("info","ℹ️") + " " + sc("what is approve"), sc("approved users bypass locks / blacklist / antiflood / captcha") + " " + pe("spark",""))
        return await rich_send(bot, m.chat.id, body)
    rows = []
    for i, uid in enumerate(arr[:28], 1):
        rows.append(("<code>" + str(i) + "</code>", '<a href="tg://user?id=' + str(uid) + '">' + str(uid) + '</a>', rich_button(pe("cross","❌") + " " + sc("remove"), callback_data="approve:rm:" + str(uid), style="danger")))
    extra = "<p>" + sc("and") + " " + str(len(arr)-28) + " " + sc("more") + "…</p>" if len(arr) > 28 else ""
    body = _hdr(sb("Approved") + " • " + str(len(arr)),2) + rich_table([pe("target","") + " #", pe("hex","") + " " + sc("user"), pe("diamond","") + " " + sc("action")], rows)
    if len(arr) > 1:
        body += "<p>" + rich_button(pe("cross","❌") + " " + sc("clear all"), callback_data="approve:clear", style="danger") + "</p>"
    body += rich_note(pe("line","") + " " + sc("tap remove to unapprove") + " • " + pe("diamond","") + " <code>/unapprove</code> " + sc("reply")) + extra
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("cross","❌") + " " + sc("unapprove first"), callback_data="approve:rm:" + str(arr[0]))] if arr else [], [InlineKeyboardButton(pe("spark","") + " " + sc("close"), callback_data="approve:close")]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command(["approval"]) & filters.group & group_allowed & user_allowed)
async def approval_info(_, m):
    arr = list_approved(m.chat.id)
    body = _hdr(sc("approval") + " • " + str(len(arr)),3) + rich_note(pe("diamond","") + " " + sc("approved bypass locks/blacklist/antiflood"))
    body += rich_kv_table([(pe("circle","") + " " + sc("count"), "<code>" + str(len(arr)) + "</code>"), (pe("target","") + " " + sc("view"), "<code>/approved</code>")])
    body += "<p>" + rich_button(pe("eyes","👀") + " " + sc("view approved"), callback_data="approve:list") + "</p>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("eyes","👀") + " " + sc("view approved"), callback_data="approve:list")]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_callback_query(filters.regex(r"^approve:"))
async def approve_cbs(_, q):
    if not await is_user_authorized(q):
        return await q.answer(pe("warn","⚠️") + " " + sc("admin only"), show_alert=True)
    chat_id = q.message.chat.id if q.message and q.message.chat else 0
    data = q.data or ""
    if data == "approve:list":
        await q.answer()
        arr = list_approved(chat_id)
        if not arr:
            try:
                await rich_edit(q.message, _hdr(sc("no approved"),3))
            except Exception:
                pass
            return
        rows = [("<code>" + str(i) + "</code>", '<a href="tg://user?id=' + str(uid) + '">' + str(uid) + '</a>', rich_button(pe("cross","❌") + " " + sc("remove"), callback_data="approve:rm:" + str(uid), style="danger")) for i, uid in enumerate(arr[:28], 1)]
        body = _hdr(sb("Approved") + " • " + str(len(arr)),2) + rich_table([pe("target","") + " #", pe("hex","") + " " + sc("user"), pe("diamond","") + " " + sc("action")], rows)
        try:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("spark","") + " " + sc("close"), callback_data="approve:close")]])
            await rich_edit(q.message, body, reply_markup=kb)
        except Exception:
            pass
        return
    if data.startswith("approve:rm:"):
        try:
            uid = int(data.split(":")[2])
        except Exception:
            return await q.answer(pe("warn","⚠️") + " " + sc("invalid"), show_alert=True)
        disapprove_user(chat_id, uid)
        await q.answer(pe("check","✅") + " " + sc("unapproved") + " " + str(uid))
        arr = list_approved(chat_id)
        if not arr:
            try:
                await rich_edit(q.message, _hdr(pe("circle","") + " " + sc("no approved"),3))
            except Exception:
                pass
            return
        rows = [("<code>" + str(i) + "</code>", '<a href="tg://user?id=' + str(uid) + '">' + str(uid) + '</a>', rich_button(pe("cross","❌") + " " + sc("remove"), callback_data="approve:rm:" + str(uid), style="danger")) for i, uid in enumerate(arr[:28], 1)]
        body = _hdr(sb("Approved") + " • " + str(len(arr)),2) + rich_table([pe("target","") + " #", pe("hex","") + " " + sc("user"), pe("diamond","") + " " + sc("action")], rows)
        try:
            await rich_edit(q.message, body, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(pe("spark","") + " " + sc("close"), callback_data="approve:close")]]))
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
        await q.answer(pe("check","✅") + " " + sc("cleared"))
        try:
            await rich_edit(q.message, _hdr(pe("check","✅") + " " + sc("cleared all approved"),3))
        except Exception:
            pass
