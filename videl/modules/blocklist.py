# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Blocklist / Blacklist
#  Inspired by AnonymousX1025/FallenRobot • blacklist.py + blacklist_stickers.py
#  and PaulSonOfLars/tgbot • blacklist — Rose-style word/sticker filter
#  /addblacklist /delblacklist /blacklist /blacklistmode /addblsticker /delblsticker
#  Modes: off/del/warn/ban/mute/kick — better than Rose (adds cyber-dark + approve bypass)
# --------------------------------------------------------------------------------

import re
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note, rich_send
from videl.utils.db import add_blacklist, remove_blacklist, get_blacklist, get_blacklist_mode, set_blacklist_mode
from videl.utils.db import add_blacklist_sticker, remove_blacklist_sticker, list_bl_stickers
from videl.utils.db import is_approved

VALID_MODES = {"off","del","warn","mute","ban","kick","tban"}

@bot.on_message(filters.command(["addblacklist","addbl"]) & filters.group & group_allowed & user_allowed)
async def addbl_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    if not m.text or len(m.text.split(maxsplit=1))<2:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('usage')} ◍",3)+rich_note("<code>/addblacklist &lt;word&gt; [word2 ...]</code><br>◍ {sc('supports')} *ᴡɪʟᴅᴄᴀʀᴅs*} ⫶ <code>bad*</code>".format(sc=sc)))
    triggers=m.text.split(maxsplit=1)[1].lower().split()
    added=[]
    for t in triggers:
        # normalize trigger (same as FallenRobot) — escape regex but keep * ?
        add_blacklist(m.chat.id, t)
        added.append(t)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('blacklist added')} ◍",3)+rich_note("• "+"<br>• ".join(f"<code>{rich_esc(x)}</code>" for x in added)))

@bot.on_message(filters.command(["delblacklist","rmblacklist","rembl"]) & filters.group & group_allowed & user_allowed)
async def delbl_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    if not m.text or len(m.text.split(maxsplit=1))<2:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('usage')} ◍",3)+rich_note("<code>/delblacklist &lt;word&gt;</code>"))
    trig=m.text.split(maxsplit=1)[1].lower()
    if remove_blacklist(m.chat.id, trig):
        await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('removed')} ◍",3)+rich_note(f"<code>{rich_esc(trig)}</code>"))
    else:
        await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('not found')} ◍",3))

@bot.on_message(filters.command(["blacklist","blacklists","blist"]) & filters.group & group_allowed & user_allowed)
async def listbl_cmd(_, m: Message):
    bl=get_blacklist(m.chat.id)
    mode=get_blacklist_mode(m.chat.id)
    if not bl:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no blacklist')} ◍",3)+rich_kv_table([("ᴍᴏᴅᴇ", f"<code>{mode}</code>")]))
    txt="<br>".join(f"• <code>{rich_esc(b['trigger'])}</code>" for b in bl[:100])
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('blacklist')} ⫶ {len(bl)} ◍",3)+rich_kv_table([("ᴍᴏᴅᴇ", f"<code>{mode}</code>")])+rich_note(txt))

@bot.on_message(filters.command(["blacklistmode","blmode","blaction"]) & filters.group & group_allowed & user_allowed)
async def blmode_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    if not m.text or len(m.text.split(maxsplit=1))<2:
        cur=get_blacklist_mode(m.chat.id)
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('blacklist mode')} ◍",3)+rich_kv_table([("ᴄᴜʀʀᴇɴᴛ", f"<code>{cur}</code>")])+rich_note("<code>/blacklistmode del</code> — {sc('delete')}<br><code>/blacklistmode warn</code><br><code>/blacklistmode mute</code><br><code>/blacklistmode ban/kick/off/tban</code>".format(sc=sc)))
    mode=m.text.split(maxsplit=1)[1].lower().strip()
    # Allow "tban 2h" etc — store as "tban_2h"
    if mode.startswith("tban"):
        parts=mode.split()
        if len(parts)==2 and re.match(r"^\d+[smhdw]$", parts[1]):
            mode=f"tban_{parts[1]}"
        elif mode=="tban": mode="tban_1h"
        else:
            return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('usage')} ◍",3)+rich_note("<code>/blacklistmode tban 2h</code>"))
    elif mode not in VALID_MODES and not mode.startswith("tban_"):
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('invalid mode')} ◍",3)+rich_note(f"✓ {sc('valid')}: <code>off/del/warn/mute/ban/kick/tban</code>"))
    set_blacklist_mode(m.chat.id, mode)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('mode updated')} ◍",3)+rich_kv_table([("ᴍᴏᴅᴇ", f"<code>{mode}</code>")]))

# ── Sticker blacklist ──────────────────────────────────────────────────────────

@bot.on_message(filters.command(["addblsticker","addblackliststicker"]) & filters.group & group_allowed & user_allowed)
async def add_bl_sticker(_, m: Message):
    if not await is_user_authorized(m): return
    if not m.reply_to_message or not m.reply_to_message.sticker:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('reply to sticker')} ◍",3))
    fid=m.reply_to_message.sticker.file_unique_id
    add_blacklist_sticker(m.chat.id, fid)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('sticker blacklisted')} ◍",3))

@bot.on_message(filters.command(["delblsticker","remblsticker"]) & filters.group & group_allowed & user_allowed)
async def del_bl_sticker(_, m: Message):
    if not await is_user_authorized(m): return
    if not m.reply_to_message or not m.reply_to_message.sticker:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('reply to sticker')} ◍",3))
    fid=m.reply_to_message.sticker.file_unique_id
    if remove_blacklist_sticker(m.chat.id, fid):
        await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('sticker removed')} ◍",3))
    else:
        await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('not blacklisted')} ◍",3))

@bot.on_message(filters.command(["blstickers","blackliststickers"]) & filters.group & group_allowed & user_allowed)
async def list_bl_stickers_cmd(_, m: Message):
    lst=list_bl_stickers(m.chat.id)
    if not lst: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no bl stickers')} ◍",3))
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('bl stickers')} ⫶ {len(lst)} ◍",3)+rich_note(f"<code>{len(lst)}</code> {sc('stickers blacklisted')}"))


# ── Enforcement (like FallenRobot: word triggers via regex) ───────────────────

def _build_pattern(trigger: str) -> str:
    # Rose/FallenRobot style: case-insensitive, word-boundary aware, * wildcard
    # Convert "bad*word" → r"bad\w*word"
    esc=re.escape(trigger)
    esc=esc.replace(r"\*", r"\w*")
    # if trigger is alphanumeric short, use word boundary; else substring
    if re.match(r"^\w+$", trigger.replace("*","")):
        return rf"(?i)(?:\b{esc}\b)"
    return rf"(?i){esc}"

@bot.on_message(filters.group & group_allowed & ~filters.service & ~filters.me, group=6)
async def blacklist_watcher(_, m: Message):
    if not m.text or m.text.startswith("/"): return
    if not m.from_user or m.from_user.is_bot: return
    # approved bypass
    if is_approved(m.chat.id, m.from_user.id): return
    # check admin skip? (optional — we enforce even on admins? FallenRobot does not skip admins)
    try:
        mem=await bot.get_chat_member(m.chat.id, m.from_user.id)
        if mem.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER): return
    except: pass
    bl=get_blacklist(m.chat.id)
    if not bl: return
    text=m.text or ""
    hit=None
    for b in bl:
        trig=b["trigger"]
        try:
            if re.search(_build_pattern(trig), text):
                hit=b; break
        except: 
            if trig.lower() in text.lower(): hit=b; break
    if not hit: return
    mode=get_blacklist_mode(m.chat.id)
    # actions
    try: await m.delete()
    except: pass
    if mode=="off": return
    if mode=="del": 
        # already deleted
        return
    if mode=="warn":
        from videl.utils.db import add_warn, get_warn_limit
        c=add_warn(m.chat.id, m.from_user.id, f"blacklist: {hit['trigger']}")
        lim=get_warn_limit(m.chat.id)
        await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('warned — blacklist')} ◍",3)+rich_kv_table([("ᴜsᴇʀ", m.from_user.mention),("ᴡᴏʀᴅ", f"<code>{rich_esc(hit['trigger'])}</code>"),("ᴡᴀʀɴs", f"{c}/{lim}")]))
        if c>=lim:
            try: await bot.ban_chat_member(m.chat.id, m.from_user.id)
            except: pass
        return
    if mode=="mute":
        try:
            from datetime import datetime, timedelta
            from pyrogram.types import ChatPermissions
            await bot.restrict_chat_member(m.chat.id, m.from_user.id, ChatPermissions(), until_date=datetime.utcnow()+timedelta(hours=1))
            await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('muted — blacklist')} ◍",3)+rich_kv_table([("ᴜsᴇʀ", m.from_user.mention),("ᴡᴏʀᴅ", f"<code>{rich_esc(hit['trigger'])}</code>")]))
        except: pass
        return
    if mode=="kick":
        try: await bot.ban_chat_member(m.chat.id, m.from_user.id); await bot.unban_chat_member(m.chat.id, m.from_user.id)
        except: pass
        return
    if mode=="ban":
        try: await bot.ban_chat_member(m.chat.id, m.from_user.id)
        except: pass
        return
    if mode.startswith("tban"):
        dur=mode.split("_",1)[-1] if "_" in mode else "1h"
        try:
            from datetime import datetime, timedelta
            m_map={"s":1,"m":60,"h":3600,"d":86400,"w":604800}
            n=int(dur[:-1]); u=dur[-1].lower()
            secs=n*m_map.get(u,3600)
            await bot.ban_chat_member(m.chat.id, m.from_user.id, until_date=datetime.utcnow()+timedelta(seconds=secs))
        except: pass
        return

@bot.on_message(filters.group & group_allowed & filters.sticker & ~filters.me, group=7)
async def bl_sticker_watcher(_, m: Message):
    if not m.sticker or not m.from_user: return
    if is_approved(m.chat.id, m.from_user.id): return
    try:
        mem=await bot.get_chat_member(m.chat.id, m.from_user.id)
        if mem.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER): return
    except: pass
    fid=m.sticker.file_unique_id
    from videl.utils.db import is_bl_sticker
    if not is_bl_sticker(m.chat.id, fid): return
    mode=get_blacklist_mode(m.chat.id)
    try: await m.delete()
    except: pass
    if mode=="ban":
        try: await bot.ban_chat_member(m.chat.id, m.from_user.id)
        except: pass
