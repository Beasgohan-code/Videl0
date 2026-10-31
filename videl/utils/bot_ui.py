"""Videl's native keyboard design system. Uses maintained Kurigram types, not patches."""

from __future__ import annotations
import html
import copy
import logging
import os
import re
from pyrogram import enums
from pyrogram.types import InlineKeyboardButton as NativeButton, InlineKeyboardMarkup
from videl.utils.premium_emojis import FALLBACK, PREMIUM_IDS, USE_PREMIUM

ICONS_ENABLED = os.getenv(
    "USE_PREMIUM_BUTTON_ICONS", "1" if USE_PREMIUM else "0"
).lower() not in {"0", "false", "off", "no"}
_STYLES = {
    "default": enums.ButtonStyle.DEFAULT,
    "primary": enums.ButtonStyle.PRIMARY,
    "success": enums.ButtonStyle.SUCCESS,
    "danger": enums.ButtonStyle.DANGER,
}
# When Telegram rejects premium button icons, restore the visible Unicode badge
# that was promoted into the native icon by button().
_ICON_FALLBACKS = {
    str(emoji_id): FALLBACK.get(key, "")
    for key, emoji_id in PREMIUM_IDS.items()
    if FALLBACK.get(key)
}
_VISUAL_REJECTION_MARKERS = (
    "custom_emoji", "custom emoji", "icon_custom_emoji", "button_style",
    "style_invalid", "style is not allowed", "button_type_invalid",
    "unsupported button style", "unsupported start tag 'tg-emoji'",
    'unsupported start tag "tg-emoji"',
)


def _has_visual_content(args, kwargs) -> tuple[bool, bool]:
    texts = [value for value in args if isinstance(value, str)]
    texts.extend(kwargs.get(name) for name in ("text", "caption") if isinstance(kwargs.get(name), str))
    has_custom_emoji = any("<tg-emoji" in value.casefold() for value in texts)
    markups = [kwargs.get(name) for name in ("reply_markup", "markup")]
    has_button_visual = any(
        getattr(item, "icon_custom_emoji_id", None)
        or getattr(getattr(item, "style", None), "value", "default") != "default"
        for markup in markups
        for row in getattr(markup, "inline_keyboard", [])
        for item in row
    )
    return has_custom_emoji, has_button_visual


def _is_visual_rejection(error, args, kwargs) -> bool:
    message = str(error).casefold()
    has_custom_emoji, has_button_visual = _has_visual_content(args, kwargs)
    return bool(
        any(marker in message for marker in _VISUAL_REJECTION_MARKERS)
        and (has_custom_emoji or has_button_visual)
    )


def button(text: str, *args, style=None, icon=None, **kwargs) -> NativeButton:
    """Keep every existing action intact while applying a restrained semantic style."""
    if args:
        # Preserve native positional-call validation instead of silently reinterpreting it.
        return NativeButton(text, *args, **kwargs)
    # Native button labels are plain text, never Telegram HTML.
    source = str(text)
    embedded = re.search(r'<tg-emoji\b[^>]*emoji-id=["\']([0-9]+)', source)
    label = html.unescape(re.sub(r"<[^>]+>", "", source)).strip()
    label = label.translate(str.maketrans("ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ", "abcdefghijklmnopqrstuvwxyz"))
    label = re.sub(r"^[◍⬪⫶⬩𖦹⦿◎⬢]+\s*", "", label)
    leading_emoji_key = None
    if ICONS_ENABLED:
        prefixes = sorted(FALLBACK.items(), key=lambda item: len(item[1]), reverse=True)
        while label:
            for key, glyph in prefixes:
                if glyph and label.startswith(glyph):
                    leading_emoji_key = leading_emoji_key or key
                    label = label[len(glyph):].lstrip(" \t·|—–-:")
                    break
            else:
                break
    lower = label.lower()
    semantic = None
    if any(
        word in lower
        for word in ("unban", "unmute", "unlock", "resume", "confirm", "enable", "save", "restore", "unpin")
    ):
        semantic, inferred = "check", "success"
    elif "approve" in lower and "unapprove" not in lower:
        semantic, inferred = "check", "success"
    elif "unapprove" in lower:
        semantic, inferred = "cross", "danger"
    elif "ban" in lower or "kick" in lower:
        semantic, inferred = "rijif_forbid", "danger"
    elif lower.strip() == "del" or any(word in lower for word in ("delete", "clear all", "purge", "trash")):
        semantic, inferred = "ios_trash", "danger"
    elif any(word in lower for word in ("warn", "warning", "report")):
        semantic, inferred = "rijif_warning", "default"
    elif any(word in lower for word in ("mute", "silence")):
        semantic, inferred = "boseh_speaker_mute", "default"
    elif any(
        word in lower
        for word in ("delete", "remove", "close", "cancel", "stop", "disable")
    ):
        semantic, inferred = "cross", "danger"
    elif any(
        word in lower for word in ("studio", "web app", "dashboard", "open videl")
    ):
        semantic, inferred = "crown", "primary"
    else:
        inferred = "default"
        for terms, key, button_style in [
            (("game", "arcade", "chess", "ludo", "gomoku", "dice"), "boseh_gamepad", "primary"),
            (("music", "play", "queue", "audio"), "music", "primary"),
            (("group", "protect", "admin", "moderation", "blacklist", "captcha", "permission"), "shield", "default"),
            (("lock", "secure", "safety"), "lock", "default"),
            (("pin",), "pin", "default"),
            (("federation", "federations"), "globe", "default"),
            (("reminder", "afk", "timer"), "boseh_clock", "default"),
            (("owner", "console"), "crown", "primary"),
            (("download", "document", "file", "attachment"), "ios_file", "default"),
            (("photo", "image", "sticker", "avatar"), "ios_image", "default"),
            (("invite", "link", "url"), "ios_link", "default"),
            (("welcome", "start"), "spark", "primary"),
            (("setting", "setup"), "ios_gear", "default"),
            (("support", "chat"), "dash", "default"),
            (("next",), "right", "default"),
            (("back", "previous"), "left", "default"),
            (("stat", "analytic"), "stats", "default"),
            (("help", "info", "command"), "info", "primary"),
            (("search", "find"), "ios_search", "default"),
            (("video", "screen", "display"), "ios_tv", "default"),
            (("news", "article"), "ios_newspaper", "default"),
            (("note", "copy", "edit"), "ios_memo", "default"),
            (("folder", "archive"), "ios_folder", "default"),
            (("upload", "share"), "ios_upload", "default"),
            (("link", "url"), "ios_link", "default"),
            (("add", "create"), "ios_add", "default"),
        ]:
            if any(term in lower for term in terms):
                semantic, inferred = key, button_style
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
    if not emoji_id and embedded:
        emoji_id = embedded[1]
    if ICONS_ENABLED:
        emoji_id = emoji_id or PREMIUM_IDS.get(icon or leading_emoji_key or semantic or "", "") or None
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


def icon_keyboard(markup):
    """Add semantic custom-emoji icons to a copy without changing button actions."""
    if not isinstance(markup, InlineKeyboardMarkup) or not ICONS_ENABLED:
        return markup
    rows = []
    changed = False
    for row in markup.inline_keyboard:
        decorated = []
        for item in row:
            icon_id = getattr(item, "icon_custom_emoji_id", None)
            probe = None
            if getattr(item, "text", None):
                # Keep the action fields unchanged; a prefixed Unicode badge is
                # moved to Telegram's native custom-emoji button icon instead.
                probe = button(item.text, callback_data="videl:icon-probe")
                icon_id = icon_id or probe.icon_custom_emoji_id
            if icon_id and (
                not getattr(item, "icon_custom_emoji_id", None)
                or (probe is not None and item.text != probe.text)
            ):
                item = copy.copy(item)
                item.icon_custom_emoji_id = str(icon_id)
                if probe is not None:
                    item.text = probe.text
                changed = True
            decorated.append(item)
        rows.append(decorated)
    return InlineKeyboardMarkup(rows) if changed else markup


def plain_keyboard(markup):
    """Copy, never mutate actions, when optional styles/icons are rejected."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    rows = []
    for row in markup.inline_keyboard:
        clean = []
        for item in row:
            clone = copy.copy(item)
            icon_id = str(getattr(item, "icon_custom_emoji_id", "") or "")
            glyph = _ICON_FALLBACKS.get(icon_id, "")
            text = str(getattr(clone, "text", "") or "")
            if glyph and not text.startswith(glyph):
                clone.text = f"{glyph} {text}".strip()
            clone.icon_custom_emoji_id = None
            clone.style = enums.ButtonStyle.DEFAULT
            clean.append(clone)
        rows.append(clean)
    return InlineKeyboardMarkup(rows)


async def visual_call(function, *args, **kwargs):
    """Retry only rejected custom visuals. Never automatically retry network failures."""
    from pyrogram.errors import BadRequest, MessageNotModified

    kwargs = dict(kwargs)
    for field in ("reply_markup", "markup"):
        if kwargs.get(field) is not None:
            kwargs[field] = icon_keyboard(kwargs[field])
    try:
        return await function(*args, **kwargs)
    except MessageNotModified:
        return None
    except BadRequest as error:
        if not _is_visual_rejection(error, args, kwargs):
            raise
        logging.getLogger(__name__).info(
            "Telegram rejected optional custom emoji/button visuals; retrying this message with standard visuals"
        )
        safe = dict(kwargs)
        safe_args = list(args)
        changed = False
        # Richgram adapters often receive the message text positionally, while
        # native Pyrogram calls may pass it by keyword. Strip only optional
        # premium entities from either form when Telegram rejects them.
        for index, value in enumerate(safe_args):
            if isinstance(value, str) and "<tg-emoji" in value:
                safe_args[index] = re.sub(
                    r"<tg-emoji\b[^>]*>(.*?)</tg-emoji>", r"\1", value, flags=re.I | re.S
                )
                changed = True
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
        for field in ("reply_markup", "markup"):
            markup = safe.get(field)
            if any(
                getattr(item, "icon_custom_emoji_id", None)
                or getattr(item, "style", None) not in (None, enums.ButtonStyle.DEFAULT)
                for row in getattr(markup, "inline_keyboard", [])
                for item in row
            ):
                safe[field] = plain_keyboard(markup)
                changed = True
        if not changed:
            raise
        return await function(*safe_args, **safe)
