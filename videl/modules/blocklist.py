# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Blocklist / Blacklist ✦ Perfect
#  FallenRobot blacklist.py + blacklist_stickers — Richgram premium perfect
# --------------------------------------------------------------------------------

import re
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from videl.utils.bot_ui import button as InlineKeyboardButton
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc, sb
from videl.utils.rich_ui import rich_esc, rich_heading, rich_note, rich_table, rich_kv_table, rich_details, rich_button, rich_send, rich_edit
from videl.utils.db import add_blacklist, remove_blacklist, get_blacklist, get_blacklist_mode, set_blacklist_mode, add_blacklist_sticker, remove_blacklist_sticker, list_bl_stickers, is_approved

try:
    from videl.utils.premium_emojis import pe
except Exception:
    def pe(k, fb=""):
        return fb

def _hdr(t, lvl=3):
    return rich_heading(pe("orb","") + " " + t + " " + pe("spark",""), level=lvl)

VALID_MODES = {"off","del","warn","mute","ban","kick","tban"}

@bot.on_message(filters.command(["addblacklist","addbl"]) & filters.group & group_allowed & user_allowed)
async def addbl_cmd(_, m):
    if not await is_user_authorized(m):
        return
    if not m.text or len(m.text.split(maxsplit=1)) < 2:
        body = _hdr(sc("add to blacklist"),3) + rich_note(pe("diamond","") + " " + sc("usage") + ": <code>/addblacklist &lt;word&gt; [word2 ...]</code><br>" + pe("spark","") + " " + sc("supports") + " *" + sc("wildcards") + "  <code>bad*</code> " + pe("small","") + " " + sc("case-insensitive"))
        body += rich_details(pe("info","ℹ️") + " " + sc("examples"), rich_note("<code>/addblacklist spam scam*</code><br><code>/addblacklist badword*</code>"))
        body += "<p>" + rich_button(pe("eyes","👀") + " " + sc("view list"), callback_data="bl:view") + " " + rich_button(pe("target","") + " " + sc("set mode"), callback_data="bl:mode") + "</p>"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("eyes","👀") + " " + sc("view list"), callback_data="bl:view")]])
        return await rich_send(bot, m.chat.id, body, reply_markup=kb)
    triggers = m.text.split(maxsplit=1)[1].lower().split()
    added = []
    for t in triggers:
        add_blacklist(m.chat.id, t)
        added.append(t)
    rows = []
    for x in added[:20]:
        rows.append(("<code>" + rich_esc(x) + "</code>", rich_button(pe("cross","❌") + " " + sc("remove"), callback_data="bl:rm:" + rich_esc(x), style="danger")))
    body = _hdr(pe("check","✅") + " " + sc("blacklist added") + " • " + str(len(added)),3) + rich_table([pe("hex","") + " " + sc("word"), pe("diamond","") + " " + sc("action")], rows)
    body += "<p>" + rich_button(pe("eyes","👀") + " " + sc("view all"), callback_data="bl:view") + " " + rich_button(pe("target","") + " " + sc("change mode"), callback_data="bl:mode") + "</p>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("eyes","👀") + " " + sc("view all"), callback_data="bl:view")]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command(["delblacklist","rmblacklist","rembl"]) & filters.group & group_allowed & user_allowed)
async def delbl_cmd(_, m):
    if not await is_user_authorized(m):
        return
    if not m.text or len(m.text.split(maxsplit=1)) < 2:
        return await rich_send(bot, m.chat.id, _hdr(sc("remove from blacklist"),3) + rich_note("<code>/delblacklist &lt;word&gt;</code>"))
    trig = m.text.split(maxsplit=1)[1].lower()
    if remove_blacklist(m.chat.id, trig):
        body = _hdr(pe("cross","❌") + " " + sc("removed"),3) + rich_kv_table([(pe("hex","") + " " + sc("word"), "<code>" + rich_esc(trig) + "</code>")])
        body += "<p>" + rich_button(pe("eyes","👀") + " " + sc("view list"), callback_data="bl:view") + "</p>"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("eyes","👀") + " " + sc("view list"), callback_data="bl:view")]])
        await rich_send(bot, m.chat.id, body, reply_markup=kb)
    else:
        await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("not found"),3) + rich_note("<code>" + rich_esc(trig) + "</code>"))

@bot.on_message(filters.command(["blacklist","blacklists","blist"]) & filters.group & group_allowed & user_allowed)
async def listbl_cmd(_, m):
    bl = get_blacklist(m.chat.id)
    mode = get_blacklist_mode(m.chat.id)
    if not bl:
        body = _hdr(pe("circle","") + " " + sc("blacklist") + " — " + sc("empty"),3) + rich_kv_table([(pe("target","") + " " + sc("mode"), "<code>" + rich_esc(mode) + "</code>")])
        body += rich_note(pe("diamond","") + " <code>/addblacklist spam</code> " + sc("to add"))
        body += "<p>" + rich_button(pe("target","") + " " + sc("set mode"), callback_data="bl:mode") + "</p>"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("target","") + " " + sc("set mode"), callback_data="bl:mode")]])
        return await rich_send(bot, m.chat.id, body, reply_markup=kb)
    rows = []
    for b in bl[:24]:
        w = rich_esc(b["trigger"])
        rows.append(("<code>" + w + "</code>", rich_button(pe("cross","❌") + " " + sc("delete"), callback_data="bl:rm:" + w, style="danger")))
    body = _hdr(sb("Blacklist") + " • " + str(len(bl)),2) + rich_kv_table([(pe("target","") + " " + sc("mode"), "<code>" + rich_esc(mode) + "</code>"), (pe("hex","") + " " + sc("total"), "<code>" + str(len(bl)) + "</code>")])
    body += rich_table([pe("hex","") + " " + sc("word"), pe("diamond","") + " " + sc("action")], rows)
    if len(bl) > 24:
        body += "<p>" + sc("and") + " " + str(len(bl)-24) + " " + sc("more") + "… " + pe("line","") + "</p>"
    body += "<p>" + rich_button(pe("cross","❌") + " " + sc("clear all"), callback_data="bl:clear", style="danger") + " " + rich_button(pe("target","") + " " + sc("change mode"), callback_data="bl:mode") + "</p>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("cross","❌") + " " + sc("clear all"), callback_data="bl:clear"), InlineKeyboardButton(pe("target","") + " " + sc("change mode"), callback_data="bl:mode")],[InlineKeyboardButton(pe("spark","") + " " + sc("close"), callback_data="bl:close")]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command(["blacklistmode","blmode","blaction"]) & filters.group & group_allowed & user_allowed)
async def blmode_cmd(_, m):
    if not await is_user_authorized(m):
        return
    if not m.text or len(m.text.split(maxsplit=1)) < 2:
        cur = get_blacklist_mode(m.chat.id)
        body = _hdr(pe("target","") + " " + sc("blacklist mode"),3) + rich_kv_table([(pe("diamond","") + " " + sc("current"), "<code>" + rich_esc(cur) + "</code>")])
        body += rich_table([sc("mode"), sc("action")], [("<code>del</code>", pe("cross","❌") + " " + sc("delete message")), ("<code>warn</code>", pe("warn","⚠️") + " " + sc("warn user")), ("<code>mute</code>", pe("lock","🔒") + " " + sc("mute 1h")), ("<code>ban</code>", pe("ban","⛔️") + " " + sc("ban")), ("<code>kick</code>", pe("spark","") + " " + sc("kick")), ("<code>off</code>", pe("circle","") + " " + sc("no action")), ("<code>tban 2h</code>", "⏱ " + sc("temp ban"))])
        body += "<p>" + rich_button(pe("check","✅") + " del", callback_data="bl:mode:del") + " " + rich_button(pe("warn","⚠️") + " warn", callback_data="bl:mode:warn") + " " + rich_button(pe("lock","🔒") + " mute", callback_data="bl:mode:mute") + " " + rich_button(pe("ban","⛔️") + " ban", callback_data="bl:mode:ban", style="danger") + "</p>"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("del", callback_data="bl:mode:del"), InlineKeyboardButton("warn", callback_data="bl:mode:warn"), InlineKeyboardButton("mute", callback_data="bl:mode:mute")],[InlineKeyboardButton("ban", callback_data="bl:mode:ban"), InlineKeyboardButton("kick", callback_data="bl:mode:kick"), InlineKeyboardButton("off", callback_data="bl:mode:off")],[InlineKeyboardButton("tban 1h", callback_data="bl:mode:tban_1h"), InlineKeyboardButton("tban 1d", callback_data="bl:mode:tban_1d")]])
        return await rich_send(bot, m.chat.id, body, reply_markup=kb)
    mode = m.text.split(maxsplit=1)[1].lower().strip()
    if mode.startswith("tban"):
        parts = mode.split()
        if len(parts)==2 and re.match(r"^\d+[smhdw]$", parts[1]):
            mode = "tban_" + parts[1]
        elif mode == "tban":
            mode = "tban_1h"
        else:
            return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("usage"),3) + rich_note("<code>/blacklistmode tban 2h</code>"))
    elif mode not in VALID_MODES and not mode.startswith("tban_"):
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("invalid mode"),3) + rich_note("✓ " + sc("valid") + ": <code>off/del/warn/mute/ban/kick/tban</code>"))
    set_blacklist_mode(m.chat.id, mode)
    await rich_send(bot, m.chat.id, _hdr(pe("check","✅") + " " + sc("mode updated"),3) + rich_kv_table([(pe("target","") + " " + sc("mode"), "<code>" + rich_esc(mode) + "</code>")]) + "<p>" + rich_button(pe("eyes","👀") + " " + sc("view list"), callback_data="bl:view") + "</p>")

@bot.on_message(filters.command(["addblsticker","addblackliststicker"]) & filters.group & group_allowed & user_allowed)
async def add_bl_sticker(_, m):
    if not await is_user_authorized(m):
        return
    if not m.reply_to_message or not m.reply_to_message.sticker:
        return await rich_send(bot, m.chat.id, _hdr(pe("pin","📌") + " " + sc("reply to sticker"),3) + rich_note("<code>/addblsticker</code> " + sc("reply to a sticker to blacklist it")))
    fid = m.reply_to_message.sticker.file_unique_id
    add_blacklist_sticker(m.chat.id, fid)
    body = _hdr(pe("check","✅") + " " + sc("sticker blacklisted"),3) + rich_kv_table([(pe("hex","") + " " + sc("sticker"), "<code>" + rich_esc(fid[:16]) + "…</code>")])
    body += "<p>" + rich_button(pe("eyes","👀") + " " + sc("view stickers"), callback_data="bl:stickers") + "</p>"
    await rich_send(bot, m.chat.id, body)

@bot.on_message(filters.command(["delblsticker","remblsticker"]) & filters.group & group_allowed & user_allowed)
async def del_bl_sticker(_, m):
    if not await is_user_authorized(m):
        return
    if not m.reply_to_message or not m.reply_to_message.sticker:
        return await rich_send(bot, m.chat.id, _hdr(pe("pin","📌") + " " + sc("reply to sticker"),3))
    fid = m.reply_to_message.sticker.file_unique_id
    if remove_blacklist_sticker(m.chat.id, fid):
        await rich_send(bot, m.chat.id, _hdr(pe("check","✅") + " " + sc("sticker removed"),3))
    else:
        await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("not blacklisted"),3))

@bot.on_message(filters.command(["blstickers","blackliststickers"]) & filters.group & group_allowed & user_allowed)
async def list_bl_stickers_cmd(_, m):
    lst = list_bl_stickers(m.chat.id)
    if not lst:
        return await rich_send(bot, m.chat.id, _hdr(pe("circle","") + " " + sc("no bl stickers"),3))
    body = _hdr(pe("pin","📌") + " " + sc("bl stickers") + " • " + str(len(lst)),3) + rich_table([pe("hex","") + " " + sc("sticker id")], [("<code>" + rich_esc(x) + "</code>",) for x in lst[:20]])
    if len(lst) > 20:
        body += "<p>" + str(len(lst)-20) + " " + sc("more") + "…</p>"
    await rich_send(bot, m.chat.id, body)

@bot.on_callback_query(filters.regex(r"^bl:"))
async def bl_cbs(_, q):
    if not await is_user_authorized(q):
        return await q.answer(pe("warn","⚠️") + " " + sc("admin only"), show_alert=True)
    chat_id = q.message.chat.id if q.message and q.message.chat else 0
    data = (q.data or "").split(":")
    cmd = data[1] if len(data)>1 else ""
    if cmd == "view":
        await q.answer()
        bl = get_blacklist(chat_id)
        mode = get_blacklist_mode(chat_id)
        if not bl:
            try:
                await rich_edit(q.message, _hdr(pe("circle","") + " " + sc("no blacklist"),3))
            except Exception:
                pass
            return
        rows = [("<code>" + rich_esc(b["trigger"]) + "</code>", rich_button(pe("cross","❌") + " " + sc("delete"), callback_data="bl:rm:" + rich_esc(b["trigger"]), style="danger")) for b in bl[:24]]
        body = _hdr(sb("Blacklist") + " • " + str(len(bl)),2) + rich_kv_table([(pe("target","") + " " + sc("mode"), "<code>" + rich_esc(mode) + "</code>")]) + rich_table([pe("hex","") + " " + sc("word"), pe("diamond","") + " " + sc("action")], rows)
        try:
            await rich_edit(q.message, body)
        except Exception:
            pass
        return
    if cmd == "rm" and len(data)>2:
        trig = data[2]
        if remove_blacklist(chat_id, trig):
            await q.answer(pe("check","✅") + " " + sc("removed") + " " + trig)
            bl = get_blacklist(chat_id)
            mode = get_blacklist_mode(chat_id)
            if not bl:
                try:
                    await rich_edit(q.message, _hdr(pe("circle","") + " " + sc("no blacklist"),3))
                except Exception:
                    pass
                return
            rows = [("<code>" + rich_esc(b["trigger"]) + "</code>", rich_button(pe("cross","❌") + " " + sc("delete"), callback_data="bl:rm:" + rich_esc(b["trigger"]), style="danger")) for b in bl[:24]]
            body = _hdr(sb("Blacklist") + " • " + str(len(bl)),2) + rich_kv_table([(pe("target","") + " " + sc("mode"), "<code>" + rich_esc(mode) + "</code>")]) + rich_table([pe("hex","") + " " + sc("word"), pe("diamond","") + " " + sc("action")], rows)
            try:
                await rich_edit(q.message, body)
            except Exception:
                pass
        else:
            await q.answer(pe("warn","⚠️") + " " + sc("not found"), show_alert=True)
        return
    if cmd == "mode":
        if len(data)>2:
            mode_name = data[2]
            if mode_name.startswith("tban"):
                mode_name = "tban_" + mode_name.split("_")[-1] if "_" in mode_name else "tban_1h"
            set_blacklist_mode(chat_id, mode_name)
            await q.answer(pe("check","✅") + " " + mode_name)
            try:
                await rich_edit(q.message, _hdr(pe("check","✅") + " " + sc("mode updated"),3) + rich_kv_table([(pe("target","") + " " + sc("mode"), "<code>" + rich_esc(mode_name) + "</code>")]))
            except Exception:
                pass
        else:
            await q.answer()
            cur = get_blacklist_mode(chat_id)
            body = _hdr(pe("target","") + " " + sc("blacklist mode"),3) + rich_kv_table([(pe("diamond","") + " " + sc("current"), "<code>" + rich_esc(cur) + "</code>")])
            body += rich_table([sc("mode"), sc("action")], [("<code>del</code>", pe("cross","❌")), ("<code>warn</code>", pe("warn","⚠️")), ("<code>mute</code>", pe("lock","🔒")), ("<code>ban</code>", pe("ban","⛔️"))])
            body += "<p>" + rich_button(pe("check","✅") + " del", callback_data="bl:mode:del") + " " + rich_button(pe("warn","⚠️") + " warn", callback_data="bl:mode:warn") + " " + rich_button(pe("ban","⛔️") + " ban", callback_data="bl:mode:ban", style="danger") + "</p>"
            try:
                await rich_edit(q.message, body)
            except Exception:
                pass
        return
    if cmd == "clear":
        bl = get_blacklist(chat_id)
        for b in bl:
            remove_blacklist(chat_id, b["trigger"])
        await q.answer(pe("check","✅") + " " + sc("cleared") + " " + str(len(bl)))
        try:
            await rich_edit(q.message, _hdr(pe("check","✅") + " " + sc("blacklist cleared"),3))
        except Exception:
            pass
        return
    if cmd == "close":
        try:
            await q.message.delete()
        except Exception:
            pass
        await q.answer()
        return
    if cmd == "stickers":
        await q.answer()
        lst = list_bl_stickers(chat_id)
        body = _hdr(pe("pin","📌") + " " + sc("bl stickers") + " • " + str(len(lst)),3) + rich_note("<code>" + str(len(lst)) + "</code> " + sc("stickers blacklisted"))
        try:
            await rich_edit(q.message, body)
        except Exception:
            pass
        return
    await q.answer()

def _build_pattern(trigger):
    esc = re.escape(trigger)
    esc = esc.replace(r"\*", r"\w*")
    if re.match(r"^\w+$", trigger.replace("*","")):
        return r"(?i)(?:\b" + esc + r"\b)"
    return r"(?i)" + esc

@bot.on_message(filters.group & group_allowed & ~filters.service & ~filters.me, group=6)
async def blacklist_watcher(_, m):
    if not m.text or m.text.startswith("/"):
        return
    if not m.from_user or m.from_user.is_bot:
        return
    if is_approved(m.chat.id, m.from_user.id):
        return
    try:
        mem = await bot.get_chat_member(m.chat.id, m.from_user.id)
        if mem.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return
    except Exception:
        pass
    bl = get_blacklist(m.chat.id)
    if not bl:
        return
    text = m.text or ""
    hit = None
    for b in bl:
        trig = b["trigger"]
        try:
            if re.search(_build_pattern(trig), text):
                hit = b
                break
        except Exception:
            if trig.lower() in text.lower():
                hit = b
                break
    if not hit:
        return
    mode = get_blacklist_mode(m.chat.id)
    try:
        await m.delete()
    except Exception:
        pass
    if mode == "off":
        return
    if mode == "del":
        return
    if mode == "warn":
        from videl.utils.db import add_warn, get_warn_limit
        c = add_warn(m.chat.id, m.from_user.id, "blacklist: " + hit["trigger"])
        lim = get_warn_limit(m.chat.id)
        body = _hdr(pe("warn","⚠️") + " " + sc("warned — blacklist"),3) + rich_kv_table([(pe("circle","") + " " + sc("user"), m.from_user.mention), (pe("hex","") + " " + sc("word"), "<code>" + rich_esc(hit["trigger"]) + "</code>"), (pe("target","") + " " + sc("warns"), "<code>" + str(c) + "/" + str(lim) + "</code>")])
        body += "<p>" + rich_button(pe("eyes","👀") + " " + sc("warns"), callback_data="warns_view") + "</p>"
        await rich_send(bot, m.chat.id, body)
        if c >= lim:
            try:
                await bot.ban_chat_member(m.chat.id, m.from_user.id)
            except Exception:
                pass
        return
    if mode == "mute":
        try:
            from datetime import datetime, timedelta
            from pyrogram.types import ChatPermissions
            await bot.restrict_chat_member(m.chat.id, m.from_user.id, ChatPermissions(), until_date=datetime.utcnow()+timedelta(hours=1))
            await rich_send(bot, m.chat.id, _hdr(pe("lock","🔒") + " " + sc("muted — blacklist"),3) + rich_kv_table([(pe("circle","") + " " + sc("user"), m.from_user.mention), (pe("hex","") + " " + sc("word"), "<code>" + rich_esc(hit["trigger"]) + "</code>")]))
        except Exception:
            pass
        return
    if mode == "kick":
        try:
            await bot.ban_chat_member(m.chat.id, m.from_user.id)
            await bot.unban_chat_member(m.chat.id, m.from_user.id)
        except Exception:
            pass
        return
    if mode == "ban":
        try:
            await bot.ban_chat_member(m.chat.id, m.from_user.id)
        except Exception:
            pass
        return
    if mode.startswith("tban"):
        dur = mode.split("_",1)[-1] if "_" in mode else "1h"
        try:
            from datetime import datetime, timedelta
            m_map = {"s":1,"m":60,"h":3600,"d":86400,"w":604800}
            n = int(dur[:-1])
            u = dur[-1].lower()
            secs = n * m_map.get(u,3600)
            await bot.ban_chat_member(m.chat.id, m.from_user.id, until_date=datetime.utcnow()+timedelta(seconds=secs))
        except Exception:
            pass
        return

@bot.on_message(filters.group & group_allowed & filters.sticker & ~filters.me, group=7)
async def bl_sticker_watcher(_, m):
    if not m.sticker or not m.from_user:
        return
    if is_approved(m.chat.id, m.from_user.id):
        return
    try:
        mem = await bot.get_chat_member(m.chat.id, m.from_user.id)
        if mem.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return
    except Exception:
        pass
    fid = m.sticker.file_unique_id
    from videl.utils.db import is_bl_sticker
    if not is_bl_sticker(m.chat.id, fid):
        return
    mode = get_blacklist_mode(m.chat.id)
    try:
        await m.delete()
    except Exception:
        pass
    if mode == "ban":
        try:
            await bot.ban_chat_member(m.chat.id, m.from_user.id)
        except Exception:
            pass
