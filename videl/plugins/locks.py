#  Videl © 2026 | Beasgohan-code
"""Content locks and anti-flood enforcement.

Admins and approved members are exempt. Enforcement deletes the offending
message; it never restricts a member automatically, so a false positive cannot
lock someone out of the group.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import OrderedDict, deque

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup

from videl import LOGGER, bot
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.audit import record_bot
from videl.utils.bot_ui import button
from videl.utils.automation import in_quiet_hours
from videl.utils.db import is_approved
from videl.utils.moderation import LOCK_TYPES, locked_message_reason
from videl.utils.premium_emojis import pe
from videl.utils.command_ui import rich_edit

logger = LOGGER

LOCK_CHOICES = LOCK_TYPES
_LOCK_TYPES = LOCK_TYPES + ("all",)
_FLOOD_WINDOWS: "OrderedDict[tuple[int, int], deque]" = OrderedDict()
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
FLOOD_LIMIT = 7
FLOOD_WINDOW = 8


# Quiet-hours windows are read per chat. A one-minute cache keeps a busy group
# from issuing one Mongo read per message while still reacting to an edit in
# the panel almost immediately.
_QUIET_CACHE: "OrderedDict[int, tuple[float, dict]]" = OrderedDict()
_QUIET_TTL = 60.0


def _quiet_window(chat_id: int) -> dict:
    import time as _time
    from videl.utils.db import get_quiet_hours

    entry = _QUIET_CACHE.get(chat_id)
    moment = _time.monotonic()
    if entry and moment - entry[0] < _QUIET_TTL:
        _QUIET_CACHE.move_to_end(chat_id)
        return entry[1]
    try:
        config = get_quiet_hours(chat_id)
    except Exception:
        config = {"enabled": False}
    _QUIET_CACHE[chat_id] = (moment, config)
    while len(_QUIET_CACHE) > 5000:
        _QUIET_CACHE.popitem(last=False)
    return config


async def _record_rule_stat(chat_id: int, rule: str, field: str = "hits") -> None:
    try:
        from videl.utils.db import get_db
        from videl.utils.rule_effectiveness import record
        await asyncio.to_thread(record, get_db(), chat_id, rule, field)
    except Exception:
        logger.debug("Rule effectiveness counter unavailable", exc_info=True)


def _locked(chat_id: int, kind: str) -> bool:
    if base.get_setting(chat_id, f"lock_{kind}", False):
        return True
    return kind == "forward" and bool(base.get_setting(chat_id, "lock_forwards", False))


@bot.on_message(filters.group, group=15)
async def mgmt_content_checker(_, message) -> None:
    """Delete messages that break an active lock; also enforce anti-flood."""
    if not getattr(message, "chat", None):
        return
    if base.chat_kind(message) not in {"group", "supergroup"}:
        return
    if message.from_user and await base.is_admin(bot, message.chat.id, message.from_user.id):
        return
    if message.from_user and is_approved(message.chat.id, message.from_user.id):
        return
    from videl.utils.db import get_db
    from videl.utils.maintenance import is_paused
    if is_paused(get_db(), message.chat.id, "protection"):
        return
    # Quiet hours: remove member messages inside the owner's window. Admins and
    # approved members were exempted above, so this never silences staff.
    if in_quiet_hours(_quiet_window(message.chat.id)):
        try:
            await message.delete()
            logger.info("Quiet hours removed a message in %s", message.chat.id)
        except Exception:
            logger.debug("Quiet-hours deletion failed", exc_info=True)
        return
    # Repeated copy-paste text is a signal for moderators, never an automatic
    # deletion: benign announcements can legitimately be identical.
    if message.from_user:
        content = getattr(message, "text", None) or getattr(message, "caption", None) or ""
        if content:
            from videl.utils.duplicate_messages import observe
            signal = observe(message.chat.id, message.from_user.id, content)
            if signal.get("alert", False):
                await _record_rule_stat(message.chat.id, "duplicate_text")
                try:
                    record_bot(message.chat.id, "moderation", action="duplicate_text_signal",
                               detail=f"{signal['distinct_senders']} distinct senders; fingerprint {signal['fingerprint'][:12]}")
                    await bot.send_message(message.chat.id,
                        f"⚠️ Possible repeated-text spam: similar text was posted by {signal['distinct_senders']} members recently. Please review manually.")
                except Exception:
                    logger.debug("Duplicate-message alert failed", exc_info=True)
    raid_active = False
    if message.from_user:
        from videl.utils.raid import record as record_raid
        raid_config = base.get_setting(message.chat.id, "raid_mode", {})
        raid_result = record_raid(message.chat.id, "messages", raid_config)
        raid_active = raid_result["active"]
        if raid_result["started"]:
            await _record_rule_stat(message.chat.id, "raid")
            try:
                await bot.send_message(message.chat.id, "⚠️ Temporary raid protections are active. New members may need to complete join verification.")
            except Exception:
                logger.debug("Raid-mode announcement failed", exc_info=True)
    if (base.get_setting(message.chat.id, "antispam", False) or raid_active) and message.from_user:
        key = (message.chat.id, message.from_user.id)
        now = time.monotonic()
        window = _FLOOD_WINDOWS.setdefault(key, deque(maxlen=32))
        _FLOOD_WINDOWS.move_to_end(key)
        while window and now - window[0] > FLOOD_WINDOW:
            window.popleft()
        window.append(now)
        while len(_FLOOD_WINDOWS) > 10000:
            _FLOOD_WINDOWS.popitem(last=False)
        effective_limit = max(2, FLOOD_LIMIT // 2) if raid_active else FLOOD_LIMIT
        if len(window) > effective_limit:
            await _record_rule_stat(message.chat.id, "antiflood")
            try:
                await message.delete()
            except Exception:
                logger.debug("Anti-flood deletion failed", exc_info=True)
            return
    reason = locked_message_reason(message, lambda kind: _locked(message.chat.id, kind))
    if reason:
        await _record_rule_stat(message.chat.id, "content_lock")
        try:
            await message.delete()
            logger.info("Lock %s removed a message in %s", reason, message.chat.id)
        except Exception:
            logger.debug("Lock deletion failed", exc_info=True)


async def _record(chat_id: int, action: str, detail: str, user) -> None:
    """Offload the write: a slow Mongo round-trip must not stall the bot."""
    await asyncio.to_thread(
        record_bot, chat_id, "settings", action=action, detail=detail,
        actor=getattr(user, "id", None),
    )


async def change_lock(ctx, enabled: bool) -> Screen:
    selected = ctx.command.arguments.strip().casefold()
    if selected not in _LOCK_TYPES:
        return Screen(
            heading("🔒 Choose a content lock", 3)
            + body("Choose one content type or <code>all</code>.")
            + body("Available: <code>" + " · ".join(_LOCK_TYPES) + "</code>")
        )
    kinds = LOCK_TYPES if selected == "all" else (selected,)
    updates = {f"lock_{kind}": enabled for kind in kinds}
    if "forward" in kinds:
        updates["lock_forwards"] = enabled
    if not base.set_settings(ctx.message.chat.id, updates):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    await _record(
        ctx.message.chat.id, "lock" if enabled else "unlock",
        f"{'on' if enabled else 'off'}: {', '.join(sorted(updates))}",
        getattr(ctx.message, "from_user", None),
    )
    state = "Locked" if enabled else "Open"
    badge = "🔒" if enabled else "🔓"
    return Screen(
        heading(f"{badge} Protection updated", 3)
        + table([("Content type", escape(selected.capitalize())), ("Status", state)])
        + body("Current group administrators and approved members are exempt from these locks.")
        + body("View every setting with <code>/locks</code>.")
    )


async def lock(ctx) -> Screen:
    return await change_lock(ctx, True)


async def unlock(ctx) -> Screen:
    return await change_lock(ctx, False)


def lock_status_screen(chat_id: int) -> Screen:
    rows = []
    controls = []
    for kind in LOCK_TYPES:
        active = _locked(chat_id, kind)
        rows.append(((pe("lock") if active else pe("unlock")) + " " + kind.capitalize(), "On" if active else "Off"))
        label = f"Unlock {kind}" if active else f"Lock {kind}"
        controls.append(button(label, callback_data=f"mgmt_lock:set:{kind}:{0 if active else 1}", style="success" if active else "default"))
    antispam = bool(base.get_setting(chat_id, "antispam", False))
    rows.append(((pe("rijif_warning") if antispam else pe("ios_controls")) + " Anti-flood", f"{'On' if antispam else 'Off'} · removes a member’s {FLOOD_LIMIT + 1}th message within {FLOOD_WINDOW}s"))
    controls.append(button("Disable anti-flood" if antispam else "Enable anti-flood",
                           callback_data=f"mgmt_lock:set:antispam:{0 if antispam else 1}",
                           style="success" if antispam else "default"))
    keyboard_rows = [controls[index:index + 2] for index in range(0, len(controls), 2)]
    keyboard_rows.append([button("Lock all", callback_data="mgmt_lock:set:all:1"),
                          button("Unlock all", callback_data="mgmt_lock:set:all:0", style="success")])
    return Screen(
        heading("🛡 Group protection status", 3)
        + table(rows)
        + body("Tap a button to toggle a protection rule. Admin rights are checked again for every tap.")
        + body("Administrators and approved members are exempt from content locks."),
        InlineKeyboardMarkup(keyboard_rows),
    )


async def locks(ctx) -> Screen:
    return lock_status_screen(ctx.message.chat.id)


@bot.on_callback_query(filters.regex(r"^mgmt_lock:"))
async def lock_toggle_callback(client, query: CallbackQuery) -> None:
    message = getattr(query, "message", None)
    if message is None or base.chat_kind(message) not in {"group", "supergroup"}:
        await query.answer("Open protection settings in the group.", show_alert=True)
        return
    parts = (query.data or "").split(":")
    if len(parts) != 4 or parts[:2] != ["mgmt_lock", "set"] or parts[3] not in {"0", "1"}:
        await query.answer("This protection action is invalid.", show_alert=True)
        return
    chat_id = message.chat.id
    actor_id = getattr(getattr(query, "from_user", None), "id", 0)
    try:
        member = await client.get_chat_member(chat_id, actor_id)
    except Exception:
        await query.answer("I couldn’t verify your current admin status.", show_alert=True)
        return
    if getattr(member, "status", None) not in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}:
        await query.answer("A current group admin is required to change protection.", show_alert=True)
        return

    kind = parts[2]
    enabled = parts[3] == "1"
    if kind == "antispam":
        updates = {"antispam": enabled}
    elif kind == "all":
        updates = {f"lock_{name}": enabled for name in LOCK_TYPES}
        if "forward" in LOCK_TYPES:
            updates["lock_forwards"] = enabled
    elif kind in LOCK_TYPES:
        updates = {f"lock_{kind}": enabled}
        if kind == "forward":
            updates["lock_forwards"] = enabled
    else:
        await query.answer("Unknown protection type.", show_alert=True)
        return
    if not base.set_settings(chat_id, updates):
        await query.answer("The settings database is unavailable; nothing changed.", show_alert=True)
        return
    await _record(chat_id, "lock_toggle", f"{'on' if enabled else 'off'}: {', '.join(sorted(updates))}", query.from_user)
    await query.answer("Protection updated")
    screen = lock_status_screen(chat_id)
    await rich_edit(message, screen.html, reply_markup=screen.keyboard)

async def antispam(ctx) -> Screen:
    chat_id = ctx.message.chat.id
    argument = ctx.command.arguments.strip().casefold()
    if argument not in {"on", "off"}:
        return Screen(
            heading("⚠️ Anti-flood protection", 3)
            + body("Use <code>/antispam on</code> to enable protection or <code>/antispam off</code> to disable it.")
            + body(f"When enabled, a member’s messages above {FLOOD_LIMIT} in {FLOOD_WINDOW} seconds are removed. Administrators and approved members are exempt.")
        )
    if not base.set_setting(chat_id, "antispam", argument == "on"):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    await _record(
        chat_id, "settings", f"antispam: {argument}",
        getattr(ctx.message, "from_user", None),
    )
    state = "enabled" if argument == "on" else "disabled"
    details = (
        f"The limit is more than {FLOOD_LIMIT} messages in {FLOOD_WINDOW} seconds; excess messages are deleted."
        if argument == "on" else "Member messages are no longer rate-limited by this setting."
    )
    return Screen(
        heading("✅ Anti-flood updated", 3)
        + table([("Status", state.capitalize()), ("Threshold", f"{FLOOD_LIMIT} messages / {FLOOD_WINDOW}s" if argument == "on" else "Not active")])
        + body(details)
        + body("Administrators and approved members remain exempt.")
    )


COMMANDS = (
    Command("lock", lock, "Block a content type in this group", category="manage", policy="admin"),
    Command("unlock", unlock, "Allow a content type again", category="manage", policy="admin"),
    Command("locks", locks, "Show every lock state", category="manage", policy="group"),
    Command("antispam", antispam, "Toggle anti-flood protection", category="manage", policy="admin"),
)
