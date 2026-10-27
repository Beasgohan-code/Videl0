# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import logging
import random

from pyrogram import filters
from pyrogram.errors import ChatAdminRequired
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, Message
from videl.utils.bot_ui import button as InlineKeyboardButton

import config
from videl import bot
from videl.utils.db import (
    add_broadcast_chat,
    add_served_chat,
    remove_broadcast_chat,
    remove_served_chat,
)
from videl.utils.rich_ui import rich_esc, rich_heading, rich_img, rich_kv_table, rich_note
from videl.utils.command_ui import rich_send

LOGGER = logging.getLogger(__name__)

LEFT_PHOTOS = [
    "https://telegra.ph/file/1949480f01355b4e87d26.jpg",
    "https://telegra.ph/file/3ef2cc0ad2bc548bafb30.jpg",
    "https://telegra.ph/file/a7d663cd2de689b811729.jpg",
    "https://telegra.ph/file/6f19dc23847f5b005e922.jpg",
    "https://telegra.ph/file/2973150dd62fd27a3a6ba.jpg",
]


def _admin_setup_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Clear, honest onboarding: Telegram requires a human admin to promote bots."""
    content = (
        rich_heading("✨ Thanks for adding Videl!", level=2)
        + rich_note("I’m ready to help. To enable moderation and voice-chat features, a current group admin can promote me with these permissions:")
        + rich_kv_table([
            ("🗑 Delete messages", "Moderation tools"),
            ("🎥 Manage video chats", "Voice-chat features"),
            ("👥 Invite users", "Invite and join features"),
        ])
        + rich_note("Open <b>Group info → Administrators → Add administrator</b>, select Videl, then enable the permissions above. Telegram doesn’t let me grant myself admin rights.")
        + rich_note("You can still use features that don’t require these permissions. An admin can update my rights later in the same menu.")
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("ℹ️ Permission checklist", callback_data="bot_setup:permissions", style="primary"),
    ]])
    return content, keyboard


@bot.on_callback_query(filters.regex(r"^bot_setup:permissions$"))
async def bot_setup_permissions(_, query) -> None:
    await query.answer(
        "Group info → Administrators → Add administrator → choose Videl. Enable Delete messages, Manage video chats, and Invite users. A current admin must do this; Videl cannot promote itself.",
        show_alert=True,
    )


# ── Bot added to group ─────────────────────────────────────────────────────────

@bot.on_message(filters.new_chat_members, group=-10)
async def bot_added_watcher(_, message: Message) -> None:
    try:
        chat    = message.chat
        chat_id = chat.id
        me      = await bot.get_me()

        for member in message.new_chat_members:
            if member.id != me.id:
                continue

            add_served_chat(chat_id)
            add_broadcast_chat(chat_id, "group")

            added_by         = message.from_user
            added_by_mention = added_by.mention if added_by else "unknown"

            admin_request_text, admin_kb = _admin_setup_panel()
            try:
                await rich_send(bot, chat_id, admin_request_text, reply_markup=admin_kb)
            except Exception:
                pass

            if not config.LOGGER_ID:
                return

            try:
                invite_link = await bot.export_chat_invite_link(chat_id)
                link_text   = f"<a href='{invite_link}'>get link</a>"
            except (ChatAdminRequired, Exception):
                link_text = "no link"

            try:
                count = await bot.get_chat_members_count(chat_id)
            except Exception:
                count = "N/A"

            username   = f"@{chat.username}" if chat.username else "private group"
            chat_photo = None
            try:
                if chat.photo:
                    chat_photo = await bot.download_media(
                        chat.photo.big_file_id,
                        file_name=f"grppp_{chat_id}.png",
                    )
            except Exception:
                chat_photo = None

            log_rows = [
                ("chat name", rich_esc(chat.title)),
                ("chat id", f"<code>{chat_id}</code>"),
                ("username", rich_esc(username)),
                ("group link", link_text),
                ("members", str(count)),
                ("added by", added_by_mention),
            ]
            log_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    f"👤 {added_by.first_name if added_by else 'user'}",
                    user_id=added_by.id if added_by else config.OWNER_ID,
                )
            ]]) if added_by else None

            try:
                if chat_photo:
                    # Locally downloaded file — no public URL, so this has
                    # to stay a caption (rich_img() only takes URLs).
                    log_text = (
                        "<b>📝 #newgroup — bot added!</b>\n\n"
                        + "\n".join(f"<b>{k} :</b> {v}" for k, v in log_rows)
                    )
                    await bot.send_photo(
                        config.LOGGER_ID, photo=chat_photo,
                        caption=log_text, parse_mode=ParseMode.HTML, reply_markup=log_kb,
                    )
                else:
                    content = (
                        rich_heading("📝 #newgroup — bot added!", level=3)
                        + rich_kv_table(log_rows)
                    )
                    await rich_send(bot, config.LOGGER_ID, content, reply_markup=log_kb)
            except Exception:
                pass

    except Exception as e:
        LOGGER.warning(f"[watcher] bot_added: {e}", exc_info=True)


# ── Bot left / removed ─────────────────────────────────────────────────────────

@bot.on_message(filters.left_chat_member, group=-12)
async def bot_left_watcher(_, message: Message) -> None:
    try:
        left_member = message.left_chat_member
        if not left_member:
            return

        me = await bot.get_me()
        if left_member.id != me.id:
            return

        chat    = message.chat
        chat_id = chat.id

        remove_served_chat(chat_id)
        remove_broadcast_chat(chat_id)

        removed_by         = message.from_user
        removed_by_mention = removed_by.mention if removed_by else "unknown user"
        username           = f"@{chat.username}" if chat.username else "private chat"

        if not config.LOGGER_ID:
            return

        content = (
            rich_heading("✫ #leftgroup ✫", level=3)
            + rich_img(random.choice(LEFT_PHOTOS))
            + rich_kv_table([
                ("chat title", rich_esc(chat.title)),
                ("chat id", f"<code>{chat_id}</code>"),
                ("username", rich_esc(username)),
                ("removed by", removed_by_mention),
                ("bot", f"@{me.username}"),
            ])
        )

        try:
            await rich_send(bot, config.LOGGER_ID, content)
        except Exception:
            pass

    except Exception as e:
        LOGGER.warning(f"[watcher] bot_left: {e}", exc_info=True)
