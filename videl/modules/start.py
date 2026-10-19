# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio
import time

from pyrogram import filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from videl import bot, LOGGER
from videl.utils.db import add_broadcast_chat, add_served_chat, add_served_user

_last_start: dict[int, float] = {}
_START_COOLDOWN = 3.0

# Fixed banner (user requested)
START_IMG = "https://iili.io/n5ClDil.jpg"


def _btn(text: str, **kwargs) -> InlineKeyboardButton:
    kwargs.pop("style", None)
    return InlineKeyboardButton(text, **kwargs)


def _start_keyboard() -> InlineKeyboardMarkup:
    """Full start buttons — always shown."""
    bot_link = getattr(config, "BOT_LINK", None) or "https://t.me/VidelMusicBot"
    support = getattr(config, "SUPPORT_GROUP", None) or "https://t.me/BeasgohanSupport"
    updates = getattr(config, "UPDATES_CHANNEL", None) or "https://t.me/BeasgohanUpdates"
    owner = getattr(config, "OWNER_ID", None)

    rows = [
        [_btn("➕ Add me to Group", url=f"{bot_link}?startgroup=true")],
        [
            _btn("💬 Support", url=support),
            _btn("📢 Updates", url=updates),
        ],
        [_btn("📖 Help & Commands", callback_data="show_help")],
    ]
    owner_row = []
    if owner:
        owner_row.append(_btn("👑 Owner", url=f"tg://user?id={owner}"))
    owner_row.append(_btn("📦 Source", url="https://github.com/Beasgohan-code/Videl"))
    rows.append(owner_row)
    return InlineKeyboardMarkup(rows)


def _plain_private(uid: int, name: str) -> str:
    from videl.utils.formatters import sc, sb
    bot_name = getattr(config, "BOT_NAME", "Videl Music")
    # Cyber Dark Perfected — ◍ ⬪ ⫶
    return (
        f"◍ {sb(bot_name)} ◍\n\n"
        f"⬪ {sc('hey')} <a href='tg://user?id={uid}'><b>{name}</b></a> ⬪\n\n"
        f"{sc('welcome — a telegram vc music bot')} ⫶\n\n"
        f"<b>⬪ {sc('features')} ⬪</b>\n"
        f"◍ {sc('audio & video in voice chat')}\n"
        f"◍ {sc('autoplay · playlists')} ⫶ {sc('vote to skip')}\n"
        f"◍ {sc('speed & bass effects')}\n"
        f"◍ {sc('group admin tools')} ⫶ {sc('locks & antiflood')}\n"
        f"◍ {sc('lyrics · channel play · ai chat')} ⬪\n\n"
        f"<b>⫶ {sc('quick start')} ⫶</b>\n"
        f"⬩ {sc('add me to your group')}\n"
        f"⬩ {sc('give manage video chat rights')}\n"
        f"⬩ {sc('send')} <code>/play {sc('song name')}</code> ◍\n\n"
        f"⬪ {sc('made with cyber dark by')} <b>{sb('Beasgohan')}</b> ⬪"
    )


def _plain_group(uid: int, name: str, title: str) -> str:
    from videl.utils.formatters import sc, sb
    bot_name = getattr(config, "BOT_NAME", "Videl Music")
    return (
        f"◍ {sb(bot_name)} ◍\n\n"
        f"⬪ {sc('hey')} <a href='tg://user?id={uid}'><b>{name}</b></a> ⬪\n"
        f"{sc('thanks for adding me to')} <b>{title}</b> ⫶\n\n"
        f"⬩ {sc('promote me with manage video chats')}\n"
        f"◍ <code>/play {sc('song name')}</code> ⬪"
    )


def _photo_url() -> str:
    photos = getattr(config, "START_PHOTOS", None) or []
    if photos and photos[0]:
        return photos[0]
    return START_IMG


async def _send_start(
    message: Message,
    text: str,
    kb: InlineKeyboardMarkup,
) -> Message | None:
    """
    Always try photo + caption + buttons.
    Falls back to text+buttons if photo fails — never silent.
    """
    chat_id = message.chat.id
    photo = _photo_url()

    # 1) reply with photo
    try:
        return await message.reply_photo(
            photo=photo,
            caption=text,
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
        )
    except FloodWait as fw:
        await asyncio.sleep(fw.value + 1)
        try:
            return await message.reply_photo(
                photo=photo,
                caption=text,
                reply_markup=kb,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            LOGGER.warning(f"start reply_photo retry: {e}")
    except Exception as e:
        LOGGER.warning(f"start reply_photo: {e}")

    # 2) send_photo to chat (not as reply)
    try:
        return await bot.send_photo(
            chat_id,
            photo=photo,
            caption=text,
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        LOGGER.warning(f"start send_photo: {e}")

    # 3) text only with buttons
    try:
        return await message.reply_text(
            text,
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as e:
        LOGGER.warning(f"start reply_text: {e}")

    try:
        return await bot.send_message(
            chat_id,
            text,
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as e:
        LOGGER.error(f"start send_message failed: {e}")
    return None


@bot.on_message(filters.command("start") & ~filters.forwarded, group=0)
async def start_handler(_, message: Message) -> None:
    chat_id = message.chat.id if message.chat else 0
    now = time.time()

    last = _last_start.get(chat_id, 0)
    if now - last < _START_COOLDOWN:
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

        kb = _start_keyboard()

        if chat_type == ChatType.PRIVATE:
            text = _plain_private(uid, name)
            await _send_start(message, text, kb)
            try:
                add_broadcast_chat(chat_id, "private")
            except Exception:
                pass
            return

        title = (message.chat.title or "this chat").replace("<", "").replace(">", "")
        text = _plain_group(uid, name, title)
        await _send_start(message, text, kb)

        try:
            add_broadcast_chat(chat_id, "group")
        except Exception:
            pass

    except Exception as e:
        LOGGER.error(f"/start crash: {e}")
        try:
            await message.reply_text(
                "⚡ Bot is online.\nUse <code>/play song</code> in a group.",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


@bot.on_message(filters.command("help") & ~filters.forwarded, group=0)
async def help_handler(_, message: Message) -> None:
    try:
        kb = InlineKeyboardMarkup([
            [
                _btn("🎵 Play", callback_data="help_play"),
                _btn("⚙️ Admin", callback_data="help_admin"),
            ],
            [
                _btn("🛠️ Tools", callback_data="help_tools"),
                _btn("ℹ️ Extra", callback_data="help_extra"),
            ],
            [_btn("🏠 Home", callback_data="start_home")],
        ])
        text = (
            "📖 <b>Help menu</b>\n\n"
            "• <code>/play song</code>\n"
            "• <code>/vplay song</code>\n"
            "• <code>/cplay song</code>\n"
            "• <code>/pause</code> · <code>/skip</code> · <code>/stop</code>\n"
            "• <code>/queue</code> · <code>/lyrics</code>\n"
            "• <code>/ping</code>"
        )
        await message.reply_text(
            text,
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as e:
        LOGGER.error(f"/help failed: {e}")
