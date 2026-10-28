# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Federations
#  PaulSonOfLars/tgbot + FallenRobot feds — Richgram UI
# --------------------------------------------------------------------------------

import re
from pyrogram import filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from videl.utils.bot_ui import button as InlineKeyboardButton
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc, sb
from videl.utils.rich_ui import rich_esc, rich_heading, rich_note, rich_table, rich_kv_table, rich_details, rich_button, rich_img
from videl.utils.command_ui import rich_send, rich_edit
from videl.utils.db import create_fed, delete_fed, get_fed, list_feds, join_fed_chat, leave_fed_chat, get_chat_fed, set_chat_fed, fban, unfban, get_fban, list_fbans, fed_add_admin, fed_remove_admin, fed_list_admins, is_fed_admin, get_fed_chats
import config
try:
    from videl.utils.premium_emojis import pe
except Exception:
    def pe(k, fb=""):
        return fb

_HERO = "https://iili.io/n5ClDil.jpg"
def _hdr(t, lvl=3):
    return rich_heading(t, level=lvl)
def _hero():
    return rich_img(_HERO)
def _fed_id(name):
    return re.sub(r"[^a-z0-9_]", "", name.lower().replace(" ", "_"))[:32]

async def _is_telegram_admin(client, chat_id, user_id):
    """Check Telegram's live role; bot owner/sudo status is not a group role."""
    if not user_id:
        return False
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return str(getattr(member.status, "value", member.status)).lower() in {"owner", "creator", "administrator"}
    except Exception:
        return False

async def _bot_can_ban(client, chat_id):
    """Federation membership is only useful when the bot can enforce bans."""
    try:
        me = await client.get_me()
        member = await client.get_chat_member(chat_id, me.id)
        status = str(getattr(member.status, "value", member.status)).lower()
        return status in {"owner", "creator"} or (status == "administrator" and bool(getattr(member, "can_restrict_members", False)))
    except Exception:
        return False

async def _enforce_existing_bans(chat_id, fid):
    applied, failed = [], []
    for record in list_fbans(fid):
        uid = record.get("user")
        try:
            await bot.ban_chat_member(chat_id, int(uid))
            applied.append(int(uid))
        except Exception:
            failed.append(uid)
    return applied, failed

def _is_fed_owner(fid, user_id):
    fed = get_fed(fid)
    return bool(fed and user_id and (fed.get("owner") == user_id or user_id == config.OWNER_ID))

def _is_fed_manager(fid, user_id):
    return bool(user_id and (user_id == config.OWNER_ID or is_fed_admin(fid, user_id)))

def _fed_pills(fid=""):
    if fid:
        return "<p>" + rich_button(pe("hex","") + " " + sc("info"), callback_data="fed:info:" + fid) + " " + rich_button(pe("cross","❌") + " " + sc("leave"), callback_data="fed:leave:" + fid, style="danger") + "</p>"
    return "<p>" + rich_button(pe("hex","") + " " + sc("my feds"), callback_data="fed:myfeds") + " " + rich_button(pe("target","") + " " + sc("my chats"), callback_data="fed:mychats") + "</p>"

@bot.on_message(filters.command("newfed", prefixes=config.COMMAND_PREFIX_LIST) & filters.group & group_allowed & user_allowed)
async def newfed_cmd(_, m):
    if not m.text or len(m.text.split(maxsplit=1)) < 2:
        body = _hero() + _hdr(sc("create federation"),2) + rich_note(pe("diamond","") + " " + sc("usage") + ": <code>/newfed &lt;name&gt;</code> " + pe("small","") + " " + sc("e.g.") + " <code>/newfed VidelElite</code>")
        body += rich_details(pe("info","ℹ️") + " " + sc("what is a federation"), rich_note(pe("line","") + " " + sc("group multiple chats under one global ban list") + "<br>" + pe("line","") + " " + sc("fban in one group → auto-ban in all fed chats")))
        body += _fed_pills()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("hex","") + " " + sc("my feds"), callback_data="fed:myfeds")]])
        return await rich_send(bot, m.chat.id, body, reply_markup=kb)
    if not await _is_telegram_admin(bot, m.chat.id, m.from_user.id if m.from_user else None):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("group admin only"),3))
    if not m.from_user:
        return
    name = m.text.split(maxsplit=1)[1].strip()
    if not 3 <= len(name) <= 48:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("name must be 3 to 48 characters"),3))
    fid = _fed_id(name)
    if not fid:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("name needs at least one Latin letter or number"),3))
    if not create_fed(fid, name, m.from_user.id):
        message = sc("fed exists") if get_fed(fid) else sc("could not create federation; try again")
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + message,3) + rich_note("<code>" + rich_esc(fid) + "</code>"))
    body = _hero() + _hdr(pe("check","✅") + " " + sc("federation created"),2) + rich_kv_table([(pe("target","") + " " + sc("name"), rich_esc(name)), (pe("hex","") + " " + sc("id"), "<code>" + rich_esc(fid) + "</code>"), (pe("circle","") + " " + sc("owner"), "<code>" + str(m.from_user.id) + "</code>")], headers=[pe("spark","") + " " + sc("federation"), ""])
    body += rich_note(pe("diamond","") + " " + sc("add groups") + ": <code>/joinfed " + rich_esc(fid) + "</code> " + pe("line","")) + _fed_pills(fid)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("hex","") + " " + sc("info"), callback_data="fed:info:" + fid), InlineKeyboardButton(pe("diamond","") + " " + sc("join this chat"), callback_data="fed:join:" + fid)],[InlineKeyboardButton(pe("eyes","👀") + " " + sc("my feds"), callback_data="fed:myfeds")]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command("delfed", prefixes=config.COMMAND_PREFIX_LIST) & filters.group & group_allowed & user_allowed)
async def delfed_cmd(_, m):
    if not await _is_telegram_admin(bot, m.chat.id, m.from_user.id if m.from_user else None):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("group admin only"),3))
    if not m.text or len(m.text.split(maxsplit=1)) < 2:
        return await rich_send(bot, m.chat.id, _hdr(sc("delete federation"),3) + rich_note("<code>/delfed &lt;fed_id&gt;</code>"))
    fid = m.text.split(maxsplit=1)[1].strip().lower()
    fed = get_fed(fid)
    if not fed:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("fed not found"),3))
    if not _is_fed_owner(fid, m.from_user.id if m.from_user else None):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("owner only"),3))
    warning = _hdr(pe("warn","⚠️") + " " + sc("delete federation?"),3)
    warning += rich_note(sc("This removes the shared ban list and federation admins. Existing Telegram group bans will remain until lifted separately."))
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(pe("cross","❌") + " " + sc("confirm delete"), callback_data="fed:delete:" + fid, style="danger")]])
    await rich_send(bot, m.chat.id, warning, reply_markup=keyboard)

@bot.on_message(filters.command(["joinfed","chatfed"], prefixes=config.COMMAND_PREFIX_LIST) & filters.group & group_allowed & user_allowed)
async def joinfed_cmd(_, m):
    if not await _is_telegram_admin(bot, m.chat.id, m.from_user.id if m.from_user else None):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("group admin only"),3))
    if not m.text or len(m.text.split(maxsplit=1)) < 2:
        return await rich_send(bot, m.chat.id, _hdr(sc("join federation"),3) + rich_note("<code>/joinfed &lt;fed_id&gt;</code>"))
    fid = m.text.split(maxsplit=1)[1].strip().lower()
    if not get_fed(fid):
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("fed not found"),3))
    existing = get_chat_fed(m.chat.id)
    if existing and existing != fid:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("chat already in another federation"),3) + rich_note("Leave <code>" + rich_esc(existing) + "</code> before joining another."))
    if not await _bot_can_ban(bot, m.chat.id):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("bot needs restrict members permission"),3))
    set_chat_fed(m.chat.id, fid)
    if get_chat_fed(m.chat.id) != fid:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("could not save federation membership"),3))
    applied, failed = await _enforce_existing_bans(m.chat.id, fid)
    body = _hdr(pe("check","✅") + " " + sc("joined federation"),3) + rich_kv_table([(pe("hex","") + " " + sc("fed"), "<code>" + rich_esc(fid) + "</code>"), (pe("target","") + " " + sc("chat"), "<code>" + str(m.chat.id) + "</code>"), (pe("ban","⛔️") + " " + sc("existing bans enforced"), "<code>" + str(len(applied)) + "/" + str(len(applied) + len(failed)) + "</code>")]) + _fed_pills(fid)
    if failed:
        body += rich_note(pe("warn","⚠️") + " " + sc("some existing bans could not be applied") + ": <code>" + rich_esc(", ".join(map(str, failed[:10]))) + ("…" if len(failed) > 10 else "") + "</code>")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("hex","") + " " + sc("info"), callback_data="fed:info:" + fid), InlineKeyboardButton(pe("cross","❌") + " " + sc("leave"), callback_data="fed:leave:" + fid)]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command("leavefed", prefixes=config.COMMAND_PREFIX_LIST) & filters.group & group_allowed & user_allowed)
async def leavefed_cmd(_, m):
    if not await _is_telegram_admin(bot, m.chat.id, m.from_user.id if m.from_user else None):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("group admin only"),3))
    cur = get_chat_fed(m.chat.id)
    if not cur:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("not in fed"),3))
    set_chat_fed(m.chat.id, None)
    if get_chat_fed(m.chat.id) is not None:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("could not save federation leave"),3))
    await rich_send(bot, m.chat.id, _hdr(pe("cross","❌") + " " + sc("left federation"),3) + rich_note("<code>" + rich_esc(cur) + "</code> " + pe("diamond","")))

@bot.on_message(filters.command("fban", prefixes=config.COMMAND_PREFIX_LIST) & group_allowed & user_allowed)
async def fban_cmd(_, m):
    uid = None
    reason = "No reason"
    if m.reply_to_message and m.reply_to_message.from_user:
        uid = m.reply_to_message.from_user.id
        if len(m.text.split(maxsplit=1)) > 1:
            reason = m.text.split(maxsplit=1)[1]
    elif len(m.command) > 1:
        arg = m.command[1]
        if arg.isdigit():
            uid = int(arg)
            reason = " ".join(m.command[2:]) if len(m.command) > 2 else "No reason"
        else:
            try:
                u = await bot.get_users(arg)
                uid = u.id
                reason = " ".join(m.command[2:]) if len(m.command) > 2 else "No reason"
            except Exception:
                pass
    if not uid:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("reply or id"),3) + rich_note("<code>/fban</code> " + sc("reply to user or id")))
    fid = get_chat_fed(m.chat.id)
    if not fid:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("this chat must join a federation first"),3) + rich_note("Use <code>/joinfed &lt;fed_id&gt;</code> in this chat."))
    fed = get_fed(fid)
    if not fed or not m.from_user or (not is_fed_admin(fid, m.from_user.id) and m.from_user.id != config.OWNER_ID):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("fed admin only"),3))
    if not fban(fid, uid, reason, m.from_user.id):
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("could not save federation ban"),3))
    chats = get_fed_chats(fid)
    count, failed_chats = 0, []
    for cid in chats:
        try:
            await bot.ban_chat_member(cid, uid)
            count += 1
        except Exception:
            failed_chats.append(cid)
    body = _hero() + _hdr(pe("ban","⛔️") + " " + sc("fbanned"),2) + rich_kv_table([(pe("hex","") + " " + sc("user"), "<code>" + str(uid) + "</code>"), (pe("target","") + " " + sc("fed"), "<code>" + rich_esc(fid) + "</code>"), (pe("diamond","") + " " + sc("reason"), rich_esc(reason)), (pe("circle","") + " " + sc("enforced"), "<code>" + str(count) + "/" + str(len(chats)) + "</code> " + sc("chats"))], headers=[pe("spark","") + " " + sc("federation ban"), ""])
    if failed_chats:
        body += rich_note(pe("warn","⚠️") + " " + sc("ban saved, but enforcement failed in some chats") + ": <code>" + rich_esc(", ".join(map(str, failed_chats[:10]))) + ("…" if len(failed_chats) > 10 else "") + "</code>")
    body += "<p>" + rich_button(pe("check","✅") + " " + sc("unfban"), callback_data="fed:unfban:" + fid + ":" + str(uid), style="danger") + "</p>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("check","✅") + " " + sc("unfban"), callback_data="fed:unfban:" + fid + ":" + str(uid))]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command("unfban", prefixes=config.COMMAND_PREFIX_LIST) & group_allowed & user_allowed)
async def unfban_cmd(_, m):
    uid = None
    if m.reply_to_message and m.reply_to_message.from_user:
        uid = m.reply_to_message.from_user.id
    elif len(m.command) > 1 and m.command[1].isdigit():
        uid = int(m.command[1])
    else:
        if len(m.command) > 1:
            try:
                u = await bot.get_users(m.command[1])
                uid = u.id
            except Exception:
                pass
    if not uid:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("reply or id"),3))
    fid = get_chat_fed(m.chat.id)
    if not fid:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("this chat must join a federation first"),3))
    if not m.from_user or not is_fed_admin(fid, m.from_user.id):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("fed admin only"),3))
    if not unfban(fid, uid):
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("could not update federation ban"),3))
    chats = get_fed_chats(fid)
    released, failed = 0, []
    for cid in chats:
        try:
            await bot.unban_chat_member(cid, uid)
            released += 1
        except Exception:
            failed.append(cid)
    body = _hdr("✅ " + sc("unfbanned"),3) + rich_kv_table([(pe("hex","") + " " + sc("user"), "<code>" + str(uid) + "</code>"), (pe("circle","") + " " + sc("groups unbanned"), "<code>" + str(released) + "/" + str(len(chats)) + "</code>")])
    if failed:
        body += rich_note(pe("warn","⚠️") + " " + sc("shared ban removed, but some group bans remain") + ": <code>" + rich_esc(", ".join(map(str, failed[:10]))) + ("…" if len(failed) > 10 else "") + "</code>")
    body += rich_note(sc("use") + " <code>/fban " + str(uid) + "</code> " + sc("to ban again"))
    await rich_send(bot, m.chat.id, body)

@bot.on_message(filters.command(["fedinfo","fedstat"], prefixes=config.COMMAND_PREFIX_LIST) & group_allowed & user_allowed)
async def fedinfo_cmd(_, m):
    fid = None
    if len(m.text.split(maxsplit=1)) > 1:
        fid = m.text.split(maxsplit=1)[1].strip().lower()
    else:
        fid = get_chat_fed(m.chat.id)
    if not fid:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("no fed"),3))
    fed = get_fed(fid)
    if not fed:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("fed not found"),3))
    chats = len(get_fed_chats(fid))
    bans = len(list_fbans(fid))
    admins = len(fed_list_admins(fid))
    body = _hero() + _hdr(sb("Federation") + "  " + rich_esc(fed["name"]),2) + rich_kv_table([(pe("hex","") + " " + sc("id"), "<code>" + rich_esc(fid) + "</code>"), (pe("target","") + " " + sc("owner"), "<code>" + str(fed["owner"]) + "</code>"), (pe("circle","") + " " + sc("chats"), "<code>" + str(chats) + "</code>"), (pe("ban","⛔️") + " " + sc("bans"), "<code>" + str(bans) + "</code>"), (pe("diamond","") + " " + sc("admins"), "<code>" + str(admins) + "</code>")], headers=[pe("spark","") + " " + sc("federation info"), ""])
    body += rich_details(pe("info","ℹ️") + " " + sc("chats in fed"), rich_note(sc("use") + " <code>/fedchats " + rich_esc(fid) + "</code>")) + _fed_pills(fid)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("circle","") + " " + sc("chats") + " (" + str(chats) + ")", callback_data="fed:chats:" + fid), InlineKeyboardButton(pe("ban","⛔️") + " " + sc("bans") + " (" + str(bans) + ")", callback_data="fed:bans:" + fid)],[InlineKeyboardButton(pe("hex","") + " " + sc("add this chat"), callback_data="fed:join:" + fid), InlineKeyboardButton(pe("cross","❌") + " " + sc("leave fed"), callback_data="fed:leave:" + fid)]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command("myfeds", prefixes=config.COMMAND_PREFIX_LIST) & group_allowed)
async def myfeds_cmd(_, m):
    feds = [f for f in list_feds() if f["owner"] == m.from_user.id or is_fed_admin(f["_id"], m.from_user.id)]
    if not feds:
        return await rich_send(bot, m.chat.id, _hdr(pe("circle","") + " " + sc("no feds"),3) + rich_note(pe("diamond","") + " <code>/newfed VidelElite</code> " + sc("to create one")))
    rows = [("<code>" + rich_esc(f["_id"]) + "</code>", rich_esc(f["name"]), rich_button(pe("hex","") + " " + sc("info"), callback_data="fed:info:" + f["_id"])) for f in feds[:24]]
    body = _hero() + _hdr(sb("Your Federations") + " • " + str(len(feds)),2) + rich_table([pe("hex","") + " " + sc("id"), pe("target","") + " " + sc("name"), pe("diamond","") + " " + sc("action")], rows)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("hex","") + " " + rich_esc(f["_id"]), callback_data="fed:info:" + f["_id"]) for f in feds[:3]]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command("fedchats", prefixes=config.COMMAND_PREFIX_LIST) & group_allowed & user_allowed)
async def fedchats_cmd(_, m):
    fid = get_chat_fed(m.chat.id)
    if len(m.text.split(maxsplit=1)) > 1:
        fid = m.text.split(maxsplit=1)[1].strip().lower()
    if not fid:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("no fed"),3))
    if not get_fed(fid):
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("fed not found"),3))
    if not _is_fed_manager(fid, m.from_user.id if m.from_user else None):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("fed admin only"),3))
    chats = get_fed_chats(fid)
    if not chats:
        return await rich_send(bot, m.chat.id, _hdr(pe("circle","") + " " + sc("no chats"),3) + rich_note("<code>/joinfed " + rich_esc(fid) + "</code>"))
    rows = [("<code>" + str(c) + "</code>",) for c in chats[:24]]
    body = _hdr(pe("circle","") + " " + sc("fed chats") + " • " + str(len(chats)),3) + rich_table([pe("hex","") + " " + sc("chat id")], rows)
    if len(chats) > 24:
        body += "<p>" + sc("and") + " " + str(len(chats)-24) + " " + sc("more") + "…</p>"
    body += "<p>" + rich_button(pe("hex","") + " " + sc("info"), callback_data="fed:info:" + fid) + "</p>"
    await rich_send(bot, m.chat.id, body)

@bot.on_message(filters.command("fedbanlist", prefixes=config.COMMAND_PREFIX_LIST) & group_allowed & user_allowed)
async def fedbanlist_cmd(_, m):
    fid = get_chat_fed(m.chat.id)
    if len(m.text.split(maxsplit=1)) > 1:
        fid = m.text.split(maxsplit=1)[1].strip().lower()
    if not fid:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("no fed"),3))
    if not get_fed(fid):
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("fed not found"),3))
    if not _is_fed_manager(fid, m.from_user.id if m.from_user else None):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("fed admin only"),3))
    bans = list_fbans(fid)
    if not bans:
        return await rich_send(bot, m.chat.id, _hdr(pe("check","✅") + " " + sc("no fbans"),3) + rich_note(pe("spark","") + " " + sc("clean federation")))
    rows = [("<code>" + str(b["user"]) + "</code>", rich_esc(b.get("reason","")[:32]), rich_button(pe("check","✅") + " " + sc("unfban"), callback_data="fed:unfban:" + fid + ":" + str(b["user"]), style="danger")) for b in bans[:20]]
    body = _hdr(pe("ban","⛔️") + " " + sc("fed bans") + " • " + str(len(bans)),2) + rich_table([pe("hex","") + " " + sc("user"), pe("diamond","") + " " + sc("reason"), pe("target","") + " " + sc("action")], rows)
    if len(bans) > 20:
        body += "<p>" + sc("and") + " " + str(len(bans)-20) + " " + sc("more") + "… " + pe("line","") + "</p>"
    await rich_send(bot, m.chat.id, body)

@bot.on_message(filters.command(["fpromote","faddadmin"], prefixes=config.COMMAND_PREFIX_LIST) & filters.group & group_allowed & user_allowed)
async def fpromote_cmd(_, m):
    if not await _is_telegram_admin(bot, m.chat.id, m.from_user.id if m.from_user else None):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("group admin only"),3))
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("reply to user"),3))
    fid = get_chat_fed(m.chat.id) or (m.text.split(maxsplit=1)[1].strip().lower() if len(m.text.split()) > 1 else None)
    if not fid:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("no fed"),3))
    if not _is_fed_owner(fid, m.from_user.id if m.from_user else None):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("owner only"),3))
    fed = get_fed(fid)
    target = m.reply_to_message.from_user.id
    if not fed:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("fed not found"),3))
    if target == fed.get("owner"):
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("user is already the federation owner"),3))
    if not fed_add_admin(fid, target):
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("could not save federation admin"),3))
    await rich_send(bot, m.chat.id, _hdr(pe("check","✅") + " " + sc("fed admin added"),3) + rich_kv_table([(pe("target","") + " " + sc("user"), "<code>" + str(target) + "</code>")]) + "<p>" + rich_button(pe("cross","❌") + " " + sc("demote"), callback_data="fed:demote:" + fid + ":" + str(target), style="danger") + "</p>")

@bot.on_message(filters.command(["fdemote","fremadmin"], prefixes=config.COMMAND_PREFIX_LIST) & filters.group & group_allowed & user_allowed)
async def fdemote_cmd(_, m):
    if not await _is_telegram_admin(bot, m.chat.id, m.from_user.id if m.from_user else None):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("group admin only"),3))
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("reply to user"),3))
    fid = get_chat_fed(m.chat.id)
    if not fid:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("no fed"),3))
    if not _is_fed_owner(fid, m.from_user.id if m.from_user else None):
        return await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("owner only"),3))
    fed = get_fed(fid)
    if not fed:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("fed not found"),3))
    target = m.reply_to_message.from_user.id
    if target == fed.get("owner"):
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("cannot demote federation owner"),3))
    if not fed_remove_admin(fid, target):
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("user was not a federation admin or could not be removed"),3))
    await rich_send(bot, m.chat.id, _hdr(pe("cross","❌") + " " + sc("fed admin removed"),3) + rich_kv_table([(pe("target","") + " " + sc("user"), "<code>" + str(target) + "</code>")]))

@bot.on_callback_query(filters.regex(r"^fed:"))
async def fed_cbs(_, q):
    data = (q.data or "").split(":")
    action = data[1] if len(data) > 1 else ""
    fid = data[2] if len(data) > 2 else ""
    chat_id = q.message.chat.id if q.message and q.message.chat else 0
    if action in ("join","leave","delete","fban","unfban","info","chats","bans","demote","myfeds","mychats"):
        if not await is_user_authorized(q):
            return await q.answer("⚠️ " + sc("admin only"), show_alert=True)
    if action == "myfeds":
        feds = [f for f in list_feds() if f["owner"] == q.from_user.id or is_fed_admin(f["_id"], q.from_user.id)]
        if not feds:
            return await q.answer(sc("no feds"), show_alert=True)
        await q.answer()
        rows = [("<code>" + rich_esc(f["_id"]) + "</code>", rich_esc(f["name"])) for f in feds[:12]]
        body = _hdr(sc("your feds") + " • " + str(len(feds)),3) + rich_table([pe("hex","") + " " + sc("id"), pe("target","") + " " + sc("name")], rows)
        buttons = [[InlineKeyboardButton(pe("hex","") + " " + rich_esc(f["_id"]), callback_data="fed:info:" + f["_id"]) for f in feds[index:index + 3]] for index in range(0, min(len(feds), 12), 3)]
        try:
            await rich_edit(q.message, body, reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)
        except Exception:
            pass
        return
    if action == "mychats":
        current = get_chat_fed(chat_id)
        if not current:
            return await q.answer(sc("this chat has not joined a federation"), show_alert=True)
        fed = get_fed(current)
        if not fed:
            return await q.answer(sc("federation record is missing"), show_alert=True)
        await q.answer()
        body = _hdr(sc("this chat's federation"), 3) + rich_kv_table([
            (pe("target","") + " " + sc("name"), rich_esc(fed.get("name") or current)),
            (pe("hex","") + " " + sc("id"), "<code>" + rich_esc(current) + "</code>"),
            (pe("circle","") + " " + sc("member chats"), "<code>" + str(len(get_fed_chats(current))) + "</code>"),
        ])
        try:
            await rich_edit(q.message, body, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(pe("hex","") + " " + sc("federation info"), callback_data="fed:info:" + current)]]))
        except Exception:
            pass
        return
    if action == "delete" and fid:
        if not await _is_telegram_admin(bot, chat_id, q.from_user.id if q.from_user else None):
            return await q.answer(sc("group admin only"), show_alert=True)
        if not _is_fed_owner(fid, q.from_user.id if q.from_user else None):
            return await q.answer(sc("owner only"), show_alert=True)
        if not delete_fed(fid):
            return await q.answer(sc("could not delete federation"), show_alert=True)
        await q.answer(sc("federation deleted"))
        try:
            await rich_edit(q.message, _hdr(pe("cross","❌") + " " + sc("federation deleted"),3) + rich_note("<code>" + rich_esc(fid) + "</code>"))
        except Exception:
            pass
        return
    if action == "info" and fid:
        fed = get_fed(fid)
        if not fed:
            return await q.answer(sc("fed not found"), show_alert=True)
        await q.answer()
        chats = len(get_fed_chats(fid))
        bans = len(list_fbans(fid))
        body = _hdr(sb("Federation") + " — " + rich_esc(fed["name"]),3) + rich_kv_table([(pe("hex","") + " " + sc("id"), "<code>" + rich_esc(fid) + "</code>"), (pe("circle","") + " " + sc("chats"), "<code>" + str(chats) + "</code>"), (pe("ban","⛔️") + " " + sc("bans"), "<code>" + str(bans) + "</code>")])
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(pe("circle","") + " " + sc("chats"), callback_data="fed:chats:" + fid), InlineKeyboardButton(pe("ban","⛔️") + " " + sc("bans"), callback_data="fed:bans:" + fid)], [InlineKeyboardButton(pe("cross","❌") + " " + sc("leave"), callback_data="fed:leave:" + fid)]])
        try:
            await rich_edit(q.message, body, reply_markup=keyboard)
        except Exception:
            pass
        return
    if action in ("chats", "bans") and fid:
        if not get_fed(fid):
            return await q.answer(sc("fed not found"), show_alert=True)
        if not _is_fed_manager(fid, q.from_user.id if q.from_user else None):
            return await q.answer(sc("fed admin only"), show_alert=True)
        if action == "chats":
            chats = get_fed_chats(fid)
            rows = [("<code>" + str(chat) + "</code>",) for chat in chats[:24]]
            body = _hdr(pe("circle","") + " " + sc("fed chats") + " • " + str(len(chats)), 3)
            body += rich_table([pe("hex","") + " " + sc("chat id")], rows) if rows else rich_note(sc("no chats"))
            if len(chats) > 24:
                body += rich_note(sc("and") + " " + str(len(chats) - 24) + " " + sc("more"))
        else:
            bans = list_fbans(fid)
            rows = [("<code>" + str(row.get("user", "")) + "</code>", rich_esc(str(row.get("reason", ""))[:32])) for row in bans[:20]]
            body = _hdr(pe("ban","⛔️") + " " + sc("fed bans") + " • " + str(len(bans)), 3)
            body += rich_table([pe("hex","") + " " + sc("user"), pe("diamond","") + " " + sc("reason")], rows) if rows else rich_note(sc("no fbans"))
        await q.answer()
        try:
            await rich_edit(q.message, body, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(pe("hex","") + " " + sc("federation info"), callback_data="fed:info:" + fid)]]))
        except Exception:
            pass
        return
    if action == "demote" and fid and len(data) > 3:
        if not await _is_telegram_admin(bot, chat_id, q.from_user.id if q.from_user else None):
            return await q.answer(sc("group admin only"), show_alert=True)
        fed = get_fed(fid)
        if not fed or not _is_fed_owner(fid, q.from_user.id if q.from_user else None):
            return await q.answer(sc("owner only"), show_alert=True)
        try:
            if not fed_remove_admin(fid, int(data[3])):
                return await q.answer(sc("not an admin or removal failed"), show_alert=True)
            await q.answer(sc("fed admin removed"))
        except (TypeError, ValueError):
            await q.answer(sc("invalid user"), show_alert=True)
        return
    if action == "join" and fid:
        if not await _is_telegram_admin(bot, chat_id, q.from_user.id if q.from_user else None):
            return await q.answer(sc("group admin only"), show_alert=True)
        if not get_fed(fid):
            return await q.answer(sc("fed not found"), show_alert=True)
        existing = get_chat_fed(chat_id)
        if existing and existing != fid:
            return await q.answer(sc("chat already in another federation"), show_alert=True)
        if not await _bot_can_ban(bot, chat_id):
            return await q.answer(sc("bot needs restrict members permission"), show_alert=True)
        set_chat_fed(chat_id, fid)
        if get_chat_fed(chat_id) != fid:
            return await q.answer(sc("could not save federation membership"), show_alert=True)
        applied, failed = await _enforce_existing_bans(chat_id, fid)
        await q.answer("✅ " + sc("joined") + " " + fid)
        try:
            body = _hdr(pe("check","✅") + " " + sc("joined federation"),3) + rich_kv_table([(pe("hex","") + " " + sc("fed"), "<code>" + rich_esc(fid) + "</code>"), (pe("ban","⛔️") + " " + sc("existing bans enforced"), "<code>" + str(len(applied)) + "/" + str(len(applied) + len(failed)) + "</code>")])
            if failed:
                body += rich_note(pe("warn","⚠️") + " " + sc("some existing bans could not be applied") + ": <code>" + rich_esc(", ".join(map(str, failed[:10]))) + ("…" if len(failed) > 10 else "") + "</code>")
            await rich_edit(q.message, body)
        except Exception:
            pass
        return
    if action == "leave" and fid:
        if not await _is_telegram_admin(bot, chat_id, q.from_user.id if q.from_user else None):
            return await q.answer(sc("group admin only"), show_alert=True)
        if get_chat_fed(chat_id) != fid:
            return await q.answer(sc("this chat is not in that federation"), show_alert=True)
        set_chat_fed(chat_id, None)
        if get_chat_fed(chat_id) is not None:
            return await q.answer(sc("could not save federation leave"), show_alert=True)
        await q.answer("✅ " + sc("left") + " " + fid)
        try:
            await rich_edit(q.message, _hdr(pe("cross","❌") + " " + sc("left federation"),3))
        except Exception:
            pass
        return
    if action == "unfban" and fid and len(data) > 3:
        try:
            uid = int(data[3])
            fed = get_fed(fid)
            if not fed or not _is_fed_manager(fid, q.from_user.id if q.from_user else None):
                return await q.answer(sc("fed admin only"), show_alert=True)
            if not unfban(fid, uid):
                return await q.answer(sc("could not update federation ban"), show_alert=True)
            chats = get_fed_chats(fid)
            failed = []
            for cid in chats:
                try:
                    await bot.unban_chat_member(cid, uid)
                except Exception:
                    failed.append(cid)
            status = "✅ " + sc("unfbanned") + " " + str(uid) + " • " + str(len(chats) - len(failed)) + "/" + str(len(chats))
            await q.answer(status + (" • " + sc("some group bans remain") if failed else ""), show_alert=bool(failed))
        except Exception:
            await q.answer("⚠️ " + sc("failed"), show_alert=True)
        return
    await q.answer()

@bot.on_message(filters.new_chat_members & group_allowed, group=5)
async def fed_enforce(_, m):
    fed = get_chat_fed(m.chat.id)
    if not fed:
        return
    for u in m.new_chat_members:
        if get_fban(fed, u.id):
            try:
                await bot.ban_chat_member(m.chat.id, u.id)
            except Exception:
                await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("failed to enforce federation ban"),3) + rich_note("<code>" + str(u.id) + "</code> " + sc("may still be in the group; grant the bot restrict members permission and review this ban")))
            else:
                await rich_send(bot, m.chat.id, _hdr(pe("ban","⛔️") + " " + sc("fbanned user removed"),3) + rich_note("<code>" + str(u.id) + "</code> • " + pe("diamond","") + " " + rich_esc(u.first_name or "")))
