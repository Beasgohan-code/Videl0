"""Videl's native keyboard design system. Uses maintained Kurigram types, not patches."""

from __future__ import annotations
import copy
import os
import re
from pyrogram import enums
from pyrogram.types import InlineKeyboardButton as NativeButton, InlineKeyboardMarkup
from videl.utils.premium_emojis import PREMIUM_IDS, USE_PREMIUM

ICONS_ENABLED = os.getenv(
    "USE_PREMIUM_BUTTON_ICONS", "1" if USE_PREMIUM else "0"
).lower() not in {"0", "false", "off", "no"}
_STYLES = {
    "default": enums.ButtonStyle.DEFAULT,
    "primary": enums.ButtonStyle.PRIMARY,
    "success": enums.ButtonStyle.SUCCESS,
    "danger": enums.ButtonStyle.DANGER,
}


def button(text: str, *args, style=None, icon=None, **kwargs) -> NativeButton:
    """Keep every existing action intact while applying a restrained semantic style."""
    if args:
        # Preserve native positional-call validation instead of silently reinterpreting it.
        return NativeButton(text, *args, **kwargs)
    label = str(text).strip()
    label = re.sub(r"^[◍⬪⫶⬩𖦹⦿◎⬢]+\s*", "", label)
    lower = label.lower()
    semantic = None
    if any(
        word in lower
        for word in ("unban", "unlock", "resume", "confirm", "enable", "save")
    ):
        semantic, inferred = "check", "success"
    elif any(
        word in lower
        for word in ("delete", "remove", "close", "cancel", "stop", "disable", "ban")
    ):
        semantic, inferred = "cross", "danger"
    elif any(
        word in lower for word in ("studio", "web app", "dashboard", "open videl")
    ):
        semantic, inferred = "crown", "primary"
    else:
        inferred = "default"
        for terms, key in [
            (("music", "play", "queue", "audio"), "music"),
            (("group", "protect", "admin"), "shield"),
            (("setting", "setup"), "key"),
            (("support", "chat"), "dash"),
            (("next",), "right"),
            (("back", "previous"), "left"),
            (("stat", "analytic"), "stats"),
            (("help", "info", "command"), "info"),
        ]:
            if any(term in lower for term in terms):
                semantic = key
                break
    selected = style if style is not None else inferred
    if isinstance(selected, str):
        aliases = {
            "blue": "primary",
            "green": "success",
            "red": "danger",
            "grey": "default",
            "gray": "default",
        }
        selected = _STYLES.get(
            aliases.get(selected.lower(), selected.lower()), enums.ButtonStyle.DEFAULT
        )
    emoji_id = kwargs.pop("icon_custom_emoji_id", None)
    if ICONS_ENABLED:
        emoji_id = emoji_id or PREMIUM_IDS.get(icon or semantic or "", "") or None
    else:
        emoji_id = None
    if emoji_id is not None and (
        not re.fullmatch(r"[1-9][0-9]{0,18}", str(emoji_id))
        or int(emoji_id) > 9223372036854775807
    ):
        emoji_id = None
    return NativeButton(
        label,
        style=selected,
        icon_custom_emoji_id=str(emoji_id) if emoji_id else None,
        **kwargs,
    )


def plain_keyboard(markup):
    """Copy, never mutate shared keyboards, when custom icons are rejected."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    rows = []
    for row in markup.inline_keyboard:
        clean = []
        for item in row:
            clone = copy.copy(item)
            clone.icon_custom_emoji_id = None
            clean.append(clone)
        rows.append(clean)
    return InlineKeyboardMarkup(rows)


async def visual_call(function, *args, **kwargs):
    """Retry only rejected custom visuals. Never automatically retry network failures."""
    from pyrogram.errors import BadRequest, MessageNotModified

    try:
        return await function(*args, **kwargs)
    except MessageNotModified:
        return None
    except BadRequest:
        safe = dict(kwargs)
        changed = False
        for field in ("text", "caption"):
            value = safe.get(field)
            if isinstance(value, str) and "<tg-emoji" in value:
                safe[field] = re.sub(
                    r"<tg-emoji\b[^>]*>(.*?)</tg-emoji>",
                    r"\1",
                    value,
                    flags=re.I | re.S,
                )
                changed = True
        markup = safe.get("reply_markup")
        if any(
            getattr(item, "icon_custom_emoji_id", None)
            for row in getattr(markup, "inline_keyboard", [])
            for item in row
        ):
            safe["reply_markup"] = plain_keyboard(markup)
            changed = True
        if not changed:
            raise
        return await function(*args, **safe)
