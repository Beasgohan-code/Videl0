"""Member reports with private-by-default moderator review and resolution."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.rich_ui import rich_footer

REPORTS = "mgmt_reports"
MAX_REPORTS_PER_REPORTER = 5
REPORT_WINDOW = timedelta(hours=1)


def _reports_collection():
    return base.collection(REPORTS)


async def report(ctx) -> Screen:
    if not base.is_group(ctx.message):
        raise CommandError("Reports can only be submitted from a group.")
    actor = ctx.user
    reply = getattr(ctx.message, "reply_to_message", None)
    target = getattr(reply, "from_user", None) if reply else None
    if actor is None:
        raise CommandError("I couldn’t verify your Telegram account.")
    if reply is None or target is None:
        raise CommandError("Reply to the message you want moderators to review, then run <code>/report [reason]</code>.")
    if int(target.id) == int(actor.id):
        raise CommandError("You can’t report your own message.")

    collection = _reports_collection()
    if collection is None:
        raise CommandError("Reports can’t be stored right now because MongoDB is unavailable.")
    now = datetime.now(timezone.utc)
    try:
        recent = await asyncio.to_thread(collection.count_documents, {
            "chat_id": int(ctx.message.chat.id),
            "reporter": int(actor.id),
            "ts": {"$gte": now - REPORT_WINDOW},
        })
        if recent >= MAX_REPORTS_PER_REPORTER:
            raise CommandError("You’ve reached the report limit for now. Please wait before submitting another.")
        reason = ctx.command.arguments.strip()[:300] or "No reason provided"
        inserted = await asyncio.to_thread(collection.insert_one, {
            "chat_id": int(ctx.message.chat.id),
            "message_id": int(reply.id),
            "reporter": int(actor.id),
            "target": int(target.id),
            "reason": reason,
            "status": "open",
            "ts": now,
        })
        report_id = str(getattr(inserted, "inserted_id", ""))
        if not report_id:
            raise RuntimeError("database did not acknowledge report id")
    except CommandError:
        raise
    except Exception:
        raise CommandError("I couldn’t save that report. Please try again later.") from None
    return Screen(
        heading("📣 Report submitted", 3)
        + table([("Report ID", f"<code>{escape(report_id)}</code>"), ("Status", "Pending moderator review")])
        + body("The report is queued for this group’s admins. The original message was not changed.")
    )


def _require_private_review(ctx) -> None:
    # ConnectedMessage is created only by the private command router after it
    # resolves the saved group and rechecks the actual Telegram actor's admin role.
    if not hasattr(ctx.message, "_original"):
        raise CommandError("For report privacy, connect this group with <code>/connect</code>, then run <code>/reports</code> in my private chat.")


async def reports(ctx) -> Screen:
    _require_private_review(ctx)
    collection = _reports_collection()
    if collection is None:
        raise CommandError("Reports are unavailable because MongoDB is not connected.")
    try:
        cursor = await asyncio.to_thread(
            lambda: list(collection.find({"chat_id": int(ctx.message.chat.id), "status": "open"})
                         .sort("ts", -1).limit(8))
        )
    except Exception:
        raise CommandError("I couldn’t load the reports for this group.") from None
    if not cursor:
        return Screen(heading("📣 Open reports", 3) + body("There are no reports waiting for review."))
    rows = []
    for item in cursor:
        rows.append((
            f"<code>{escape(str(item.get('_id') or item.get('id') or ''))}</code> · message <code>{int(item.get('message_id', 0))}</code>",
            f"{escape(str(item.get('reason') or item.get('text') or 'No reason provided')[:140])}<br>Reporter <code>{int(item.get('reporter', item.get('reporter_id', 0)))}</code> · target <code>{int(item.get('target', item.get('target_id', 0)))}</code>",
        ))
    return Screen(
        heading("📣 Open reports", 3)
        + table(rows)
        + body("Resolve a reviewed item with <code>/resolve REPORT_ID</code>. Reports are visible only to group admins through this command.")
        + rich_footer(f"Showing {len(rows)} of the newest open reports")
    )


async def resolve(ctx) -> Screen:
    _require_private_review(ctx)
    report_id = ctx.command.arguments.strip().split(maxsplit=1)[0] if ctx.command.arguments.strip() else ""
    from bson import ObjectId
    if not ObjectId.is_valid(report_id):
        raise CommandError("Usage: <code>/resolve REPORT_ID</code> · copy the ID shown by <code>/reports</code>.")
    collection = _reports_collection()
    if collection is None:
        raise CommandError("Reports are unavailable because MongoDB is not connected.")
    try:
        result = await asyncio.to_thread(
            collection.update_one,
            {"chat_id": int(ctx.message.chat.id), "_id": ObjectId(report_id), "status": "open"},
            {"$set": {"status": "resolved", "resolved": datetime.now(timezone.utc), "resolved_by": int(ctx.user.id)}},
        )
    except Exception:
        raise CommandError("I couldn’t update that report. Please try again.") from None
    if not getattr(result, "modified_count", 0):
        raise CommandError("That report is already resolved or its ID doesn’t belong to this group.")
    return Screen(heading("✅ Report resolved", 3) + body(f"Report <code>{escape(report_id.lower())}</code> was marked resolved."))


COMMANDS = (
    Command("report", report, "Report a replied-to message for moderator review", category="manage", policy="group"),
    Command("reports", reports, "Review open reports for this group", category="manage", policy="admin"),
    Command("resolve", resolve, "Mark a report as resolved", category="manage", policy="admin"),
)
