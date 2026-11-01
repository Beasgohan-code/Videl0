# Videl © 2026 | Beasgohan-code
"""Member-controlled opt-in announcements and personal reminder quiet hours."""
from __future__ import annotations

import asyncio
import re

from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, heading, table

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

    quiet = saved["quiet_hours"]
    quiet_display = (f"On · {quiet['start']}–{quiet['end']} · UTC{quiet['utc_offset_minutes'] / 60:+g}"
                     if quiet["enabled"] else "Off")
    from videl.utils.i18n import LANGUAGES
    return Screen(heading("Your private preferences", 3)
                  + table([("Optional bot updates", "Opted in" if saved["notifications_enabled"] else "Off by default"),
                           ("Reminder quiet hours", quiet_display),
                           ("Private reply language", LANGUAGES.get(saved["language"], "English"))])
                  + body("Opt-in updates control owner announcements sent to private users. Group announcements are not affected.")
                  + body("Quiet hours defer your scheduled reminders; reminders are not cancelled. Use a fixed UTC offset such as UTC+05:30." )
                  + body("Examples: <code>/preferences notifications on</code> · <code>/preferences quiet 22:00-07:00 UTC+05:30</code> · <code>/preferences language ml</code> · <code>/preferences quiet off</code>. Languages: en, ml, hi and ta; untranslated phrases stay in English."))


COMMANDS = (
    Command("preferences", preferences, "Manage optional private updates and reminder quiet hours", category="tools"),
)
