#  Videl © 2026 | Beasgohan-code
"""Moderation: warnings, bans, kicks, mutes and promotion.

Every action is validated before Telegram is called, every duration is finite,
and failures say exactly what happened instead of pretending success.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from pyrogram.enums import ChatMemberStatus, ChatMembersFilter
from pyrogram.errors import UserNotParticipant
from pyrogram.types import ChatAdministratorRights, ChatPermissions, InlineKeyboardMarkup

from videl import LOGGER
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table, target_link
from videl.utils import warnings
from videl.utils.audit import record_bot
from videl.utils.bot_ui import button
from videl.utils.command_ui import usage

WARNINGS = "mgmt_warnings"
BANS = "mgmt_banned_users"
PROTECTED = "The bot and its owner cannot be moderated."


def _warnings():
    return base.collection(WARNINGS)


def _bans():
    return base.collection(BANS)


def warn_limit(chat_id: int) -> int:
    return int(base.get_setting(chat_id, "warn_threshold", 3) or 3)


def _names(message):
    actor = getattr(message, "from_user", None)
    return base.authority(message)[0], getattr(actor, "first_name", "an admin")


def duration(value: str) -> int:
    """Strict duration parsing that raises a user-facing error."""
    seconds = base.parse_duration(value)
    if seconds is None:
        raise CommandError("Temporary actions need a duration such as 10m, 2h or 7d.")
    return seconds


async def resolve(ctx):
    """Compatibility helper: ``(user, remaining_tokens)`` for a command context."""
    return await base.resolve_target(ctx.client, ctx.message, ctx.command.arguments.split())


async def _target(ctx):
    user, rest = await base.resolve_target(ctx.client, ctx.message, ctx.command.arguments.split())
    if user is None:
        raise CommandError("Reply to a member, or use @username or a numeric user ID.")
    if int(getattr(user, "id", 0)) <= 0:
        raise CommandError("Anonymous and channel senders cannot be targeted.")
    return user, rest


async def _protect(ctx, user) -> None:
    me = getattr(ctx.client, "me", None) or await ctx.client.get_me()
    if int(user.id) in {int(me.id), int(getattr(ctx.client, "owner_id", 0) or 6265999542)}:
        raise CommandError(PROTECTED)
    try:
        member = await ctx.client.get_chat_member(ctx.message.chat.id, user.id)
    except UserNotParticipant:
        member = None
    except Exception as exc:
        raise CommandError(
            "Membership could not be verified, so nothing was changed. Try again in a moment."
        ) from exc
    if member is not None and member.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}:
        raise CommandError("Group owners and administrators are protected targets.")


async def _require(ctx, needed: tuple[str, ...]) -> None:
    rights = await base.bot_rights(ctx.client, ctx.message.chat.id)
    missing = base.missing_rights(rights, needed)
    if missing:
        labels = ", ".join(base.SETTING_LABELS.get(name, name) for name in missing)
        raise CommandError(f"I need these administrator rights first: {labels}.")


def _reason(tokens, fallback="No reason supplied") -> str:
    return " ".join(tokens)[:400] or fallback


def _audit(chat_id: int, user_id: int, reason: str, remove: bool = False) -> bool:
    store = _bans()
    if store is None:
        return False
    selector = {"chat_id": chat_id, "user_id": user_id}
    if remove:
        store.delete_one(selector)
    else:
        store.update_one(
            selector,
            {"$set": {"reason": reason, "ts": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
    return True


# ── Warnings ─────────────────────────────────────────────────────────────────


def _escalation(chat_id: int) -> dict:
    """The group's configured warning ladder; defaults match historic behaviour."""
    try:
        from videl.utils.db import get_escalation
        return get_escalation(chat_id)
    except Exception:
        from videl.utils.automation import normalize_escalation
        return normalize_escalation({})


async def _apply_action(ctx, chat_id: int, user_id: int, action: str, escalation: dict) -> str:
    """Apply the configured action and return a phrase for the confirmation text."""
    if action == "mute":
        hours = int(escalation.get("mute_hours") or 6)
        until = datetime.now(timezone.utc) + timedelta(hours=hours)
        await ctx.client.ban_chat_member(chat_id, user_id, until_date=until)
        return f"the member was muted for {hours} hour{'s' if hours != 1 else ''}"
    if action == "kick":
        await ctx.client.ban_chat_member(chat_id, user_id)
        await ctx.client.unban_chat_member(chat_id, user_id)
        return "the member was removed and may rejoin"
    await ctx.client.ban_chat_member(chat_id, user_id)
    return "the member was banned"


async def warn(ctx) -> Screen:
    chat_id, _ = _names(ctx.message)
    user, tokens = await _target(ctx)
    store = _warnings()
    if store is None:
        raise CommandError("MongoDB is not connected, so the warning was not saved.")
    await _protect(ctx, user)
    reason = _reason(tokens)
    escalation = _escalation(chat_id)
    document = await asyncio.to_thread(store.find_one, {"chat_id": chat_id, "user_id": user.id})
    limit = warn_limit(chat_id)
    # One shared verdict for both warning surfaces: decay first, then the rung
    # this warning reaches. A stale warning must never count against a member.
    plan = warnings.next_stage(document, limit, escalation.get("decay_days", 0))
    count, stage = plan["count"], plan["stage"]
    stored_total = int((document or {}).get("count", 0)) + 1
    await asyncio.to_thread(
        store.update_one,
        {"chat_id": chat_id, "user_id": user.id},
        {
            "$push": {"reasons": {"reason": reason, "ts": datetime.now(timezone.utc).isoformat()}},
            "$set": {"count": stored_total, "updated": datetime.now(timezone.utc),
                     "stages": plan["next_stage"] if plan["reached"] else int((document or {}).get("stages") or 0)},
        },
        upsert=True,
    )
    if ctx.command.name == "dwarn":
        reply = getattr(ctx.message, "reply_to_message", None)
        if reply is not None:
            try:
                await reply.delete()
            except Exception:
                LOGGER.debug("dwarn could not delete the replied message", exc_info=True)
    await asyncio.to_thread(
        record_bot, chat_id, "warn", action="warn",
        detail=f"member {user.id}: {reason}"[:240],
        actor=getattr(getattr(ctx.message, "from_user", None), "id", None),
    )
    notes = ""
    if plan["reached"]:
        action = warnings.ladder_action(escalation, stage) if escalation.get("enabled") else "none"
        if action == "none":
            notes = f"Reached the limit of {limit}; escalation is switched off for this group."
        else:
            try:
                await _require(ctx, ("can_restrict_members",))
                note = await _apply_action(ctx, chat_id, user.id, action, escalation)
                await asyncio.to_thread(_audit, chat_id, user.id, f"{limit} warnings")
                notes = f"Reached the limit of {limit}; {note}."
            except Exception as exc:
                notes = f"Reached the limit of {limit}, but the {action} was not confirmed ({type(exc).__name__})."
    return Screen(
        heading("Warning added", 3)
        + table([
            ("Member", target_link(user)),
            ("Reason", escape(reason)),
            ("Warnings", f"{count}/{limit}"),
        ])
        + body(notes or "The warning is saved. Admins can review it with /warnings.")
        + (body(f"{plan['decayed']} older warning{'s' if plan['decayed'] != 1 else ''} no longer count towards this limit.")
           if plan["decayed"] else body("")),
        InlineKeyboardMarkup([[button("All warnings", callback_data="help:manage")]]),
    )


async def unwarn(ctx) -> Screen:
    chat_id, _ = _names(ctx.message)
    user, _ = await _target(ctx)
    store = _warnings()
    if store is None:
        raise CommandError("MongoDB is not connected.")
    document = await asyncio.to_thread(store.find_one, {"chat_id": chat_id, "user_id": user.id})
    if not document or int(document.get("count", 0)) <= 0:
        return Screen(heading("No warnings", 3) + body(f"{target_link(user)} has no warnings to remove."))
    reasons = list(document.get("reasons") or [])
    if reasons:
        reasons.pop()
    count = max(0, int(document.get("count", 1)) - 1)
    stage = max(0, int(document.get("stages") or 0) - 1)
    await asyncio.to_thread(
        store.update_one,
        {"chat_id": chat_id, "user_id": user.id},
        {"$set": {"count": count, "reasons": reasons, "stages": stage,
                  "updated": datetime.now(timezone.utc)}},
    )
    return Screen(heading("Warning removed", 3) + table([("Member", target_link(user)), ("Warnings", f"{count}/{warn_limit(chat_id)}")]))


async def warnings(ctx) -> Screen:
    chat_id, _ = _names(ctx.message)
    store = _warnings()
    if store is None:
        raise CommandError("MongoDB is not connected.")
    if ctx.command.arguments.strip() or getattr(ctx.message, "reply_to_message", None):
        user, _ = await _target(ctx)
    else:
        user = getattr(ctx.message, "from_user", None)
    if user is None:
        raise CommandError("Reply to a member or pass @username.")
    document = await asyncio.to_thread(store.find_one, {"chat_id": chat_id, "user_id": user.id})
    limit = warn_limit(chat_id)
    state = warnings.active_warnings(document, _escalation(chat_id).get("decay_days", 0))
    if not state["total"]:
        return Screen(heading("Clean record", 3) + body(f"{target_link(user)} has no warnings."))
    decay_days = int(_escalation(chat_id).get("decay_days", 0) or 0)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=decay_days)) if decay_days else None
    rows = []
    for index, item in enumerate((document or {}).get("reasons") or []):
        entry = warnings.warning_entries({"reasons": [item]})[0]
        live = cutoff is None or entry["ts"] is None or entry["ts"] >= cutoff
        when = entry["ts"].strftime("%d %b %Y") if entry["ts"] else "undated"
        rows.append((f"#{index + 1}", f"{escape(entry['reason'] or '—')} · {when}" + ("" if live else " · expired")))
    notes = f"{state['count']} of {state['total']} warnings still count towards the limit of {limit}."
    if state["decayed"]:
        notes += f" {state['decayed']} lapsed after the decay window."
    if state["expires_at"]:
        notes += f" The next one lapses on {state['expires_at'].strftime('%d %b %Y')}."
    return Screen(
        heading("Warning history", 3)
        + table([("Member", target_link(user)), ("Active", f"{state['count']}/{limit}")])
        + table(rows)
        + body(notes)
    )


async def clear_warnings(ctx) -> Screen:
    chat_id, _ = _names(ctx.message)
    user, _ = await _target(ctx)
    store = _warnings()
    if store is None:
        raise CommandError("MongoDB is not connected.")
    await asyncio.to_thread(store.delete_one, {"chat_id": chat_id, "user_id": user.id})
    await asyncio.to_thread(
        record_bot, chat_id, "warn_reset", action="warn_reset",
        detail=f"member {user.id}: warnings cleared",
        actor=getattr(getattr(ctx.message, "from_user", None), "id", None),
    )
    return Screen(heading("Warnings cleared", 3)
                  + body(f"{target_link(user)} now has a clean record, and the ladder starts again."))


async def set_warn_limit(ctx) -> Screen:
    chat_id, _ = _names(ctx.message)
    argument = ctx.command.arguments.strip()
    if not argument.isdecimal() or not 1 <= int(argument) <= 10:
        return Screen(usage("/setwarnlimit 3", "Choose a limit between 1 and 10 warnings."))
    limit = int(argument)
    if not base.set_setting(chat_id, "warn_threshold", limit):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("Warning limit", 3) + body(f"Members are banned after <b>{limit}</b> warnings."))


async def ban_list(ctx) -> Screen:
    chat_id, _ = _names(ctx.message)
    store = _bans()
    if store is None:
        raise CommandError("MongoDB is not connected.")
    documents = await asyncio.to_thread(lambda: list(store.find({"chat_id": chat_id}).limit(30)))
    if not documents:
        return Screen(heading("Ban records", 3) + body("No bans recorded for this group."))
    rows = [(f"<code>{escape(item.get('user_id'))}</code>", escape((item.get("reason") or "—")[:40])) for item in documents]
    return Screen(heading("Ban records", 3) + table(rows))


# ── Bans, kicks and mutes ────────────────────────────────────────────────────


async def moderate(ctx) -> Screen:
    name = ctx.command.name
    chat_id, _ = _names(ctx.message)
    user, tokens = await _target(ctx)
    await _protect(ctx, user)
    until_date = None
    if name in {"tban", "tmute"}:
        if not tokens:
            return Screen(usage(f"/{name} @user 10m reason", "Temporary actions need a duration."))
        seconds = duration(tokens.pop(0))
        until_date = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    reason = _reason(tokens)
    notes: list[str] = []

    if name in {"ban", "tban", "dban", "kick", "dkick"}:
        await _require(ctx, ("can_restrict_members",) + (("can_delete_messages",) if name in {"dban", "dkick"} else ()))
        expiry = datetime.now(timezone.utc) + timedelta(seconds=60) if name in {"kick", "dkick"} else until_date
        if await ctx.client.ban_chat_member(chat_id, user.id, until_date=expiry) is False:
            raise CommandError("Telegram did not confirm the ban. Nothing else was changed.")
        title = "Member banned"
        if name in {"kick", "dkick"}:
            try:
                if await ctx.client.unban_chat_member(chat_id, user.id) is False:
                    raise RuntimeError("unban not acknowledged")
                title = "Member removed"
            except Exception:
                title = "Removal partly confirmed"
                notes.append("The temporary ban is confirmed; the release is not. It expires in about a minute.")
        else:
            try:
                if not await asyncio.to_thread(_audit, chat_id, user.id, reason):
                    notes.append("Telegram confirmed the ban, but the audit database is offline.")
            except Exception:
                notes.append("Telegram confirmed the ban; the audit record could not be saved.")
    elif name == "unban":
        await _require(ctx, ("can_restrict_members",))
        if await ctx.client.unban_chat_member(chat_id, user.id) is False:
            raise CommandError("Telegram did not confirm the unban.")
        title = "Member unbanned"
        try:
            await asyncio.to_thread(_audit, chat_id, user.id, reason, True)
        except Exception:
            notes.append("Telegram confirmed the unban; the local record could not be updated.")
    elif name in {"mute", "tmute", "unmute"}:
        await _require(ctx, ("can_restrict_members",))
        if name == "unmute":
            chat = await ctx.client.get_chat(chat_id)
            permissions = chat.permissions
            if permissions is None:
                raise CommandError("Group default permissions could not be read. Nothing changed.")
        else:
            permissions = ChatPermissions(can_send_messages=False)
        if await ctx.client.restrict_chat_member(chat_id, user.id, permissions, until_date=until_date) is False:
            raise CommandError("Telegram did not confirm the restriction.")
        title = "Member unmuted" if name == "unmute" else "Member muted"
    else:
        raise CommandError("Unknown moderation action.")

    if name in {"dban", "dkick"}:
        reply = getattr(ctx.message, "reply_to_message", None)
        if reply is not None:
            try:
                if await ctx.client.delete_messages(chat_id, reply.id) is False:
                    raise RuntimeError("delete not acknowledged")
            except Exception:
                notes.append("The membership action is confirmed; message deletion is not.")

    # The action is already confirmed by Telegram; the trail records who did it
    # and why, so the panel can answer "who removed this member?" later.
    await asyncio.to_thread(
        record_bot, chat_id, "moderation",
        action=name,
        detail=f"member {user.id}: {reason}"[:240]
               + (f" until {until_date.strftime('%d %b %Y %H:%M')} UTC" if until_date else ""),
        actor=getattr(getattr(ctx.message, "from_user", None), "id", None),
    )
    rows = [("Member", target_link(user)), ("User ID", f"<code>{user.id}</code>"), ("Reason", escape(reason))]
    if until_date is not None:
        rows.append(("Until (UTC)", until_date.strftime("%d %b %Y %H:%M")))
    return Screen(
        heading(title, 3)
        + table(rows)
        + body(" ".join(notes) or "Telegram acknowledged the action."),
        InlineKeyboardMarkup([[button("Warnings", callback_data="help:manage")]]),
    )


# ── Promotion and roster ────────────────────────────────────────────────────


async def promote(ctx) -> Screen:
    chat_id, _ = _names(ctx.message)
    user, _ = await _target(ctx)
    await _protect(ctx, user)
    await _require(ctx, ("can_promote_members",))
    rights = ChatAdministratorRights(
        can_delete_messages=True,
        can_restrict_members=True,
        can_pin_messages=True,
        can_invite_users=True,
        can_manage_video_chats=True,
    )
    try:
        await ctx.client.promote_chat_member(chat_id, user.id, privileges=rights)
    except Exception as exc:
        raise CommandError(f"Telegram rejected the promotion ({type(exc).__name__}).") from None
    return Screen(heading("Promoted", 3) + body(f"{target_link(user)} can now moderate this group."))


async def demote(ctx) -> Screen:
    chat_id, _ = _names(ctx.message)
    user, _ = await _target(ctx)
    await _protect(ctx, user)
    await _require(ctx, ("can_promote_members",))
    try:
        await ctx.client.promote_chat_member(chat_id, user.id, privileges=ChatAdministratorRights())
    except Exception as exc:
        raise CommandError(f"Telegram rejected the demotion ({type(exc).__name__}).") from None
    return Screen(heading("Demoted", 3) + body(f"{target_link(user)} is a regular member again."))


async def admins(ctx) -> Screen:
    chat_id, _ = _names(ctx.message)
    try:
        members = [
            member
            async for member in ctx.client.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS, limit=50)
        ]
    except Exception as exc:
        raise CommandError(f"The administrator list could not be read ({type(exc).__name__}).") from None
    rows = [
        (
            ("Owner · " if member.status == ChatMemberStatus.OWNER else "Admin · ")
            + escape(getattr(member.user, "first_name", "Unknown")),
            f"<code>{member.user.id}</code>",
        )
        for member in members
    ]
    return Screen(heading("Administrators", 3) + (table(rows) if rows else body("No administrators found.")))


COMMANDS = (
    Command("warn", warn, "Warn a member and auto-ban at the limit", category="manage", policy="admin"),
    Command("dwarn", warn, "Warn a member and delete their message", category="manage", policy="admin",
            rights=("can_delete_messages",)),
    Command("unwarn", unwarn, "Remove the latest warning", category="manage", policy="admin"),
    Command("warnings", warnings, "Show a member's warning history", category="manage"),
    Command("clearwarns", clear_warnings, "Clear every warning for a member", category="manage", policy="admin"),
    Command("setwarnlimit", set_warn_limit, "Set how many warnings trigger a ban", category="manage", policy="admin"),
    Command("banlist", ban_list, "Show recorded bans", category="manage", policy="admin"),
    Command("ban", moderate, "Ban a member", category="manage", policy="admin", rights=("can_restrict_members",)),
    Command("tban", moderate, "Temporarily ban a member", category="manage", policy="admin", rights=("can_restrict_members",)),
    Command("dban", moderate, "Ban a member and delete their message", category="manage", policy="admin",
            rights=("can_restrict_members", "can_delete_messages")),
    Command("unban", moderate, "Lift a ban", category="manage", policy="admin", rights=("can_restrict_members",)),
    Command("kick", moderate, "Remove a member", category="manage", policy="admin", rights=("can_restrict_members",)),
    Command("dkick", moderate, "Remove a member and delete their message", category="manage", policy="admin",
            rights=("can_restrict_members", "can_delete_messages")),
    Command("mute", moderate, "Mute a member", category="manage", policy="admin", rights=("can_restrict_members",)),
    Command("tmute", moderate, "Temporarily mute a member", category="manage", policy="admin", rights=("can_restrict_members",)),
    Command("unmute", moderate, "Restore a member's permissions", category="manage", policy="admin", rights=("can_restrict_members",)),
    Command("promote", promote, "Promote a member with moderation rights", category="manage", policy="admin",
            rights=("can_promote_members",)),
    Command("demote", demote, "Remove administrator rights", category="manage", policy="admin", rights=("can_promote_members",)),
    Command("admins", admins, "List group administrators", category="manage"),
)
