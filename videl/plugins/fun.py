"""Friendly text and original animated reactions for Telegram chats."""
from __future__ import annotations

import asyncio
import unicodedata

from videl.app.router import Command, CommandError, Screen
from videl.plugins.base import body, escape, heading, target_link
from videl.utils.premium_emojis import pe


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


async def _target(ctx):
    argument = ctx.command.arguments.strip()
    if argument:
        try:
            return await ctx.client.get_users(int(argument) if argument.isdecimal() else argument.lstrip("@"))
        except Exception:
            raise CommandError("I couldn't find that Telegram user. Pass a username or reply to them.") from None
    replied = getattr(ctx.message, "reply_to_message", None)
    return getattr(replied, "from_user", None) if replied else None


async def _reaction(ctx, action: str) -> Screen:
    target = await _target(ctx) if action in {"hug", "kiss", "like", "highfive"} or ctx.command.arguments.strip() else None
    sender = target_link(ctx.user) if ctx.user else "Someone in the group"
    recipient = target_link(target) if target else None
    captions = {
        "hug": ("vector_101", "A little hug", f"<b>{sender}</b> sends a warm, friendly hug" + (f" to <b>{recipient}</b>." if recipient else " to everyone here.")),
        "kiss": ("vector_102", "Kindness only", f"<b>{sender}</b> sends a friendly cheek kiss" + (f" to <b>{recipient}</b> — only if they’re comfortable!" if recipient else " to the chat — keep it kind and respectful!")),
        "like": ("rijif_heart_fire", "A little appreciation", f"<b>{sender}</b> sends a little appreciation" + (f" to <b>{recipient}</b>." if recipient else " to everyone in the chat.")),
        "wave": ("rijif_speech", "Hello there!", f"<b>{sender}</b> waves hello" + (f" to <b>{recipient}</b>." if recipient else " to the group.")),
        "highfive": ("rijif_thumbs_up", "High five!", f"<b>{sender}</b> shares a cheerful high five" + (f" with <b>{recipient}</b>." if recipient else " with everyone here.")),
        "dance": ("rijif_disco", "Dance break!", f"<b>{sender}</b> starts a little dance break for the group."),
    }
    icon, title, text = captions[action]
    from videl.utils.fun_animation import fetch_reaction, render
    remote = await fetch_reaction(action)
    animation = remote.data if remote is not None else None
    if animation is None:
        actor_id = getattr(ctx.user, "id", 0) if ctx.user else 0
        target_id = getattr(target, "id", 0) if target else 0
        try:
            animation = await asyncio.to_thread(render, action, f"{actor_id}:{target_id}")
        except Exception:
            animation = None

    if animation:
        if remote is not None:
            sources = []
            if remote.artist_name:
                artist = escape(remote.artist_name)
                sources.append(f'<a href="{escape(remote.artist_href)}">{artist}</a>' if remote.artist_href else artist)
            if remote.anime_name:
                sources.append(escape(remote.anime_name))
            if remote.source_url:
                sources.append(f'<a href="{escape(remote.source_url)}">original source</a>')
            sources.append('<a href="https://nekos.best">Nekos.best GIF</a>')
            credit = '<br><i>Art: ' + ' · '.join(sources) + '</i>'
        else:
            credit = '<br><i>Videl original animation</i>'
        caption = f"<b>{pe(icon)} {escape(title)}</b><br>{text}{credit}"
        return Screen(caption, animation=animation)
    # Keep every command useful on lean installs that omit Pillow.
    return Screen(heading(pe(icon) + " " + title, 3) + body(text))


async def hug(ctx) -> Screen:
    return await _reaction(ctx, "hug")


async def kiss(ctx) -> Screen:
    return await _reaction(ctx, "kiss")


async def like(ctx) -> Screen:
    return await _reaction(ctx, "like")


async def wave(ctx) -> Screen:
    return await _reaction(ctx, "wave")


async def highfive(ctx) -> Screen:
    return await _reaction(ctx, "highfive")


async def dance(ctx) -> Screen:
    return await _reaction(ctx, "dance")


COMMANDS = (
    Command("font", font, "Style text in bold, italic, script or monospace", category="tools"),
    Command("hug", hug, "Send an original animated friendly hug", category="tools"),
    Command("kiss", kiss, "Send a respectful, animated cheek-kiss reaction", category="tools"),
    Command("like", like, "Send an animated appreciation reaction", category="tools"),
    Command("wave", wave, "Send an original animated hello", category="tools"),
    Command("highfive", highfive, "Share an animated high five", category="tools"),
    Command("dance", dance, "Start an animated group dance break", category="tools"),
)
