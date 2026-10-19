# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Perfected
#  ◍ ⬪ ⫶ Cyber Dark • Always photo+caption+buttons, never silent ⫶ ⬪ ◍
# --------------------------------------------------------------------------------
import asyncio, time
from pyrogram import filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
import config
from videl import bot, LOGGER
from videl.utils.db import add_broadcast_chat, add_served_chat, add_served_user

_last_start: dict[int, float] = {}
_COOLDOWN = 3.0
START_IMG = "https://iili.io/n5ClDil.jpg"

def _btn(text: str, **kw) -> InlineKeyboardButton:
    kw.pop("style", None); return InlineKeyboardButton(text, **kw)

def _start_kb() -> InlineKeyboardMarkup:
    from videl.utils.formatters import sc
    bot_link = getattr(config, "BOT_LINK", "https://t.me/VidelMusicBot")
    sup = getattr(config, "SUPPORT_GROUP", "https://t.me/BeasgohanSupport")
    upd = getattr(config, "UPDATES_CHANNEL", "https://t.me/BeasgohanUpdates")
    web = getattr(config, "WEBAPP_URL", "https://hosting-bot-dashboard.vercel.app")
    return InlineKeyboardMarkup([
        [_btn(f"⬪ {sc('add to group')}", url=f"{bot_link}?startgroup=true")],
        [_btn(f"⫶ {sc('support')}", url=sup), _btn(f"◎ {sc('updates')}", url=upd)],
        [_btn(f"◍ {sc('dashboard')}", url=web), _btn(f"⬩ {sc('help')}", callback_data="show_help")],
        [_btn(f"⦿ {sc('commands')}", callback_data="help_extra"), _btn(f"⬢ {sc('source')}", url="https://github.com/Beasgohan-code/Videl")],
    ])

def _plain_private(uid: int, name: str) -> str:
    from videl.utils.formatters import sc, sb
    bn = getattr(config, "BOT_NAME", "Videl Music")
    return (
        f"◍ {sb(bn)} ◍\n\n"
        f"⬪ {sc('hey')} <a href='tg://user?id={uid}'><b>{name}</b></a> ⬪\n"
        f"{sc('welcome — a telegram vc music bot')} ⫶\n\n"
        f"<b>⬪ {sc('features')} ⬪</b>\n"
        f"◍ {sc('audio & video in voice chat')}\n"
        f"◍ {sc('autoplay · playlists')} ⫶ {sc('vote to skip')}\n"
        f"◍ {sc('speed & bass effects')} ⫶ {sc('ai chat')}\n"
        f"◍ {sc('group admin tools')} ⫶ {sc('antiflood & locks')}\n"
        f"◍ {sc('lyrics · channel play · queue')} ⬪\n\n"
        f"<b>⫶ {sc('quick start')} ⫶</b>\n"
        f"⬩ {sc('add me to your group')}\n"
        f"⬩ {sc('give manage video chat rights')}\n"
        f"⬩ {sc('send')} <code>/play {sc('song name')}</code> ◍\n\n"
        f"⬪ {sc('made with cyber dark by')} <b>{sb('Beasgohan')}</b> ⬪"
    )

def _plain_group(uid: int, name: str, title: str) -> str:
    from videl.utils.formatters import sc, sb
    bn = getattr(config, "BOT_NAME", "Videl Music")
    return (
        f"◍ {sb(bn)} ◍\n"
        f"⬪ {sc('hey')} <a href='tg://user?id={uid}'><b>{name}</b></a> ⬪\n"
        f"{sc('thanks for adding me to')} <b>{title}</b> ⫶\n"
        f"⬩ {sc('promote me with manage video chats')}\n"
        f"◍ <code>/play {sc('song name')}</code> ⬪"
    )

def _photo_url() -> str:
    photos = getattr(config, "START_PHOTOS", [])
    return photos[0] if photos and photos[0] else START_IMG

async def _send_start(message: Message, text: str, kb: InlineKeyboardMarkup):
    chat_id = message.chat.id; photo = _photo_url()
    try: return await message.reply_photo(photo=photo, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except FloodWait as fw:
        await asyncio.sleep(fw.value+1)
        try: return await message.reply_photo(photo=photo, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except Exception as e: LOGGER.warning(f"start retry: {e}")
    except Exception as e: LOGGER.warning(f"start photo: {e}")
    try: return await bot.send_photo(chat_id, photo=photo, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception as e: LOGGER.warning(f"start send_photo: {e}")
    try: return await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e: LOGGER.warning(f"start text: {e}")
    try: return await bot.send_message(chat_id, text, reply_markup=kb, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e: LOGGER.error(f"start failed: {e}")
    return None

@bot.on_message(filters.command("start") & ~filters.forwarded, group=0)
async def start_handler(_, message: Message):
    chat_id = message.chat.id if message.chat else 0
    now = time.time()
    if now - _last_start.get(chat_id, 0) < _COOLDOWN: return
    _last_start[chat_id] = now
    if len(_last_start) > 500:
        cutoff = now - 60
        for k in [k for k,t in _last_start.items() if t < cutoff]: _last_start.pop(k, None)
    try:
        uid = message.from_user.id if message.from_user else 0
        name = (message.from_user.first_name if message.from_user else "User") or "User"
        name = name.replace("<","").replace(">","")
        chat_type = message.chat.type
        try:
            if uid: add_served_user(uid)
            add_served_chat(chat_id)
        except: pass
        kb = _start_kb()
        if chat_type == ChatType.PRIVATE:
            await _send_start(message, _plain_private(uid, name), kb)
            try: add_broadcast_chat(chat_id, "private")
            except: pass
            return
        title = (message.chat.title or "this chat").replace("<","").replace(">","")
        await _send_start(message, _plain_group(uid, name, title), kb)
        try: add_broadcast_chat(chat_id, "group")
        except: pass
    except Exception as e:
        LOGGER.error(f"/start: {e}")
        try: await message.reply_text("◍ ᴠɪᴅᴇʟ — <code>/play song</code> ◍", parse_mode=ParseMode.HTML)
        except: pass

@bot.on_message(filters.command("help") & ~filters.forwarded, group=0)
async def help_handler(_, message: Message):
    from videl.utils.formatters import sc, sb
    kb = InlineKeyboardMarkup([
        [_btn(f"◍ {sc('play')} ⫶ {sc('queue')}", callback_data="help_play"), _btn(f"⬪ {sc('admin')}", callback_data="help_admin")],
        [_btn(f"⫶ {sc('tools')}", callback_data="help_tools"), _btn(f"◎ {sc('ai chat')}", callback_data="help_extra")],
        [_btn(f"⬩ {sc('dashboard')}", url=getattr(config,"WEBAPP_URL","https://hosting-bot-dashboard.vercel.app")), _btn(f"⦿ {sc('home')}", callback_data="start_home")],
    ])
    text = (
        f"◍ {sb('Videl Help')} ◍\n\n"
        f"⬪ {sc('music')} ⫶ <code>/play</code> <code>/vplay</code> <code>/cplay</code>\n"
        f"⫶ {sc('controls')} ⫶ <code>/pause</code> <code>/resume</code> <code>/skip</code> <code>/stop</code> <code>/queue</code>\n"
        f"◍ {sc('extras')} ⫶ <code>/lyrics</code> <code>/autoplay</code> <code>/seek</code> <code>/shuffle</code>\n"
        f"⬩ {sc('admin')} ⫶ <code>/ban</code> <code>/mute</code> <code>/warn</code> <code>/lock</code> <code>/purge</code>\n"
        f"⬢ {sc('ai')} ⫶ <code>/ask</code> <code>/imagine</code>\n"
        f"𖦹 {sc('utils')} ⫶ <code>/weather</code> <code>/qr</code> <code>/wiki</code> <code>/calc</code>\n\n"
        f"⫶ {sc('tip: tap a category below')} ⫶"
    )
    try: await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e: LOGGER.error(f"/help: {e}")
