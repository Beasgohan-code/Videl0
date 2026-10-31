"""Private group-ban appeals with connected-admin review."""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from pyrogram.enums import ChatMemberStatus

from videl.app.router import Command, CommandError, Screen, chat_kind
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.rich_ui import rich_footer

APPEALS = "mgmt_appeals"
MAX_APPEALS_PER_DAY = 3
APPEAL_WINDOW = timedelta(hours=24)


def _collection():
    return base.collection(APPEALS)


def _status(value) -> str:
    return str(getattr(value, "value", value)).casefold()


async def appeal(ctx) -> Screen:
    """Let a banned member appeal in private without notifying the group."""
    if chat_kind(ctx.message) != "private" or hasattr(ctx.message, "_original"):
        raise CommandError("Send <code>/appeal GROUP_ID your reason</code> in a private chat with me.")
    actor = ctx.user
    match = re.match(r"^(-100\d{8,}|-\d{5,})\s+([\s\S]+)$", ctx.command.arguments.strip())
    if actor is None or not match:
        raise CommandError("Usage: <code>/appeal GROUP_ID your reason</code>. Ask a group admin for the group ID if you don’t know it.")
    chat_id = int(match.group(1))
    reason = match.group(2).strip()
    if not reason:
        raise CommandError("Please include a short reason for your appeal.")
    reason = reason[:1000]
    collection = _collection()
    if collection is None:
        raise CommandError("Appeals can’t be stored right now because MongoDB is unavailable.")

    try:
        group = await ctx.client.get_chat(chat_id)
        kind = _status(getattr(group, "type", ""))
        if kind not in {"group", "supergroup"}:
            raise CommandError("That ID isn’t a supported group chat.")
        membership = await ctx.client.get_chat_member(chat_id, int(actor.id))
        member_status = _status(getattr(membership, "status", ""))
        if member_status in {_status(ChatMemberStatus.BANNED), "banned", "kicked"}:
            action_type = "ban"
        elif member_status == _status(ChatMemberStatus.RESTRICTED):
            permissions = getattr(membership, "permissions", None)
            if permissions is None or getattr(permissions, "can_send_messages", True) is not False:
                raise CommandError("You can appeal here only while banned or muted in that group.")
            action_type = "mute"
        else:
            raise CommandError("You can appeal here only while banned or muted in that group.")
        now = datetime.now(timezone.utc)
        if await asyncio.to_thread(collection.find_one, {"chat_id": chat_id, "user_id": int(actor.id), "status": "open"}):
            raise CommandError("You already have an open appeal for that group. A current group admin can review it with <code>/appeals</code>.")
        recent = await asyncio.to_thread(collection.count_documents, {
            "user_id": int(actor.id), "ts": {"$gte": now - APPEAL_WINDOW},
        })
        if recent >= MAX_APPEALS_PER_DAY:
            raise CommandError("You’ve reached the appeal limit for now. Please try again later.")
        saved = await asyncio.to_thread(collection.insert_one, {
            "chat_id": chat_id,
            "user_id": int(actor.id),
            "action_type": action_type,
            "reason": reason,
            "status": "open",
            "ts": now,
        })
        appeal_id = str(getattr(saved, "inserted_id", ""))
        if not appeal_id:
            raise RuntimeError("database did not return appeal ID")
    except CommandError:
        raise
    except Exception:
        raise CommandError("I couldn’t verify your ban or save the appeal. Check the group ID and try again later.") from None

    return Screen(
        heading("📨 Appeal sent", 3)
        + table([("Appeal ID", f"<code>{escape(appeal_id)}</code>"), ("Group", escape(str(getattr(group, "title", "group"))[:80])), ("Status", "Waiting for group-admin review")])
        + body(f"Your reason was sent privately to the group’s appeal inbox as a {action_type} appeal. Acceptance is reviewed by a current group admin."),
    )


def _require_connected_admin(ctx) -> int:
    # The connected-group proxy is built only after the router resolves the
    # saved group and revalidates the real Telegram administrator.
    if not hasattr(ctx.message, "_original") or not ctx.user:
        raise CommandError("Connect this group with <code>/connect</code>, then review appeals from a current group admin’s private chat.")
    return int(ctx.message.chat.id)


async def appeals(ctx) -> Screen:
    chat_id = _require_connected_admin(ctx)
    collection = _collection()
    if collection is None:
        raise CommandError("Appeals are unavailable because MongoDB is not connected.")
    try:
        rows = await asyncio.to_thread(lambda: list(
            collection.find({"chat_id": chat_id, "status": "open"}).sort("ts", -1).limit(10)
        ))
    except Exception:
        raise CommandError("I couldn’t load the appeal inbox. Please try again.") from None
    if not rows:
        return Screen(heading("📨 Open appeals", 3) + body("There are no appeals waiting for review."))
    rendered = []
    for item in rows:
        rendered.append((
            f"<code>{escape(str(item.get('_id', '')))}</code> · {escape(str(item.get('action_type') or 'ban'))} · user <code>{int(item.get('user_id', 0))}</code>",
            escape(str(item.get("reason") or "No reason provided")[:240]) + f"<br><small>{escape(str(item.get('ts', ''))[:19])}</small>",
        ))
    return Screen(
        heading("📨 Open appeals", 3) + table(rendered)
        + body("Review the request, then use <code>/appealresolve ID accept</code> to unban, or <code>/appealresolve ID deny</code> to close it without changing membership.")
        + rich_footer(f"Showing {len(rows)} of the newest open appeals"),
    )


async def appealresolve(ctx) -> Screen:
    chat_id = _require_connected_admin(ctx)
    match = re.fullmatch(r"([0-9a-fA-F]{24})\s+(accept|deny)(?:\s+([\s\S]+))?", ctx.command.arguments.strip(), re.IGNORECASE)
    if not match:
        raise CommandError("Usage: <code>/appealresolve APPEAL_ID accept|deny [note]</code> · find IDs with <code>/appeals</code>.")
    appeal_id, decision = match.group(1).lower(), match.group(2).lower()
    outcome_note = (match.group(3) or "").strip()
    if len(outcome_note) > 300:
        raise CommandError("The outcome note must be 300 characters or fewer.")
    collection = _collection()
    if collection is None:
        raise CommandError("Appeals are unavailable because MongoDB is not connected.")
    query = {"_id": ObjectId(appeal_id), "chat_id": chat_id, "status": "open"}
    try:
        item = await asyncio.to_thread(collection.find_one, query)
        if not item:
            raise CommandError("That appeal is already closed or doesn’t belong to this connected group.")
        user_id = int(item["user_id"])
        action_type = str(item.get("action_type") or "ban")
        if decision == "accept":
            # Require Telegram to confirm the matching reversal before closing
            # the appeal. Unmuting restores the group's default permissions;
            # it never grants more than the group currently allows.
            if action_type == "mute":
                group = await ctx.client.get_chat(chat_id)
                permissions = getattr(group, "permissions", None)
                if permissions is None:
                    raise CommandError("The group’s default permissions couldn’t be read, so the mute was not changed and the appeal remains open.")
                result = await ctx.client.restrict_chat_member(chat_id, user_id, permissions=permissions)
            else:
                result = await ctx.client.unban_chat_member(chat_id, user_id, only_if_banned=True)
            if result is False:
                raise CommandError("Telegram didn’t confirm the membership change. The appeal remains open.")
        result = await asyncio.to_thread(collection.update_one, query, {"$set": {
            "status": "accepted" if decision == "accept" else "denied",
            "action_type": action_type,
            "outcome_note": outcome_note,
            "resolved_at": datetime.now(timezone.utc),
            "resolved_by": int(ctx.user.id),
        }})
        if not getattr(result, "modified_count", 0):
            raise CommandError("The appeal changed while you were reviewing it. Refresh <code>/appeals</code> before trying again.")
    except CommandError:
        raise
    except Exception:
        raise CommandError("I couldn’t complete that decision. The appeal remains open unless Telegram already confirmed an unban; recheck the group before retrying.") from None
    if decision == "accept":
        change = "unmuted" if action_type == "mute" else "unbanned"
        return Screen(heading("✅ Appeal accepted", 3) + body(f"User <code>{user_id}</code> was {change} and the appeal was closed."))
    return Screen(heading("Appeal closed", 3) + body(f"Appeal <code>{escape(appeal_id)}</code> was denied. The existing {escape(action_type)} restriction was not changed."))


COMMANDS = (
    Command("appeal", appeal, "Submit a private appeal for a group ban or mute", category="manage"),
    Command("appeals", appeals, "Review open appeals for the connected group", category="manage", policy="admin"),
    Command("appealresolve", appealresolve, "Accept or deny a group-ban appeal", category="manage", policy="admin", rights=("can_restrict_members",)),
)
