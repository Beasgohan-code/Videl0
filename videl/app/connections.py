"""Authenticated private-chat routing for a user's connected group.

Only explicit group-admin and playback commands are proxied. The target group
comes from the server-side Mongo mapping, never from command arguments, and
handlers still receive the real Telegram actor. Reply targets are intentionally
removed because a private reply's message ID cannot safely target a group.
"""
from __future__ import annotations

CONNECTED_COMMANDS = frozenset({
    "admins", "adminlist", "rules", "locks", "lock", "unlock", "setrules", "clearrules",
    "welcome", "setwelcome", "setgoodbye", "goodbye", "setcaptcha", "greetings",
    "warnings", "banlist", "warn", "unwarn", "clearwarns", "setwarnlimit", "ban", "tban",
    "dban", "unban", "kick", "dkick", "mute", "tmute", "unmute", "promote", "demote",
    "notes", "save", "get", "delnote", "filter", "filters", "stopfilter",
    "settitle", "setdescription", "slowmode",
    "pause", "resume", "loop", "shuffle", "clear", "skip", "stop", "end", "resetplayer",
    "replay", "queue", "q", "reports", "resolve", "appeals", "appealresolve",
})


class ConnectedMessage:
    """Group-context view of a private message, retaining private reply methods."""
    def __init__(self, original, target_chat):
        self._original = original
        self.chat = target_chat
        self.reply_to_message = None
        self.message_thread_id = None

    def __getattr__(self, name):
        return getattr(self._original, name)


async def connected_message(client, original, command_name):
    """Resolve a trusted group target, or return a concise user-safe error."""
    if command_name not in CONNECTED_COMMANDS:
        return None, None
    actor = getattr(original, "from_user", None)
    if not actor:
        return None, "I couldn’t verify your Telegram account for a connected-group action."
    from videl.utils.db import get_connected_chat
    import asyncio

    chat_id = await asyncio.to_thread(get_connected_chat, int(actor.id))
    if not chat_id:
        return None, "No group is connected to this account. Run <code>/connect</code> as a group admin in that group first."
    try:
        chat = await client.get_chat(int(chat_id))
        kind = str(getattr(getattr(chat, "type", None), "value", getattr(chat, "type", "")))
        if kind not in {"group", "supergroup"}:
            return None, "The saved connection is no longer a group. Run <code>/connect</code> again in the correct group."
        from pyrogram.enums import ChatMemberStatus
        member = await client.get_chat_member(int(chat_id), int(actor.id))
        if getattr(member, "status", None) not in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}:
            return None, "You’re no longer a current administrator of the connected group. Ask an admin to reconnect you after your permissions are restored."
    except Exception:
        return None, "I can’t access the connected group. Check that I’m still in it, then reconnect with <code>/connect</code>."
    return ConnectedMessage(original, chat), None
