#  Videl © 2026 | Beasgohan-code
"""Group housekeeping: pins, purge, slow mode, polls and chat stats."""
from __future__ import annotations

import asyncio
import html
import time

from pyrogram.types import InlineKeyboardMarkup

import config
from videl import bot_start_time
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.bot_ui import button
from videl.utils.command_ui import usage
from videl.utils.rich_ui import rich_heading, rich_note


async def pin(ctx) -> Screen:
    chat_id = ctx.message.chat.id
    reply = getattr(ctx.message, "reply_to_message", None)
    name = ctx.command.name
    if name == "pin":
        if reply is None:
            return Screen(usage("/pin", "Reply to the message you want pinned."))
        if await ctx.client.pin_chat_message(chat_id, reply.id, disable_notification=False) is False:
            raise CommandError("Telegram did not confirm the pin.")
        return Screen(heading("Pinned", 3) + body("The message is pinned for everyone."))
    if name == "unpin":
        if await ctx.client.unpin_chat_message(chat_id) is False:
            raise CommandError("Telegram did not confirm the unpin.")
        return Screen(heading("Unpinned", 3) + body("The latest pin was removed."))
    if await ctx.client.unpin_all_chat_messages(chat_id) is False:
        raise CommandError("Telegram did not confirm the unpin of all messages.")
    return Screen(heading("Pins cleared", 3) + body("Every pinned message was removed."))


async def purge(ctx) -> Screen:
    chat_id = ctx.message.chat.id
    if ctx.command.name == "cleanup":
        argument = ctx.command.arguments.strip()
        if not argument.isdecimal() or not 1 <= int(argument) <= 100:
            return Screen(usage("/cleanup 20", "Deletes the last 1–100 messages including this command."))
        deleted = 0
        for offset in range(int(argument)):
            try:
                if await ctx.client.delete_messages(chat_id, ctx.message.id - offset):
                    deleted += 1
            except Exception:
                continue
        return Screen(heading("Cleanup finished", 3) + body(f"Telegram confirmed {deleted} deletions."))
    reply = getattr(ctx.message, "reply_to_message", None)
    if reply is None:
        return Screen(usage("/purge", "Reply to the first message you want removed."))
    start, end = reply.id, ctx.message.id
    if end <= start:
        raise CommandError("The replied message must be older than this command.")
    if end - start > 200:
        raise CommandError("Purge is limited to 200 messages at a time.")
    deleted = 0
    for message_id in range(start, end + 1):
        try:
            if await ctx.client.delete_messages(chat_id, message_id):
                deleted += 1
        except Exception:
            continue
    return Screen(heading("Purge finished", 3) + body(f"Telegram confirmed {deleted} deletions."))


async def slowmode(ctx) -> Screen:
    argument = ctx.command.arguments.strip()
    if not argument.isdecimal():
        return Screen(usage("/slowmode 10", "Seconds between messages, 0 to disable, up to 3600."))
    seconds = int(argument)
    if not 0 <= seconds <= 3600:
        raise CommandError("Choose between 0 and 3600 seconds.")
    try:
        await ctx.client.set_chat_slow_mode(ctx.message.chat.id, seconds or None)
    except Exception as exc:
        raise CommandError(f"Telegram rejected slow mode ({type(exc).__name__}).") from None
    state = "disabled" if not seconds else f"{seconds}s"
    return Screen(heading("Slow mode", 3) + body(f"Now <b>{state}</b>."))


async def poll(ctx) -> Screen:
    from videl.utils.bot_api import bot_api
    from videl.utils.poll_options import build_poll

    try:
        payload = build_poll(ctx.command.arguments, quiz=ctx.command.name == "quiz")
    except ValueError as exc:
        return Screen(heading("Poll setup", 3) + body(escape(str(exc))))
    payload["chat_id"] = ctx.message.chat.id
    if getattr(ctx.message, "message_thread_id", None):
        payload["message_thread_id"] = ctx.message.message_thread_id
    ok, result = await bot_api("sendPoll", payload)
    if not ok or not result.get("ok"):
        description = result.get("description", "Telegram rejected this poll")
        raise CommandError(f"Poll not sent: {escape(description)}")
    return Screen(heading("Poll sent", 3) + body("Members can vote right away."))


async def sticker_id(ctx) -> Screen:
    reply = getattr(ctx.message, "reply_to_message", None)
    sticker = getattr(reply, "sticker", None) if reply else None
    if sticker is None:
        return Screen(usage("/stickerid", "Reply to a sticker to read its file id."))
    return Screen(
        heading("Sticker file id", 3)
        + body(f"<code>{escape(sticker.file_id)}</code>")
        + body(f"Set: <code>{escape(getattr(sticker, 'set_name', None) or 'unknown')}</code> · "
               f"Unique: <code>{escape(sticker.file_unique_id)}</code>")
    )


async def stats(ctx) -> Screen:
    def collect():
        database = base.db()
        if database is None:
            return None
        counts = {}
        for key, name in (("groups", "mgmt_chat_settings"), ("warnings", "mgmt_warnings"), ("notes", "mgmt_notes")):
            try:
                counts[key] = database[name].count_documents({})
            except Exception:
                counts[key] = "—"
        return counts

    counts = await asyncio.to_thread(collect)
    if counts is None:
        raise CommandError("MongoDB is not connected.")
    uptime = int(time.time() - bot_start_time)
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)
    rows = [
        ("Uptime", f"{hours}h {minutes}m {seconds}s"),
        ("Configured groups", counts["groups"]),
        ("Warnings stored", counts["warnings"]),
        ("Notes stored", counts["notes"]),
        ("Bot", "@" + escape(getattr(config, "BOT_USERNAME", "Videl0Bot"))),
    ]
    return Screen(
        heading("Videl statistics", 3) + table(rows),
        InlineKeyboardMarkup([[button("Owner workspace", callback_data="help:owner:0")]]),
    )


async def invite(ctx) -> Screen:
    """Create an approval-only invite link (admins with invite rights)."""
    argument = ctx.command.arguments.strip().casefold()
    if argument not in {"", "--request", "request"}:
        return Screen(usage("/invite --request", "Creates a link that needs admin approval."))
    try:
        link = await ctx.client.create_chat_invite_link(
            ctx.message.chat.id,
            name="Videl request link",
            request_needed=True,
            creates_join_request=True,
        )
    except Exception as exc:
        raise CommandError(f"Telegram rejected the invite link ({type(exc).__name__}).") from None
    return Screen(
        heading("Invite link ready", 3)
        + body(f"<code>{escape(link.invite_link)}</code>")
        + body("New members using it appear as join requests for an admin to approve.")
    )


async def tagall(ctx) -> Screen | None:
    """Mention a bounded sample of members Telegram exposes to this bot."""
    from html import escape as html_escape

    argument = ctx.command.arguments.strip()
    if len(argument) > 180:
        raise CommandError("Keep the optional announcement under 180 characters.")
    client = ctx.client
    chat_id = ctx.message.chat.id
    mentions = []
    try:
        async for member in client.get_chat_members(chat_id, limit=51):
            user = getattr(member, "user", None)
            if not user or getattr(user, "is_bot", False):
                continue
            name = " ".join(part for part in (getattr(user, "first_name", ""), getattr(user, "last_name", "")) if part).strip() or "member"
            mentions.append(f'<a href="tg://user?id={user.id}">{html_escape(name)}</a>')
            if len(mentions) >= 50:
                break
    except Exception as exc:
        raise CommandError(f"Could not read this group's member list ({type(exc).__name__}). Check the bot's access and try again.") from None
    if not mentions:
        raise CommandError("Telegram did not return any mentionable members.")

    # Telegram messages are limited to 4096 chars. Bound output and disclose
    # that this is a sample rather than implying the API returned everyone.
    selected = mentions
    while selected:
        label = f"📣 <b>Announcement · {len(selected)} members</b>"
        prefix = label + (f"\n{html_escape(argument)}" if argument else "") + "\n"
        if len(prefix + " ".join(selected)) <= 3900:
            break
        selected = selected[:-1]
    if not selected:
        raise CommandError("Member names were too long to fit in one Telegram message.")
    body_text = prefix + " ".join(selected)
    await client.send_message(chat_id, body_text, parse_mode="html",
                              message_thread_id=getattr(ctx.message, "message_thread_id", None))
    # The announcement is the confirmation; a second reply would add noise to
    # the group immediately after a potentially large mention.
    return None


COMMANDS = (
    Command("pin", pin, "Pin a replied message", category="manage", policy="admin", rights=("can_pin_messages",)),
    Command("unpin", pin, "Unpin the latest pin", category="manage", policy="admin", rights=("can_pin_messages",)),
    Command("unpinall", pin, "Remove every pinned message", category="manage", policy="admin", rights=("can_pin_messages",)),
    Command("purge", purge, "Delete everything between a reply and this command", category="manage", policy="admin",
            rights=("can_delete_messages",)),
    Command("cleanup", purge, "Delete the last N messages", category="manage", policy="admin",
            rights=("can_delete_messages",)),
    Command("slowmode", slowmode, "Set the group slow mode", category="manage", policy="admin",
            rights=("can_restrict_members",)),
    Command("poll", poll, "Create a poll", category="tools"),
    Command("quiz", poll, "Create a quiz with one correct answer", category="tools"),
    Command("stickerid", sticker_id, "Read the file id of a sticker", category="tools"),
    Command("stats", stats, "Stored data and uptime", category="tools"),
    Command("invite", invite, "Create an approval-only invite link", category="manage", policy="admin",
            rights=("can_invite_users",)),
    Command("tagall", tagall, "Mention up to 50 group members (admin only)", category="manage", policy="admin"),
)
