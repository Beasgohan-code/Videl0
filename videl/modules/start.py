# --------------------------------------------------------------------------------
#  Videl 👑 Telegram Web App & Music/Group Bot © 2026 | Beasgohan-code
#  Cyber-Dark Studio UI • Native Telegram Mini App + Single Vercel URL
# --------------------------------------------------------------------------------
import asyncio
import time
from pyrogram import filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

import config
from videl import LOGGER, bot, bot_start_time
from videl.utils.db import (
    add_broadcast_chat,
    add_served_chat,
    add_served_user,
    get_served_chats_count,
    get_served_users_count,
    get_total_plays,
)

_last_start: dict[int, float] = {}
_COOLDOWN = 2.5
START_IMG = "https://iili.io/n5ClDil.jpg"


def _btn(text: str, **kw) -> InlineKeyboardButton:
    kw.pop("style", None)
    return InlineKeyboardButton(text, **kw)


def _normalize_url(u: str, fallback: str) -> str:
    u = (u or fallback).strip()
    if u.startswith("@"):
        return f"https://t.me/{u[1:]}"
    if u.startswith("t.me/") or u.startswith("telegram.me/"):
        return f"https://{u}"
    if u.startswith("http://") or u.startswith("https://") or u.startswith("tg://"):
        return u
    if u and " " not in u and "." not in u and "/" not in u:
        return f"https://t.me/{u.lstrip('@')}"
    return fallback


def _webapp_url() -> str:
    return _normalize_url(
        getattr(config, "WEBAPP_URL", "https://videl0-control-panel.vercel.app"),
        "https://videl0-control-panel.vercel.app",
    ).rstrip("/")


def _start_kb(is_private: bool = True, use_webapp_btn: bool = True) -> InlineKeyboardMarkup:
    bot_link = _normalize_url(getattr(config, "BOT_LINK", "https://t.me/Videl0Bot"), "https://t.me/Videl0Bot")
    sup = _normalize_url(getattr(config, "SUPPORT_GROUP", "https://t.me/VidelSupport"), "https://t.me/VidelSupport")
    upd = _normalize_url(getattr(config, "UPDATES_CHANNEL", "https://t.me/VidelUpdates"), "https://t.me/VidelUpdates")
    web = _webapp_url()

    if is_private and use_webapp_btn and web.startswith("https://"):
        studio_row = [_btn("👑 Launch Videl Web App Studio", web_app=WebAppInfo(url=web))]
    else:
        studio_row = [_btn("👑 Open Videl Web App Studio", url=web)]

    return InlineKeyboardMarkup([
        studio_row,
        [
            _btn("➕ Add to Group", url=f"{bot_link}?startgroup=true"),
            _btn("⚡ Group Wizard", callback_data="wiz2_start_full"),
        ],
        [
            _btn("💬 Smart Chat & Post", url=f"{web}?tab=post"),
            _btn("👥 Group Manager", url=f"{web}?tab=groups"),
        ],
        [
            _btn("🎵 Music & Commands", callback_data="show_help"),
            _btn("🛠️ Pro Modules", callback_data="pro_plugins_0"),
        ],
        [
            _btn("💬 Support", url=sup),
            _btn("📢 Updates", url=upd),
        ],
    ])


def _studio_private_caption(uid: int, name: str) -> str:
    bn = getattr(config, "BOT_NAME", "Videl")
    uptime_s = max(0, int(time.time() - bot_start_time))
    h, rem = divmod(uptime_s, 3600)
    m, _ = divmod(rem, 60)
    try:
        groups = get_served_chats_count()
        users = get_served_users_count()
        plays = get_total_plays()
    except Exception:
        groups, users, plays = 0, 0, 0

    return (
        f"✈️ <b>{bn} 👑 — Telegram Web App &amp; Bot Studio</b>\n"
        f"<i>Your Bot. Your Groups. Your Community.</i>\n\n"
        f"👋 Welcome, <a href='tg://user?id={uid}'><b>{name}</b></a>!\n"
        f"Manage groups, stream music, publish rich posts, chat &amp; automate — all from one unified Telegram Web App.\n\n"
        f"<blockquote>"
        f"📊 <b>Live Studio Telemetry</b>\n"
        f"• <b>Groups:</b> <code>{groups}</code>  |  <b>Users:</b> <code>{users}</code>\n"
        f"• <b>Streams:</b> <code>{plays}</code>  |  <b>Uptime:</b> <code>{h}h {m}m</code>"
        f"</blockquote>\n\n"
        f"⚡ <b>Core Modules</b>\n"
        f"• 💬 <b>Smart Chat:</b> Chat as bot or user from the web console\n"
        f"• 📝 <b>Post Studio:</b> Rich media posts with inline buttons\n"
        f"• 👥 <b>Group Manager:</b> Locks, anti-spam, welcome &amp; moderation\n"
        f"• 🎵 <b>Voice Music:</b> <code>/play</code> · <code>/vplay</code> · Eldian HD audio\n"
        f"• 📈 <b>Analytics:</b> Real-time MongoDB command &amp; group metrics\n\n"
        f"<i>“Discipline today… Freedom tomorrow.” — Gohan</i>"
    )


def _studio_group_caption(uid: int, name: str, title: str) -> str:
    bn = getattr(config, "BOT_NAME", "Videl")
    return (
        f"✈️ <b>{bn} 👑 — Community &amp; Music Studio</b>\n\n"
        f"👋 Hey <a href='tg://user?id={uid}'><b>{name}</b></a>, <b>{title}</b> is connected!\n\n"
        f"<blockquote>"
        f"• 🎵 <b>Stream Music:</b> <code>/play song name</code> or <code>/vplay</code>\n"
        f"• 🛡️ <b>Group Protection:</b> <code>/setup</code> or <code>/locks</code>\n"
        f"• 👑 <b>Web App Studio:</b> Manage this group from the single Vercel URL"
        f"</blockquote>"
    )


def _photo_url() -> str:
    photos = getattr(config, "START_PHOTOS", [])
    return photos[0] if photos and photos[0] else START_IMG


async def _send_start(message: Message, text: str, is_private: bool):
    chat_id = message.chat.id
    photo = _photo_url()
    for use_webapp in ([True, False] if is_private else [False]):
        kb = _start_kb(is_private=is_private, use_webapp_btn=use_webapp)
        try:
            return await message.reply_photo(photo=photo, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except FloodWait as fw:
            await asyncio.sleep(fw.value + 1)
        except Exception as e:
            LOGGER.warning("start reply_photo (webapp=%s): %s", use_webapp, e)
        try:
            return await bot.send_photo(chat_id, photo=photo, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except Exception as e:
            LOGGER.warning("start send_photo (webapp=%s): %s", use_webapp, e)
        for fn in (
            lambda: message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML, disable_web_page_preview=True),
            lambda: message.reply(text, reply_markup=kb, parse_mode=ParseMode.HTML),
            lambda: bot.send_message(chat_id, text, reply_markup=kb, parse_mode=ParseMode.HTML),
        ):
            try:
                return await fn()
            except Exception:
                continue
    return None


@bot.on_message(filters.command("start") & ~filters.forwarded, group=0)
async def start_handler(_, message: Message):
    chat_id = message.chat.id if message.chat else 0
    now = time.time()
    if now - _last_start.get(chat_id, 0) < _COOLDOWN:
        return
    _last_start[chat_id] = now
    if len(_last_start) > 500:
        cutoff = now - 60
        for k in [k for k, t in _last_start.items() if t < cutoff]:
            _last_start.pop(k, None)
    try:
        uid = message.from_user.id if message.from_user else 0
        name = (message.from_user.first_name if message.from_user else "User") or "User"
        name = name.replace("<", "").replace(">", "")
        chat_type = message.chat.type
        try:
            if uid:
                add_served_user(uid)
            add_served_chat(chat_id)
        except Exception:
            pass
        if chat_type == ChatType.PRIVATE:
            await _send_start(message, _studio_private_caption(uid, name), is_private=True)
            try:
                add_broadcast_chat(chat_id, "private")
            except Exception:
                pass
            return
        title = (message.chat.title or "this group").replace("<", "").replace(">", "")
        await _send_start(message, _studio_group_caption(uid, name, title), is_private=False)
        try:
            add_broadcast_chat(chat_id, "group")
        except Exception:
            pass
    except Exception as e:
        LOGGER.error("/start error: %s", e)
        try:
            await message.reply_text("✈️ <b>Videl 👑 Studio</b> — Use <code>/play song</code> or <code>/help</code>", parse_mode=ParseMode.HTML)
        except Exception:
            pass
