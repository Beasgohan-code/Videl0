# Videl © 2026 | Beasgohan-code
"""Member-owned data export, scoped erasure, and anonymous feedback."""
from __future__ import annotations

import asyncio
import io
import json

from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table


def _private(ctx) -> bool:
    return base.chat_kind(ctx.message) == "private" and int(ctx.message.chat.id) == int(ctx.user.id)


async def my_data(ctx) -> Screen:
    if not _private(ctx):
        raise CommandError("For privacy, request your export in a private chat with Videl.")
    from videl.utils.db import get_db
    from videl.utils.member_data import export_user_data
    database = get_db()
    if database is None:
        raise CommandError("The data store is unavailable; no export was generated.")
    try:
        data = await asyncio.to_thread(export_user_data, database, int(ctx.user.id))
    except Exception as exc:
        raise CommandError("A complete export could not be generated. Nothing was removed; please try again later.") from exc
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    if len(payload) > 5 * 1024 * 1024:
        raise CommandError("Your export is larger than the safe download limit. Contact the bot owner for help.")
    file = io.BytesIO(payload)
    file.name = f"videl-member-data-{int(ctx.user.id)}.json"
    try:
        await ctx.client.send_document(ctx.message.chat.id, file, caption="Your Videl data export. It contains records linked to your Telegram account.")
    except Exception as exc:
        raise CommandError("Telegram did not confirm delivery of the export. No data was removed.") from exc
    return Screen(heading("✅ Data export sent", 3)
                  + body("The JSON file was sent in this private chat. It contains records currently linked to your Telegram ID; records already expired or deleted are not recoverable."))


async def forget_member(ctx) -> Screen:
    chat = ctx.message.chat
    if base.chat_kind(ctx.message) not in {"group", "supergroup"}:
        raise CommandError("Use this command in the group whose records should be removed.")
    parts = ctx.command.arguments.strip().split()
    if len(parts) != 2 or not parts[0].isdecimal() or parts[1].casefold() != "confirm":
        return Screen(heading("Remove a member's group records", 3)
                      + body("Usage: <code>/forgetmember USER_ID confirm</code>. This removes selected warnings, reports, join requests, approvals and case notes for this group only.")
                      + body("Immutable audit history is retained. Owner-managed inbox recordings are not changed by this group-admin command."))
    user_id = int(parts[0])
    if user_id <= 0 or user_id > 2**63 - 1 or user_id == int(ctx.user.id):
        raise CommandError("Choose another valid Telegram user ID.")
    from videl.utils.db import get_db
    from videl.utils.member_data import delete_member_group_data
    database = get_db()
    if database is None:
        raise CommandError("The data store is unavailable; nothing was removed.")
    counts = await asyncio.to_thread(delete_member_group_data, database, int(chat.id), user_id)
    from videl.utils.audit import record_bot
    result_summary = ", ".join(f"{name}={value}" for name, value in counts.items())
    audit_ok = await asyncio.to_thread(record_bot, int(chat.id), "moderation", action="member_data_removal",
                                       detail=f"member {user_id}; {result_summary}", actor=int(ctx.user.id))
    failed = any(value == "error" for value in counts.values())
    return Screen(heading("⚠️ Removal partly failed" if failed else "✅ Member records removed", 3)
                  + table([(name.replace("_", " ").title(), str(value)) for name, value in counts.items()])
                  + body("Some records could not be processed; contact the bot owner before considering the request complete." if failed else "Only the selected group was changed.")
                  + body("The deletion was recorded in the group audit history." if audit_ok else "The deletion was applied, but the audit write failed; notify the bot owner."))


async def feedback(ctx) -> Screen:
    if not _private(ctx):
        raise CommandError("Send anonymous feedback in a private chat with Videl, not in a group.")
    text = ctx.command.arguments.strip()
    if not text:
        return Screen(heading("Anonymous feedback", 3)
                      + body("Usage: <code>/feedback your suggestion</code> · up to 1000 characters.")
                      + body("Videl does not store your Telegram user or chat ID with the submission. Telegram itself still processes the message."))
    from videl.utils.db import get_db
    from videl.utils.member_data import submit_feedback
    identifier = await asyncio.to_thread(submit_feedback, get_db(), text)
    if not identifier:
        raise CommandError("Feedback could not be saved. Please try again later.")
    return Screen(heading("✅ Feedback received", 3)
                  + body("Your suggestion was saved without a sender ID or chat ID. It is scheduled for deletion after 180 days; automated cleanup may take additional time."))


async def feedback_list(ctx) -> Screen:
    if not _private(ctx):
        raise CommandError("Use this owner-only command in private chat.")
    from videl.utils.db import get_db
    from videl.utils.member_data import feedback_rows
    rows = await asyncio.to_thread(feedback_rows, get_db(), 20)
    if not rows:
        return Screen(heading("Anonymous feedback", 3) + body("No feedback is stored right now."))
    return Screen(heading("Anonymous feedback", 3)
                  + table([(item["created_at"] or "unknown time", escape(item["text"][:300])) for item in rows])
                  + body("Submissions contain no sender ID or chat ID."))


COMMANDS = (
    Command("mydata", my_data, "Download a private export of your stored Videl data", category="tools", policy="public"),
    Command("forgetmember", forget_member, "Remove selected member records from this group", category="manage", policy="admin"),
    Command("feedback", feedback, "Send anonymous private feedback", category="tools", policy="public"),
    Command("feedbacklist", feedback_list, "Read anonymous feedback (owner only)", category="owner", policy="owner"),
)
