#  Videl © 2026 | Beasgohan-code
"""Group housekeeping: pins, purge, slow mode, polls and chat stats."""
from __future__ import annotations

import asyncio
import html
import logging
import time

from pyrogram.types import InlineKeyboardMarkup

import config
from videl import bot_start_time
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.bot_ui import button
from videl.utils.command_ui import usage
from videl.utils.rich_ui import (
    rich_heading, rich_note, rich_hr, rich_footer, rich_button, rich_button_row,
)

LOGGER = logging.getLogger(__name__)


async def pin(ctx) -> Screen:
    chat_id = ctx.message.chat.id
    reply = getattr(ctx.message, "reply_to_message", None)
    name = ctx.command.name
    if name == "pin":
        if reply is None:
            return Screen(usage("/pin", "Reply to the message you want pinned."))
        if await ctx.client.pin_chat_message(chat_id, reply.id, disable_notification=False) is False:
            raise CommandError("Telegram did not confirm the pin.")
        return Screen(heading("📌 Message pinned", 3) + body("Telegram confirmed the pin. Group members can find it in the pinned-message banner."))
    if name == "unpin":
        if await ctx.client.unpin_chat_message(chat_id) is False:
            raise CommandError("Telegram did not confirm the unpin.")
        return Screen(heading("🔓 Latest pin removed", 3) + body("Telegram confirmed the pin was removed."))
    if await ctx.client.unpin_all_chat_messages(chat_id) is False:
        raise CommandError("Telegram did not confirm the unpin of all messages.")
    return Screen(heading("✅ All pins cleared", 3) + body("Telegram confirmed that the chat’s pinned messages were removed."))


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
        return Screen(
            heading("🧹 Cleanup complete", 3)
            + table([("Deleted", str(deleted)), ("Requested", argument)])
            + body("The count includes only deletions confirmed by Telegram. Messages Videl could not remove are not included.")
        )
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
    return Screen(
        heading("🧹 Purge complete", 3)
        + table([("Deleted", str(deleted)), ("Range", f"{start}–{end}")])
        + body("Only deletions confirmed by Telegram are counted. Messages the bot could not remove were skipped.")
    )


async def slowmode(ctx) -> Screen:
    argument = ctx.command.arguments.strip()
    if not argument.isdecimal():
        return Screen(usage("/slowmode 10", "Seconds between messages, 0 to disable, up to 3600."))
    seconds = int(argument)
    if not 0 <= seconds <= 3600:
        raise CommandError("Choose between 0 and 3600 seconds.")
    try:
        await ctx.client.set_chat_slow_mode(ctx.message.chat.id, seconds or None)
    except Exception:
        LOGGER.exception("Slow-mode update could not be confirmed in chat %s", ctx.message.chat.id)
        raise CommandError("I couldn’t confirm the slow-mode change. Check the group setting before retrying.") from None
    state = "disabled" if not seconds else f"{seconds}s"
    return Screen(
        heading("⏳ Slow mode updated", 3)
        + table([("Status", state.capitalize())])
        + body("Slow mode sets the minimum time between member messages. Use <code>/slowmode 0</code> to turn it off.")
    )


async def poll(ctx) -> Screen:
    from videl.utils.bot_api import bot_api
    from videl.utils.poll_options import build_poll

    try:
        payload = build_poll(ctx.command.arguments, quiz=ctx.command.name == "quiz")
    except ValueError as exc:
        return Screen(
            heading("📊 Check your poll", 3)
            + body(escape(str(exc)))
            + body("Format: <code>/poll Question | Option 1 | Option 2</code>.")
            + body("For a quiz, prefix the correct option with <code>*</code>: <code>/quiz Question | *Right | Wrong</code>.")
        )
    payload["chat_id"] = ctx.message.chat.id
    if getattr(ctx.message, "message_thread_id", None):
        payload["message_thread_id"] = ctx.message.message_thread_id
    ok, result = await bot_api("sendPoll", payload)
    if not ok or not result.get("ok"):
        description = str(result.get("description", "Telegram returned an unconfirmed response"))[:240]
        LOGGER.warning("Poll send rejected in chat %s: %s", ctx.message.chat.id, description)
        raise CommandError("Telegram did not confirm the poll. Check the poll format and chat permissions before trying again.")
    return Screen(
        heading("📊 Poll sent", 3)
        + body("Telegram accepted the poll; members can vote in the chat now.")
        + body("Use <code>/pollstop</code> in reply to a bot-created poll to close it early.")
    )


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
    next_action = (
        rich_button("Owner workspace", callback_data="help:owner:0", style="primary")
        if ctx.owner else rich_button("Help center", callback_data="help:home", style="primary")
    )
    text = (heading("Videl statistics", 3) + table(rows) + rich_hr()
            + rich_footer("Live service snapshot · refreshed when you run /stats")
            + rich_button_row(next_action))
    return Screen(text)


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
    except Exception:
        LOGGER.exception("Invite-link creation could not be confirmed in chat %s", ctx.message.chat.id)
        raise CommandError("I couldn’t confirm the invite-link request. Check my invite permissions and the group’s join-request settings before retrying.") from None
    return Screen(
        heading("Invite link ready", 3)
        + body(f"<code>{escape(link.invite_link)}</code>")
        + body("New members using it appear as join requests for an admin to approve.")
    )


async def set_title(ctx) -> Screen:
    """Update a group's display title (requires Telegram's change-info right)."""
    title = ctx.command.arguments.strip()
    if not title:
        current = escape(getattr(ctx.message.chat, "title", "Group"))
        return Screen(
            heading("🏷 Update group title", 3)
            + table([("Current title", current)])
            + body("Usage: <code>/settitle New group title</code> · 1–128 characters.")
        )
    if "\n" in title or "\r" in title:
        raise CommandError("Use a single line for the group title.")
    units = len(title.encode("utf-16-le")) // 2
    if not 1 <= units <= 128:
        raise CommandError("Group titles must be 1–128 Telegram UTF-16 units.")
    try:
        result = await ctx.client.set_chat_title(ctx.message.chat.id, title)
        if not result:
            raise RuntimeError("Telegram did not confirm the title change")
    except Exception:
        LOGGER.exception("Group title change could not be confirmed in chat %s", ctx.message.chat.id)
        raise CommandError("I couldn’t confirm the title change. Check the group’s Change info permission before retrying.") from None
    return Screen(
        heading("🏷 Group title updated", 3)
        + table([("New title", escape(title)), ("Length", f"{units} / 128 UTF-16 units")])
    )


async def set_description(ctx) -> Screen:
    """Update or clear a group's description (requires Change info)."""
    description = ctx.command.arguments.strip()
    if not description:
        current = getattr(ctx.message.chat, "description", None)
        preview = escape(current[:255]) if current else "No description is available in this message."
        return Screen(
            heading("📰 Update group description", 3)
            + table([("Current description", preview)])
            + body("Usage: <code>/setdescription Text for the group info page</code>.")
            + body("Use <code>/setdescription clear</code> to remove it. Maximum: 255 Telegram UTF-16 units.")
        )
    clear = description.casefold() == "clear"
    value = "" if clear else description
    units = len(value.encode("utf-16-le")) // 2
    if units > 255:
        raise CommandError("Group descriptions must be at most 255 Telegram UTF-16 units.")
    try:
        result = await ctx.client.set_chat_description(ctx.message.chat.id, value)
        if not result:
            raise RuntimeError("Telegram did not confirm the description change")
    except Exception:
        LOGGER.exception("Group description change could not be confirmed in chat %s", ctx.message.chat.id)
        raise CommandError("I couldn’t confirm the description change. Check the group’s Change info permission before retrying.") from None
    if clear:
        return Screen(heading("🗑 Group description cleared", 3) + body("The group info page no longer has a description."))
    return Screen(
        heading("📰 Group description updated", 3)
        + table([("Preview", escape(value[:255])), ("Length", f"{units} / 255 UTF-16 units")])
    )


async def set_photo(ctx) -> Screen:
    """Use a replied Telegram photo as the group's avatar."""
    reply = getattr(ctx.message, "reply_to_message", None)
    photo = getattr(reply, "photo", None) if reply else None
    if photo is None:
        return Screen(usage("/setphoto", "Reply to a photo and send /setphoto to use it as the group avatar."))
    try:
        result = await ctx.client.set_chat_photo(ctx.message.chat.id, photo.file_id)
        if not result:
            raise RuntimeError("Telegram did not confirm the photo change")
    except Exception:
        LOGGER.exception("Group photo update could not be confirmed in chat %s", ctx.message.chat.id)
        raise CommandError("I couldn’t confirm the group photo change. Check the group’s Change info permission before retrying.") from None
    return Screen(
        heading("🖼 Group photo updated", 3)
        + body("Telegram confirmed the new photo. Reply to another photo with <code>/setphoto</code> to replace it.")
    )


async def delete_photo(ctx) -> Screen:
    """Remove the group's current profile photo."""
    try:
        result = await ctx.client.delete_chat_photo(ctx.message.chat.id)
        if not result:
            raise RuntimeError("Telegram did not confirm the photo removal")
    except Exception:
        LOGGER.exception("Group photo removal could not be confirmed in chat %s", ctx.message.chat.id)
        raise CommandError("I couldn’t confirm the photo removal. Check the group’s Change info permission before retrying.") from None
    return Screen(heading("🗑 Group photo removed", 3) + body("Telegram confirmed the group photo was removed."))


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
    except Exception:
        LOGGER.exception("Could not read mentionable members in chat %s", chat_id)
        raise CommandError("I couldn’t read this group’s member list. Check the bot’s access and try again.") from None
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
    from videl.utils.command_ui import navigation_markup
    await client.send_message(
        chat_id, body_text, parse_mode="html",
        message_thread_id=getattr(ctx.message, "message_thread_id", None),
        reply_markup=navigation_markup(),
    )
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
    Command("settitle", set_title, "Update the group title", category="manage", policy="admin",
            rights=("can_change_info",)),
    Command("setdescription", set_description, "Update or clear the group description", category="manage", policy="admin",
            rights=("can_change_info",)),
    Command("setphoto", set_photo, "Set the group photo from a replied photo", category="manage", policy="admin",
            rights=("can_change_info",)),
    Command("delphoto", delete_photo, "Remove the group photo", category="manage", policy="admin",
            rights=("can_change_info",)),
    Command("tagall", tagall, "Mention up to 50 group members (admin only)", category="manage", policy="admin"),
)
