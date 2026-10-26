#  Videl © 2026 | Beasgohan-code
"""Welcomes, goodbyes, rules and the join CAPTCHA.

One plugin owns the join path: greeting first, then the optional challenge.
Placeholders available in a welcome: ``{name}``, ``{id}``, ``{title}``.
"""
from __future__ import annotations

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup

from videl import LOGGER, bot
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.bot_ui import button
from videl.utils.captcha import answer_challenge, issue_challenge
from videl.utils.db import is_approved
from videl.utils.premium_emojis import pe

DEFAULT_WELCOME = "Welcome {name} to {title}!"
DEFAULT_GOODBYE = "Goodbye {name}."


def _render(template: str, member, chat) -> str:
    values = {
        "name": escape(getattr(member, "first_name", "there")),
        "id": int(getattr(member, "id", 0)),
        "title": escape(getattr(chat, "title", "the group")),
        "mention": f'<a href="tg://user?id={int(getattr(member, "id", 0))}">{escape(getattr(member, "first_name", "there"))}</a>',
    }
    try:
        return template.format(**values)
    except Exception:
        return template


async def set_welcome(ctx) -> Screen:
    text = ctx.command.arguments.strip()
    if not text:
        return Screen(
            heading("👋 Set the welcome message", 3)
            + body("Example: <code>/setwelcome Welcome {name} to {title}!</code>")
            + body("Available placeholders: <code>{name}</code>, <code>{id}</code>, <code>{title}</code> and <code>{mention}</code>.")
        )
    if not base.set_setting(ctx.message.chat.id, "welcome_message", text[:1000]):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(
        heading("✅ Welcome message saved", 3)
        + table([("Preview", escape(text[:400]))])
        + body("Placeholders: <code>{name}</code>, <code>{id}</code>, <code>{title}</code> and <code>{mention}</code>.")
        + body("Turn delivery on or off with <code>/welcome on</code> or <code>/welcome off</code>.")
    )


async def toggle_welcome(ctx) -> Screen:
    argument = ctx.command.arguments.strip().casefold()
    if argument not in {"on", "off"}:
        return Screen(heading("Welcome messages", 3) + body("Usage: <code>/welcome on</code> or <code>/welcome off</code>."))
    if not base.set_setting(ctx.message.chat.id, "welcome_enabled", argument == "on"):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(
        heading("✅ Welcome setting updated", 3)
        + table([("New-member messages", (pe("check") + " On") if argument == "on" else (pe("cross") + " Off"))])
        + body("New members see the saved welcome text when they join." if argument == "on" else "The saved message stays in settings and can be re-enabled any time.")
    )


async def set_goodbye(ctx) -> Screen:
    text = ctx.command.arguments.strip()
    if not text:
        return Screen(
            heading("👋 Set the goodbye message", 3)
            + body("Example: <code>/setgoodbye Goodbye {name}.</code>")
            + body("Use <code>{name}</code> for the departing member’s name; the message is sent only when goodbye delivery is on.")
        )
    if not base.set_setting(ctx.message.chat.id, "goodbye_message", text[:1000]):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(
        heading("✅ Goodbye message saved", 3)
        + table([("Preview", escape(text[:400]))])
        + body("Use <code>{name}</code>, <code>{id}</code>, <code>{title}</code> or <code>{mention}</code> as a placeholder.")
        + body("Enable or pause delivery with <code>/goodbye on</code> or <code>/goodbye off</code>.")
    )


async def toggle_goodbye(ctx) -> Screen:
    argument = ctx.command.arguments.strip().casefold()
    if argument not in {"on", "off"}:
        return Screen(heading("Goodbye messages", 3) + body("Usage: <code>/goodbye on</code> or <code>/goodbye off</code>."))
    if not base.set_setting(ctx.message.chat.id, "goodbye_enabled", argument == "on"):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(
        heading("✅ Goodbye setting updated", 3)
        + table([("Departing-member messages", (pe("check") + " On") if argument == "on" else (pe("cross") + " Off"))])
        + body("The saved goodbye text will be sent when a member leaves." if argument == "on" else "The saved message remains available and can be re-enabled any time.")
    )


async def set_rules(ctx) -> Screen:
    text = ctx.command.arguments.strip()
    if not text:
        return Screen(heading("📝 Publish group rules", 3) + body("Example: <code>/setrules Be kind. No spam.</code>"))
    if not base.set_setting(ctx.message.chat.id, "rules", text[:2000]):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(
        heading("✅ Group rules published", 3)
        + table([("Preview", escape(text[:400]))])
        + body("Members can read the current rules with <code>/rules</code>.")
        + body("Edit them any time with <code>/setrules</code> or remove them with <code>/clearrules</code>.")
    )


async def rules(ctx) -> Screen:
    text = base.get_setting(ctx.message.chat.id, "rules")
    if not text:
        return Screen(heading("Group rules", 3) + body("No rules saved yet. An admin can add them with <code>/setrules</code>."))
    return Screen(heading("Group rules", 3) + body(escape(text)))


async def clear_rules(ctx) -> Screen:
    if not base.set_setting(ctx.message.chat.id, "rules", None):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("✅ Group rules cleared", 3) + body("The group no longer has published rules. Add them again with <code>/setrules</code>."))


async def toggle_captcha(ctx) -> Screen:
    argument = ctx.command.arguments.strip().casefold()
    if argument not in {"on", "off"}:
        return Screen(
            heading("🛡 Join verification", 3)
            + body("Use <code>/setcaptcha on</code> to enable a challenge for new members, or <code>/setcaptcha off</code> to turn it off.")
            + body("When enabled, new non-approved members must solve a short challenge before they can post.")
        )
    if not base.set_setting(ctx.message.chat.id, "captcha_enabled", argument == "on"):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(
        heading("✅ Join-verification setting updated", 3)
        + table([("New-member challenge", (pe("check") + " On") if argument == "on" else (pe("cross") + " Off"))])
        + body("New non-approved members will be asked to solve a challenge before posting." if argument == "on" else "New members can join without this challenge.")
    )


async def greeting_status(ctx) -> Screen:
    chat_id = ctx.message.chat.id
    rows = [
        ("Welcome messages", (pe("check") + " On") if base.get_setting(chat_id, "welcome_enabled", True) else (pe("cross") + " Off")),
        ("Goodbye messages", (pe("check") + " On") if base.get_setting(chat_id, "goodbye_enabled", False) else (pe("cross") + " Off")),
        ("Join verification", (pe("check") + " On") if base.get_setting(chat_id, "captcha_enabled", False) else (pe("cross") + " Off")),
        ("Group rules", (pe("check") + " Published") if base.get_setting(chat_id, "rules") else (pe("cross") + " Not set")),
    ]
    return Screen(
        heading("👋 Greetings & rules status", 3) + table(rows),
        InlineKeyboardMarkup([[button("Rules", callback_data="help:manage"), button("Locks", callback_data="help:manage")]]),
    )


@bot.on_message(filters.new_chat_members, group=5)
async def welcome_handler(_, message) -> None:
    me = await bot.get_me()
    for member in message.new_chat_members:
        if member.id == me.id:
            continue
        if base.get_setting(message.chat.id, "welcome_enabled", True):
            template = base.get_setting(message.chat.id, "welcome_message", DEFAULT_WELCOME)
            try:
                await bot.send_message(message.chat.id, _render(template, member, message.chat))
            except Exception:
                LOGGER.debug("Welcome delivery failed", exc_info=True)
        if (
            not getattr(member, "is_bot", False)
            and base.get_setting(message.chat.id, "captcha_enabled", False)
            and not is_approved(message.chat.id, member.id)
        ):
            try:
                await issue_challenge(message.chat.id, member.id, getattr(member, "first_name", None) or "New member")
            except Exception:
                LOGGER.debug("Captcha issue failed", exc_info=True)


@bot.on_message(filters.left_chat_member, group=6)
async def goodbye_handler(_, message) -> None:
    member = message.left_chat_member
    if member is None or getattr(member, "is_bot", False):
        return
    if not base.get_setting(message.chat.id, "goodbye_enabled", False):
        return
    template = base.get_setting(message.chat.id, "goodbye_message", DEFAULT_GOODBYE)
    try:
        await bot.send_message(message.chat.id, _render(template, member, message.chat))
    except Exception:
        LOGGER.debug("Goodbye delivery failed", exc_info=True)


@bot.on_callback_query(filters.regex(r"^verify:"))
async def captcha_callback(_, query) -> None:
    await answer_challenge(query)


COMMANDS = (
    Command("setwelcome", set_welcome, "Set the message shown to new members", category="manage", policy="admin"),
    Command("welcome", toggle_welcome, "Turn welcome messages on or off", category="manage", policy="admin"),
    Command("setgoodbye", set_goodbye, "Set the message shown when a member leaves", category="manage", policy="admin"),
    Command("goodbye", toggle_goodbye, "Turn goodbye messages on or off", category="manage", policy="admin"),
    Command("setcaptcha", toggle_captcha, "Require a challenge before new members post", category="manage", policy="admin"),
    Command("setrules", set_rules, "Publish the group rules", category="manage", policy="admin"),
    Command("rules", rules, "Show the group rules", category="manage", policy="group"),
    Command("clearrules", clear_rules, "Remove the published rules", category="manage", policy="admin"),
    Command("greetings", greeting_status, "Show greeting and captcha settings", category="manage", policy="group"),
)
