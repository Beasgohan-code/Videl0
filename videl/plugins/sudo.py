"""A narrowly-scoped bot operator role, managed only by the private owner.

Sudo may use bot-wide blocklist commands. It never substitutes for Telegram
admin rights and never grants access to owner fleet, backup, recording, or
account controls.
"""
from __future__ import annotations

import asyncio
import logging

from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup

import config
from videl import bot
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.audit import record_bot
from videl.utils.bot_ui import button
from videl.utils.command_ui import rich_edit, usage
from videl.utils.db import add_sudo_user, get_sudo_users, is_sudo_user, remove_sudo_user

LOGGER = logging.getLogger(__name__)
MAX_SUDO_USERS = 25


def _is_private_owner(message, actor) -> bool:
    chat_type = getattr(getattr(message, "chat", None), "type", None)
    chat_type = str(getattr(chat_type, "value", chat_type)).casefold()
    chat_id = int(getattr(getattr(message, "chat", None), "id", 0) or 0)
    return (
        chat_type == "private"
        and chat_id == int(config.OWNER_ID)
        and int(getattr(actor, "id", 0) or 0) == int(config.OWNER_ID)
    )


def _sudo_screen(documents) -> Screen:
    if documents is None:
        raise CommandError("The sudo roster database is unavailable; no changes were made.")
    if not documents:
        return Screen(
            heading("🛡 Bot sudo", 3)
            + body("No sudo operators are configured.")
            + body("Add one with <code>/addsudo user_id [duration]</code> or reply with <code>/addsudo [duration]</code>. Omit duration for permanent access; for example, <code>7d</code> expires after seven days."),
        )
    rows = []
    buttons = []
    for item in documents[:MAX_SUDO_USERS]:
        user_id = int(item.get("_id", 0))
        added_by = int(item.get("added_by", 0) or 0)
        expires_at = item.get("expires_at")
        expiry = "Never" if expires_at is None else escape(expires_at.strftime("%Y-%m-%d %H:%M UTC"))
        rows.append((f'<a href="tg://user?id={user_id}">User {user_id}</a>',
                     f"<code>{user_id}</code> · added by <code>{added_by}</code> · expires: {expiry}"))
        buttons.append([button(f"Remove {user_id}", callback_data=f"sudoadmin:remove:{user_id}", style="danger")])
    text = (
        heading(f"🛡 Bot sudo operators · {len(documents)}", 3)
        + table(rows)
            + body("These operators can use <code>/gblock</code>, <code>/gunblock</code>, <code>/ublock</code>, <code>/uunblock</code>, <code>/blocklist</code>, <code>/voicequality</code>, and <code>/voicehealth</code> from private chat. They cannot use group-admin controls, restart the service, or access owner fleet, backup, recording, deployment, or sudo-management tools.")
    )
    return Screen(text, InlineKeyboardMarkup(buttons))


async def _resolve_operator(ctx):
    """Resolve one user by reply, numeric ID, or username without trusting extra args."""
    reply = getattr(ctx.message, "reply_to_message", None)
    replied_user = getattr(reply, "from_user", None) if reply else None
    if replied_user is not None:
        user_id = int(getattr(replied_user, "id", 0) or 0)
        label = f'<a href="tg://user?id={user_id}">{escape(getattr(replied_user, "first_name", None) or f"User {user_id}")}</a>'
        return user_id, label, ctx.command.arguments.split(), bool(getattr(replied_user, "is_bot", False))
    tokens = ctx.command.arguments.split()
    if not tokens:
        return 0, "", [], False
    identifier, *remainder = tokens
    if identifier.isdecimal():
        user_id = int(identifier)
        return user_id, f"<code>{user_id}</code>", remainder, False
    try:
        user = await ctx.client.get_users(identifier)
    except Exception:
        user = None
    if user is None:
        return 0, "", remainder, False
    user_id = int(getattr(user, "id", 0) or 0)
    label = f'<a href="tg://user?id={user_id}">{escape(getattr(user, "first_name", None) or f"User {user_id}")}</a>'
    return user_id, label, remainder, bool(getattr(user, "is_bot", False))


async def add_sudo(ctx) -> Screen:
    user_id, label, remainder, is_bot = await _resolve_operator(ctx)
    if not user_id:
        return Screen(usage("/addsudo @username", "Or reply to a user message, or use /addsudo numeric_id."))
    expires_at = None
    if len(remainder) > 1:
        return Screen(usage("/addsudo @username [duration]", "Use one optional duration such as 7d, 12h, or 30m."))
    if remainder:
        seconds = base.parse_duration(remainder[0])
        if seconds is None:
            return Screen(usage("/addsudo @username [duration]", "Duration must be 60 seconds to 365 days, for example 7d."))
        expires_at = base.until(seconds)
    if user_id <= 0 or user_id > 9_223_372_036_854_775_807 or is_bot:
        raise CommandError("Sudo can only be assigned to a valid human Telegram user ID.")
    if user_id == int(config.OWNER_ID):
        raise CommandError("The owner already has every owner permission and cannot be added as sudo.")

    documents = await asyncio.to_thread(get_sudo_users)
    if documents is None:
        raise CommandError("The sudo database is unavailable; no change was made.")
    if user_id not in {int(item.get("_id", 0)) for item in documents} and len(documents) >= MAX_SUDO_USERS:
        raise CommandError(f"The sudo roster is limited to {MAX_SUDO_USERS} operators. Remove one before adding another.")
    status = await asyncio.to_thread(add_sudo_user, user_id, int(ctx.user.id), expires_at)
    if status is None:
        raise CommandError("The database could not confirm the sudo change.")
    if status == "exists":
        return Screen(heading("Already a sudo operator", 3) + body(f"{label} already has the limited bot-operator role."))
    await asyncio.to_thread(
        record_bot, int(ctx.user.id), "settings", action="sudo_add",
        detail=f"added bot sudo user {user_id}", actor=int(ctx.user.id),
    )
    screen = _sudo_screen(await asyncio.to_thread(get_sudo_users))
    return Screen(
        heading("✅ Sudo operator added", 3)
        + table([("User", label), ("User ID", f"<code>{user_id}</code>"), ("Expires", "Never" if expires_at is None else escape(expires_at.strftime("%Y-%m-%d %H:%M UTC"))), ("Scope", "Bot group/user blocklists only")])
        + body("Allowed in private chat only: <code>/gblock</code>, <code>/gunblock</code>, <code>/ublock</code>, <code>/uunblock</code>, and <code>/blocklist</code>.")
        + body("This does not grant Telegram administrator rights or access to owner-only fleet, backup, recording, deployment, or sudo commands."),
        screen.keyboard,
    )

async def remove_sudo(ctx) -> Screen:
    user_id, label, remainder, _is_bot = await _resolve_operator(ctx)
    if not user_id:
        return Screen(usage(f"/{ctx.command.name} @username", "Or reply to the operator's message, or use a numeric ID."))
    if remainder:
        return Screen(usage(f"/{ctx.command.name} @username", "Remove exactly one operator."))
    if user_id <= 0 or user_id == int(config.OWNER_ID):
        raise CommandError("The owner cannot be removed from the sudo role.")
    result = await asyncio.to_thread(remove_sudo_user, user_id)
    if result is None:
        raise CommandError("The sudo database could not confirm the change.")
    if not result:
        return Screen(heading("Not a sudo operator", 3) + body(f"User {label} was not on the sudo roster."))
    await asyncio.to_thread(
        record_bot, int(ctx.user.id), "settings", action="sudo_remove",
        detail=f"removed bot sudo user {user_id}", actor=int(ctx.user.id),
    )
    screen = _sudo_screen(await asyncio.to_thread(get_sudo_users))
    return Screen(
        heading("✅ Sudo operator removed", 3)
        + body(f"User {label} no longer has bot-level blocklist access.")
        + body("Telegram group-admin permissions and owner-only controls are unchanged."),
        screen.keyboard,
    )

async def sudo_list(ctx) -> Screen:
    documents = await asyncio.to_thread(get_sudo_users)
    return _sudo_screen(documents)


async def sudo_help(ctx) -> Screen:
    user_id = int(getattr(ctx.user, "id", 0) or 0)
    if base.chat_kind(ctx.message) != "private" or int(getattr(ctx.message.chat, "id", 0) or 0) != user_id:
        raise CommandError("Use /sudohelp in your own private chat.")
    if user_id != int(config.OWNER_ID) and not await asyncio.to_thread(is_sudo_user, user_id):
        raise CommandError("This account is not on the bot sudo roster.")
    return Screen(
        heading("🛡 Limited bot sudo", 3)
        + body("Available only from private chat: <code>/gblock</code>, <code>/gunblock</code>, <code>/ublock</code>, <code>/uunblock</code>, <code>/blocklist</code>, <code>/voicequality</code>, and <code>/voicehealth</code>.")
        + body("Voice quality changes are global and apply to new streams. Sudo is not Telegram admin status; it cannot bypass group permissions, restart the service, or open owner fleet, backup, recording, deployment, or sudo-management controls."),
    )


@bot.on_callback_query(filters.regex(r"^sudoadmin:"))
async def sudo_inline_callback(client, query: CallbackQuery) -> None:
    message = getattr(query, "message", None)
    user = getattr(query, "from_user", None)
    if message is None or not _is_private_owner(message, user):
        await query.answer("Only the owner in private chat can manage sudo.", show_alert=True)
        return
    try:
        bot_user = getattr(client, "me", None) or await client.get_me()
    except Exception:
        await query.answer("I couldn’t verify this bot message.", show_alert=True)
        return
    if int(getattr(getattr(message, "from_user", None), "id", 0) or 0) != int(getattr(bot_user, "id", 0) or 0):
        await query.answer("This is not a Videl sudo panel.", show_alert=True)
        return
    parts = (query.data or "").split(":")
    if len(parts) != 3 or parts[:2] != ["sudoadmin", "remove"] or not parts[2].isdigit():
        await query.answer("This sudo action is invalid.", show_alert=True)
        return
    user_id = int(parts[2])
    if user_id <= 0 or user_id == int(config.OWNER_ID):
        await query.answer("The owner cannot be removed from sudo.", show_alert=True)
        return
    result = await asyncio.to_thread(remove_sudo_user, user_id)
    if result is None:
        await query.answer("The sudo database is unavailable.", show_alert=True)
        return
    await query.answer("Sudo access removed" if result else "That operator was already removed")
    if result:
        await asyncio.to_thread(
            record_bot, int(config.OWNER_ID), "settings", action="sudo_remove",
            detail=f"removed bot sudo user {user_id}", actor=int(config.OWNER_ID),
        )
    screen = _sudo_screen(await asyncio.to_thread(get_sudo_users))
    await rich_edit(message, screen.html, reply_markup=screen.keyboard)


COMMANDS = (
    Command("addsudo", add_sudo, "Grant limited bot-blocklist operator access", category="owner", policy="owner"),
    Command("delsudo", remove_sudo, "Remove a bot sudo operator", category="owner", policy="owner"),
    Command("rmsudo", remove_sudo, "Remove a bot sudo operator", category="owner", policy="owner"),
    Command("sudolist", sudo_list, "List limited bot sudo operators", category="owner", policy="owner"),
    Command("sudohelp", sudo_help, "Show the limited bot sudo command scope", category="tools"),
)
