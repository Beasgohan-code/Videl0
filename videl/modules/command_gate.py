"""Per-group command switches, enforced before any other handler.

The group manager can turn a command off for one group. Half the bot's
commands are plain decorators that never pass through the declarative router,
so the only honest place to enforce the switch is a handler that runs before
every other handler group.

Admins and the bot owner are always exempt: a switch protects a community from
a command, it does not lock its own staff out of the tool they administer.
"""
from __future__ import annotations

import asyncio
import re

from pyrogram import StopPropagation, filters

from videl import LOGGER, bot
from videl.app.router import OWNER_ID
from videl.plugins.base import is_admin
from videl.utils.command_ui import notice, rich_reply

_COMMAND = re.compile(r"^/([A-Za-z0-9_]{1,32})(?:@([A-Za-z0-9_]{1,32}))?(?:\s|$)")


@bot.on_message(filters.group & filters.text, group=-2)
async def trace_group_commands(_, message):
    """Log only command names and mention-match state to diagnose missing replies."""
    match = _COMMAND.match(getattr(message, "text", "") or "")
    if not match:
        return
    mention = match.group(2)
    username = getattr(getattr(bot, "me", None), "username", "") or ""
    mention_matches = not mention or bool(username and mention.casefold() == username.casefold())
    LOGGER.info("Group command update received: /%s (bot mention matches: %s)", match.group(1).casefold(), mention_matches)


@bot.on_message(filters.group & filters.text, group=-1)
async def disabled_command_gate(_, message):
    """Refuse a command the group switched off, then stop lower handlers."""
    match = _COMMAND.match(getattr(message, "text", "") or "")
    if not match:
        return
    user = getattr(message, "from_user", None)
    if user is None or getattr(user, "is_bot", False):
        return
    name = match.group(1).casefold()
    try:
        from videl.utils.db import is_disabled
        blocked = await asyncio.to_thread(is_disabled, message.chat.id, name)
    except Exception:
        return
    if not blocked:
        return
    if user.id == OWNER_ID:
        return
    try:
        if await is_admin(bot, message.chat.id, user.id):
            return
    except Exception:
        LOGGER.debug("admin check failed in the command gate", exc_info=True)
    LOGGER.warning("Group command blocked by disabled-command policy: /%s", name)
    try:
        await rich_reply(
            message,
            notice(
                f"<code>/{name}</code> is turned off in this group. A group admin can switch it back on in the group manager.",
                status="warning",
                title="Command turned off",
            ),
            client=bot,
        )
    except Exception as error:
        LOGGER.warning("The disabled-command notice failed to send (%s)", type(error).__name__)
    raise StopPropagation
