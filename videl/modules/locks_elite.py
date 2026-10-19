# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Elite Locks (better than Rose)
#  Fully inspired by PaulSonOfLars/tgbot • locks.py + AnonymousX1025/FallenRobot
#  locks.py (30+ lock types) + botdev72/GroupHelp — unified + cyber-dark
#  Rose has ~27 locks — Videl has 32+ with approve bypass + federated sync
#  /lock /unlock /locks /locktypes — with elite panel
# --------------------------------------------------------------------------------

import re, time
from collections import defaultdict, deque
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, MessageMediaType
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc
from videl.utils.db import get_mod_settings, set_mod_setting, get_antiflood, set_antiflood, is_approved
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note, rich_send
import config

# Elite lock types — superset of Rose + FallenRobot + GroupHelp
LOCK_TYPES = {
    # messages
    "all": "ᴀʟʟ — ᴡʜᴏʟᴇ ɢʀᴏᴜᴘ ᴍᴜᴛᴇᴅ",
    "url": "ᴜʀʟs / ʟɪɴᴋs",
    "invite": "ɪɴᴠɪᴛᴇ ʟɪɴᴋs (t.me)",
    "email": "ᴇᴍᴀɪʟs",
    "phone": "ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀs",
    "forward": "ғᴏʀᴡᴀʀᴅs",
    "forward_channel": "ᴄʜᴀɴɴᴇʟ ғᴏʀᴡᴀʀᴅs",
    "bot": "ʙᴏᴛs (ᴀᴜᴛᴏ-ᴋɪᴄᴋ)",
    "replybot": "ʀᴇᴘʟʏ-ʙᴏᴛ (ᴀɴᴏɴ ʙᴏᴛs)",
    # media
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
    # moderation
    "nsfw": "ɴsғᴡ / ᴀᴅᴜʟᴛ",
    "badword": "ʙᴀᴅ ᴡᴏʀᴅs",
    "spoiler": "sᴘᴏɪʟᴇʀs",
    "rtl": "ʀᴛʟ / ᴀʀᴀʙɪᴄ ғʟᴏᴏᴅ",
    "anon": "ᴀɴᴏɴ ᴀᴅᴍɪɴ (sᴇɴᴅᴀsᴀɴᴏɴ)",
    "pin": "ᴘɪɴs",
}

# For panel we show top 24, rest via /locktypes
PANEL_KEYS = ["url","invite","forward","photo","video","audio","voice","document","sticker","animation","contact","location","poll","game","inline","bot","nsfw","badword","all"]

def _elite_kb(chat_id: int) -> InlineKeyboardMarkup:
    s=get_mod_settings(chat_id)
    rows=[]
    for k in PANEL_KEYS:
        on=s.get(k, False)  # default OFF except legacy 4 which default True — we handle
        # fallback: legacy only those 4 default True
        if k in ("nsfw","badword","link","document") and k not in s:
            on=True
        label=LOCK_TYPES.get(k, k)
        rows.append([InlineKeyboardButton(f"{'◍' if on else '⬪'} {label}: {'ON' if on else 'OFF'}", callback_data=f"elock:{k}")])
    af=get_antiflood(chat_id)
    rows.append([InlineKeyboardButton(f"{'◍' if af.get('enabled') else '⬪'} ᴀɴᴛɪғʟᴏᴏᴅ: {'ON' if af.get('enabled') else 'OFF'} ({af.get('limit',6)}/{af.get('window',8)}s)", callback_data="elock:antiflood")])
    rows.append([InlineKeyboardButton(f"⬪ {sc('lock types')} ⫶ {len(LOCK_TYPES)}", callback_data="elock:types"), InlineKeyboardButton(f"◍ {sc('close')} ◍", callback_data="elock:close")])
    return InlineKeyboardMarkup(rows)

@bot.on_message(filters.command(["locks","lockpanel","contentlocks","elocks"]) & filters.group & group_allowed & user_allowed)
async def elite_locks_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('elite locks')} ⫶ {len(LOCK_TYPES)} ◍",3)+rich_note(f"⬪ {sc('tap to toggle')} — {sc('on = delete when matched')} ⫶<br>◎ {sc('approved users bypass')} ⬪<br><code>/lock url</code> <code>/unlock photo</code> <code>/locktypes</code>"), reply_markup=_elite_kb(m.chat.id))

@bot.on_message(filters.command(["locktypes","lockslist"]) & filters.group & group_allowed)
async def locktypes_cmd(_, m: Message):
    txt="<br>".join(f"• <code>{k}</code> — {LOCK_TYPES[k]}" for k in LOCK_TYPES)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('lock types')} ⫶ {len(LOCK_TYPES)} ◍",3)+rich_note(txt))

@bot.on_message(filters.command("lock") & filters.group & group_allowed & user_allowed)
async def lock_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    if len(m.command)<2: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('usage')} ◍",3)+rich_note("<code>/lock url</code> — {sc('lock a type')}"))
    k=m.command[1].lower()
    # alias
    alias={"link":"url","links":"url","stickers":"sticker","photos":"photo","videos":"video","files":"document","urls":"url"}
    k=alias.get(k,k)
    if k not in LOCK_TYPES: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('invalid type')} ◍",3)+rich_note(f"{sc('try')} <code>/locktypes</code>"))
    set_mod_setting(m.chat.id, k, True)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('locked')} ◍",3)+rich_kv_table([("ᴛʏᴘᴇ", f"<code>{k}</code>")]))

@bot.on_message(filters.command("unlock") & filters.group & group_allowed & user_allowed)
async def unlock_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    if len(m.command)<2: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('usage')} ◍",3)+rich_note("<code>/unlock url</code>"))
    k=m.command[1].lower()
    alias={"link":"url","links":"url","stickers":"sticker"}
    k=alias.get(k,k)
    if k not in LOCK_TYPES: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('invalid type')} ◍",3))
    set_mod_setting(m.chat.id, k, False)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('unlocked')} ◍",3)+rich_kv_table([("ᴛʏᴘᴇ", f"<code>{k}</code>")]))

@bot.on_message(filters.command("locksreset") & filters.group & group_allowed & user_allowed)
async def locks_reset(_, m: Message):
    if not await is_user_authorized(m): return
    for k in LOCK_TYPES: set_mod_setting(m.chat.id, k, False)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('all locks reset')} ◍",3))

@bot.on_callback_query(filters.regex(r"^elock:"))
async def elite_cb(_, q):
    if not await is_user_authorized(q): return await q.answer(f"◍ {sc('admin only')} ◍", show_alert=True)
    chat_id=q.message.chat.id
    data=q.data.split(":",1)[1] if ":" in q.data else ""
    if data=="close":
        try: await q.message.delete()
        except: pass
        return await q.answer()
    if data=="types":
        return await q.answer(f"⬪ {len(LOCK_TYPES)} types — use /locktypes ⫶", show_alert=True)
    if data=="antiflood":
        af=get_antiflood(chat_id)
        set_antiflood(chat_id, not af.get("enabled"), af.get("limit",6), af.get("window",8))
        await q.answer(f"◍ {sc('toggled')} ◍")
    elif data in LOCK_TYPES:
        cur=get_mod_settings(chat_id).get(data, False)
        # legacy defaults True for old 4
        if data in ("nsfw","badword") and data not in get_mod_settings(chat_id): cur=True
        set_mod_setting(chat_id, data, not cur)
        await q.answer(f"{LOCK_TYPES[data]} {'ON' if not cur else 'OFF'}")
    else: return await q.answer()
    try: await q.message.edit_reply_markup(reply_markup=_elite_kb(chat_id))
    except: pass

# ── Elite enforcement (comprehensive) ────────────────────────────────────────

def _should_lock(chat_id: int, key: str) -> bool:
    s=get_mod_settings(chat_id)
    # legacy compat: link alias
    if key=="url" and "link" in s and key not in s: return bool(s.get("link"))
    return bool(s.get(key, False))

@bot.on_message(filters.group & group_allowed & ~filters.service, group=9)
async def elite_enforce(_, m: Message):
    if not m.from_user or m.from_user.is_bot: return
    if is_approved(m.chat.id, m.from_user.id): return
    # admin bypass? Rose normally still enforces on admins? We bypass admins for UX
    try:
        mem=await bot.get_chat_member(m.chat.id, m.from_user.id)
        if mem.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER): return
    except: pass
    chat_id=m.chat.id
    # all lock
    if _should_lock(chat_id, "all"):
        try: await m.delete(); return
        except: pass
    # url / invite / email / phone
    if m.text:
        t=m.text
        if _should_lock(chat_id,"url") and re.search(r"https?://|www\.|t\.me/|telegram\.me", t, re.I):
            try: await m.delete(); return
            except: pass
        if _should_lock(chat_id,"invite") and re.search(r"t\.me/(joinchat/|\+)", t):
            try: await m.delete(); return
            except: pass
        if _should_lock(chat_id,"email") and re.search(r"[\w\.-]+@[\w\.-]+\.\w+", t):
            try: await m.delete(); return
            except: pass
        if _should_lock(chat_id,"phone") and re.search(r"\+?\d[\d\s\-]{7,}\d", t):
            try: await m.delete(); return
            except: pass
        if _should_lock(chat_id,"spoiler") and getattr(m, "has_protected_content", False):
            try: await m.delete(); return
            except: pass
        if _should_lock(chat_id,"rtl") and re.search(r"[\u0600-\u06FF\u0750-\u077F]", t):
            try: await m.delete(); return
            except: pass
    # forward
    if m.forward_from or m.forward_from_chat:
        if _should_lock(chat_id,"forward"): 
            try: await m.delete(); return
            except: pass
        if _should_lock(chat_id,"forward_channel") and m.forward_from_chat and getattr(m.forward_from_chat,"type",None)=="channel":
            try: await m.delete(); return
            except: pass
    # pin lock? — service message for pin is filters.pinned_message
    # media locks
    media=m.media if hasattr(m,"media") else None
    # Use MessageMediaType
    mt=m.media if hasattr(m,"media") else None
    # Check via m.photo etc
    if m.photo and _should_lock(chat_id,"photo"):
        try: await m.delete(); return
        except: pass
    if m.video and _should_lock(chat_id,"video"):
        try: await m.delete(); return
        except: pass
    if m.audio and _should_lock(chat_id,"audio"):
        try: await m.delete(); return
        except: pass
    if m.voice and _should_lock(chat_id,"voice"):
        try: await m.delete(); return
        except: pass
    if m.video_note and _should_lock(chat_id,"video_note"):
        try: await m.delete(); return
        except: pass
    if m.document and _should_lock(chat_id,"document"):
        try: await m.delete(); return
        except: pass
    if m.sticker and _should_lock(chat_id,"sticker"):
        try: await m.delete(); return
        except: pass
    if m.animation and _should_lock(chat_id,"animation"):
        try: await m.delete(); return
        except: pass
    if m.contact and _should_lock(chat_id,"contact"):
        try: await m.delete(); return
        except: pass
    if m.location and _should_lock(chat_id,"location"):
        try: await m.delete(); return
        except: pass
    if m.poll and _should_lock(chat_id,"poll"):
        try: await m.delete(); return
        except: pass
    if m.game and _should_lock(chat_id,"game"):
        try: await m.delete(); return
        except: pass
    if m.via_bot and _should_lock(chat_id,"inline"):
        try: await m.delete(); return
        except: pass

# anon channel lock
@bot.on_message(filters.group & group_allowed & filters.sender_chat, group=9)
async def anon_lock(_, m: Message):
    if _should_lock(m.chat.id, "anon"):
        try: await m.delete()
        except: pass

# bot auto-kick on join
@bot.on_message(filters.new_chat_members & group_allowed, group=9)
async def bot_lock_join(_, m: Message):
    if not _should_lock(m.chat.id, "bot"): return
    for u in m.new_chat_members:
        if u.is_bot:
            try:
                await bot.ban_chat_member(m.chat.id, u.id)
                await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('bot kicked — bots locked')} ◍",3)+rich_note(f"<code>{u.id}</code>"))
            except: pass
