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
from videl.utils.rich_ui import rich_reply, rich_send

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
            heading("Welcome message", 3)
            + body("Usage: <code>/setwelcome Welcome {name} to {title}!</code>")
            + body("Placeholders: <code>{name}</code>, <code>{id}</code>, <code>{title}</code>, <code>{mention}</code>.")
        )
    if not base.set_setting(ctx.message.chat.id, "welcome_message", text[:1000]):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("Welcome updated", 3) + body(escape(text[:400])))


async def toggle_welcome(ctx) -> Screen:
    argument = ctx.command.arguments.strip().casefold()
    if argument not in {"on", "off"}:
        return Screen(heading("Welcome messages", 3) + body("Usage: <code>/welcome on</code> or <code>/welcome off</code>."))
    if not base.set_setting(ctx.message.chat.id, "welcome_enabled", argument == "on"):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("Welcome messages", 3) + body(f"Now <b>{argument}</b>."))


async def set_goodbye(ctx) -> Screen:
    text = ctx.command.arguments.strip()
    if not text:
        return Screen(heading("Goodbye message", 3) + body("Usage: <code>/setgoodbye Goodbye {name}.</code>"))
    if not base.set_setting(ctx.message.chat.id, "goodbye_message", text[:1000]):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("Goodbye updated", 3) + body(escape(text[:400])))


async def toggle_goodbye(ctx) -> Screen:
    argument = ctx.command.arguments.strip().casefold()
    if argument not in {"on", "off"}:
        return Screen(heading("Goodbye messages", 3) + body("Usage: <code>/goodbye on</code> or <code>/goodbye off</code>."))
    if not base.set_setting(ctx.message.chat.id, "goodbye_enabled", argument == "on"):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("Goodbye messages", 3) + body(f"Now <b>{argument}</b>."))


async def set_rules(ctx) -> Screen:
    text = ctx.command.arguments.strip()
    if not text:
        return Screen(heading("Group rules", 3) + body("Usage: <code>/setrules Be kind. No spam.</code>"))
    if not base.set_setting(ctx.message.chat.id, "rules", text[:2000]):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("Rules saved", 3) + body("Members can read them with <code>/rules</code>."))


async def rules(ctx) -> Screen:
    text = base.get_setting(ctx.message.chat.id, "rules")
    if not text:
        return Screen(heading("Group rules", 3) + body("No rules saved yet. An admin can add them with <code>/setrules</code>."))
    return Screen(heading("Group rules", 3) + body(escape(text)))


async def clear_rules(ctx) -> Screen:
    if not base.set_setting(ctx.message.chat.id, "rules", None):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("Rules cleared", 3) + body("No rules are published now."))


async def toggle_captcha(ctx) -> Screen:
    argument = ctx.command.arguments.strip().casefold()
    if argument not in {"on", "off"}:
        return Screen(
            heading("Join captcha", 3)
            + body("Usage: <code>/setcaptcha on</code> or <code>/setcaptcha off</code>.")
            + body("New members must solve a short challenge before they can post.")
        )
    if not base.set_setting(ctx.message.chat.id, "captcha_enabled", argument == "on"):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("Join captcha", 3) + body(f"Now <b>{argument}</b>."))


async def greeting_status(ctx) -> Screen:
    chat_id = ctx.message.chat.id
    rows = [
        ("Welcome", "on" if base.get_setting(chat_id, "welcome_enabled", True) else "off"),
        ("Goodbye", "on" if base.get_setting(chat_id, "goodbye_enabled", False) else "off"),
        ("Captcha", "on" if base.get_setting(chat_id, "captcha_enabled", False) else "off"),
        ("Rules", "published" if base.get_setting(chat_id, "rules") else "not set"),
    ]
    return Screen(
        heading("Greetings", 3) + table(rows),
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
