#  Videl © 2026 | Beasgohan-code
"""Welcomes, goodbyes, rules and the join CAPTCHA.

One plugin owns the join path: greeting first, then the optional challenge.
Placeholders available in a welcome: ``{name}``, ``{id}``, ``{title}``.
"""
from __future__ import annotations

import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter
from pyrogram.types import CallbackQuery, CopyTextButton, ForceReply, InlineKeyboardMarkup

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


_SUPPORTED_WELCOME_FIELDS = {"name", "id", "title", "mention"}


def validate_welcome_template(template: str) -> str:
    """Accept only the placeholders supported by the existing welcome renderer."""
    import string
    if not isinstance(template, str):
        raise ValueError("Send welcome text as a message.")
    template = template.strip()
    if not template:
        raise ValueError("Welcome text cannot be empty.")
    if len(template) > 1000:
        raise ValueError("Welcome text must be 1,000 characters or fewer.")
    try:
        for _, field_name, format_spec, conversion in string.Formatter().parse(template):
            if field_name is None:
                continue
            if field_name not in _SUPPORTED_WELCOME_FIELDS or format_spec or conversion:
                raise ValueError(f"Unsupported placeholder. Use only {{name}}, {{id}}, {{title}} or {{mention}}.")
    except ValueError as error:
        if "Unsupported placeholder" in str(error):
            raise
        raise ValueError("Welcome text has an unmatched brace; use double braces for literal braces.") from None
    return template


def preview_welcome_template(template: str, chat) -> str:
    """Render with the existing delivery formatter and safe sample values."""
    from types import SimpleNamespace
    return _render(validate_welcome_template(template), SimpleNamespace(first_name="Alex", id=12345), chat)


from videl.utils.interactive_settings import Step, engine as _interaction_engine

_WELCOME_MEDIA_TYPES = ("photo", "video", "animation", "document", "audio", "voice")
_WELCOME_WORKFLOWS = {"welcome_text", "welcome_media", "welcome_buttons"}


def _welcome_markup(chat_id: int, links=None):
    from videl.utils.welcome_checklist import safe_stored
    current = safe_stored(base.get_setting(chat_id, "welcome_checklist", []) if links is None else links)
    from videl.utils.member_faq import normalize as normalize_faq
    faq_items = normalize_faq(base.get_setting(chat_id, "welcome_faq", []))
    rows = [[button(item["label"], url=item["url"])] for item in current]
    if faq_items:
        rows.append([button("New-member FAQ", callback_data=f"faq:open:{chat_id}")])
    return InlineKeyboardMarkup(rows) if rows else None


def _preview_markup(chat_id: int, token: str, links=None) -> InlineKeyboardMarkup:
    existing = _welcome_markup(chat_id, links)
    rows = [list(row) for row in existing.inline_keyboard] if existing else []
    rows.append([
        button("Edit Again", callback_data=f"welcome_edit:{token}:edit"),
        button("Save", callback_data=f"welcome_edit:{token}:save", style="primary"),
        button("Cancel", callback_data=f"welcome_edit:{token}:cancel", style="danger"),
    ])
    return InlineKeyboardMarkup(rows)


def _media_from_message(message):
    for kind in _WELCOME_MEDIA_TYPES:
        item = getattr(message, kind, None)
        if item is not None and getattr(item, "file_id", None):
            return {"type": kind, "file_id": str(item.file_id)}
    return None


def _stored_welcome_media(chat_id: int):
    value = base.get_setting(chat_id, "welcome_media", None)
    try:
        return Step("media", "", kind="media", required=False).validate(value)
    except ValueError:
        return None


async def start_welcome_workflow(client, chat_id: int, actor_id: int, revision: int, workflow: str) -> str:
    """Start one isolated, revision-bound Welcome Settings conversation."""
    if workflow not in _WELCOME_WORKFLOWS:
        raise ValueError("Unknown Welcome Settings workflow")
    if workflow == "welcome_text":
        step = Step("welcome_message", "Send welcome text", max_length=1000)
        prompt_text = (
            "Reply with the new welcome text (up to 1,000 characters). Supported placeholders: "
            "<code>{name}</code>, <code>{id}</code>, <code>{title}</code>, <code>{mention}</code>. "
            "Send <code>/cancel</code> to stop."
        )
    elif workflow == "welcome_media":
        step = Step("welcome_media", "Send supported media", kind="media", required=False)
        prompt_text = (
            "Reply with a photo, video, animation, document, audio, or voice message to use with the welcome. "
            "Send <code>/clear</code> to remove existing media, or <code>/cancel</code> to leave settings unchanged."
        )
    else:
        step = Step("welcome_checklist", "Send checklist button links", max_length=4096)
        prompt_text = (
            "Reply with up to four HTTPS buttons, one per line: "
            "<code>Label | https://example.com</code>. This edits the existing welcome checklist; "
            "send <code>/clear</code> to remove its links, or <code>/cancel</code> to stop."
        )
    session = await _interaction_engine.begin(
        chat_id=chat_id, actor_id=actor_id, target_chat_id=chat_id,
        workflow=workflow, revision=revision, steps=(step,), timeout_seconds=600,
    )
    try:
        prompt = await client.send_message(chat_id, prompt_text, reply_markup=ForceReply(selective=True))
        await _interaction_engine.bind_prompt(session.token, chat_id=chat_id, actor_id=actor_id, message_id=prompt.id)
    except Exception:
        await _interaction_engine.cancel(session.token, chat_id=chat_id, actor_id=actor_id)
        raise RuntimeError("Could not send the Welcome Settings prompt; no settings changed.") from None
    return "Reply to the prompt to continue. Nothing is saved until you confirm the preview."


async def _send_welcome_prompt(client, session) -> None:
    workflow = session.workflow
    prompt_text = {
        "welcome_text": "Reply with welcome text using only {name}, {id}, {title}, or {mention}. Send /cancel to stop.",
        "welcome_media": "Reply with a photo, video, animation, document, audio, voice message, or /clear to remove media. Send /cancel to stop.",
        "welcome_buttons": "Reply with up to four HTTPS buttons as Label | https://example.com, one per line; /clear removes checklist links. Send /cancel to stop.",
    }.get(workflow)
    if prompt_text:
        prompt = await client.send_message(session.chat_id, prompt_text, reply_markup=ForceReply(selective=True))
        await _interaction_engine.bind_prompt(session.token, chat_id=session.chat_id,
                                              actor_id=session.actor_id, message_id=prompt.id)


@bot.on_message(filters.incoming, group=1)
async def welcome_edit_message(client, message) -> None:
    if not base.is_group(message) or getattr(message, "from_user", None) is None:
        return
    chat_id, actor_id = int(message.chat.id), int(message.from_user.id)
    session = await _interaction_engine.for_owner(chat_id=chat_id, actor_id=actor_id, target_chat_id=chat_id)
    if session is None or session.workflow not in _WELCOME_WORKFLOWS:
        return
    text = str(getattr(message, "text", "") or "")
    command = text.strip().split(maxsplit=1)[0].split("@", 1)[0].casefold() if text.strip() else ""
    if command == "/cancel":
        if await _interaction_engine.cancel(session.token, chat_id=chat_id, actor_id=actor_id):
            await client.send_message(chat_id, "Welcome editing cancelled. Nothing was saved.")
        return
    if getattr(getattr(message, "reply_to_message", None), "id", None) != session.expected_message_id:
        return

    if session.workflow == "welcome_text":
        try:
            value = validate_welcome_template(text)
        except ValueError as error:
            await _send_welcome_prompt(client, session)
            await client.send_message(chat_id, str(error))
            return
    elif session.workflow == "welcome_media":
        value = None if command == "/clear" else _media_from_message(message)
        if value is None and command != "/clear":
            await _send_welcome_prompt(client, session)
            await client.send_message(chat_id, "That media type is not supported here. Send a photo, video, animation, document, audio, or voice message.")
            return
    else:
        if command == "/clear":
            value = "/clear"
        else:
            from videl.utils.welcome_checklist import validate
            try:
                validate(text)
            except ValueError as error:
                await _send_welcome_prompt(client, session)
                await client.send_message(chat_id, str(error))
                return
            value = text

    result = await _interaction_engine.capture(
        session.token, chat_id=chat_id, actor_id=actor_id, target_chat_id=chat_id,
        reply_to_message_id=getattr(getattr(message, "reply_to_message", None), "id", None), value=value,
    )
    if result.status in {"stale", "expired", "unauthorized"}:
        return
    if result.status == "invalid":
        await _send_welcome_prompt(client, result.session)
        await client.send_message(chat_id, result.error or "That value is invalid.")
        return
    if result.status != "preview":
        return
    try:
        current_template = base.get_setting(chat_id, "welcome_message", DEFAULT_WELCOME)
        current_media = _stored_welcome_media(chat_id)
        from videl.utils.welcome_checklist import safe_stored, validate
        current_links = safe_stored(base.get_setting(chat_id, "welcome_checklist", []))
        template, media, links = current_template, current_media, current_links
        if result.session.workflow == "welcome_text":
            template = result.session.values["welcome_message"]
        elif result.session.workflow == "welcome_media":
            media = result.session.values["welcome_media"]
        else:
            raw_links = result.session.values["welcome_checklist"]
            links = [] if raw_links == "/clear" else validate(raw_links)
        rendered = preview_welcome_template(template, message.chat)
        markup = _preview_markup(chat_id, result.session.token, links)
        if media:
            method = getattr(client, f"send_{media['type']}", None)
            if method is None:
                raise ValueError("This media method is unavailable in the Telegram client.")
            preview = await method(chat_id, media["file_id"], caption=rendered, reply_markup=markup)
        else:
            preview = await client.send_message(chat_id, rendered, reply_markup=markup)
        await _interaction_engine.bind_prompt(result.session.token, chat_id=chat_id,
                                              actor_id=actor_id, message_id=preview.id)
    except Exception:
        await _interaction_engine.cancel(session.token, chat_id=chat_id, actor_id=actor_id)
        await client.send_message(chat_id, "Could not render the Welcome preview; nothing was saved. Start again from /settings → Welcome.")


@bot.on_callback_query(filters.regex(r"^welcome_edit:[A-Za-z0-9_-]{1,24}:(?:edit|save|cancel)$"))
async def welcome_edit_callback(client, query: CallbackQuery) -> None:
    message = getattr(query, "message", None)
    actor = getattr(query, "from_user", None)
    if message is None or actor is None or not base.is_group(message):
        await query.answer("Open Welcome Settings in the group.", show_alert=True)
        return
    try:
        _, token, action = str(query.data).split(":")
    except ValueError:
        await query.answer("This welcome action is invalid.", show_alert=True)
        return
    chat_id, actor_id = int(message.chat.id), int(actor.id)
    session = await _interaction_engine.get(token, chat_id=chat_id, actor_id=actor_id, target_chat_id=chat_id)
    if session is None or session.workflow not in _WELCOME_WORKFLOWS:
        await query.answer("This welcome edit expired or belongs to another admin. Nothing was saved.", show_alert=True)
        return
    if action == "cancel":
        await _interaction_engine.cancel(token, chat_id=chat_id, actor_id=actor_id)
        await query.answer("Cancelled; nothing was saved.")
        await rich_edit(message, heading("Welcome edit cancelled", 3) + body("Nothing was saved. Reopen /settings → Welcome to start again."), reply_markup=None)
        return
    if action == "edit":
        edited = await _interaction_engine.edit_again(token, chat_id=chat_id, actor_id=actor_id, message_id=message.id)
        if edited is None:
            await query.answer("This preview is no longer active.", show_alert=True)
            return
        try:
            await rich_edit(message, heading("Edit Welcome settings again", 3) + body("Reply to the next prompt. Nothing has been saved."), reply_markup=None)
            await _send_welcome_prompt(client, edited)
            await query.answer("Reply to the prompt to edit again.")
        except Exception:
            await _interaction_engine.cancel(token, chat_id=chat_id, actor_id=actor_id)
            await query.answer("Could not restart the editor; nothing was saved.", show_alert=True)
        return

    field_by_workflow = {
        "welcome_text": "welcome_message",
        "welcome_media": "welcome_media",
        "welcome_buttons": "welcome_checklist",
    }
    async def authorize(target_chat_id: int, user_id: int) -> bool:
        try:
            member = await client.get_chat_member(target_chat_id, user_id)
            status = getattr(getattr(member, "status", None), "value", getattr(member, "status", None))
            return str(status).casefold() in {"owner", "administrator"}
        except Exception:
            return False

    save_issue = {"conflict": False}
    async def save(snapshot) -> bool:
        from videl.utils.settings_store import SettingsConflict, write
        value = snapshot.values[field_by_workflow[snapshot.workflow]]
        if snapshot.workflow == "welcome_buttons":
            from videl.utils.welcome_checklist import validate
            value = [] if value == "/clear" else validate(value)
        try:
            await asyncio.to_thread(write, snapshot.target_chat_id,
                                    {field_by_workflow[snapshot.workflow]: value}, snapshot.revision)
            return True
        except SettingsConflict:
            save_issue["conflict"] = True
            return False
        except Exception:
            return False

    outcome, _ = await _interaction_engine.commit(
        token, chat_id=chat_id, actor_id=actor_id, target_chat_id=chat_id,
        message_id=int(message.id), authorize=authorize, save=save,
    )
    labels = {"welcome_text": "Welcome text", "welcome_media": "Welcome media", "welcome_buttons": "Welcome checklist buttons"}
    label = labels[session.workflow]
    if outcome == "saved":
        await query.answer(f"{label} saved.")
        await rich_edit(message, heading(f"{label} saved", 3)
                        + body("The new configuration is stored. Delivery still follows the current welcome-enabled setting."),
                        reply_markup=None)
    elif outcome == "permission_denied":
        await _interaction_engine.cancel(token, chat_id=chat_id, actor_id=actor_id)
        await query.answer("Current group-admin permission could not be verified. Nothing was saved.", show_alert=True)
        await rich_edit(message, heading("Welcome settings not saved", 3)
                        + body("Your current group-admin permission could not be verified. Reopen settings if your access is restored."), reply_markup=None)
    elif outcome == "save_failed" and save_issue["conflict"]:
        await _interaction_engine.cancel(token, chat_id=chat_id, actor_id=actor_id)
        await query.answer("Settings changed elsewhere. This draft was not saved; review the latest value.", show_alert=True)
        from videl.plugins import settings as settings_plugin
        latest = settings_plugin._screen(chat_id, "welcome")
        await rich_edit(message, latest.html, reply_markup=latest.keyboard)
    elif outcome == "save_failed":
        await query.answer("Could not save the Welcome setting. Nothing was reported as saved; you can retry.", show_alert=True)
    elif outcome == "expired":
        await query.answer("This edit expired. Nothing was saved.", show_alert=True)
    elif outcome in {"unauthorized", "stale"}:
        await query.answer("This action is not available to this admin or preview.", show_alert=True)


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
            markup = _welcome_markup(message.chat.id)
            rendered = _render(template, member, message.chat)
            media = _stored_welcome_media(message.chat.id)
            try:
                if media:
                    send_media = getattr(bot, f"send_{media['type']}", None)
                    if send_media is None:
                        raise RuntimeError("Configured welcome media method is unavailable")
                    await send_media(message.chat.id, media["file_id"], caption=rendered, reply_markup=markup)
                else:
                    await bot.send_message(message.chat.id, rendered, reply_markup=markup)
            except Exception as error:
                # Only a definite Telegram rejection is safe to fall back from;
                # retrying after a transport timeout could duplicate a greeting.
                from pyrogram.errors import BadRequest, Forbidden
                if media and isinstance(error, (BadRequest, Forbidden)):
                    LOGGER.warning("Telegram rejected welcome media; sending text-only fallback: %s", type(error).__name__)
                    try:
                        await bot.send_message(message.chat.id, rendered, reply_markup=markup)
                    except Exception:
                        LOGGER.debug("Welcome delivery fallback failed", exc_info=True)
                else:
                    LOGGER.debug("Welcome delivery failed without retry", exc_info=True)
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
