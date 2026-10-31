# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

from pyrogram import filters
from pyrogram.types import Message

import asyncio

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
    is_sudo_user,
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


async def _owner_or_sudo(_, __, message: Message) -> bool:
    """Owner everywhere; sudo users only in private chat for the blocklist allowlist."""
    user = getattr(message, "from_user", None)
    user_id = int(getattr(user, "id", 0) or 0)
    if not user_id:
        return False
    if user_id == int(config.OWNER_ID):
        return True
    chat_type = getattr(getattr(message, "chat", None), "type", None)
    chat_type = str(getattr(chat_type, "value", chat_type)).casefold()
    if chat_type != "private":
        return False
    try:
        return await asyncio.to_thread(is_sudo_user, user_id)
    except Exception:
        return False


owner_or_sudo = filters.create(_owner_or_sudo)


# ── /gblock ────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("gblock", prefixes=config.COMMAND_PREFIX_LIST) & owner_or_sudo)
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
                rich_heading("⚠️ Invalid chat ID", level=3)
                + rich_kv_table([("Usage", "<code>/gblock -100xxxxxxx</code>")]),
            )
            return
    else:
        if message.chat.type.name == "PRIVATE":
            await rich_send(
                bot, chat_id,
                rich_heading("ℹ️ Choose a group or provide its chat ID", level=3)
                + rich_kv_table([("Usage", "<code>/gblock -100xxxxxxx</code>")]),
            )
            return
        chat_id = message.chat.id

    if is_group_blocked(chat_id):
        await rich_send(
            bot, message.chat.id,
            rich_heading("⛔ Group already blocked", level=3)
            + rich_kv_table([("Group", f"<code>{chat_id}</code>")]),
        )
        return

    block_group(chat_id)
    await rich_send(
        bot, message.chat.id,
        rich_heading("⛔ Group blocked", level=3)
        + rich_kv_table([("Chat ID", f"<code>{chat_id}</code>")])
        + rich_note("Commands are now disabled in this group."),
    )


# ── /gunblock ──────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("gunblock", prefixes=config.COMMAND_PREFIX_LIST) & owner_or_sudo)
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
                rich_heading("⚠️ Invalid chat ID", level=3)
                + rich_kv_table([("Usage", "<code>/gunblock -100xxxxxxx</code>")]),
            )
            return
    else:
        if message.chat.type.name == "PRIVATE":
            await rich_send(
                bot, chat_id,
                rich_heading("ℹ️ Choose a group or provide its chat ID", level=3)
                + rich_kv_table([("Usage", "<code>/gunblock -100xxxxxxx</code>")]),
            )
            return
        chat_id = message.chat.id

    if not is_group_blocked(chat_id):
        await rich_send(
            bot, message.chat.id,
            rich_heading("ℹ️ Group is not blocked", level=3)
            + rich_kv_table([("Group", f"<code>{chat_id}</code>")]),
        )
        return

    unblock_group(chat_id)
    await rich_send(
        bot, message.chat.id,
        rich_heading("✅ Group unblocked", level=3)
        + rich_kv_table([("Chat ID", f"<code>{chat_id}</code>")])
        + rich_note("Commands are enabled in this group again."),
    )


# ── /ublock ────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("ublock", prefixes=config.COMMAND_PREFIX_LIST) & owner_or_sudo)
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
                rich_heading("⚠️ Invalid user ID", level=3)
                + rich_note("Use <code>/ublock 123456789</code>, or reply to the member’s message."),
            )
            return
    else:
        await rich_send(
            bot, chat_id,
            rich_heading("ℹ️ Choose a member to block", level=3)
            + rich_kv_table([("Usage", "<code>/ublock 123456789</code>")]),
        )
        return

    if user_id == config.OWNER_ID:
        await rich_send(bot, chat_id, rich_heading("⛔ You can’t block the bot owner", level=3))
        return

    if is_user_blocked_db(user_id):
        await rich_send(
            bot, chat_id,
            rich_heading("⛔ User already blocked", level=3)
            + rich_kv_table([("user", f"<code>{user_id}</code>")]),
        )
        return

    block_user(user_id)
    rows = [("User ID", f"<code>{user_id}</code>")]
    if user_name:
        rows.append(("Name", rich_esc(user_name)))
    await rich_send(
        bot, chat_id,
        rich_heading("⛔ User blocked", level=3)
        + rich_kv_table(rows)
        + rich_note("This user can no longer use bot commands."),
    )


# ── /uunblock ──────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("uunblock", prefixes=config.COMMAND_PREFIX_LIST) & owner_or_sudo)
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
                rich_heading("⚠️ Invalid user ID", level=3)
                + rich_note("Use <code>/uunblock 123456789</code>, or reply to the member’s message."),
            )
            return
    else:
        await rich_send(
            bot, chat_id,
            rich_heading("ℹ️ Choose a member to unblock", level=3)
            + rich_kv_table([("Usage", "<code>/uunblock 123456789</code>")]),
        )
        return

    if not is_user_blocked_db(user_id):
        await rich_send(
            bot, chat_id,
            rich_heading("ℹ️ User is not blocked", level=3)
            + rich_kv_table([("user", f"<code>{user_id}</code>")]),
        )
        return

    unblock_user(user_id)
    rows = [("User ID", f"<code>{user_id}</code>")]
    if user_name:
        rows.append(("Name", rich_esc(user_name)))
    await rich_send(
        bot, chat_id,
        rich_heading("✅ User unblocked", level=3)
        + rich_kv_table(rows)
        + rich_note("This user can use bot commands again."),
    )


# ── /blocklist ─────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("blocklist", prefixes=config.COMMAND_PREFIX_LIST) & owner_or_sudo)
async def blocklist_cmd(_, message: Message) -> None:
    """Show all blocked groups and users."""
    groups = get_blocked_groups()
    users  = get_blocked_users()

    rows = [("Group", f"<code>{g}</code>") for g in groups]
    rows += [("User", f"<code>{u}</code>") for u in users]

    content = rich_heading(f"🛡 Block list · {len(groups)} groups · {len(users)} users", level=3)
    if rows:
        content += rich_kv_table(rows, headers=["Type", "ID"])
    else:
        content += rich_note("No groups or users are currently blocked.")

    await rich_send(bot, message.chat.id, content)
    
