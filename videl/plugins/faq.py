# Videl © 2026 | Beasgohan-code
"""Admin-maintained group FAQ with safe, public answer buttons."""
from __future__ import annotations

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup

from videl import bot
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table
from videl.utils.bot_ui import button
from videl.utils.command_ui import rich_edit


def _faq(chat_id: int):
    from videl.utils.member_faq import normalize
    return normalize(base.get_setting(chat_id, "welcome_faq", []))


def _markup(chat_id: int, items):
    return [[button(f"{index}. {item['question'][:48]}",
                    callback_data=f"faq:item:{int(chat_id)}:{index - 1}")]
            for index, item in enumerate(items, 1)]


async def set_faq(ctx) -> Screen:
    raw = ctx.command.arguments.strip()
    chat_id = int(ctx.message.chat.id)
    current = _faq(chat_id)
    if not raw:
        return Screen(heading("Group FAQ settings", 3)
                      + (table([(str(index), escape(item["question"]))
                                for index, item in enumerate(current, 1)]) if current else body("No FAQ questions are set."))
                      + body("Add or update: <code>/setfaq add Question | Answer</code>. Remove by number with <code>/setfaq remove 2</code>; clear all with <code>/setfaq clear</code>. Up to eight entries; answers appear in the group."))
    parts = raw.split(maxsplit=1)
    action = parts[0].casefold()
    from videl.utils.member_faq import add, remove
    if action == "clear" and len(parts) == 1:
        updated = []
    elif action == "remove" and len(parts) == 2 and parts[1].isdecimal():
        try: updated = remove(current, int(parts[1]))
        except ValueError as error: raise CommandError(escape(str(error))) from None
    elif action == "add" and len(parts) == 2:
        question, separator, answer = parts[1].partition("|")
        if not separator:
            raise CommandError("Use <code>/setfaq add Question | Answer</code>.")
        try: updated = add(current, question, answer)
        except ValueError as error: raise CommandError(escape(str(error))) from None
    else:
        raise CommandError("Use <code>/setfaq add Question | Answer</code>, <code>/setfaq remove NUMBER</code>, or <code>/setfaq clear</code>.")
    if not base.set_setting(chat_id, "welcome_faq", updated):
        raise CommandError("The FAQ could not be saved; nothing changed.")
    return Screen(heading("✅ Group FAQ updated", 3)
                  + body(f"{len(updated)} question{'s' if len(updated) != 1 else ''} saved. New members can open it from the welcome checklist or run <code>/faq</code>."))


async def faq(ctx) -> Screen:
    items = _faq(int(ctx.message.chat.id))
    if not items:
        return Screen(heading("Group FAQ", 3) + body("This group has not published any FAQ entries."))
    return Screen(heading("New-member FAQ", 3)
                  + body("Choose a question to read its answer. The questions and answers are visible to everyone in this group.")
                  + table([(str(index), escape(item["question"])) for index, item in enumerate(items, 1)]),
                  _markup(ctx.message.chat.id, items))


@bot.on_callback_query(filters.regex(r"^faq:(?:open:-?[0-9]{1,20}|item:-?[0-9]{1,20}:[0-7])$"))
async def faq_callback(_, query) -> None:
    message = getattr(query, "message", None)
    actor = getattr(query, "from_user", None)
    if message is None or actor is None or base.chat_kind(message) not in {"group", "supergroup"}:
        return await query.answer("Open the FAQ in its group.", show_alert=True)
    try:
        pieces = str(query.data).split(":")
        if pieces[0] == "faq" and pieces[1] == "open":
            chat_id = int(pieces[2])
            index = None
        elif len(pieces) == 4 and pieces[0] == "faq" and pieces[1] == "item":
            chat_id, index = int(pieces[2]), int(pieces[3])
        else:
            raise ValueError
    except (TypeError, ValueError, IndexError):
        return await query.answer("That FAQ button is invalid.", show_alert=True)
    if chat_id != int(message.chat.id):
        return await query.answer("That FAQ belongs to another group.", show_alert=True)
    items = _faq(chat_id)
    if not items:
        await query.answer("The group FAQ is empty.", show_alert=True)
        return
    if index is not None and not 0 <= index < len(items):
        return await query.answer("That FAQ entry has been removed.", show_alert=True)
    await query.answer()
    if index is None:
        text = (heading("New-member FAQ", 3)
                + body("Choose a question to read its answer. Everyone in the group can see it.")
                + table([(str(number), escape(item["question"])) for number, item in enumerate(items, 1)]))
        await rich_edit(message, text, reply_markup=_markup(chat_id, items))
        return
    selected = items[index]
    text = heading(escape(selected["question"]), 3) + body(escape(selected["answer"]))
    controls = InlineKeyboardMarkup([[button("All questions", callback_data=f"faq:open:{chat_id}")]])
    await rich_edit(message, text, reply_markup=controls)


COMMANDS = (
    Command("faq", faq, "Show this group's new-member FAQ", category="manage", policy="group"),
    Command("setfaq", set_faq, "Add or edit group FAQ entries", category="manage", policy="admin"),
)
