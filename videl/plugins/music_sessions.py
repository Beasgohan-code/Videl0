# Videl © 2026 | Beasgohan-code
"""Temporary, admin-controlled DJ handoff for group music queues."""
from __future__ import annotations

from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, heading


async def dj(ctx) -> Screen:
    chat_id = int(ctx.message.chat.id)
    args = ctx.command.arguments.strip().casefold()
    current = base.get_setting(chat_id, "music_dj_session", {})
    if args in {"off", "end", "release"}:
        if not base.set_setting(chat_id, "music_dj_session", {}):
            raise CommandError("The DJ handoff could not be saved.")
        return Screen(heading("DJ session ended", 3) + body("Queue controls are back to group administrators."))
    if not args and getattr(ctx.message, "reply_to_message", None) is not None:
        args = "on"
    if not args:
        if isinstance(current, dict) and current.get("user_id"):
            return Screen(heading("DJ session", 3) + body(
                f"Temporary DJ: <a href=\"tg://user?id={int(current['user_id'])}\">{int(current['user_id'])}</a>. "
                "They can manage playback controls until an admin ends or replaces this handoff."))
        return Screen(heading("DJ session", 3) + body(
            "No temporary DJ is assigned. Reply to a member with <code>/dj</code> to hand off, "
            "or use <code>/dj USER_ID</code>. Admins always retain control; use <code>/dj off</code> to end."))

    if args.startswith("@") or not args.isdecimal():
        target = getattr(getattr(ctx.message, "reply_to_message", None), "from_user", None)
        if args not in {"on", "start"} or target is None:
            raise CommandError("Reply to a member with <code>/dj</code> or specify their numeric Telegram user ID: <code>/dj USER_ID</code>.")
        user_id = int(target.id)
    else:
        user_id = int(args)
    if user_id <= 0 or user_id == int(ctx.message.chat.id):
        raise CommandError("Choose a valid member user ID.")
    try:
        member = await ctx.client.get_chat_member(chat_id, user_id)
        if str(getattr(member.status, "value", member.status)).casefold() in {"left", "kicked", "banned"}:
            raise CommandError("That user is not a current group member.")
    except CommandError:
        raise
    except Exception:
        raise CommandError("I could not verify that person is a current group member.") from None
    if not base.set_setting(chat_id, "music_dj_session", {"user_id": user_id}):
        raise CommandError("The DJ handoff could not be saved.")
    return Screen(heading("🎧 DJ handoff active", 3) + body(
        f"<a href=\"tg://user?id={user_id}\">{user_id}</a> can use the group's playback controls. "
        "Group administrators retain control and can replace or end the session with <code>/dj off</code>."))


COMMANDS = (Command("dj", dj, "Assign or end a temporary music DJ", category="music", policy="admin", block_policy="chat"),)
