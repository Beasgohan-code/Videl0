#  Videl © 2026 | Beasgohan-code
"""Welcomes, goodbyes, rules and the join CAPTCHA.

One plugin owns the join path: greeting first, then the optional challenge.
Placeholders available in a welcome: ``{name}``, ``{id}``, ``{title}``.
"""
from __future__ import annotations

import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter
from pyrogram.types import CallbackQuery, CopyTextButton, InlineKeyboardMarkup

from videl import LOGGER, bot
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.bot_ui import button
from videl.utils.captcha import answer_challenge, issue_challenge
from videl.utils.db import is_approved
from videl.utils.premium_emojis import pe
from videl.utils.command_ui import rich_edit, usage

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


async def set_checklist(ctx) -> Screen:
    """Configure up to four concise, safe links shown with new-member greetings."""
    raw = ctx.command.arguments.strip()
    if raw.casefold() == "clear":
        if not base.set_setting(ctx.message.chat.id, "welcome_checklist", []):
            raise CommandError("MongoDB is not connected, so nothing changed.")
        return Screen(heading("Welcome checklist cleared", 3)
                      + body("New members will no longer see checklist buttons."))
    if not raw:
        from videl.utils.welcome_checklist import safe_stored
        current = safe_stored(base.get_setting(ctx.message.chat.id, "welcome_checklist", []))
        lines = [f"{item['label']} → {item['url']}" for item in current]
        return Screen(heading("Welcome checklist links", 3)
                      + (table([("Current links", "<br>".join(escape(line) for line in lines))]) if lines else body("No checklist links are set."))
                      + body("Set up to four links, one per line: <code>/setchecklist Start here | https://example.com/start</code>. All links must use HTTPS.")
                      + body("Use <code>/setchecklist clear</code> to remove them. The checklist appears under the normal welcome message."))
    from videl.utils.welcome_checklist import validate
    try:
        rows = validate(raw)
    except ValueError as error:
        raise CommandError(escape(str(error))) from None
    if not base.set_setting(ctx.message.chat.id, "welcome_checklist", rows):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("Welcome checklist saved", 3)
                  + table([("Buttons", " · ".join(escape(item["label"]) for item in rows))])
                  + body("New members will see these links with the group welcome message."))


async def clear_rules(ctx) -> Screen:
    if not base.set_setting(ctx.message.chat.id, "rules", None):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("✅ Group rules cleared", 3) + body("The group no longer has published rules. Add them again with <code>/setrules</code>."))


async def raidmode(ctx) -> Screen:
    from videl.utils.raid import normalize
    chat_id = ctx.message.chat.id
    parts = ctx.command.arguments.strip().split()
    current = normalize(base.get_setting(chat_id, "raid_mode", {}))
    if not parts:
        return Screen(heading("Raid response mode", 3)
                      + table([("Status", "On" if current["enabled"] else "Off"),
                               ("Detection window", f"{current['window_seconds']} seconds"),
                               ("Join threshold", str(current["join_threshold"])),
                               ("Message threshold", str(current["message_threshold"])),
                               ("Protection duration", f"{current['duration_minutes']} minutes")])
                      + body("Use <code>/raidmode on [window] [joins] [messages] [minutes]</code> or <code>/raidmode off</code>. While active, join verification and anti-flood are temporarily enforced. Admins and approved members remain exempt."))
    if parts[0].casefold() == "off":
        value = {**current, "enabled": False}
    elif parts[0].casefold() == "on" and len(parts) <= 5:
        names = ("window_seconds", "join_threshold", "message_threshold", "duration_minutes")
        value = {**current, "enabled": True}
        for name, raw in zip(names, parts[1:]):
            if not raw.isdecimal():
                raise CommandError("Raid thresholds must be positive whole numbers.")
            value[name] = int(raw)
        value = normalize(value)
    else:
        return Screen(usage("/raidmode on 30 8 20 15", "Set window seconds, join threshold, message threshold and active minutes."))
    if not base.set_setting(chat_id, "raid_mode", value):
        raise CommandError("MongoDB is not connected, so nothing changed.")
    return Screen(heading("✅ Raid response settings saved", 3)
                  + table([("Status", "On" if value["enabled"] else "Off"),
                           ("Window", f"{value['window_seconds']} seconds"),
                           ("Join threshold", str(value["join_threshold"])),
                           ("Message threshold", str(value["message_threshold"])),
                           ("Duration", f"{value['duration_minutes']} minutes")]))


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


def greeting_status_screen(chat_id: int) -> Screen:
    states = {
        "welcome_enabled": bool(base.get_setting(chat_id, "welcome_enabled", True)),
        "goodbye_enabled": bool(base.get_setting(chat_id, "goodbye_enabled", False)),
        "captcha_enabled": bool(base.get_setting(chat_id, "captcha_enabled", False)),
    }
    rows = [
        ("Welcome messages", (pe("check") + " On") if states["welcome_enabled"] else (pe("cross") + " Off")),
        ("Goodbye messages", (pe("check") + " On") if states["goodbye_enabled"] else (pe("cross") + " Off")),
        ("Join verification", (pe("check") + " On") if states["captcha_enabled"] else (pe("cross") + " Off")),
        ("Group rules", (pe("check") + " Published") if base.get_setting(chat_id, "rules") else (pe("cross") + " Not set")),
    ]
    controls = [
        button("Welcome off" if states["welcome_enabled"] else "Welcome on",
               callback_data=f"mgmt_greeting:welcome_enabled:{0 if states['welcome_enabled'] else 1}",
               style="success" if states["welcome_enabled"] else "default"),
        button("Goodbye off" if states["goodbye_enabled"] else "Goodbye on",
               callback_data=f"mgmt_greeting:goodbye_enabled:{0 if states['goodbye_enabled'] else 1}",
               style="success" if states["goodbye_enabled"] else "default"),
        button("Captcha off" if states["captcha_enabled"] else "Captcha on",
               callback_data=f"mgmt_greeting:captcha_enabled:{0 if states['captcha_enabled'] else 1}",
               style="success" if states["captcha_enabled"] else "default"),
        button("Copy /setrules", copy_text=CopyTextButton(text="/setrules ")),
    ]
    keyboard = InlineKeyboardMarkup([controls[:2], controls[2:]])
    return Screen(
        heading("👋 Greetings & rules status", 3)
        + table(rows)
        + body("Use the buttons to toggle welcome, goodbye, and join verification. Each change checks current admin status."),
        keyboard,
    )


async def greeting_status(ctx) -> Screen:
    return greeting_status_screen(ctx.message.chat.id)


@bot.on_callback_query(filters.regex(r"^mgmt_greeting:"))
async def greeting_toggle_callback(client, query: CallbackQuery) -> None:
    message = getattr(query, "message", None)
    if message is None or base.chat_kind(message) not in {"group", "supergroup"}:
        await query.answer("Open greetings settings in the group.", show_alert=True)
        return
    parts = (query.data or "").split(":")
    allowed = {"welcome_enabled", "goodbye_enabled", "captcha_enabled"}
    if len(parts) != 3 or parts[1] not in allowed or parts[2] not in {"0", "1"}:
        await query.answer("This greetings action is invalid.", show_alert=True)
        return
    chat_id = message.chat.id
    actor_id = getattr(getattr(query, "from_user", None), "id", 0)
    try:
        member = await client.get_chat_member(chat_id, actor_id)
    except Exception:
        await query.answer("I couldn’t verify your current admin status.", show_alert=True)
        return
    if getattr(member, "status", None) not in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}:
        await query.answer("A current group admin is required to change greetings.", show_alert=True)
        return
    enabled = parts[2] == "1"
    if not base.set_setting(chat_id, parts[1], enabled):
        await query.answer("The settings database is unavailable; nothing changed.", show_alert=True)
        return
    await query.answer("Setting updated")
    screen = greeting_status_screen(chat_id)
    await rich_edit(message, screen.html, reply_markup=screen.keyboard)

async def _check_lookalike(chat_id: int, member) -> None:
    """Alert only; resemblance is never grounds for restriction or removal."""
    try:
        admins = []
        async for entry in bot.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS, limit=100):
            candidate = getattr(entry, "user", None)
            if candidate is not None:
                admins.append(candidate)
        from videl.utils.identity_signals import lookalike
        match = lookalike(member, admins)
        if match:
            from videl.utils.db import get_db
            from videl.utils.rule_effectiveness import record as record_rule
            await asyncio.to_thread(record_rule, get_db(), chat_id, "impersonation")
            incoming = " ".join(filter(None, [getattr(member, "first_name", ""), getattr(member, "last_name", "")]))[:80]
            await bot.send_message(chat_id,
                f"⚠️ Possible name impersonation: new member {incoming or 'unknown'} resembles an admin ({match['reference']}, {match['field']}). This is only a warning; please verify manually.")
    except Exception:
        LOGGER.debug("Impersonation similarity check unavailable", exc_info=True)


@bot.on_message(filters.new_chat_members, group=5)
async def welcome_handler(_, message) -> None:
    me = await bot.get_me()
    from videl.utils.onboarding import record as record_onboarding
    for member in message.new_chat_members:
        if member.id == me.id:
            continue
        from videl.utils.db import get_db
        from videl.utils.maintenance import is_paused
        maintenance_db = get_db()
        protection_paused = is_paused(maintenance_db, message.chat.id, "protection")
        onboarding_paused = is_paused(maintenance_db, message.chat.id, "onboarding")
        raid_active = False
        if not getattr(member, "is_bot", False):
            record_onboarding(message.chat.id, "joins")
            if not protection_paused:
                await _check_lookalike(message.chat.id, member)
                from videl.utils.raid import record as record_raid
                raid_config = base.get_setting(message.chat.id, "raid_mode", {})
                raid_result = record_raid(message.chat.id, "joins", raid_config)
                raid_active = raid_result["active"]
                if raid_result["started"]:
                    from videl.utils.rule_effectiveness import record as record_rule
                    await asyncio.to_thread(record_rule, maintenance_db, message.chat.id, "raid")
                    try:
                        await bot.send_message(message.chat.id, "⚠️ Temporary raid protections are active. New members may need to complete join verification.")
                    except Exception:
                        LOGGER.debug("Raid-mode announcement failed", exc_info=True)
        if not onboarding_paused and base.get_setting(message.chat.id, "welcome_enabled", True):
            template = base.get_setting(message.chat.id, "welcome_message", DEFAULT_WELCOME)
            from videl.utils.welcome_checklist import safe_stored
            links = safe_stored(base.get_setting(message.chat.id, "welcome_checklist", []))
            safe_buttons = [button(item["label"], url=item["url"]) for item in links]
            from videl.utils.member_faq import normalize as normalize_faq
            faq_items = normalize_faq(base.get_setting(message.chat.id, "welcome_faq", []))
            checklist_rows = [[item] for item in safe_buttons]
            if faq_items:
                checklist_rows.append([button("New-member FAQ", callback_data=f"faq:open:{message.chat.id}")])
            markup = InlineKeyboardMarkup(checklist_rows) if checklist_rows else None
            try:
                await bot.send_message(message.chat.id, _render(template, member, message.chat), reply_markup=markup)
            except Exception:
                LOGGER.debug("Welcome delivery failed", exc_info=True)
        if (
            not getattr(member, "is_bot", False)
            and not onboarding_paused
            and (base.get_setting(message.chat.id, "captcha_enabled", False) or raid_active)
            and not is_approved(message.chat.id, member.id)
        ):
            try:
                established = await issue_challenge(message.chat.id, member.id, getattr(member, "first_name", None) or "New member")
                if established:
                    record_onboarding(message.chat.id, "challenged")
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
    Command("raidmode", raidmode, "Configure temporary join and message raid protection", category="manage", policy="admin"),
    Command("setrules", set_rules, "Publish the group rules", category="manage", policy="admin"),
    Command("setchecklist", set_checklist, "Add HTTPS links to the new-member welcome checklist", category="manage", policy="admin"),
    Command("rules", rules, "Show the group rules", category="manage", policy="group"),
    Command("clearrules", clear_rules, "Remove the published rules", category="manage", policy="admin"),
    Command("greetings", greeting_status, "Show greeting and captcha settings", category="manage", policy="group"),
)
