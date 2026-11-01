#  Videl © 2026 | Beasgohan-code
"""Group housekeeping: pins, purge, slow mode, polls and chat stats."""
from __future__ import annotations

import asyncio
import html
import logging
import secrets
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import config
from videl import bot_start_time
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.command_ui import usage, section, format_bytes
from videl.utils.rich_ui import (
    rich_heading, rich_note, rich_hr, rich_footer, rich_button, rich_button_row, rich_kv_table,
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
    fields = [
        ("File ID", f"<code>{escape(sticker.file_id)}</code>"),
        ("Unique ID", f"<code>{escape(sticker.file_unique_id)}</code>"),
        ("Sticker set", escape(getattr(sticker, "set_name", None) or "Not part of a set")),
    ]
    if getattr(sticker, "emoji", None):
        fields.append(("Emoji", escape(sticker.emoji)))
    if getattr(sticker, "file_size", None):
        fields.append(("File size", format_bytes(sticker.file_size)))
    try:
        width, height = int(getattr(sticker, "width", 0) or 0), int(getattr(sticker, "height", 0) or 0)
        if width > 0 and height > 0:
            fields.append(("Dimensions", f"{width} × {height} px"))
    except (TypeError, ValueError, OverflowError):
        pass
    kind = "Video" if getattr(sticker, "is_video", False) else "Animated" if getattr(sticker, "is_animated", False) else "Static"
    fields.append(("Format", f"{kind} sticker"))
    return Screen(
        section(
            "Sticker file details",
            rich_kv_table(fields)
            + body("The file ID can be reused by the bot. The unique ID is for identification only."),
            level=3,
        )
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
    me = getattr(ctx.client, "me", None)
    if not getattr(me, "username", None):
        try:
            me = await ctx.client.get_me()
        except Exception:
            me = None
    bot_username = getattr(me, "username", None) or "Videlapp"
    bot_username = str(bot_username).strip().lstrip("@") or "Videlapp"
    rows = [
        ("Uptime", f"{hours}h {minutes}m {seconds}s"),
        ("Configured groups", counts["groups"]),
        ("Warnings stored", counts["warnings"]),
        ("Notes stored", counts["notes"]),
        ("Bot", "@" + escape(bot_username)),
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


_TAGALL_INTERVAL_SECONDS = 5
_TAGALL_BATCH_SIZE = 5
_TAGALL_LOCKS: dict[int, asyncio.Lock] = {}
_TAGALL_TASKS: dict[int, asyncio.Task] = {}
_TAGALL_PROGRESS: dict[int, object] = {}
_RELOAD_LOCKS: dict[int, asyncio.Lock] = {}


async def _telegram_bot_api(method: str, payload: dict):
    from videl.utils.bot_api import bot_api
    status, response = await bot_api(method, payload)
    if status != 200 or not isinstance(response, dict) or not response.get("ok"):
        description = str((response or {}).get("description") or "Telegram returned an unconfirmed response")[:220]
        raise RuntimeError(f"{method}: {description}")
    return response.get("result")


def _human_admins(rows):
    """Use only the current admin roster Telegram's Bot API exposes."""
    from html import escape as html_escape
    unique = {}
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, dict) or row.get("status") not in {"creator", "administrator"}:
            continue
        user = row.get("user")
        if not isinstance(user, dict) or user.get("is_bot"):
            continue
        try:
            user_id = int(user.get("id"))
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id in unique:
            continue
        name = " ".join(part for part in (user.get("first_name"), user.get("last_name"))
                         if isinstance(part, str) and part)
        unique[user_id] = f'<a href="tg://user?id={user_id}">{html_escape(name[:80] or "member")}</a>'
    return list(unique.items())


def _tagall_batches(members, announcement):
    from html import escape as html_escape
    prefix = f"📣 {html_escape(announcement)}\n" if announcement else "📣 Group administrators (Telegram-visible list):\n"
    batches, batch, size = [], [], len(prefix)
    for user_id, mention in members:
        addition = len(mention) + (1 if batch else 0)
        if batch and (len(batch) >= _TAGALL_BATCH_SIZE or size + addition > 3500):
            batches.append((prefix + "\n".join(item[1] for item in batch), len(batch)))
            batch, size = [], len(prefix)
            addition = len(mention)
        batch.append((user_id, mention))
        size += addition
    if batch:
        batches.append((prefix + "\n".join(item[1] for item in batch), len(batch)))
    return batches


async def _update_tagall_progress(client, chat_id, progress, text):
    if progress is None:
        return
    try:
        edit = getattr(progress, "edit_text", None)
        if callable(edit):
            await edit(text)
        else:
            await client.edit_message_text(chat_id, progress.id, text)
    except Exception:
        LOGGER.debug("Tag-all progress update failed in chat %s", chat_id, exc_info=True)


async def tagall(ctx) -> Screen | None:
    """Mention only the human administrators Telegram makes available to bots."""
    argument = ctx.command.arguments.strip()
    client = ctx.client
    chat_id = int(ctx.message.chat.id)
    if argument.casefold() == "stop":
        active = _TAGALL_TASKS.get(chat_id)
        if active is None or active.done():
            raise CommandError("There isn’t an active /tagall run in this group.")
        active.cancel()
        return Screen(heading("⏹ Tag-all stopping", 3) + body("No more mentions will be sent. Messages already delivered cannot be recalled."))
    if len(argument) > 180:
        raise CommandError("Keep the optional announcement under 180 characters. Use <code>/tagall stop</code> to stop a run.")
    lock = _TAGALL_LOCKS.setdefault(chat_id, asyncio.Lock())
    if lock.locked():
        raise CommandError("A /tagall run is already active in this group. Wait for it to finish before starting another.")

    sent = 0
    progress = None
    async with lock:
        task = asyncio.current_task()
        if task is not None:
            _TAGALL_TASKS[chat_id] = task
        try:
            try:
                identity = await _telegram_bot_api("getMe", {})
                bot_id = int(identity.get("id") or 0)
                if bot_id <= 0:
                    raise RuntimeError("Telegram did not return the bot identity")
                bot_member = await _telegram_bot_api("getChatMember", {"chat_id": chat_id, "user_id": bot_id})
                bot_status = str(bot_member.get("status") or "unknown")
                if bot_status not in {"creator", "administrator"}:
                    raise CommandError(
                        f"/tagall requires bot Administrator status to read Telegram’s administrator list. "
                        f"Current status: {bot_status}; missing permission: Administrator. No mentions were sent."
                    )
                rows = await _telegram_bot_api("getChatAdministrators", {"chat_id": chat_id})
            except CommandError:
                raise
            except Exception as error:
                LOGGER.warning("Tag-all could not read Telegram admin roster in %s (%s)", chat_id, type(error).__name__)
                raise CommandError(
                    "Telegram could not provide the group’s administrator list. Bots cannot retrieve a complete member directory; "
                    "this command can mention only administrators returned by Telegram. Check the bot’s Administrator status and try again."
                ) from None
            members = _human_admins(rows)
            if not members:
                raise CommandError("Telegram returned no mentionable human administrators; no message was sent.")
            batches = _tagall_batches(members, argument)
            try:
                progress = await client.send_message(
                    chat_id,
                    f"Starting /tagall for {len(members)} Telegram-visible human administrators in {len(batches)} safe batches. "
                    "This is not a complete group-member list.",
                    message_thread_id=getattr(ctx.message, "message_thread_id", None),
                )
                if progress is False or progress is None:
                    raise RuntimeError("Telegram did not confirm the progress message")
                _TAGALL_PROGRESS[chat_id] = progress
            except Exception as error:
                LOGGER.warning("Tag-all progress message failed in %s (%s)", chat_id, type(error).__name__)
                raise CommandError("I couldn’t send the progress message, so no mentions were started. Check the bot’s Send Messages permission.") from None

            for index, (text, batch_size) in enumerate(batches):
                if index:
                    await asyncio.sleep(_TAGALL_INTERVAL_SECONDS)
                try:
                    result = await client.send_message(
                        chat_id, text, parse_mode="html",
                        message_thread_id=getattr(ctx.message, "message_thread_id", None),
                    )
                    if result is False or result is None:
                        raise RuntimeError("Telegram did not confirm the mention batch")
                    sent += batch_size
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    if sent:
                        detail = "Earlier batches were sent; check the group before retrying."
                    else:
                        detail = "The first batch was not confirmed; check the group before retrying. Verify the bot has Send Messages permission."
                    await _update_tagall_progress(
                        client, chat_id, progress,
                        f"Tag-all stopped after {sent} of {len(members)} Telegram-visible administrators. {detail}",
                    )
                    raise CommandError(
                        f"Tag-all stopped after {sent} of {len(members)} administrators because Telegram rejected or did not confirm a batch. "
                        f"{detail}"
                    ) from error
                await _update_tagall_progress(
                    client, chat_id, progress,
                    f"Tag-all progress: {sent} of {len(members)} Telegram-visible human administrators mentioned. "
                    "Telegram does not provide bots a complete member directory.",
                )
        except asyncio.CancelledError:
            await _update_tagall_progress(
                client, chat_id, progress,
                f"Tag-all stopped after {sent} of {len(members) if 'members' in locals() else 0} administrators. "
                "Messages already delivered cannot be recalled.",
            )
            return Screen(heading("⏹ Tag-all stopped", 3) + body(f"Sent {sent} mention(s) before the stop request. Earlier messages cannot be recalled."))
        finally:
            if _TAGALL_TASKS.get(chat_id) is task:
                _TAGALL_TASKS.pop(chat_id, None)
            _TAGALL_PROGRESS.pop(chat_id, None)

    await _update_tagall_progress(
        client, chat_id, progress,
        f"Tag-all complete: mentioned {sent} of {len(members)} human administrators Telegram exposes to bots. "
        "Other group members are not listed by the Telegram Bot API.",
    )
    return Screen(heading("✅ Tag-all complete", 3)
                  + table([("Mentioned", f"{sent} of {len(members)} Telegram-visible human administrators"),
                           ("Member-list coverage", "Administrator roster only; not all group members")])
                  + body("Telegram’s Bot API does not provide bots with a complete group-member directory."))


async def reload_group_permissions(ctx) -> Screen:
    """Freshly verify group admins and bot rights without restarting or mutating settings."""
    chat_id = int(ctx.message.chat.id)
    actor_id = int(getattr(ctx.user, "id", 0) or 0)
    raw_operators = getattr(config, "ADMIN_IDS", ()) or ()
    if isinstance(raw_operators, int):
        raw_operators = (raw_operators,)
    elif isinstance(raw_operators, str):
        raw_operators = raw_operators.replace(";", ",").split(",")
    configured_operators = set()
    for value in raw_operators:
        try:
            configured_operators.add(int(value))
        except (TypeError, ValueError):
            continue
    is_configured_operator = base.is_owner(actor_id) or actor_id in configured_operators
    lock = _RELOAD_LOCKS.setdefault(chat_id, asyncio.Lock())
    if lock.locked():
        raise CommandError("A permission refresh is already running for this group. Wait for it to finish.")

    lease_db = None
    lease_token = None
    async with lock:
        try:
            # Caller authorization is read fresh before any cache write. Owners
            # may recover a group where the bot has already lost admin access.
            caller = None
            try:
                caller = await _telegram_bot_api("getChatMember", {"chat_id": chat_id, "user_id": actor_id})
            except Exception:
                if not is_configured_operator:
                    raise CommandError("Telegram could not verify your current group-admin status; no cache was changed.") from None
            caller_status = str((caller or {}).get("status") or "unknown")
            if not is_configured_operator and caller_status not in {"creator", "administrator"}:
                raise CommandError("Only a current group administrator or configured Videl owner/admin may run /reload.")

            lease_db = base.db()
            if lease_db is None:
                raise CommandError("The permission cache is unavailable; no refresh was attempted.")
            from videl.utils.chat_admins import acquire_refresh_lock
            lease_token = secrets.token_urlsafe(18)
            if not acquire_refresh_lock(lease_db, chat_id, lease_token):
                lease_token = None
                raise CommandError("Another Videl instance is refreshing permissions for this group. Wait and try again.")

            me = await _telegram_bot_api("getMe", {})
            bot_id = int(me.get("id") or 0)
            if bot_id <= 0:
                raise CommandError("Telegram did not return Videl’s bot identity; permission refresh failed and the cache was unchanged.")
            bot_member = await _telegram_bot_api("getChatMember", {"chat_id": chat_id, "user_id": bot_id})
            chat_info = await _telegram_bot_api("getChat", {"chat_id": chat_id})
            bot_status = str(bot_member.get("status") or "unknown")
            try:
                admins = await _telegram_bot_api("getChatAdministrators", {"chat_id": chat_id})
            except Exception:
                if bot_status not in {"creator", "administrator"}:
                    missing = ["Administrator access"]
                    if bot_status == "member" and (chat_info.get("permissions") or {}).get("can_send_messages") is not True:
                        missing.append("Send Messages")
                    elif bot_status == "restricted" and bot_member.get("can_send_messages") is not True:
                        missing.append("Send Messages in bot restrictions")
                    raise CommandError(
                        f"Telegram refused to return the admin list. The bot’s current status is {bot_status}; "
                        f"missing permission: {', '.join(missing)}. The previous permission cache was retained."
                    ) from None
                raise CommandError(
                    "Telegram refused to return the administrator list. The previous permission cache was retained. "
                    "Check the bot’s administrator status and retry when Telegram is available."
                ) from None
            if not isinstance(admins, list):
                raise CommandError("Telegram returned an invalid administrator list; refresh failed and the prior cache was retained.")
            if not is_configured_operator and not any(
                int((row.get("user") or {}).get("id") or 0) == actor_id
                and row.get("status") in {"creator", "administrator"}
                for row in admins if isinstance(row, dict)
            ):
                raise CommandError("Telegram’s fresh administrator list does not include you; no cache was changed.")

            from videl.utils.chat_admins import replace_group_snapshot
            raw_permissions = chat_info.get("permissions") if isinstance(chat_info, dict) else None
            snapshot = replace_group_snapshot(lease_db, chat_id, admins, bot_member,
                                              raw_permissions if isinstance(raw_permissions, dict) else {})
            bot_is_admin = bot_status in {"creator", "administrator"}
            if bot_is_admin:
                send_allowed = True
            elif bot_status == "restricted":
                send_allowed = bot_member.get("can_send_messages") is True
            elif bot_status == "member":
                default_permissions = chat_info.get("permissions") or {}
                send_allowed = default_permissions.get("can_send_messages") is True
            else:
                send_allowed = False
            missing = []
            if not bot_is_admin:
                missing.append("Administrator status (needed to retrieve the Telegram administrator list)")
            if not send_allowed:
                missing.append("Send Messages" if bot_status == "member" else "Send Messages in bot restrictions")
            admin_count = len(snapshot.get("admins") or [])
            lines = [
                ("Administrator list", f"Refreshed from Telegram ({admin_count} administrators)"),
                ("Caller", "Configured Videl owner/admin" if is_configured_operator else f"Verified current {caller_status}"),
                ("Bot admin status", bot_status.capitalize()),
                ("Bot send permission", "Available" if send_allowed else "Missing"),
                ("/tagall access", "Available for Telegram-visible administrators only" if bot_is_admin and send_allowed
                 else "Unavailable: bot access is insufficient"),
                ("Cache update", "Atomic group snapshot synchronized"),
            ]
            if missing:
                lines.append(("Missing permission", ", ".join(missing)))
            return Screen(heading("🔄 Group permission refresh complete", 3) + table(lines)
                          + body("No group settings or Telegram roles were changed. Telegram exposes administrators, not a complete member directory."))
        except CommandError:
            raise
        except Exception as error:
            LOGGER.warning("Group permission refresh failed for %s (%s)", chat_id, type(error).__name__)
            raise CommandError("Telegram could not provide a complete fresh permission snapshot. The existing cache was retained; try again when Telegram is available.") from None
        finally:
            if lease_token and lease_db is not None:
                from videl.utils.chat_admins import release_refresh_lock
                release_refresh_lock(lease_db, chat_id, lease_token)


async def admin_activity(ctx) -> Screen:
    """Show an aggregate, content-free summary of recent admin audit actions."""
    chat_id = int(ctx.message.chat.id)
    since = datetime.now(timezone.utc) - timedelta(days=30)
    selector = {"chat_id": chat_id, "ts": {"$gte": since}, "actor": {"$ne": None}}
    db = base.db()
    if db is None:
        raise CommandError("Group audit history is temporarily unavailable.")
    try:
        total = db["mgmt_audit"].count_documents(selector)
        rows = list(db["mgmt_audit"].find(
            selector, {"_id": 0, "actor": 1, "kind": 1, "action": 1, "ts": 1}
        ).sort("ts", -1).limit(1000))
    except Exception as error:
        LOGGER.exception("Admin activity summary failed for chat %s", chat_id)
        raise CommandError("Group audit history is temporarily unavailable.") from error

    admins: dict[int, Counter] = {}
    for row in rows:
        try:
            actor = int(row.get("actor"))
        except (TypeError, ValueError):
            continue
        if actor <= 0:
            continue
        label = str(row.get("action") or row.get("kind") or "other")[:48]
        admins.setdefault(actor, Counter())[label] += 1
    if not admins:
        return Screen(heading("Admin activity · 30 days", 3) + body("No admin-attributed actions were recorded in this group during this period."))

    ranking = sorted(admins.items(), key=lambda item: (-sum(item[1].values()), item[0]))[:10]
    summary_rows = []
    for actor, actions in ranking:
        action_summary = ", ".join(
            f"{html.escape(name)} ×{count}"
            for name, count in actions.most_common(3)
        )
        summary_rows.append((f"Admin {actor}", f"{sum(actions.values())} events · {action_summary}"))
    note = f"<p>Showing the latest {len(rows)} of {total} admin-attributed audit events in the last 30 days. Counts and action types only; message contents and member details are not shown.</p>" if total > len(rows) else "<p>Counts and action types only; message contents and member details are not shown.</p>"
    content = heading("Admin activity · 30 days", 3) + table(summary_rows) + note
    return Screen(content)


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
    Command("adminactivity", admin_activity, "Summarize group admin actions from the last 30 days", category="manage", policy="admin"),
    Command("reload", reload_group_permissions, "Refresh the current group administrator and bot-permission snapshot (does not restart Videl)", category="manage", policy="group"),
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
    Command("tagall", tagall, "Mention Telegram-visible human administrators in safe batches; the Bot API cannot list all members; /tagall stop cancels", category="manage", policy="admin"),
)
