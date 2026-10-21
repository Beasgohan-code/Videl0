"""Small, friendly text utilities for chats."""
from __future__ import annotations

import unicodedata

from videl.app.router import Command, CommandError, Screen
from videl.plugins.base import body, escape, heading, target_link


def _font_map(style: str) -> dict[int, int]:
    labels = {"bold": "BOLD", "italic": "ITALIC", "script": "SCRIPT", "mono": "MONOSPACE"}
    mapping: dict[int, int] = {}
    for alphabet, name in (("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "CAPITAL"), ("abcdefghijklmnopqrstuvwxyz", "SMALL")):
        for letter in alphabet:
            try:
                mapped = unicodedata.lookup(f"MATHEMATICAL {labels[style]} {name} {letter}")
            except KeyError:
                # Some legacy Unicode mathematical alphabets have gaps; leave
                # those letters readable instead of emitting unassigned glyphs.
                continue
            mapping[ord(letter)] = ord(mapped)
    for digit, word in zip("0123456789", ("ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE")):
        if style in {"bold", "mono"}:
            try:
                mapped = unicodedata.lookup(f"MATHEMATICAL {labels[style]} DIGIT {word}")
                mapping[ord(digit)] = ord(mapped)
            except KeyError:
                pass
    return mapping


async def font(ctx) -> Screen:
    argument = ctx.command.arguments.strip()
    if not argument:
        return Screen(heading("Text font", 3) + body("Use <code>/font bold Your text</code>, or choose <code>italic</code>, <code>script</code> or <code>mono</code>."))
    style, separator, text = argument.partition(" ")
    style = style.casefold()
    if style not in {"bold", "italic", "script", "mono"}:
        raise CommandError("Choose bold, italic, script or mono. Example: /font bold Hello!")
    if not separator or not text.strip():
        raise CommandError("Add text after the style, for example: /font script Hello world")
    if len(text) > 500:
        raise CommandError("Keep font text under 500 characters.")
    rendered = text.translate(_font_map(style))
    return Screen(heading("Font · " + style, 3) + body(f"<code>{escape(rendered)}</code>"))


async def hug(ctx) -> Screen:
    argument = ctx.command.arguments.strip()
    target = None
    if argument:
        try:
            target = await ctx.client.get_users(int(argument) if argument.isdecimal() else argument.lstrip("@"))
        except Exception:
            raise CommandError("I couldn't find that Telegram user. Pass a username or reply to them.") from None
    else:
        replied = getattr(ctx.message, "reply_to_message", None)
        target = getattr(replied, "from_user", None) if replied else None
    if target:
        sender = target_link(ctx.user) if ctx.user else "Someone in the group"
        text = f"<b>{sender}</b> sends a warm, friendly hug to <b>{target_link(target)}</b> 🤗"
    else:
        text = "A big, friendly group hug for everyone here 🤗🫂"
    return Screen(heading("Hug time", 3) + body(text))


async def kiss(ctx) -> Screen:
    argument = ctx.command.arguments.strip()
    target = None
    if argument:
        try:
            target = await ctx.client.get_users(int(argument) if argument.isdecimal() else argument.lstrip("@"))
        except Exception:
            raise CommandError("I couldn't find that Telegram user. Pass a username or reply to them.") from None
    else:
        replied = getattr(ctx.message, "reply_to_message", None)
        target = getattr(replied, "from_user", None) if replied else None
    if target:
        text = f"A friendly cheek kiss for <b>{target_link(target)}</b> 😘 Keep it kind and only if they’re comfortable!"
    else:
        text = "Sending a little friendly kiss to the chat 😘 Keep it kind and respectful!"
    return Screen(heading("A little kindness", 3) + body(text))


COMMANDS = (
    Command("font", font, "Style text in bold, italic, script or monospace", category="tools"),
    Command("hug", hug, "Send a friendly hug to a member or the group", category="tools"),
    Command("kiss", kiss, "Send a playful, respectful kiss", category="tools"),
)
