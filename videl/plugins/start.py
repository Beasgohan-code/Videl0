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
from videl.utils.rich_ui import rich_details, rich_img
from videl.utils.premium_emojis import pe

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
    return base.studio_url()


def _welcome_art() -> str:
    """Our own hosted welcome artwork, served alongside the web studio."""
    return rich_img(studio_url() + "/videl-music-hero.png")


def _telegram_link(value: str) -> str | None:
    """Normalize configured public Telegram destinations for inline URL buttons."""
    value = str(value or "").strip()
    if value.startswith("@"):
        value = "https://t.me/" + value[1:]
    elif value.startswith("t.me/"):
        value = "https://" + value
    if not value.startswith("https://"):
        return None
    from urllib.parse import urlsplit
    parsed = urlsplit(value)
    if parsed.netloc not in {"t.me", "telegram.me"} or not parsed.path.strip("/"):
        return None
    return value


def private_keyboard(owner: bool, username: str = "") -> InlineKeyboardMarkup:
    root = studio_url()
    rows: list[list] = []
    first = [button("Music & playlists", callback_data="help:music", style="primary", icon="music")]
    if username:
        first.append(button("Add to group", url=f"https://t.me/{username}?startgroup=true", icon="shield"))
    rows.append(first)
    rows.append([button("Help center", callback_data="help:home", icon="info"), button("Browse commands", callback_data="cmds:all:0", icon="search")])
    rows.append([button("Group setup", callback_data="v2:setup", icon="ios_gear"), button("About & credits", callback_data="help:about", icon="star")])
    community_links = []
    support_url = _telegram_link(getattr(config, "SUPPORT_CHAT", ""))
    updates_url = _telegram_link(getattr(config, "SUPPORT_CHANNEL", ""))
    if support_url:
        community_links.append(button("Support", url=support_url, icon="dash"))
    if updates_url:
        community_links.append(button("Updates", url=updates_url, icon="spark"))
    if community_links:
        rows.append(community_links)
    rows.append([button("Browse the full guide", url=root + "/?tab=guide", icon="globe")])
    rows.append([button("Open Post Studio", web_app=WebAppInfo(url=root), style="primary", icon="crown")])
    if owner:
        rows.insert(0, [button("Owner workspace", web_app=WebAppInfo(url=root + "/?tab=settings"), style="primary"),
                        button("Owner commands", callback_data="cmds:owner:0")])
    return InlineKeyboardMarkup(rows)


def group_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [button("Check group setup", callback_data="v2:setup", style="primary", icon="ios_gear"), button("Help center", callback_data="help:home", icon="info")],
        [button("Group safety", callback_data="help:manage", icon="shield"), button("Music", callback_data="help:music", icon="music")],
        [button("Browse commands", callback_data="cmds:all:0", icon="search"), button("Open Post Studio", url=studio_url(), icon="crown")],
    ]
    support_url = _telegram_link(getattr(config, "SUPPORT_CHAT", ""))
    updates_url = _telegram_link(getattr(config, "SUPPORT_CHANNEL", ""))
    links = []
    if support_url:
        links.append(button("Support", url=support_url, icon="dash"))
    if updates_url:
        links.append(button("Updates", url=updates_url, icon="spark"))
    if links:
        rows.append(links)
    return InlineKeyboardMarkup(rows)


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
    intro = (f"Welcome, {escape(name)}! Your quick-start guide to music, group tools and creative tools."
             if private else "I’m ready to help this group. Pick a quick start below or open Help for the full guide.")
    steps = [
        (pe("music") + " Music", "<code>/play song or link</code> in a group voice chat"),
        (pe("shield") + " Group safety", "Group setup button checks access · <code>/lock links</code> protects links"),
        (pe("spark") + " Community", "<code>/welcome on</code> · <code>/rules</code> · <code>/save name text</code>"),
        (pe("ios_add") + " Admin tools", "<code>/tagall [message]</code> mentions up to 50 members"),
        (pe("ios_controls") + " More tools", "Try <code>/poll</code>, <code>/remind 10m call</code> or browse commands"),
    ]
    private_note = body("Music plays in a group voice chat. Add Videl to a group to start listening together.") if private else body(
        "Start a voice chat, then send <code>/play</code> with a song name or link.")
    title = "🎵 Vɪᴅᴇʟ Sᴛᴜᴅɪᴏ · Qᴜɪᴄᴋ sᴛᴀʀᴛ" if private else "🛡 Vɪᴅᴇʟ Sᴛᴜᴅɪᴏ · Gʀᴏᴜᴘ ɢᴜɪᴅᴇ"
    overview = rich_details("✨ Quick-start guide", table(steps), open=True)
    return heading(title, 2) + body(intro) + private_note + overview


async def render_start(user, *, private: bool, owner: bool, username: str = "") -> Screen:
    """Build the start card for a user without needing a full command context."""
    if private and owner:
        caption = await asyncio.to_thread(owner_caption, getattr(user, "first_name", "owner"))
        return Screen(_welcome_art() + caption, private_keyboard(True))
    name = getattr(user, "first_name", "there")
    if not private:
        return Screen(_welcome_art() + member_caption(name, private=False), group_keyboard())
    return Screen(_welcome_art() + member_caption(name, private=True), private_keyboard(False, username))


async def start(ctx) -> Screen:
    user = getattr(ctx.message, "from_user", None)
    arguments = ctx.command.arguments.casefold().strip()
    if arguments in SECTIONS:
        from videl.plugins.help import render_section

        text, keyboard = render_section(SECTIONS[arguments], owner=ctx.owner)
        return Screen(text, keyboard)
    private = base.is_private(ctx.message)
    username = getattr(getattr(ctx.client, "me", None), "username", "")
    return await render_start(user, private=private, owner=ctx.owner, username=username)


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
