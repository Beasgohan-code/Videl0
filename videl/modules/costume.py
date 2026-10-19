# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Premium Costume Stickers ✦ Perfect
#  Premium emoji packs + costume stickers per event — Richgram perfect edition
#  Rich: rich_heading + rich_table + rich_button + rich_img + rich_details
# --------------------------------------------------------------------------------

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from videl import bot
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc, sb
from videl.utils.rich_ui import rich_esc, rich_heading, rich_note, rich_table, rich_kv_table, rich_details, rich_button, rich_img, rich_send, rich_edit
from videl.utils.db import set_costume as _set, get_costume as _get, del_costume as _del, list_costumes as _list

try:
    from videl.utils.premium_emojis import pe, PREMIUM_IDS, USE_PREMIUM
except Exception:
    def pe(k, fb="◍"):
        return fb
    PREMIUM_IDS = {}
    USE_PREMIUM = False

EVENTS = {
    "welcome": "ᴡᴇʟᴄᴏᴍᴇ — ᴜsᴇʀ ᴊᴏɪɴ",
    "goodbye": "ɢᴏᴏᴅʙʏᴇ — ᴜsᴇʀ ʟᴇᴀᴠᴇ",
    "ban": "ʙᴀɴ — ᴜsᴇʀ ʙᴀɴɴᴇᴅ",
    "unban": "ᴜɴʙᴀɴ",
    "mute": "ᴍᴜᴛᴇ — ᴜsᴇʀ ᴍᴜᴛᴇᴅ",
    "warn": "ᴡᴀʀɴ — ᴡᴀʀɴ ɢɪᴠᴇɴ",
    "lock": "ʟᴏᴄᴋ — ᴅᴇʟᴇᴛᴇᴅ",
    "captcha": "ᴄᴀᴘᴛᴄʜᴀ — ᴠᴇʀɪғɪᴇᴅ",
    "play": "ᴘʟᴀʏ — ᴍᴜsɪᴄ sᴛᴀʀᴛ",
    "help": "ʜᴇʟᴘ — ᴍᴇɴᴜ ʙᴀɴɴᴇʀ",
}

_HERO = "https://iili.io/n5ClDil.jpg"
def _hdr(t, lvl=3):
    return rich_heading(pe("orb","◍") + " " + t + " " + pe("spark","𖦹"), level=lvl)
def _hero():
    return rich_img(_HERO)

@bot.on_message(filters.command(["costume","costumes","costumelist"]) & filters.group & group_allowed & user_allowed)
async def costumes_cmd(_, m):
    if not await is_user_authorized(m):
        return
    arr = _list(m.chat.id)
    hero = _hero()
    pills = "<p>" + rich_button(pe("spark","𖦹") + " " + sc("set welcome"), callback_data="costume_help:welcome") + " " + rich_button(pe("diamond","⬪") + " " + sc("premium"), callback_data="costume_help:premium") + " " + rich_button(pe("circle","⦿") + " " + sc("help"), callback_data="costume_help:help") + "</p>"
    if not arr:
        body = hero + _hdr(sb("Videl") + " — " + sc("costume"),2) + rich_note(pe("line","⫶") + " " + sc("no costume stickers yet") + " — " + sc("set via") + " <code>/setcostume welcome</code> " + pe("diamond","⬪"))
        body += rich_table([pe("target","◎") + " " + sc("event"), pe("small","⬩") + " " + sc("description")], [(f"<code>{k}</code>", sc(v.lower())) for k,v in EVENTS.items()])
        body += rich_details(pe("star","⭐️") + " " + sc("available events"), rich_table(None, [("<code>" + k + "</code>",) for k in EVENTS]) + rich_note(sc("reply to a sticker with") + " <code>/setcostume welcome</code><br>" + sc("premium active") + ": <b>" + ("ON" if USE_PREMIUM else "OFF") + "</b> • " + pe("spark","𖦹") + " <code>/premium</code>"))
        body += pills
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("spark","𖦹") + " " + sc("set welcome"), callback_data="costume_help:welcome"), InlineKeyboardButton(pe("diamond","⬪") + " " + sc("premium"), callback_data="costume_help:premium")],[InlineKeyboardButton(pe("circle","⦿") + " " + sc("help"), callback_data="costume_help:help")]])
        return await rich_send(bot, m.chat.id, body, reply_markup=kb)
    rows = []
    for r in arr:
        evt = r.get("event","?")
        fid = r.get("file_id","")
        short = fid[:18] + "…" if len(fid) > 18 else fid
        rows.append(("<code>" + rich_esc(evt) + "</code>", "<code>" + rich_esc(short) + "</code>", rich_button(pe("cross","❌") + " " + sc("remove"), callback_data="delcostume:" + evt, style="danger")))
    body = hero + _hdr(sc("costume stickers") + " • " + str(len(arr)),2) + rich_table([pe("pin","📌") + " " + sc("event"), pe("hex","⬢") + " " + sc("sticker"), pe("target","◎") + " " + sc("action")], rows)
    body += rich_note(pe("line","⫶") + " " + sc("tap remove to delete") + " • " + pe("diamond","⬪") + " <code>/setcostume</code> " + sc("to add more")) + pills
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("cross","❌") + " " + sc("remove welcome"), callback_data="delcostume:welcome"), InlineKeyboardButton(pe("cross","❌") + " " + sc("remove goodbye"), callback_data="delcostume:goodbye")],[InlineKeyboardButton(pe("star","⭐️") + " " + sc("premium"), callback_data="costume_help:premium")]])
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_message(filters.command(["setcostume","setsticker","addcostume"]) & filters.group & group_allowed & user_allowed)
async def set_costume_cmd(_, m):
    if not await is_user_authorized(m):
        return
    if len(m.command) < 2:
        body = _hdr(sc("set costume"),3) + rich_note(pe("diamond","⬪") + " " + sc("usage") + ": <code>/setcostume welcome</code> " + sc("reply to a sticker"))
        body += rich_table([pe("target","◎") + " " + sc("event"), pe("small","⬩") + " " + sc("description")], [("<code>" + k + "</code>", sc(v.lower())) for k,v in EVENTS.items()])
        body += "<p>" + rich_button(pe("orb","◍") + " " + sc("welcome"), callback_data="setcostume:welcome") + " " + rich_button(pe("circle","⦿") + " " + sc("goodbye"), callback_data="setcostume:goodbye") + " " + rich_button(pe("hex","⬢") + " " + sc("ban"), callback_data="setcostume:ban") + "</p>"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◍ " + sc("welcome"), callback_data="setcostume:welcome"), InlineKeyboardButton("⦿ " + sc("goodbye"), callback_data="setcostume:goodbye"), InlineKeyboardButton("⬢ " + sc("ban"), callback_data="setcostume:ban")]])
        return await rich_send(bot, m.chat.id, body, reply_markup=kb)
    event = m.command[1].lower().strip()
    if event not in EVENTS:
        body = _hdr(pe("cross","❌") + " " + sc("invalid event"),3) + rich_table([sc("event")], [("<code>" + k + "</code>",) for k in EVENTS]) + rich_note(pe("line","⫶") + " " + sc("try") + ": <code>/setcostume welcome</code>")
        return await rich_send(bot, m.chat.id, body)
    if not m.reply_to_message or not m.reply_to_message.sticker:
        body = _hdr(pe("pin","📌") + " " + sc("reply to a sticker"),3) + rich_note(sc("you must reply to a sticker with") + " <code>/setcostume " + rich_esc(event) + "</code> " + pe("pin","📌"))
        body += rich_details(pe("info","ℹ️") + " " + sc("how to get stickers"), sc("open") + " <a href='https://t.me/addstickers/VidelCostume'>t.me/addstickers</a> " + sc("or forward any sticker"))
        return await rich_send(bot, m.chat.id, body)
    fid = m.reply_to_message.sticker.file_id
    _set(m.chat.id, event, fid)
    try:
        await bot.send_sticker(m.chat.id, fid, reply_to_message_id=m.reply_to_message.id)
    except Exception:
        pass
    confirm = _hdr(pe("check","✅") + " " + sc("costume set"),3) + rich_kv_table([(pe("diamond","⬪") + " " + sc("event"), "<code>" + rich_esc(event) + "</code>"), (pe("hex","⬢") + " " + sc("sticker"), "<code>" + rich_esc(fid[:22]) + "…</code>"), (pe("spark","𖦹") + " " + sc("description"), sc(EVENTS[event].lower()))])
    confirm += "<p>" + rich_button(pe("eyes","👀") + " " + sc("view all"), callback_data="costume_list") + " " + rich_button(pe("cross","❌") + " " + sc("remove"), callback_data="delcostume:" + event, style="danger") + "</p>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("eyes","👀") + " " + sc("view all"), callback_data="costume_list"), InlineKeyboardButton(pe("cross","❌") + " " + sc("remove"), callback_data="delcostume:" + event)]])
    await rich_send(bot, m.chat.id, confirm, reply_markup=kb)

@bot.on_message(filters.command(["delcostume","rmcostume","removecostume"]) & filters.group & group_allowed & user_allowed)
async def del_costume_cmd(_, m):
    if not await is_user_authorized(m):
        return
    if len(m.command) < 2:
        body = _hdr(sc("remove costume"),3) + rich_note("<code>/delcostume welcome</code> " + pe("diamond","⬪") + " " + sc("events") + ": " + ", ".join("<code>" + k + "</code>" for k in EVENTS))
        return await rich_send(bot, m.chat.id, body)
    event = m.command[1].lower()
    ok = _del(m.chat.id, event)
    if ok:
        body = _hdr(pe("check","✅") + " " + sc("costume removed"),3) + rich_kv_table([(pe("circle","⦿") + " " + sc("event"), "<code>" + rich_esc(event) + "</code>")]) + "<p>" + rich_button(pe("eyes","👀") + " " + sc("view all"), callback_data="costume_list") + "</p>"
    else:
        body = _hdr(pe("warn","⚠️") + " " + sc("not found"),3) + rich_note("<code>" + rich_esc(event) + "</code> " + sc("was not set"))
    await rich_send(bot, m.chat.id, body)

@bot.on_message(filters.command(["premium","premiumemoji","costume_emoji"]) & filters.group & group_allowed & user_allowed)
async def premium_cmd(_, m):
    if not await is_user_authorized(m):
        return
    sample = pe("orb","◍") + " " + pe("diamond","⬪") + " " + pe("line","⫶") + " " + pe("small","⬩") + " " + pe("spark","𖦹") + " " + pe("circle","⦿") + " " + pe("target","◎") + " " + pe("hex","⬢") + " " + pe("arrow","➪")
    hero = _hero()
    body = hero + _hdr(pe("star","⭐️") + " " + sb("Premium Costume"),2) + rich_kv_table([(pe("diamond","⬪") + " " + sc("status"), "<b>" + ("ON" if USE_PREMIUM else "OFF") + "</b>"), (pe("hex","⬢") + " " + sc("packs"), "NewsEmoji • tgiosicons • @rijif • SoLo_HaMiD"), (pe("target","◎") + " " + sc("ids mapped"), "<code>" + str(len(PREMIUM_IDS)) + "</code>"), (pe("small","⬩") + " " + sc("sample"), sample)], headers=[pe("spark","𖦹") + " " + sc("premium info"), ""])
    body += rich_note(pe("line","⫶") + " " + sc("env") + " <code>USE_PREMIUM_EMOJI=1/0</code> — " + sc("fallback to") + " ◍ ⬪ ⫶ ⬩<br>" + pe("check","✅") + " " + sc("bot does not need Premium to send — just IDs"))
    body += rich_details(pe("star","⭐️") + " " + sc("cyber glyphs → premium"), rich_table([sc("glyph"), sc("premium"), sc("id")], [("◍", pe("orb","◍"), "<code>" + PREMIUM_IDS.get("orb","") + "</code>"), ("⬪", pe("diamond","⬪"), "<code>" + PREMIUM_IDS.get("diamond","") + "</code>"), ("⫶", pe("line","⫶"), "<code>" + PREMIUM_IDS.get("line","") + "</code>"), ("⬩", pe("small","⬩"), "<code>" + PREMIUM_IDS.get("small","") + "</code>"), ("𖦹", pe("spark","𖦹"), "<code>" + PREMIUM_IDS.get("spark","") + "</code>"), ("⦿", pe("circle","⦿"), "<code>" + PREMIUM_IDS.get("circle","") + "</code>"), ("◎", pe("target","◎"), "<code>" + PREMIUM_IDS.get("target","") + "</code>"), ("⬢", pe("hex","⬢"), "<code>" + PREMIUM_IDS.get("hex","") + "</code>")]))
    body += "<p>" + rich_button(pe("eyes","👀") + " " + sc("showcase 24"), callback_data="premium:test") + " " + rich_button(pe("spark","𖦹") + " " + sc("costume"), callback_data="costume_list") + "</p>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(pe("eyes","👀") + " " + sc("showcase 24"), callback_data="premium:test"), InlineKeyboardButton(pe("spark","𖦹") + " " + sc("costume"), callback_data="costume_list")],[InlineKeyboardButton(pe("diamond","⬪") + " " + sc("toggle info"), url="https://t.me/addemoji/NewsEmoji")]])
    if len(m.command) > 1 and m.command[1].lower() == "test":
        rows = []
        for k,v in list(PREMIUM_IDS.items())[:28]:
            rows.append(("<code>" + rich_esc(k) + "</code>", pe(k,"?"), "<code>" + rich_esc(v) + "</code>"))
        showcase = hero + _hdr(pe("eyes","👀") + " " + sc("premium showcase") + " • 28/" + str(len(PREMIUM_IDS)),2) + rich_table([sc("key"), sc("emoji"), sc("id")], rows)
        showcase += rich_note(pe("line","⫶") + " … + " + str(len(PREMIUM_IDS)-28) + " " + sc("more") + " — <a href='https://t.me/addemoji/NewsEmoji'>NewsEmoji</a> • <a href='https://t.me/addemoji/tgiosicons'>tgiosicons</a> • <a href='https://t.me/addemoji/Udif7rr7_by_fStikBot'>@rijif</a> • <a href='https://t.me/addemoji/SoLo_HaMiD'>SoLo_HaMiD</a>")
        showcase += "<p>" + rich_button(pe("eyes","👀") + " " + sc("view costumes"), callback_data="costume_list") + "</p>"
        return await rich_send(bot, m.chat.id, showcase, reply_markup=kb)
    await rich_send(bot, m.chat.id, body, reply_markup=kb)

@bot.on_callback_query(filters.regex(r"^(costume_help|premium|setcostume|delcostume|costume_list)"))
async def costume_cbs(_, q):
    data = q.data or ""
    chat_id = q.message.chat.id if q.message and q.message.chat else 0
    if data.startswith(("setcostume:", "delcostume:")) and not await is_user_authorized(q):
        return await q.answer(pe("warn","⚠️") + " " + sc("admin only"), show_alert=True)
    if data == "costume_list":
        arr = _list(chat_id)
        if not arr:
            await q.answer(pe("line","⫶") + " " + sc("no costumes yet"), show_alert=True)
            return
        txt = "\n".join("• " + r["event"] + " — " + r["file_id"][:14] + "…" for r in arr[:12])
        await q.answer()
        body = _hdr(sc("costume stickers") + " • " + str(len(arr)),3) + rich_note(txt.replace("\n","<br>"))
        try:
            await rich_edit(q.message, body)
        except Exception:
            await q.message.reply_text(txt)
        return
    if data.startswith("premium"):
        await q.answer()
        rows = [("<code>" + rich_esc(k) + "</code>", pe(k,"?"), "<code>" + rich_esc(v) + "</code>") for k,v in list(PREMIUM_IDS.items())[:24]]
        showcase = _hdr(pe("eyes","👀") + " " + sc("premium showcase"),2) + rich_table([sc("key"), sc("emoji"), sc("id")], rows)
        try:
            await rich_edit(q.message, showcase)
        except Exception:
            pass
        return
    if data.startswith("setcostume:"):
        evt = data.split(":",1)[1]
        await q.answer(pe("pin","📌") + " " + sc("reply to a sticker with") + " /setcostume " + evt, show_alert=True)
        return
    if data.startswith("delcostume:"):
        evt = data.split(":",1)[1]
        ok = _del(chat_id, evt)
        if ok:
            await q.answer(pe("check","✅") + " " + sc("removed") + " " + evt)
            try:
                await rich_edit(q.message, _hdr(pe("check","✅") + " " + sc("costume removed") + " — " + rich_esc(evt),3) + rich_note("<code>" + rich_esc(evt) + "</code> " + sc("deleted") + " " + pe("diamond","⬪")))
            except Exception:
                pass
        else:
            await q.answer(pe("warn","⚠️") + " " + sc("not found"), show_alert=True)
        return
    if data.startswith("costume_help:"):
        sub = data.split(":",1)[1] if ":" in data else ""
        if sub == "premium":
            await premium_cmd(None, q.message)
            await q.answer()
        elif sub == "welcome":
            await q.answer(sc("reply to sticker") + " → /setcostume welcome", show_alert=True)
        else:
            await q.answer()

def _try_costume(chat_id, event):
    return _get(chat_id, event)

@bot.on_message(filters.new_chat_members & group_allowed, group=12)
async def costume_welcome(_, m):
    fid = _try_costume(m.chat.id, "welcome")
    if not fid:
        return
    try:
        await bot.send_sticker(m.chat.id, fid)
    except Exception:
        pass

@bot.on_message(filters.left_chat_member & group_allowed, group=12)
async def costume_goodbye(_, m):
    fid = _try_costume(m.chat.id, "goodbye")
    if not fid:
        return
    try:
        await bot.send_sticker(m.chat.id, fid)
    except Exception:
        pass
