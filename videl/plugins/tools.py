#  Videl © 2026 | Beasgohan-code
"""Everyday tools: identifiers, profiles, latency and source credits."""
from __future__ import annotations

import time
from datetime import timedelta

from pyrogram.types import InlineKeyboardMarkup

import config
from videl import bot_start_time
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table, target_link
from videl.utils.bot_ui import button

REPOSITORY = "https://github.com/Beasgohan-code/Videl0"


async def identifiers(ctx) -> Screen:
    message = ctx.message
    user = getattr(message, "from_user", None)
    rows = [
        ("Chat ID", f"<code>{message.chat.id}</code>"),
        ("Message ID", f"<code>{message.id}</code>"),
        ("Your user ID", f"<code>{user.id}</code>" if user else "anonymous sender"),
    ]
    argument = ctx.command.arguments.strip()
    if argument:
        if len(argument.split()) != 1:
            return Screen(heading("Identifiers", 3) + body("Use <code>/id @username</code>, <code>/id 12345</code> or reply to a message."))
        try:
            target = await ctx.client.get_users(int(argument) if argument.isdecimal() else argument)
        except Exception:
            raise CommandError("Telegram could not resolve that user.") from None
        rows.extend([("Resolved user", target_link(target)), ("Resolved ID", f"<code>{target.id}</code>")])
    reply = getattr(message, "reply_to_message", None)
    if reply is not None:
        rows.append(("Replied message", f"<code>{reply.id}</code>"))
        author = getattr(reply, "from_user", None) or getattr(reply, "sender_chat", None)
        if author is not None:
            rows.append(("Replied author", f"<code>{author.id}</code>"))
    return Screen(heading("Identifiers", 3) + table(rows))


async def whois(ctx) -> Screen:
    user, _ = await base.resolve_target(ctx.client, ctx.message, ctx.command.arguments.split())
    if user is None:
        user = getattr(ctx.message, "from_user", None)
    if user is None:
        raise CommandError("Reply to a member or pass @username.")
    rows = [
        ("Name", escape(" ".join(filter(None, [getattr(user, "first_name", None), getattr(user, "last_name", None)])))),
        ("ID", f"<code>{user.id}</code>"),
        ("Username", "@" + escape(user.username) if getattr(user, "username", None) else "—"),
        ("Mention", target_link(user)),
    ]
    if getattr(user, "is_bot", False):
        rows.append(("Account", "bot"))
    if base.is_group(ctx.message):
        try:
            member = await ctx.client.get_chat_member(ctx.message.chat.id, user.id)
            rows.append(("Membership", escape(str(getattr(member.status, "value", member.status)))))
        except Exception:
            rows.append(("Membership", "not a member"))
    return Screen(heading("Member profile", 3) + table(rows))


async def ping(ctx) -> Screen:
    started = time.perf_counter()
    await ctx.client.get_me()
    latency = round((time.perf_counter() - started) * 1000)
    uptime = str(timedelta(seconds=max(0, int(time.time() - bot_start_time))))
    return Screen(
        heading("Connection", 3)
        + table([("Telegram round trip", f"{latency} ms"), ("Uptime", uptime)])
        + body("This measures an acknowledged identity request, not voice quality.")
    )


async def source(ctx) -> Screen:
    return Screen(
        heading("Source and credits", 3)
        + body("Videl by Beasgohan-code. Rich UI uses the MIT-licensed Badmunda05 Richgram fork. "
               "Eldian music components keep their original attribution.")
        + table([("Repository", "github.com/Beasgohan-code/Videl0"), ("Bot", "@" + escape(getattr(config, "BOT_USERNAME", "Videl0Bot")))]),
        InlineKeyboardMarkup([[button("Open repository", url=REPOSITORY, style="primary")]]),
    )


COMMANDS = (
    Command("id", identifiers, "Read chat, message and user identifiers", category="tools", block_policy="user"),
    Command("whois", whois, "Show a member's profile and membership", category="tools"),
    Command("ping", ping, "Measure an acknowledged Telegram round trip", category="tools"),
    Command("repo", source, "Source code and third-party credits", category="tools", block_policy="user"),
)
