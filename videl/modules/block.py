# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

from pyrogram import filters
from pyrogram.types import Message

import config
from videl import bot
from videl.utils.db import (
    block_group,
    unblock_group,
    is_group_blocked,
    get_blocked_groups,
    block_user,
    unblock_user,
    is_user_blocked_db,
    get_blocked_users,
)
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note, sanitize_display_name
from videl.utils.command_ui import rich_send


# ── Pyrogram filters (import these in other modules) ──────────────────────────

def _group_not_blocked(_, __, message: Message) -> bool:
    try:
        if message.chat and message.chat.id:
            return not is_group_blocked(message.chat.id)
    except Exception:
        return True
    return True


def _user_not_blocked(_, __, message: Message) -> bool:
    try:
        if message.from_user and message.from_user.id:
            return not is_user_blocked_db(message.from_user.id)
    except Exception:
        return True
    return True


group_allowed = filters.create(_group_not_blocked)
user_allowed  = filters.create(_user_not_blocked)


# ── /gblock ────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("gblock") & filters.user(config.OWNER_ID))
async def gblock_cmd(_, message: Message) -> None:
    """Block a group — /gblock or /gblock -100xxxxxxx"""
    chat_id = message.chat.id
    args = message.command[1:]

    if args:
        try:
            chat_id = int(args[0])
        except ValueError:
            await rich_send(
                bot, chat_id,
                rich_heading("❍ invalid chat id", level=3)
                + rich_kv_table([("usage", "<code>/gblock -100xxxxxxx</code>")]),
            )
            return
    else:
        if message.chat.type.name == "PRIVATE":
            await rich_send(
                bot, chat_id,
                rich_heading("❍ use in a group or provide a chat id", level=3)
                + rich_kv_table([("usage", "<code>/gblock -100xxxxxxx</code>")]),
            )
            return
        chat_id = message.chat.id

    if is_group_blocked(chat_id):
        await rich_send(
            bot, message.chat.id,
            rich_heading("❍ already blocked", level=3)
            + rich_kv_table([("group", f"<code>{chat_id}</code>")]),
        )
        return

    block_group(chat_id)
    await rich_send(
        bot, message.chat.id,
        rich_heading(" group blocked ", level=3)
        + rich_kv_table([("chat id", f"<code>{chat_id}</code>")])
        + rich_note("no commands will work in this group now."),
    )


# ── /gunblock ──────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("gunblock") & filters.user(config.OWNER_ID))
async def gunblock_cmd(_, message: Message) -> None:
    """Unblock a group — /gunblock or /gunblock -100xxxxxxx"""
    chat_id = message.chat.id
    args = message.command[1:]

    if args:
        try:
            chat_id = int(args[0])
        except ValueError:
            await rich_send(
                bot, chat_id,
                rich_heading("❍ invalid chat id", level=3)
                + rich_kv_table([("usage", "<code>/gunblock -100xxxxxxx</code>")]),
            )
            return
    else:
        if message.chat.type.name == "PRIVATE":
            await rich_send(
                bot, chat_id,
                rich_heading("❍ use in a group or provide a chat id", level=3)
                + rich_kv_table([("usage", "<code>/gunblock -100xxxxxxx</code>")]),
            )
            return
        chat_id = message.chat.id

    if not is_group_blocked(chat_id):
        await rich_send(
            bot, message.chat.id,
            rich_heading("❍ not blocked", level=3)
            + rich_kv_table([("group", f"<code>{chat_id}</code>")]),
        )
        return

    unblock_group(chat_id)
    await rich_send(
        bot, message.chat.id,
        rich_heading(" group unblocked ", level=3)
        + rich_kv_table([("chat id", f"<code>{chat_id}</code>")])
        + rich_note("commands are now enabled in this group."),
    )


# ── /ublock ────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("ublock") & filters.user(config.OWNER_ID))
async def ublock_cmd(_, message: Message) -> None:
    """Block a user — reply to their message or /ublock 123456789"""
    chat_id   = message.chat.id
    args      = message.command[1:]
    user_id   = None
    user_name = None

    if message.reply_to_message and message.reply_to_message.from_user:
        user_id   = message.reply_to_message.from_user.id
        user_name = sanitize_display_name(message.reply_to_message.from_user.first_name)
    elif args:
        try:
            user_id = int(args[0])
        except ValueError:
            await rich_send(
                bot, chat_id,
                rich_heading("❍ invalid user id", level=3)
                + rich_note("use » <code>/ublock 123456789</code> or reply to a user."),
            )
            return
    else:
        await rich_send(
            bot, chat_id,
            rich_heading("❍ reply to a user's message or provide a user id", level=3)
            + rich_kv_table([("usage", "<code>/ublock 123456789</code>")]),
        )
        return

    if user_id == config.OWNER_ID:
        await rich_send(bot, chat_id, rich_heading("❍ you cannot block yourself (owner)", level=3))
        return

    if is_user_blocked_db(user_id):
        await rich_send(
            bot, chat_id,
            rich_heading("❍ already blocked", level=3)
            + rich_kv_table([("user", f"<code>{user_id}</code>")]),
        )
        return

    block_user(user_id)
    rows = [("user id", f"<code>{user_id}</code>")]
    if user_name:
        rows.append(("name", rich_esc(user_name)))
    await rich_send(
        bot, chat_id,
        rich_heading(" user blocked ", level=3)
        + rich_kv_table(rows)
        + rich_note("this user cannot use any bot commands now."),
    )


# ── /uunblock ──────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("uunblock") & filters.user(config.OWNER_ID))
async def uunblock_cmd(_, message: Message) -> None:
    """Unblock a user — reply to their message or /uunblock 123456789"""
    chat_id   = message.chat.id
    args      = message.command[1:]
    user_id   = None
    user_name = None

    if message.reply_to_message and message.reply_to_message.from_user:
        user_id   = message.reply_to_message.from_user.id
        user_name = sanitize_display_name(message.reply_to_message.from_user.first_name)
    elif args:
        try:
            user_id = int(args[0])
        except ValueError:
            await rich_send(
                bot, chat_id,
                rich_heading("❍ invalid user id", level=3)
                + rich_note("use » <code>/uunblock 123456789</code> or reply to a user."),
            )
            return
    else:
        await rich_send(
            bot, chat_id,
            rich_heading("❍ reply to a user's message or provide a user id", level=3)
            + rich_kv_table([("usage", "<code>/uunblock 123456789</code>")]),
        )
        return

    if not is_user_blocked_db(user_id):
        await rich_send(
            bot, chat_id,
            rich_heading("❍ not blocked", level=3)
            + rich_kv_table([("user", f"<code>{user_id}</code>")]),
        )
        return

    unblock_user(user_id)
    rows = [("user id", f"<code>{user_id}</code>")]
    if user_name:
        rows.append(("name", rich_esc(user_name)))
    await rich_send(
        bot, chat_id,
        rich_heading(" user unblocked ", level=3)
        + rich_kv_table(rows)
        + rich_note("this user can now use bot commands again."),
    )


# ── /blocklist ─────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("blocklist") & filters.user(config.OWNER_ID))
async def blocklist_cmd(_, message: Message) -> None:
    """Show all blocked groups and users."""
    groups = get_blocked_groups()
    users  = get_blocked_users()

    rows = [("group", f"<code>{g}</code>") for g in groups]
    rows += [("user", f"<code>{u}</code>") for u in users]

    content = rich_heading(f"❍ block list — {len(groups)} groups, {len(users)} users", level=3)
    if rows:
        content += rich_kv_table(rows, headers=["type", "id"])
    else:
        content += rich_note("nothing is blocked.")

    await rich_send(bot, message.chat.id, content)
    
