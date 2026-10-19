# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Elite Locks ✦ Perfect
#  32+ lock types — Richgram premium perfect
# --------------------------------------------------------------------------------

import re
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc, sb
from videl.utils.db import get_mod_settings, set_mod_setting, get_antiflood, set_antiflood, is_approved
from videl.utils.rich_ui import rich_esc, rich_heading, rich_note, rich_table, rich_kv_table, rich_details, rich_button, rich_img, rich_send, rich_edit
try:
    from videl.utils.premium_emojis import pe
except Exception:
    def pe(k, fb="◍"):
        return fb

LOCK_TYPES = {
    "all": "ᴀʟʟ — ᴡʜᴏʟᴇ ɢʀᴏᴜᴘ ᴍᴜᴛᴇᴅ",
    "url": "ᴜʀʟs / ʟɪɴᴋs",
    "invite": "ɪɴᴠɪᴛᴇ ʟɪɴᴋs (t.me)",
    "email": "ᴇᴍᴀɪʟs",
    "phone": "ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀs",
    "forward": "ғᴏʀᴡᴀʀᴅs",
    "forward_channel": "ᴄʜᴀɴɴᴇʟ ғᴏʀᴡᴀʀᴅs",
    "bot": "ʙᴏᴛs (ᴀᴜᴛᴏ-ᴋɪᴄᴋ)",
    "replybot": "ʀᴇᴘʟʏ-ʙᴏᴛ (ᴀɴᴏɴ ʙᴏᴛs)",
    "photo": "ᴘʜᴏᴛᴏs",
    "video": "ᴠɪᴅᴇᴏs",
    "audio": "ᴀᴜᴅɪᴏ / ᴍᴜsɪᴄ",
    "voice": "ᴠᴏɪᴄᴇ ɴᴏᴛᴇs",
    "video_note": "ᴠɪᴅᴇᴏ ɴᴏᴛᴇs",
    "document": "ғɪʟᴇs / ᴅᴏᴄᴜᴍᴇɴᴛs",
    "sticker": "sᴛɪᴄᴋᴇʀs",
    "animation": "ɢɪғs / ᴀɴɪᴍᴀᴛɪᴏɴs",
    "contact": "ᴄᴏɴᴛᴀᴄᴛs",
    "location": "ʟᴏᴄᴀᴛɪᴏɴs",
    "poll": "ᴘᴏʟʟs",
    "game": "ɢᴀᴍᴇs",
    "inline": "ɪɴʟɪɴᴇ ʙᴏᴛs",
    "nsfw": "ɴsғᴡ / ᴀᴅᴜʟᴛ",
    "badword": "ʙᴀᴅ ᴡᴏʀᴅs",
    "spoiler": "sᴘᴏɪʟᴇʀs",
    "rtl": "ʀᴛʟ / ᴀʀᴀʙɪᴄ ғʟᴏᴏᴅ",
    "anon": "ᴀɴᴏɴ ᴀᴅᴍɪɴ (sᴇɴᴅᴀsᴀɴᴏɴ)",
    "pin": "ᴘɪɴs",
}
PANEL_KEYS = ["url","invite","forward","photo","video","audio","voice","document","sticker","animation","contact","location","poll","game","inline","bot","nsfw","badword","all"]
_HERO = "https://iili.io/n5ClDil.jpg"
def _hdr(t, lvl=2):
    return rich_heading(pe("lock","🔒") + " " + t + " " + pe("spark","𖦹"), level=lvl)
def _hero():
    return rich_img(_HERO)
def _should_lock(chat_id, key):
    s = get_mod_settings(chat_id)
    if key == "url" and "link" in s and key not in s:
        return bool(s.get("link"))
    return bool(s.get(key, False))
def _elite_kb(chat_id):
    s = get_mod_settings(chat_id)
    rows = []
    for k in PANEL_KEYS:
        on = s.get(k, False)
        if k in ("nsfw","badword","link","document") and k not in s:
            on = True
        label = LOCK_TYPES.get(k, k)
        rows.append([InlineKeyboardButton(("◍" if on else "⬪") + " " + label + ": " + ("ON" if on else "OFF"), callback_data="elock:" + k)])
    af = get_antiflood(chat_id)
    rows.append([InlineKeyboardButton(("◍" if af.get("enabled") else "⬪") + " ᴀɴᴛɪғʟᴏᴏᴅ: " + ("ON" if af.get("enabled") else "OFF") + " (" + str(af.get("limit",6)) + "/" + str(af.get("window",8)) + "s)", callback_data="elock:antiflood")])
    rows.append([InlineKeyboardButton("⬪ " + sc("lock types") + " ⫶ " + str(len(LOCK_TYPES)), callback_data="elock:types"), InlineKeyboardButton("◍ " + sc("close") + " ◍", callback_data="elock:close")])
    return InlineKeyboardMarkup(rows)
def _rich_panel(chat_id):
    s = get_mod_settings(chat_id)
    af = get_antiflood(chat_id)
    rows = []
    for k in PANEL_KEYS:
        on = s.get(k, False)
        if k in ("nsfw","badword","link","document") and k not in s:
            on = True
        label = LOCK_TYPES.get(k, k)
        status = pe("lock","🔒") + " ON" if on else pe("unlock","🔓") + " OFF"
        toggle = rich_button(status, callback_data="elock:" + k, style="primary" if not on else "danger")
        rows.append((pe("hex","⬢") + " " + sc(label.lower()), status, toggle))
    af_status = pe("lock","🔒") + " ON" if af.get("enabled") else pe("unlock","🔓") + " OFF"
    rows.append((pe("diamond","⬪") + " ᴀɴᴛɪғʟᴏᴏᴅ", af_status + " <code>" + str(af.get("limit",6)) + "/" + str(af.get("window",8)) + "s</code>", rich_button(pe("target","◎") + " " + sc("toggle"), callback_data="elock:antiflood")))
    return rich_table([pe("target","◎") + " " + sc("lock type"), pe("circle","⦿") + " " + sc("status"), pe("spark","𖦹") + " " + sc("toggle")], rows)

@bot.on_message(filters.command(["locks","lockpanel","contentlocks","elocks"]) & filters.group & group_allowed & user_allowed)
async def elite_locks_cmd(_, m):
    if not await is_user_authorized(m):
        return
    body = _hero() + _hdr(sb("Elite Locks") + " • " + str(len(LOCK_TYPES)),2) + _rich_panel(m.chat.id)
    body += rich_note(pe("line","⫶") + " " + sc("tap toggle to enable/disable") + " — " + pe("diamond","⬪") + " " + sc("on = delete when matched") + "<br>" + pe("target","◎") + " " + sc("approved users bypass") + " " + pe("small","⬩") + " " + sc("admins bypass") + " • <code>/lock url</code> <code>/unlock photo</code> <code>/locktypes</code>")
    body += rich_details(pe("info","ℹ️") + " " + sc("commands"), rich_table([sc("command"), sc("action")], [("<code>/lock url</code>", sc("lock urls/links")), ("<code>/unlock url</code>", sc("unlock")), ("<code>/locktypes</code>", sc("list all") + " " + str(len(LOCK_TYPES)) + " " + sc("types")), ("<code>/locksreset</code>", sc("reset all locks"))]))
    body += "<p>" + rich_button(pe("eyes","👀") + " " + sc("view types"), callback_data="elock:types") + " " + rich_button(pe("cross","❌") + " " + sc("close"), callback_data="elock:close", style="danger") + "</p>"
    await rich_send(bot, m.chat.id, body, reply_markup=_elite_kb(m.chat.id))

@bot.on_message(filters.command(["locktypes","lockslist"]) & filters.group & group_allowed)
async def locktypes_cmd(_, m):
    rows = [("<code>" + k + "</code>", sc(v.lower()), rich_button(pe("lock","🔒") + " " + sc("lock"), callback_data="elock_quick:" + k)) for k,v in LOCK_TYPES.items()]
    body = _hdr(sc("lock types") + " • " + str(len(LOCK_TYPES)),2) + rich_table([pe("hex","⬢") + " " + sc("key"), pe("target","◎") + " " + sc("description"), pe("diamond","⬪") + " " + sc("action")], rows)
    body += rich_note(pe("diamond","⬪") + " " + sc("use") + " <code>/lock &lt;key&gt;</code> — " + pe("small","⬩") + " " + sc("example") + ": <code>/lock url</code>")
    await rich_send(bot, m.chat.id, body)

@bot.on_message(filters.command("lock") & filters.group & group_allowed & user_allowed)
async def lock_cmd(_, m):
    if not await is_user_authorized(m):
        return
    if len(m.command) < 2:
        return await rich_send(bot, m.chat.id, _hdr(sc("lock"),3) + rich_note("<code>/lock url</code> — " + sc("lock a type") + " " + pe("diamond","⬪") + " <code>/locktypes</code>"))
    k = m.command[1].lower()
    alias = {"link":"url","links":"url","stickers":"sticker","photos":"photo","videos":"video","files":"document","urls":"url"}
    k = alias.get(k,k)
    if k not in LOCK_TYPES:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("invalid type"),3) + rich_note(sc("try") + " <code>/locktypes</code>"))
    set_mod_setting(m.chat.id, k, True)
    body = _hdr(pe("lock","🔒") + " " + sc("locked"),3) + rich_kv_table([(pe("target","◎") + " " + sc("type"), "<code>" + rich_esc(k) + "</code>"), (pe("hex","⬢") + " " + sc("label"), sc(LOCK_TYPES[k].lower()))])
    body += "<p>" + rich_button(pe("unlock","🔓") + " " + sc("unlock"), callback_data="elock:" + k, style="danger") + " " + rich_button(pe("eyes","👀") + " " + sc("panel"), callback_data="elock:panel") + "</p>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("unlock","🔓") + " " + sc("unlock"), callback_data="elock:" + k), InlineKeyboardButton(pe("eyes","👀") + " " + sc("panel"), callback_data="elock:panel")]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command("unlock") & filters.group & group_allowed & user_allowed)
async def unlock_cmd(_, m):
    if not await is_user_authorized(m):
        return
    if len(m.command) < 2:
        return await rich_send(bot, m.chat.id, _hdr(sc("unlock"),3) + rich_note("<code>/unlock url</code>"))
    k = m.command[1].lower()
    alias = {"link":"url","links":"url","stickers":"sticker"}
    k = alias.get(k,k)
    if k not in LOCK_TYPES:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("invalid type"),3))
    set_mod_setting(m.chat.id, k, False)
    body = _hdr(pe("unlock","🔓") + " " + sc("unlocked"),3) + rich_kv_table([(pe("target","◎") + " " + sc("type"), "<code>" + rich_esc(k) + "</code>")])
    body += "<p>" + rich_button(pe("lock","🔒") + " " + sc("lock"), callback_data="elock:" + k) + " " + rich_button(pe("eyes","👀") + " " + sc("panel"), callback_data="elock:panel") + "</p>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("lock","🔒") + " " + sc("lock"), callback_data="elock:" + k)]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command("locksreset") & filters.group & group_allowed & user_allowed)
async def locks_reset(_, m):
    if not await is_user_authorized(m):
        return
    for k in LOCK_TYPES:
        set_mod_setting(m.chat.id, k, False)
    body = _hdr(pe("cross","❌") + " " + sc("all locks reset"),3) + rich_note(pe("spark","𖦹") + " " + str(len(LOCK_TYPES)) + " " + sc("locks disabled"))
    await rich_send(bot, m.chat.id, body)

@bot.on_callback_query(filters.regex(r"^elock:"))
async def elite_cb(_, q):
    if not await is_user_authorized(q):
        return await q.answer(pe("warn","⚠️") + " " + sc("admin only"), show_alert=True)
    chat_id = q.message.chat.id if q.message and q.message.chat else 0
    data = (q.data or "").split(":",1)[1] if ":" in (q.data or "") else ""
    if data == "close":
        try:
            await q.message.delete()
        except Exception:
            pass
        return await q.answer()
    if data == "panel":
        try:
            body = _hero() + _hdr(sb("Elite Locks") + " • " + str(len(LOCK_TYPES)),2) + _rich_panel(chat_id) + "<p>" + rich_button(pe("cross","❌") + " " + sc("close"), callback_data="elock:close", style="danger") + "</p>"
            await rich_edit(q.message, body, reply_markup=_elite_kb(chat_id))
        except Exception:
            pass
        return await q.answer()
    if data == "types":
        await q.answer()
        rows = [("<code>" + k + "</code>", sc(v.lower())) for k,v in LOCK_TYPES.items()]
        body = _hdr(sc("lock types") + " • " + str(len(LOCK_TYPES)),2) + rich_table([pe("hex","⬢") + " " + sc("key"), pe("target","◎") + " " + sc("description")], rows)
        try:
            await rich_edit(q.message, body)
        except Exception:
            await q.answer("⬪ " + str(len(LOCK_TYPES)) + " " + sc("types") + " — /locktypes ⫶", show_alert=True)
        return
    if data == "antiflood":
        af = get_antiflood(chat_id)
        set_antiflood(chat_id, not af.get("enabled"), af.get("limit",6), af.get("window",8))
        await q.answer(pe("diamond","⬪") + " " + sc("toggled") + " " + pe("spark","𖦹"))
    elif data in LOCK_TYPES:
        cur = get_mod_settings(chat_id).get(data, False)
        if data in ("nsfw","badword") and data not in get_mod_settings(chat_id):
            cur = True
        set_mod_setting(chat_id, data, not cur)
        await q.answer(LOCK_TYPES[data] + " " + ("ON" if not cur else "OFF") + " " + pe("spark","𖦹"))
    else:
        return await q.answer()
    try:
        body = _hero() + _hdr(sb("Elite Locks") + " • " + str(len(LOCK_TYPES)),2) + _rich_panel(chat_id) + rich_note(pe("line","⫶") + " " + sc("tap to toggle") + " • " + pe("target","◎") + " " + sc("approved bypass"))
        await rich_edit(q.message, body, reply_markup=_elite_kb(chat_id))
    except Exception:
        pass

@bot.on_message(filters.group & group_allowed & ~filters.service, group=9)
async def elite_enforce(_, m):
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
    chat_id = m.chat.id
    if _should_lock(chat_id, "all"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.text:
        t = m.text
        if _should_lock(chat_id,"url") and re.search(r"https?://|www\.|t\.me/|telegram\.me", t, re.I):
            try:
                await m.delete()
                return
            except Exception:
                pass
        if _should_lock(chat_id,"invite") and re.search(r"t\.me/(joinchat/|\+)", t):
            try:
                await m.delete()
                return
            except Exception:
                pass
        if _should_lock(chat_id,"email") and re.search(r"[\w\.-]+@[\w\.-]+\.\w+", t):
            try:
                await m.delete()
                return
            except Exception:
                pass
        if _should_lock(chat_id,"phone") and re.search(r"\+?\d[\d\s\-]{7,}\d", t):
            try:
                await m.delete()
                return
            except Exception:
                pass
        if _should_lock(chat_id,"spoiler") and getattr(m, "has_protected_content", False):
            try:
                await m.delete()
                return
            except Exception:
                pass
        if _should_lock(chat_id,"rtl") and re.search(r"[\u0600-\u06FF\u0750-\u077F]", t):
            try:
                await m.delete()
                return
            except Exception:
                pass
    if m.forward_from or m.forward_from_chat:
        if _should_lock(chat_id,"forward"):
            try:
                await m.delete()
                return
            except Exception:
                pass
        if _should_lock(chat_id,"forward_channel") and m.forward_from_chat and getattr(m.forward_from_chat,"type",None)=="channel":
            try:
                await m.delete()
                return
            except Exception:
                pass
    if m.photo and _should_lock(chat_id,"photo"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.video and _should_lock(chat_id,"video"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.audio and _should_lock(chat_id,"audio"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.voice and _should_lock(chat_id,"voice"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.video_note and _should_lock(chat_id,"video_note"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.document and _should_lock(chat_id,"document"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.sticker and _should_lock(chat_id,"sticker"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.animation and _should_lock(chat_id,"animation"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.contact and _should_lock(chat_id,"contact"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.location and _should_lock(chat_id,"location"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.poll and _should_lock(chat_id,"poll"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.game and _should_lock(chat_id,"game"):
        try:
            await m.delete()
            return
        except Exception:
            pass
    if m.via_bot and _should_lock(chat_id,"inline"):
        try:
            await m.delete()
            return
        except Exception:
            pass

@bot.on_message(filters.group & group_allowed & filters.sender_chat, group=9)
async def anon_lock(_, m):
    if _should_lock(m.chat.id, "anon"):
        try:
            await m.delete()
        except Exception:
            pass

@bot.on_message(filters.new_chat_members & group_allowed, group=9)
async def bot_lock_join(_, m):
    if not _should_lock(m.chat.id, "bot"):
        return
    for u in m.new_chat_members:
        if u.is_bot:
            try:
                await bot.ban_chat_member(m.chat.id, u.id)
                await rich_send(bot, m.chat.id, rich_heading(pe("lock","🔒") + " " + sc("bot kicked — bots locked"),3) + rich_note("<code>" + str(u.id) + "</code>"))
            except Exception:
                pass
