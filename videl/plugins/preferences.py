# Videl © 2026 | Beasgohan-code
"""Member-controlled opt-in announcements and personal reminder quiet hours."""
from __future__ import annotations

import asyncio
import re

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup

from videl import bot
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, heading, table
from videl.utils.bot_ui import button
from videl.utils.command_ui import rich_edit

_QUIET = re.compile(r"^(\d{2}:\d{2})-(\d{2}:\d{2})\s+UTC([+-])(\d{1,2})(?::(\d{2}))?$", re.I)


def _private(ctx) -> bool:
    return bool(ctx.user and base.chat_kind(ctx.message) == "private"
                and int(ctx.message.chat.id) == int(ctx.user.id))


def _offset(sign: str, hours: str, minutes: str | None) -> int | None:
    hour, minute = int(hours), int(minutes or 0)
    if minute >= 60 or hour > 14 or (hour == 14 and minute != 0):
        return None
    value = hour * 60 + minute
    return value if sign == "+" else -value


def _preferences_screen(user_id: int, saved: dict) -> Screen:
    quiet = saved["quiet_hours"]
    quiet_display = (f"On · {quiet['start']}–{quiet['end']} · UTC{quiet['utc_offset_minutes'] / 60:+g}"
                     if quiet["enabled"] else "Off")
    from videl.utils.i18n import LANGUAGES
    language = saved["language"]
    keyboard = InlineKeyboardMarkup([
        [button(f"Optional updates: {'On' if saved['notifications_enabled'] else 'Off'}")],
        [button("Turn on", callback_data=f"preferences:{user_id}:notifications:on", style="success"),
         button("Turn off", callback_data=f"preferences:{user_id}:notifications:off", style="danger")],
        [button(f"Language: {LANGUAGES.get(language, 'English')}")],
        [button(label, callback_data=f"preferences:{user_id}:language:{code}",
                style="primary" if language == code else None)
         for code, label in (("en", "English"), ("ml", "മലയാളം"), ("hi", "हिन्दी"), ("ta", "தமிழ்"))],
        [button(f"Reminder quiet hours: {quiet_display}")],
        [button("Turn quiet hours off", callback_data=f"preferences:{user_id}:quiet:off",
                style="danger" if quiet["enabled"] else None),
         button("Configure…", callback_data=f"preferences:{user_id}:quiet:help")],
    ])
    return Screen(heading("Your private preferences", 3)
                  + table([("Optional bot updates", "Opted in" if saved["notifications_enabled"] else "Off by default"),
                           ("Reminder quiet hours", quiet_display),
                           ("Private reply language", LANGUAGES.get(language, "English"))])
                  + body("Opt-in updates control owner announcements sent to private users. Group announcements are not affected.")
                  + body("Quiet hours defer scheduled reminders; they are not cancelled. The saved schedule uses a fixed UTC offset, so daylight-saving changes are not automatic.")
                  + body("Use Configure for quiet hours: <code>/preferences quiet 22:00-07:00 UTC+05:30</code>."), keyboard)


async def preferences(ctx) -> Screen:
    if not _private(ctx):
        raise CommandError("For privacy, manage personal preferences in a private chat with Videl.")
    from videl.utils.db import get_db
    from videl.utils.member_preferences import read, update
    db = get_db()
    if db is None:
        raise CommandError("Preferences cannot be saved while the database is unavailable.")
    parts = ctx.command.arguments.strip().split(maxsplit=2)
    if len(parts) == 2 and parts[0].casefold() == "notifications":
        switch = parts[1].casefold()
        if switch not in {"on", "off"}:
            raise CommandError("Use <code>/preferences notifications on</code> or <code>off</code>.")
        saved = await asyncio.to_thread(update, db, int(ctx.user.id), notifications_enabled=switch == "on")
        if saved is None:
            raise CommandError("That preference could not be saved; nothing changed.")
        try:
            if switch == "on":
                await asyncio.to_thread(db["broadcast"].update_one, {"_id": int(ctx.user.id)},
                    {"$set": {"_id": int(ctx.user.id), "chat_id": int(ctx.user.id), "type": "private"}}, upsert=True)
            else:
                await asyncio.to_thread(db["broadcast"].delete_one,
                    {"_id": int(ctx.user.id), "type": "private"})
        except Exception as exc:
            if switch == "on":
                await asyncio.to_thread(update, db, int(ctx.user.id), notifications_enabled=False)
            raise CommandError("The notification preference could not be fully applied; private broadcasts remain disabled.") from exc
    elif len(parts) == 2 and parts[0].casefold() == "language":
        language = parts[1].casefold()
        from videl.utils.i18n import LANGUAGES
        if language not in LANGUAGES:
            raise CommandError("Supported private-reply languages: <code>en</code>, <code>ml</code>, <code>hi</code>, <code>ta</code>.")
        saved = await asyncio.to_thread(update, db, int(ctx.user.id), language=language)
        if saved is None:
            raise CommandError("That language could not be saved; nothing changed.")
    elif len(parts) == 2 and parts[0].casefold() == "quiet" and parts[1].casefold() == "off":
        current = await asyncio.to_thread(read, db, int(ctx.user.id))
        quiet = {**current["quiet_hours"], "enabled": False}
        saved = await asyncio.to_thread(update, db, int(ctx.user.id), quiet_hours=quiet)
        if saved is None:
            raise CommandError("That preference could not be saved; nothing changed.")
    elif len(parts) >= 2 and parts[0].casefold() == "quiet":
        raw = " ".join(parts[1:])
        match = _QUIET.fullmatch(raw)
        if not match:
            raise CommandError("Use <code>/preferences quiet 22:00-07:00 UTC+05:30</code>, or <code>/preferences quiet off</code>. The UTC offset is fixed; daylight-saving changes are not automatic.")
        start, end, sign, hours, minutes = match.groups()
        from videl.utils.member_preferences import normalize_quiet_hours, parse_time
        offset = _offset(sign, hours, minutes)
        if offset is None or parse_time(start) is None or parse_time(end) is None or start == end:
            raise CommandError("Choose valid 24-hour times and a UTC offset from -12:00 through +14:00; start and end must differ.")
        quiet = normalize_quiet_hours({"enabled": True, "start": start, "end": end,
                                       "utc_offset_minutes": offset})
        saved = await asyncio.to_thread(update, db, int(ctx.user.id), quiet_hours=quiet)
        if saved is None:
            raise CommandError("That preference could not be saved; nothing changed.")
    elif ctx.command.arguments.strip():
        raise CommandError("Use <code>/preferences notifications on|off</code>, <code>/preferences quiet HH:MM-HH:MM UTC+05:30</code>, <code>/preferences quiet off</code>, or <code>/preferences language en|ml|hi|ta</code>.")
    else:
        saved = await asyncio.to_thread(read, db, int(ctx.user.id))
    return _preferences_screen(int(ctx.user.id), saved)


@bot.on_callback_query(filters.regex(r"^preferences:[0-9]{1,20}:(?:notifications:(?:on|off)|language:(?:en|ml|hi|ta)|quiet:(?:off|help))$"))
async def preferences_callback(client, query):
    message = getattr(query, "message", None)
    actor = getattr(query, "from_user", None)
    if (message is None or actor is None or base.chat_kind(message) != "private"
            or int(message.chat.id) != int(actor.id)):
        return await query.answer("Open personal preferences in your own private chat.", show_alert=True)
    try:
        _, raw_user, section, value = str(query.data).split(":")
        user_id = int(raw_user)
    except (TypeError, ValueError):
        return await query.answer("That preference button is invalid.", show_alert=True)
    if user_id != int(actor.id):
        return await query.answer("This preference panel belongs to another user.", show_alert=True)
    if section == "quiet" and value == "help":
        return await query.answer("Use /preferences quiet 22:00-07:00 UTC+05:30 to configure a fixed-offset quiet window.", show_alert=True)
    from videl.utils.db import get_db
    from videl.utils.member_preferences import read, update
    db = get_db()
    if db is None:
        return await query.answer("Preferences are unavailable while the database is disconnected.", show_alert=True)
    if section == "notifications":
        enabled = value == "on"
        saved = await asyncio.to_thread(update, db, user_id, notifications_enabled=enabled)
        if saved is None:
            return await query.answer("Could not save this preference; nothing changed.", show_alert=True)
        try:
            if enabled:
                await asyncio.to_thread(db["broadcast"].update_one, {"_id": user_id},
                    {"$set": {"_id": user_id, "chat_id": user_id, "type": "private"}}, upsert=True)
            else:
                await asyncio.to_thread(db["broadcast"].delete_one, {"_id": user_id, "type": "private"})
        except Exception:
            if enabled:
                await asyncio.to_thread(update, db, user_id, notifications_enabled=False)
            return await query.answer("The update preference could not be fully applied; it remains off.", show_alert=True)
    elif section == "language":
        saved = await asyncio.to_thread(update, db, user_id, language=value)
        if saved is None:
            return await query.answer("Could not save the language; nothing changed.", show_alert=True)
    else:
        current = await asyncio.to_thread(read, db, user_id)
        quiet = {**current["quiet_hours"], "enabled": False}
        saved = await asyncio.to_thread(update, db, user_id, quiet_hours=quiet)
        if saved is None:
            return await query.answer("Could not save quiet hours; nothing changed.", show_alert=True)
    screen = _preferences_screen(user_id, saved)
    await query.answer("Preference saved.")
    return await rich_edit(message, screen.html, reply_markup=screen.keyboard)


COMMANDS = (
    Command("preferences", preferences, "Manage optional private updates and reminder quiet hours", category="tools"),
)
