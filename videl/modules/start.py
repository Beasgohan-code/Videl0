# --------------------------------------------------------------------------------
#  Videl 👑 Telegram Web App & Music/Group Bot © 2026 | Beasgohan-code
#  Cyber-Dark Studio UI • Native Telegram Mini App + Single Vercel URL
# --------------------------------------------------------------------------------
import html
import time
from pyrogram import filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import InlineKeyboardMarkup, Message, WebAppInfo
from videl.utils.bot_ui import button as InlineKeyboardButton

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
        studio_row = [_btn("Open Videl Studio", web_app=WebAppInfo(url=web))]
    else:
        studio_row = [_btn("Open Videl Studio", url=web)]

    return InlineKeyboardMarkup([
        studio_row,
        [
            _btn("Add to Group", url=f"{bot_link}?startgroup=true"),
            _btn("Group Setup", callback_data="wiz2_start_full"),
        ],
        [
            _btn("Post Studio", **({"web_app": WebAppInfo(url=f"{web}?tab=post")} if is_private else {"url": f"{web}?tab=post"})),
            _btn("Group Manager", **({"web_app": WebAppInfo(url=f"{web}?tab=groups")} if is_private else {"url": f"{web}?tab=groups"})),
        ],
        [
            _btn("Music & Commands", callback_data="show_help"),
            _btn("Bot API Tools", callback_data="modern_tools_help"),
        ],
        [
            _btn("Support", url=sup),
            _btn("Updates", url=upd),
        ],
    ])


def _studio_private_caption(uid: int, name: str) -> str:
    bn = html.escape(getattr(config, "BOT_NAME", "Videl"))
    uptime_s = max(0, int(time.time() - bot_start_time))
    h, rem = divmod(uptime_s, 3600)
    m, _ = divmod(rem, 60)
    try:
        from videl.utils.db import read_live_totals
        totals = read_live_totals()
        groups, users, plays = totals["chats"], totals["users"], totals["plays"]
    except Exception:
        groups, users, plays = "Unavailable", "Unavailable", "Unavailable"

    from videl.utils.rich_ui import rich_heading
    return (
        rich_heading(f"{bn} · Telegram Studio", level=2) + "\n"
        f"<i>Your Bot. Your Groups. Your Community.</i>\n\n"
        f"Welcome, <a href='tg://user?id={uid}'><b>{name}</b></a>!\n"
        f"Manage groups, stream music, publish rich posts, chat &amp; automate — all from one unified Telegram Web App.\n\n"
        f"<blockquote>"
        f"<b>At a glance</b>\n"
        f"• <b>Groups:</b> <code>{groups}</code>  |  <b>Users:</b> <code>{users}</code>\n"
        f"• <b>Streams:</b> <code>{plays}</code>  |  <b>Uptime:</b> <code>{h}h {m}m</code>"
        f"</blockquote>\n\n"
        f"<b>Your workspace</b>\n"
        f"• <b>Smart Chat:</b> Chat as bot or user from the web console\n"
        f"• <b>Post Studio:</b> Rich media posts with inline buttons\n"
        f"• <b>Group Manager:</b> Locks, anti-spam, welcome &amp; moderation\n"
        f"• <b>Voice Music:</b> <code>/play</code> · <code>/vplay</code> · Eldian HD audio\n"
        f"• <b>Analytics:</b> Real-time MongoDB command &amp; group metrics\n\n"
        f"<i>Everything you need. One connected workspace.</i>"
    )


def _studio_group_caption(uid: int, name: str, title: str) -> str:
    bn = html.escape(getattr(config, "BOT_NAME", "Videl"))
    from videl.utils.rich_ui import rich_heading
    return (
        rich_heading(f"{bn} · Community Studio", level=2) + "\n\n"
        f"Hello <a href='tg://user?id={uid}'><b>{name}</b></a>, <b>{title}</b> is connected!\n\n"
        f"<blockquote>"
        f"• <b>Stream Music:</b> <code>/play song name</code> or <code>/vplay</code>\n"
        f"• <b>Group Protection:</b> <code>/setup</code> or <code>/locks</code>\n"
        f"• <b>Web App Studio:</b> Manage this group from the single Vercel URL"
        f"</blockquote>"
    )


async def _send_start(message: Message, text: str, is_private: bool):
    # A text/rich card is reliable even when an external welcome image is offline.
    # Richgram handles known format/emoji rejections without retrying network failures.
    from videl.utils.rich_ui import rich_send
    return await rich_send(bot, message.chat.id, text,
                           reply_markup=_start_kb(is_private=is_private),
                           message_thread_id=getattr(message, "message_thread_id", None))


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
        name = html.escape(name)
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
        title = html.escape(message.chat.title or "this group")
        await _send_start(message, _studio_group_caption(uid, name, title), is_private=False)
        try:
            add_broadcast_chat(chat_id, "group")
        except Exception:
            pass
    except Exception as e:
        LOGGER.error("/start error: %s", e)
        try:
            await message.reply_text("<b>Videl 👑 Studio</b> — Use <code>/play song</code> or <code>/help</code>", parse_mode=ParseMode.HTML)
        except Exception:
            pass
