#  Videl © 2026 | Beasgohan-code
"""``/start`` and ``/about`` — the first screen of the bot.

Private chats get the studio entry point, groups get a short readiness card and
the owner gets live totals. Deep links (``/start help``, ``/start play``) open
the matching help page instead of a dead end.
"""
from __future__ import annotations

import asyncio
import time
from datetime import timedelta

from pyrogram.types import InlineKeyboardMarkup, WebAppInfo

import config
from videl import bot_start_time
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, small_caps, table
from videl.utils.bot_ui import button
from videl.utils.db import read_live_totals

SECTIONS = {
    "help": "home",
    "music": "music",
    "play": "music",
    "manage": "manage",
    "moderate": "manage",
    "protect": "manage",
    "tools": "tools",
    "settings": "tools",
}


def studio_url() -> str:
    from urllib.parse import urlsplit

    value = (getattr(config, "WEBAPP_URL", "") or "https://videl-studio.vercel.app").rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password:
        return value
    return "https://videl-studio.vercel.app"


def private_keyboard(owner: bool, username: str = "") -> InlineKeyboardMarkup:
    root = studio_url()
    rows: list[list] = []
    first = [button("Play music", callback_data="help:music", style="primary")]
    if username:
        first.append(button("Add to group", url=f"https://t.me/{username}?startgroup=true"))
    rows.append(first)
    rows.append([button("Help center", callback_data="help:home"), button("All commands", callback_data="cmds:all:0")])
    rows.append([button("Group setup", callback_data="v2:setup"), button("Source & credits", callback_data="help:about")])
    rows.append([button("Command guide on the web", url=root + "/?tab=guide")])
    rows.append([button("Open Post Studio", web_app=WebAppInfo(url=root), style="primary")])
    if owner:
        rows.insert(0, [button("Owner workspace", web_app=WebAppInfo(url=root + "/?tab=settings"), style="primary"),
                        button("Owner commands", callback_data="cmds:owner:0")])
    return InlineKeyboardMarkup(rows)


def group_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [button("Setup check", callback_data="v2:setup", style="primary"), button("Help center", callback_data="help:home")],
        [button("Moderation", callback_data="help:manage"), button("All commands", callback_data="cmds:all:0")],
        [button("Open Post Studio", url=studio_url())],
    ])


def owner_caption(name: str) -> str:
    try:
        totals = read_live_totals()
        rows = [("Groups", totals["chats"]), ("Users", totals["users"]), ("Streams", totals["plays"])]
    except Exception:
        rows = [("Database totals", "unavailable")]
    uptime = str(timedelta(seconds=max(0, int(time.time() - bot_start_time))))
    rows.append(("Uptime", uptime))
    return (heading("Videl owner console", 2)
            + body(f"Welcome back, {escape(name)}. Your controls stay private to this chat.")
            + table(rows))


def member_caption(name: str, private: bool) -> str:
    intro = (f"Hey {escape(name)}. I run music, moderation, saved notes and the full post studio."
             if private else "I am awake and connected to this group.")
    steps = [
        ("Music", "<code>/play</code> a song or link inside a voice chat"),
        ("Protection", "<code>/setup</code> then <code>/lock links</code>"),
        ("Commands", "<code>/help</code> or <code>/commands keyword</code>"),
    ]
    private_note = body("Music plays in your group voice chat, not in this private chat.") if private else body(
        "Start a voice chat, then send <code>/play</code> with a song name or link.")
    return heading("Videl Studio", 2) + body(intro) + private_note + table(steps)


async def start(ctx) -> Screen:
    user = getattr(ctx.message, "from_user", None)
    arguments = ctx.command.arguments.casefold().strip()
    if arguments in SECTIONS:
        from videl.plugins.help import render_section

        text, keyboard = render_section(SECTIONS[arguments], owner=ctx.owner)
        return Screen(text, keyboard)
    private = base.is_private(ctx.message)
    if private and ctx.owner:
        caption = await asyncio.to_thread(owner_caption, getattr(user, "first_name", "owner"))
        return Screen(caption, private_keyboard(True))
    name = getattr(user, "first_name", "there")
    if not private:
        return Screen(member_caption(name, private=False), group_keyboard())
    return Screen(member_caption(name, private=True), private_keyboard(False, getattr(getattr(ctx.client, "me", None), "username", "")))


async def about(ctx) -> Screen:
    configured = [
        ("Runtime", "Python + Kurigram"),
        ("Rendering", "Richgram (MIT)"),
        ("Storage", "MongoDB only"),
        ("Music", "Eldian API (attributed)"),
        ("Web studio", escape(studio_url())),
    ]
    return Screen(
        heading("About Videl", 2)
        + body("Videl is a bot studio for Telegram groups: voice-chat music, moderation, saved notes and a web designer for posts.")
        + table(configured)
        + body("No AI features, no paid Stars actions, and every credential stays on the server."),
        InlineKeyboardMarkup([
            [button("Source & licenses", callback_data="help:about", style="primary")],
            [button("Back to start", callback_data="help:start")],
        ]),
    )


COMMANDS = (
    Command("start", start, "Open the studio, the group card or the owner console"),
    Command("about", about, "Policies, stack and credits"),
)
