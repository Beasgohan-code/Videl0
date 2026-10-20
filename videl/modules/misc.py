# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

"""
Utility commands:
  /repo  — send source code link
  /id    — get IDs of message / user / chat / replied message
"""

import config
from pyrogram import enums, filters
from pyrogram.types import InlineKeyboardMarkup, Message
from videl.utils.bot_ui import button as InlineKeyboardButton

from videl import bot
from videl.modules.block import user_allowed
from videl.utils.rich_ui import (
    rich_details,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_reply,
)

# ── Source repo URL ────────────────────────────────────────────────────────────
SOURCE_URL = "https://github.com/Beasgohan-code/Videl"


# ── /repo ──────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("repo") & user_allowed)
async def repo_cmd(_, message: Message) -> None:

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    " Source Code",
                    url=SOURCE_URL,
                ),
                InlineKeyboardButton(
                    "🔱 Fork",
                    url=SOURCE_URL,
                ),
            ],
            [
                InlineKeyboardButton(
                    " support",
                    url=config.SUPPORT_GROUP,
                ),
                InlineKeyboardButton(
                    " Updates",
                    url=config.UPDATES_CHANNEL,
                ),
            ],
        ]
    )

    content = (
        rich_heading(" Videl Source", level=3)
        + "<p>❍ open source music bot, developed by <b>beaꜱgohan</b> ❤️</p>"
        + rich_details(
            "⚡ hosting support",
            rich_kv_table([
                ("free", "render  · koyeb  · railway "),
                ("premium", "heroku  vps (24x7)"),
            ]),
            open=True,
        )
        + rich_note(
            f"❍ <a href='{SOURCE_URL}'>github repo</a> — feel free to hit ⭐ on github!"
        )
    )

    await rich_reply(message, content, reply_markup=kb)


# ── /id ────────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("id") & user_allowed)
async def id_cmd(client, message: Message) -> None:

    chat       = message.chat
    your_id    = message.from_user.id if message.from_user else "N/A"
    message_id = message.id
    reply      = message.reply_to_message

    # ── Base rows ──────────────────────────────────────────────────────────────
    rows = [
        ("<a href='{}'>message id</a>".format(message.link), f"<code>{message_id}</code>"),
        (f"<a href='tg://user?id={your_id}'>your id</a>", f"<code>{your_id}</code>"),
    ]

    # ── Optional: lookup another user by username or ID ───────────────────────
    args = message.command[1:]
    if args:
        try:
            target    = await client.get_users(args[0])
            target_id = target.id
            rows.append((f"<a href='tg://user?id={target_id}'>user id</a>", f"<code>{target_id}</code>"))
        except Exception:
            await rich_reply(
                message,
                rich_heading("❍ user not found", level=3),
            )
            return

    # ── Chat ID ────────────────────────────────────────────────────────────────
    if chat.username:
        chat_link = f"https://t.me/{chat.username}"
    else:
        chat_link = f"tg://user?id={chat.id}"

    rows.append((f"<a href='{chat_link}'>chat id</a>", f"<code>{chat.id}</code>"))

    # ── Replied message ────────────────────────────────────────────────────────
    if reply and not getattr(reply, "empty", True):

        # Replied user ID
        if reply.from_user and not getattr(reply, "sender_chat", None):
            rows.append((f"<a href='{reply.link}'>replied msg id</a>", f"<code>{reply.id}</code>"))
            rows.append((
                f"<a href='tg://user?id={reply.from_user.id}'>replied user</a>",
                f"<code>{reply.from_user.id}</code>",
            ))

        # Forwarded from channel
        fwd_chat = getattr(reply, "forward_from_chat", None)
        if fwd_chat:
            rows.append(("fwd channel", fwd_chat.title))
            rows.append(("fwd channel id", f"<code>{fwd_chat.id}</code>"))

        # Sender chat (anonymous group admin / channel post)
        sender_chat = getattr(reply, "sender_chat", None)
        if sender_chat:
            rows.append(("sender chat", sender_chat.title))
            rows.append(("sender chat id", f"<code>{sender_chat.id}</code>"))

    content = (
        rich_heading("❍ id info", level=3)
        + rich_kv_table(rows)
    )

    await rich_reply(message, content)


# ── /cleanup (owner) — force 30-day DB + download cleanup ──────────────────────

@bot.on_message(filters.command(["cleanup", "dbcleanup"]) & filters.user(config.OWNER_ID))
async def cleanup_cmd(_, message: Message) -> None:
    from videl.utils.db import cleanup_old_data
    from videl.core.watcher import _cleanup_downloads
    from videl.utils.rich_ui import rich_send, rich_heading as _rh, rich_kv_table as _rkv, rich_note as _rn

    try:
        db_stats = cleanup_old_data(days=30)
        dl = await _cleanup_downloads()
        rows = [(k, str(v)) for k, v in (db_stats or {}).items()]
        rows.append(("downloads_removed", str(dl)))
        await rich_reply(
            message,
            _rh(" Cleanup complete", level=3)
            + _rkv(rows)
            + _rn("Inactive chats/users & old playlists older than 30 days removed."),
        )
    except Exception as e:
        await rich_reply(
            message,
            _rh(" Cleanup failed", level=3) + _rn(str(e)),
        )
