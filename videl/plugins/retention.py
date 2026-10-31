# Videl © 2026 | Beasgohan-code
"""Group-admin controls for bounded retention of resolved case history."""
from __future__ import annotations

import asyncio

from videl.app.router import Command, CommandError, Screen
from videl.plugins.base import body, heading, table

LABELS = {
    "case_notes": ("notes", "Moderator case notes"),
    "resolved_reports": ("reports", "Resolved or dismissed reports"),
    "resolved_join_requests": ("requests", "Resolved join requests"),
    "resolved_appeals": ("appeals", "Closed appeals"),
    "resolved_escalations": ("escalations", "Reviewed escalations"),
}
ALIASES = {alias: name for name, (alias, _label) in LABELS.items()}


def _view(policy):
    return [(label, f"{days} days" if days is not None else "Keep")
            for name, (_alias, label) in LABELS.items() for days in [policy.get(name)]]


async def retention(ctx) -> Screen:
    from videl.plugins import base
    from videl.utils.db import get_db
    from videl.utils.retention import ALLOWED_DAYS, normalize, save
    chat_id = int(ctx.message.chat.id)
    db = get_db()
    if db is None:
        raise CommandError("Retention settings are unavailable while the database is disconnected.")
    parts = ctx.command.arguments.strip().split()
    current = normalize(base.get_setting(chat_id, "data_retention", {}))
    if parts and parts[0].casefold() == "preview" and len(parts) == 1:
        from videl.utils.retention import cleanup_group_history
        preview = await asyncio.to_thread(cleanup_group_history, db, apply=False, chat_id=chat_id)
        if not preview.get("ok"):
            raise CommandError("This group’s retention preview could not be loaded.")
        rows = []
        for category, (_alias, label) in LABELS.items():
            count = sum(value for key, value in preview["counts"].items()
                        if key == f"{chat_id}:{category}")
            rows.append((label, str(count)))
        return Screen(heading("Retention preview", 3)
                      + table(rows)
                      + body("These resolved history rows are eligible under this group’s saved policy. The preview does not delete anything."))
    if not parts or parts[0].casefold() == "status":
        days = ", ".join(map(str, ALLOWED_DAYS))
        return Screen(heading("Group history retention", 3)
                      + table(_view(current))
                      + body(f"Set a category with <code>/retention notes {days}</code>; use <code>off</code> to keep it indefinitely. Preview with <code>/retention preview</code>.")
                      + body("Only old, resolved history is removed by scheduled cleanup. Pending reports, requests, appeals and reviews are never deleted. Warning state is excluded; audit retention remains a separate system policy. Message recordings have separate 1/7/30-day controls."))
    if len(parts) != 2 or parts[0].casefold() not in ALIASES:
        raise CommandError("Choose notes, reports, requests, appeals or escalations, followed by 30, 90, 180, 365 or off.")
    category = ALIASES[parts[0].casefold()]
    raw_days = parts[1].casefold()
    if raw_days == "off":
        days = None
    elif raw_days.isdecimal() and int(raw_days) in ALLOWED_DAYS:
        days = int(raw_days)
    else:
        raise CommandError("Choose 30, 90, 180, 365 or off.")
    policy = await asyncio.to_thread(save, db, chat_id, category, days)
    if policy is None:
        raise CommandError("The retention setting could not be saved; nothing changed.")
    try:
        from videl.utils.audit import record_bot
        await asyncio.to_thread(record_bot, chat_id, "settings", action="retention_policy",
                                detail=f"{category}={days if days is not None else 'keep'} days",
                                actor=int(ctx.user.id))
    except Exception:
        pass
    alias, label = LABELS[category]
    value = f"{days} days" if days is not None else "Keep indefinitely"
    return Screen(heading("✅ Retention policy saved", 3)
                  + table([(label, value)])
                  + body("The scheduled cleanup applies this policy to already-resolved history. New or pending cases are retained until closed."))


COMMANDS = (
    Command("retention", retention, "Review or configure how long resolved group history is kept", category="manage", policy="admin"),
)
