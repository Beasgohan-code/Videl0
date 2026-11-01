"""Rose-style per-admin group connection for private-chat moderation."""
from __future__ import annotations

import asyncio
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import InlineKeyboardMarkup

from videl.app.router import Command, CommandError, Screen
from videl.plugins.base import escape, is_group, is_private
from videl.utils.bot_ui import button
from videl.utils.db import connect_user, disconnect_user, get_connected_chat
from videl.utils.rich_ui import rich_heading, rich_kv_table, rich_note


def _is_group_admin(member) -> bool:
    return getattr(member, "status", None) in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}


async def _username(client) -> str:
    me = getattr(client, "me", None) or await client.get_me()
    return str(getattr(me, "username", "") or "").lstrip("@")


async def connection_status(ctx) -> Screen:
    message, user = ctx.message, ctx.user
    if not is_private(message):
        return Screen(
            rich_heading("🔗 Manage this group from DM", level=3)
            + rich_note("As a group admin, run <code>/connect</code> here. Then message me privately and use the supported admin commands there.")
        )
    if not user:
        raise CommandError("I couldn’t verify your Telegram account.")
    chat_id = await asyncio.to_thread(get_connected_chat, int(user.id))
    if not chat_id:
        return Screen(
            rich_heading("🔗 No connected group", level=3)
            + rich_note("Run <code>/connect</code> in a group where you are an administrator. I’ll only route commands to that saved group and recheck your admin rights each time.")
        )
    try:
        chat = await ctx.client.get_chat(int(chat_id))
        member = await ctx.client.get_chat_member(int(chat_id), int(user.id))
    except Exception:
        return Screen(
            rich_heading("⚠️ Connection needs attention", level=3)
            + rich_note("I can’t verify access to the saved group. Check that I’m still in the group, or run <code>/disconnect</code> to remove the link.")
        )
    active = _is_group_admin(member)
    return Screen(
        rich_heading("🔗 Connected group", level=3)
        + rich_kv_table([
            ("Group", escape(getattr(chat, "title", "Telegram group"))),
            ("Access", "Admin verified" if active else "Admin access no longer verified"),
        ])
        + rich_note("Use <code>/disconnect</code> to remove your personal link. Every remote action checks your current admin rights.")
    )


async def connect(ctx) -> Screen:
    message, user = ctx.message, ctx.user
    if not user:
        raise CommandError("I couldn’t verify your Telegram account.")
    if is_private(message):
        return await connection_status(ctx)
    if not is_group(message):
        raise CommandError("Use <code>/connect</code> in a group, or check <code>/connection</code> in private chat.")
    try:
        member = await ctx.client.get_chat_member(message.chat.id, int(user.id))
    except Exception:
        raise CommandError("Telegram could not verify your group role. Try again in the group.") from None
    if not _is_group_admin(member):
        raise CommandError("Only a current group administrator can connect this group to their private chat.")
    saved = await asyncio.to_thread(connect_user, int(user.id), int(message.chat.id))
    if not saved:
        raise CommandError("The private connection could not be saved. Check that MongoDB is connected, then try again.")
    username = await _username(ctx.client)
    buttons = []
    if username:
        buttons.append(button("Open private chat", url=f"https://t.me/{username}?start=connect", style="primary", icon="boseh_person"))
    buttons.append(button("Browse commands", callback_data="cmds:manage:0", icon="search"))
    return Screen(
        rich_heading("✅ Group connected to your DM", level=3)
        + rich_note("You can now run supported moderation, group settings and music controls in my private chat. Your admin rights are checked again for every action; this link only applies to your Telegram account.")
        + rich_kv_table([("Group", escape(getattr(message.chat, "title", "this group"))), ("Disconnect", "Use <code>/disconnect</code> in DM or here.")]),
        InlineKeyboardMarkup([buttons]),
    )


async def disconnect(ctx) -> Screen:
    message, user = ctx.message, ctx.user
    if not user:
        raise CommandError("I couldn’t verify your Telegram account.")
    connected = await asyncio.to_thread(get_connected_chat, int(user.id))
    if is_group(message):
        try:
            member = await ctx.client.get_chat_member(message.chat.id, int(user.id))
        except Exception:
            raise CommandError("Telegram could not verify your group role. Try again in the group.") from None
        if not _is_group_admin(member):
            raise CommandError("Only a current group administrator can disconnect this group.")
        if connected != message.chat.id:
            raise CommandError("Your private chat is not connected to this group.")
    elif not is_private(message):
        raise CommandError("Use <code>/disconnect</code> in the connected group or in private chat.")
    if not connected:
        return Screen(rich_heading("ℹ️ No active connection", level=3) + rich_note("There is no group link saved for your account."))
    removed = await asyncio.to_thread(disconnect_user, int(user.id))
    if not removed:
        raise CommandError("I couldn’t confirm that the connection was removed. Check MongoDB and try again.")
    return Screen(
        rich_heading("✅ Group disconnected", level=3)
        + rich_note("Your personal private-chat link was removed. Other admins’ connections are unchanged.")
    )


COMMANDS = (
    Command("connect", connect, "Connect a group to your DM for admin controls", category="manage"),
    Command("disconnect", disconnect, "Remove your private-chat group connection", category="manage"),
    Command("connection", connection_status, "Show your connected-group status", category="manage"),
)
