#  Videl © 2026 | Beasgohan-code
"""``/help`` and ``/commands`` — a help center built from the live registry.

Every row is generated from the commands that are actually registered and
installed, so the help center cannot drift away from the running bot.
"""
from __future__ import annotations

from pyrogram.types import InlineKeyboardMarkup

from videl.app.router import Command, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.bot_ui import button
from videl.utils.command_catalog import directory, visible_commands
from videl.utils.rich_ui import rich_esc

SECTION_META = {
    "music": ("Music", "Voice-chat playback, queues and playlists", "music"),
    "manage": ("Group management", "Moderation, locks, notes, welcomes and rules", "manage"),
    "tools": ("Telegram tools", "Polls, identifiers, reminders and utilities", "tools"),
    "owner": ("Owner operations", "Private diagnostics for the bot owner", "owner"),
}
SECTIONS = tuple(SECTION_META)
PAGE_SIZE = 8

ABOUT_TEXT = (
    "Videl is built by Beasgohan-code and keeps the credits of every upstream project."
)


def _command_rows(section: str, owner: bool, page: int):
    category = SECTION_META[section][2]
    entries = visible_commands(owner=owner, category=category)
    pages = max(1, (len(entries) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    window = entries[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    rows = [(f"<code>/{rich_esc(entry['name'])}</code>", rich_esc(entry["summary"])) for entry in window]
    return rows, page, pages, len(entries)


def render_section(section: str = "home", page: int = 0, *, owner: bool = False):
    """Return ``(html, keyboard)`` for a help page; used by /help and callbacks."""
    section = (section or "home").casefold()
    if section == "about":
        text = (
            heading("Source and credits", 2)
            + body("Videl by Beasgohan-code. Rich rendering uses the MIT-licensed Badmunda05 Richgram fork; "
                   "Eldian provides the music API and keeps its attribution.")
            + table([("Repository", "github.com/Beasgohan-code/Videl0"),
                     ("License", "MIT, upstream notices preserved"),
                     ("Data", "MongoDB only — nothing is sold or shared")])
        )
        keyboard = InlineKeyboardMarkup([
            [button("Open repository", url="https://github.com/Beasgohan-code/Videl0", style="primary")],
            [button("Full command list", url=base.guide_url())],
            [button("Back", callback_data="help:home")],
        ])
        return text, keyboard

    if section in SECTION_META:
        label, description, _ = SECTION_META[section]
        rows, page, pages, total = _command_rows(section, owner, page)
        text = heading(label, 2) + body(description)
        text += table(rows) if rows else body("No commands in this section yet.")
        text += body(f"{total} commands · page {page + 1} of {pages}")
        text += body("Administrative commands check live Telegram permissions when you run them.")
        navigation = []
        if page:
            navigation.append(button("Previous", callback_data=f"help:{section}:{page - 1}"))
        if page + 1 < pages:
            navigation.append(button("Next", callback_data=f"help:{section}:{page + 1}"))
        rows_keyboard = ([navigation] if navigation else [])
        rows_keyboard.append([button("Music", callback_data="help:music"), button("Groups", callback_data="help:manage")])
        rows_keyboard.append([button("Tools", callback_data="help:tools"), button("Home", callback_data="help:home")])
        if owner:
            rows_keyboard.append([button("Owner operations", callback_data="help:owner:0", style="primary")])
        return text, InlineKeyboardMarkup(rows_keyboard)

    # Home
    counts = {name: len(visible_commands(owner=owner, category=meta[2])) for name, meta in SECTION_META.items()}
    text = (
        heading("Help center", 2)
        + body("Everything Videl can do, generated from the live command registry. "
               "Pick a section or search by keyword.")
        + table([
            ("Start here", "<code>/start</code> · <code>/help</code> · <code>/commands</code>"),
            ("Play music", "<code>/play</code> a song or link inside a voice chat"),
            ("Protect a group", "<code>/lock links</code> · <code>/antispam</code> · <code>/welcome on</code>"),
            ("Stay organised", "<code>/save name text</code> · <code>/remind 10m call</code>"),
        ])
        + table([
            ("Music", f"{counts['music']} commands · playback, queues, playlists"),
            ("Groups", f"{counts['manage']} commands · moderation, locks, notes, welcomes"),
            ("Tools", f"{counts['tools']} commands · polls, ids, reminders, AFK"),
            ("Owner", (f"{counts['owner']} commands · diagnostics" if owner else "Hidden until you sign in as owner")),
        ])
        + body("Search with <code>/commands keyword</code>. Permissions are checked when a command runs; "
               "this page never grants access.")
    )
    keyboard = [
        [button("Music", callback_data="help:music", style="primary"), button("Groups", callback_data="help:manage")],
        [button("Tools", callback_data="help:tools"), button("All commands", callback_data="cmds:all:0")],
        [button("Full command list", url=base.guide_url())],
        [button("Source & credits", callback_data="help:about")],
    ]
    if owner:
        keyboard.append([button("Owner operations", callback_data="help:owner:0", style="primary")])
    return text, InlineKeyboardMarkup(keyboard)


def search(query: str, *, owner: bool = False):
    matches = visible_commands(owner=owner, query=query)[:20]
    text = heading("Search results", 2) + body(f"Matches for <code>{escape(query)}</code>")
    if matches:
        text += table([(f"<code>/{rich_esc(item['name'])}</code>", rich_esc(item["summary"])) for item in matches])
    else:
        text += body("Nothing matched. Try /commands music or a shorter keyword.")
    return text, InlineKeyboardMarkup([
        [button("Music", callback_data="help:music"), button("Groups", callback_data="help:manage")],
        [button("Home", callback_data="help:home")],
    ])


async def help_command(ctx) -> Screen:
    argument = ctx.command.arguments.strip()
    if not argument:
        text, keyboard = render_section("home", owner=ctx.owner)
        return Screen(text, keyboard)
    key = argument.casefold()
    if key in SECTION_META or key in {"home", "about"}:
        text, keyboard = render_section(key, owner=ctx.owner)
        return Screen(text, keyboard)
    text, keyboard = search(argument, owner=ctx.owner)
    return Screen(text, keyboard)


async def directory_command(ctx) -> Screen:
    query = ctx.command.arguments.casefold().strip()
    if query in {"music", "manage", "tools", "owner", "all"}:
        text, keyboard = directory(query, 0, owner=ctx.owner)
        return Screen(text, keyboard)
    if query:
        text, keyboard = search(query, owner=ctx.owner)
        return Screen(text, keyboard)
    text, keyboard = directory("all", 0, owner=ctx.owner)
    return Screen(text, keyboard)


COMMANDS = (
    Command("help", help_command, "Open the help center or a named section"),
    Command("commands", directory_command, "Search or browse every installed command"),
)
