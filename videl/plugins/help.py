#  Videl © 2026 | Beasgohan-code
"""``/help`` and ``/commands`` — a help center built from the live registry.

Every row is generated from the commands that are actually registered and
installed, so the help center cannot drift away from the running bot.
"""
from __future__ import annotations

from videl.app.router import Command, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.command_catalog import directory, visible_commands
from videl.utils.rich_ui import (
    rich_esc, rich_footer, rich_hr, rich_img, rich_button, rich_button_row,
)
from videl.utils.premium_emojis import pe

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
        actions = (
            rich_button_row(
                rich_button("Open repository", url="https://github.com/Beasgohan-code/Videl0", style="primary"),
                rich_button("Full command list", url=base.guide_url()),
            )
            + rich_button_row(rich_button("Back to help", callback_data="help:home"))
        )
        return text + actions, None

    if section in SECTION_META:
        label, description, _ = SECTION_META[section]
        rows, page, pages, total = _command_rows(section, owner, page)
        text = (heading(label, 2) + body(description) + rich_hr()
                + heading("Commands", 3))
        text += table(rows) if rows else body("No commands in this section yet.")
        text += rich_footer(f"{total} commands · page {page + 1} of {pages}")
        text += body("Admin actions check live Telegram permissions when you run them.")
        actions = ""
        if page or page + 1 < pages:
            page_buttons = []
            if page:
                page_buttons.append(rich_button("Previous", callback_data=f"help:{section}:{page - 1}"))
            if page + 1 < pages:
                page_buttons.append(rich_button("Next", callback_data=f"help:{section}:{page + 1}", style="primary"))
            actions += rich_button_row(*page_buttons)
        actions += rich_button_row(
            rich_button("Music", callback_data="help:music", style="primary" if section == "music" else None),
            rich_button("Groups", callback_data="help:manage", style="primary" if section == "manage" else None),
        )
        actions += rich_button_row(
            rich_button("Tools", callback_data="help:tools", style="primary" if section == "tools" else None),
            rich_button("Help home", callback_data="help:home"),
        )
        if owner:
            actions += rich_button_row(rich_button("Owner operations", callback_data="help:owner:0", style="primary"))
        return text + actions, None

    # Home
    counts = {name: len(visible_commands(owner=owner, category=meta[2])) for name, meta in SECTION_META.items()}
    text = (
        heading("Videl · Help center", 2)
        + rich_img(base.studio_url() + "/videl-music-hero.png")
        + body("Find the right command fast. This guide follows the commands installed in the bot.")
        + rich_hr()
        + heading("Quick starts", 3)
        + table([
            (pe("music") + " Play", "<code>/play song name</code> · start music in a group voice chat"),
            (pe("shield") + " Protect", "Group setup button checks access · <code>/lock links</code> blocks links"),
            (pe("spark") + " Welcome", "<code>/welcome on</code> · <code>/rules</code> · <code>/save name text</code>"),
            (pe("ios_add") + " Create", "<code>/poll</code> · <code>/font bold text</code> · <code>/remind 10m call</code>"),
        ])
        + rich_hr()
        + heading("Browse a section", 3)
        + table([
            (pe("music") + " Music", f"{counts['music']} commands · playback, queues and playlists"),
            (pe("shield") + " Groups", f"{counts['manage']} commands · moderation, locks, notes and welcomes"),
            (pe("ios_controls") + " Tools", f"{counts['tools']} commands · polls, IDs, reminders and AFK"),
            (pe("key") + " Owner", (f"{counts['owner']} private commands" if owner else "Private owner controls")),
        ])
        + rich_footer("Prefixes: <code>/ ! ? &amp; . # ~ $ +</code> · search with <code>/commands keyword</code>")
        + body("Permission checks happen when an action runs. Browsing this guide never grants access.")
    )
    actions = (
        rich_button_row(
            rich_button("Music", callback_data="help:music", style="primary"),
            rich_button("Group tools", callback_data="help:manage"),
        )
        + rich_button_row(
            rich_button("Telegram tools", callback_data="help:tools"),
            rich_button("All commands", callback_data="cmds:all:0"),
        )
        + rich_button_row(
            rich_button("Full command list", url=base.guide_url()),
            rich_button("Source & credits", callback_data="help:about"),
        )
    )
    if owner:
        actions += rich_button_row(rich_button("Owner operations", callback_data="help:owner:0", style="primary"))
    return text + actions, None


def search(query: str, *, owner: bool = False):
    matches = visible_commands(owner=owner, query=query)[:20]
    text = heading("🔎 Command search", 2) + body(f"Matches for <code>{escape(query)}</code>")
    if matches:
        text += table([(f"<code>/{rich_esc(item['name'])}</code>", rich_esc(item["summary"])) for item in matches])
    else:
        text += body("Nothing matched. Try /commands music or a shorter keyword.")
    actions = (
        rich_button_row(
            rich_button("Music", callback_data="help:music"),
            rich_button("Groups", callback_data="help:manage"),
            rich_button("Tools", callback_data="help:tools"),
        )
        + rich_button_row(rich_button("Help home", callback_data="help:home"))
    )
    return text + actions, None


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
