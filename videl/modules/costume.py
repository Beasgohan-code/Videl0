# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Premium Costume Stickers
#  Lets admins set costume stickers per event (welcome/goodbye/ban/mute/etc.)
#  Uses Mongo costume_stickers + premium emoji packs already wired
#  /costume /setcostume /delcostume /costumes — cyber-dark premium
# --------------------------------------------------------------------------------
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc, sb
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note, rich_send
from videl.utils.db import set_costume as _set, get_costume as _get, del_costume as _del, list_costumes as _list
try:
    from videl.utils.premium_emojis import pe, PREMIUM_IDS, USE_PREMIUM
except:  # fallback
    def pe(k, fb="◍"): return fb
    PREMIUM_IDS={}
    USE_PREMIUM=False

EVENTS = {
    "welcome":  "ᴡᴇʟᴄᴏᴍᴇ — ᴜsᴇʀ ᴊᴏɪɴ",
    "goodbye":  "ɢᴏᴏᴅʙʏᴇ — ᴜsᴇʀ ʟᴇᴀᴠᴇ",
    "ban":      "ʙᴀɴ — ᴜsᴇʀ ʙᴀɴɴᴇᴅ",
    "unban":    "ᴜɴʙᴀɴ",
    "mute":     "ᴍᴜᴛᴇ — ᴜsᴇʀ ᴍᴜᴛᴇᴅ",
    "warn":     "ᴡᴀʀɴ — ᴡᴀʀɴ ɢɪᴠᴇɴ",
    "lock":     "ʟᴏᴄᴋ — ᴅᴇʟᴇᴛᴇᴅ",
    "captcha":  "ᴄᴀᴘᴛᴄʜᴀ — ᴠᴇʀɪғɪᴇᴅ",
    "play":     "ᴘʟᴀʏ — ᴍᴜsɪᴄ sᴛᴀʀᴛ",
    "help":     "ʜᴇʟᴘ — ᴍᴇɴᴜ ʙᴀɴɴᴇʀ",
}

@bot.on_message(filters.command(["costume","costumes","costumelist"]) & filters.group & group_allowed & user_allowed)
async def costumes_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    arr=_list(m.chat.id)
    if not arr:
        txt="<br>".join(f"• <code>{k}</code> — {v}" for k,v in EVENTS.items())
        return await rich_send(bot, m.chat.id, rich_heading(f"{pe('spark','𖦹')} {sc('costume — no stickers yet')} {pe('spark','𖦹')}",3)+rich_note(f"{sc('set via')} <code>/setcostume welcome</code> {sc('reply to sticker')}<br><br>"+"<br>".join(f"<code>{k}</code> — {v}" for k,v in EVENTS.items()))+rich_note(f"<br>⬪ {sc('premium emoji active')}: {'ON' if USE_PREMIUM else 'OFF'} — <code>/premium</code>"))
    txt="<br>".join(f"{pe('small','⬩')} <code>{r['event']}</code> — <code>{r['file_id'][:16]}…</code>" for r in arr)
    await rich_send(bot, m.chat.id, rich_heading(f"{pe('spark','𖦹')} {sc('costume stickers')} ⫶ {len(arr)} {pe('spark','𖦹')}",3)+rich_note(txt))

@bot.on_message(filters.command(["setcostume","setsticker","addcostume"]) & filters.group & group_allowed & user_allowed)
async def set_costume_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    if len(m.command)<2:
        return await rich_send(bot, m.chat.id, rich_heading(f"{pe('diamond','⬪')} {sc('usage')} {pe('diamond','⬪')}",3)+rich_note(f"<code>/setcostume welcome</code> — {sc('reply to sticker')}<br>{sc('events')}: "+ ", ".join(f"<code>{k}</code>" for k in EVENTS)))
    event=m.command[1].lower()
    if event not in EVENTS: return await rich_send(bot, m.chat.id, rich_heading(f"{pe('cross','❌')} {sc('invalid event')} {pe('cross','❌')}",3)+rich_note(", ".join(EVENTS.keys())))
    if not m.reply_to_message or not m.reply_to_message.sticker:
        return await rich_send(bot, m.chat.id, rich_heading(f"{pe('pin','📌')} {sc('reply to a sticker')} {pe('pin','📌')}",3))
    fid=m.reply_to_message.sticker.file_id
    _set(m.chat.id, event, fid)
    # preview
    try: await bot.send_sticker(m.chat.id, fid, reply_to_message_id=m.reply_to_message.id)
    except: pass
    await rich_send(bot, m.chat.id, rich_heading(f"{pe('check','✅')} {sc('costume set')} {pe('check','✅')}",3)+rich_kv_table([("ᴇᴠᴇɴᴛ", f"<code>{event}</code>"),("sᴛɪᴄᴋᴇʀ", f"<code>{fid[:20]}…</code>")]))

@bot.on_message(filters.command(["delcostume","rmcostume","removecostume"]) & filters.group & group_allowed & user_allowed)
async def del_costume_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    if len(m.command)<2: return await rich_send(bot, m.chat.id, rich_heading(f"{pe('diamond','⬪')} {sc('usage')} {pe('diamond','⬪')}",3)+rich_note("<code>/delcostume welcome</code>"))
    event=m.command[1].lower()
    _del(m.chat.id, event)
    await rich_send(bot, m.chat.id, rich_heading(f"{pe('cross','❌')} {sc('costume removed')} {pe('cross','❌')}",3)+rich_kv_table([("ᴇᴠᴇɴᴛ", f"<code>{event}</code>")]))

# ── Premium control ───────────────────────────────────────────────────────────

@bot.on_message(filters.command(["premium","premiumemoji","costume_emoji"]) & filters.group & group_allowed & user_allowed)
async def premium_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    # show status + sample
    sample=f"{pe('orb','◍')} {pe('diamond','⬪')} {pe('line','⫶')} {pe('small','⬩')} {pe('spark','𖦹')} {pe('circle','⦿')} {pe('target','◎')} {pe('hex','⬢')}"
    await rich_send(bot, m.chat.id, rich_heading(f"{pe('star','⭐️')} {sc('premium costume')} {pe('star','⭐️')}",3)+rich_kv_table([("sᴛᴀᴛᴜs", "ON" if USE_PREMIUM else "OFF"),("ᴘᴀᴄᴋs", "NewsEmoji • tgiosicons • @rijif • SoLo_HaMiD"),("ɪᴅs", f"<code>{len(PREMIUM_IDS)}</code>")])+rich_note(f"{sample}<br><br>{sc('env')} <code>USE_PREMIUM_EMOJI=1/0</code> — {sc('fallback to')} ◍ ⬪ ⫶ ⬩<br>{sc('bot does not need Premium to send — just IDs')}<br><code>/premium test</code> — {sc('preview all')}")
        )
    if len(m.command)>1 and m.command[1].lower()=="test":
        # send sample emoji showcase
        showcase="<br>".join(f"<code>{k}</code> — {pe(k, '?')} <code>{v}</code>" for k,v in list(PREMIUM_IDS.items())[:24])
        await rich_send(bot, m.chat.id, rich_heading(f"{pe('eyes','👀')} {sc('premium showcase')} {pe('eyes','👀')}",3)+rich_note(showcase)+rich_note(f"<br>… + {len(PREMIUM_IDS)-24} {sc('more')} — t.me/addemoji/NewsEmoji • t.me/addemoji/tgiosicons • t.me/addemoji/Udif7rr7_by_fStikBot • t.me/addemoji/SoLo_HaMiD"))

# ── Auto-send costume stickers on events (hooked via low priority) ────────────

def _try_costume(chat_id: int, event: str):
    fid=_get(chat_id, event)
    return fid

# Welcome hook — group=2 (already has captcha there, we add sticker after)
from pyrogram import filters as _f
@bot.on_message(_f.new_chat_members & group_allowed, group=12)
async def costume_welcome(_, m: Message):
    fid=_try_costume(m.chat.id, "welcome")
    if not fid: return
    try: await bot.send_sticker(m.chat.id, fid)
    except: pass

@bot.on_message(_f.left_chat_member & group_allowed, group=12)
async def costume_goodbye(_, m: Message):
    fid=_try_costume(m.chat.id, "goodbye")
    if not fid: return
    try: await bot.send_sticker(m.chat.id, fid)
    except: pass
