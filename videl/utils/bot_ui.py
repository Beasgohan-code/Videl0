"""Videl's native keyboard design system. Uses maintained Kurigram types, not patches."""

from __future__ import annotations
import html
import copy
import logging
import os
import re
from pyrogram import enums
from pyrogram.types import InlineKeyboardButton as NativeButton, InlineKeyboardMarkup
from videl.utils.premium_emojis import (
    FALLBACK,
    PREMIUM_IDS,
    USE_PREMIUM,
    callback_text,
    custom_emoji_id,
    fallback_custom_emoji_html,
    unicode_fallback,
)

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
    if ICONS_ENABLED and not (embedded and embedded[1] not in _ICON_FALLBACKS):
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
    if not emoji_id and embedded and embedded[1] in _ICON_FALLBACKS:
        emoji_id = embedded[1]
    if ICONS_ENABLED and not emoji_id and not (embedded and embedded[1] not in _ICON_FALLBACKS):
        emoji_key = icon or leading_emoji_key or semantic
        emoji_id = custom_emoji_id(emoji_key) if emoji_key else None
    if not ICONS_ENABLED:
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


def fallback_custom_emoji_keyboard(markup):
    """Remove native custom icons after definite rejection, keeping actions/styles."""
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
            clean.append(clone)
        rows.append(clean)
    return InlineKeyboardMarkup(rows)


def plain_keyboard(markup):
    """Copy, never mutate actions, when both optional styles and icons are rejected."""
    fallback = fallback_custom_emoji_keyboard(markup)
    if not isinstance(fallback, InlineKeyboardMarkup):
        return fallback
    for row in fallback.inline_keyboard:
        for item in row:
            item.style = enums.ButtonStyle.DEFAULT
    return fallback


def fallback_custom_emoji_entities(entities):
    """Drop only CUSTOM_EMOJI entities; their visible replacement text remains."""
    if entities is None:
        return None
    kept = []
    for entity in entities:
        kind = getattr(getattr(entity, "type", None), "name", None) or getattr(getattr(entity, "type", None), "value", None) or getattr(entity, "type", None)
        if str(kind).casefold() in {"custom_emoji", "messageentitytype.custom_emoji"}:
            continue
        if getattr(entity, "custom_emoji_id", None):
            continue
        kept.append(entity)
    return kept


async def answer_callback(query, text=None, **kwargs):
    """Answer a callback with plain text and no unsupported HTML emoji entities."""
    return await query.answer(callback_text(text), **kwargs)




def unstyled_keyboard(markup):
    """Drop rejected button styles while preserving Premium Emoji icon IDs."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    rows = []
    for row in markup.inline_keyboard:
        clean = []
        for item in row:
            clone = copy.copy(item)
            clone.style = enums.ButtonStyle.DEFAULT
            clean.append(clone)
        rows.append(clean)
    return InlineKeyboardMarkup(rows)


def _is_button_style_rejection(error) -> bool:
    message = str(error).casefold()
    return any(marker in message for marker in (
        "button_style", "style_invalid", "style is not allowed", "unsupported button style",
    ))


def _is_custom_emoji_rejection(error) -> bool:
    """Recognize explicit Telegram custom-emoji ID/entity rejections only."""
    message = str(error).casefold()
    return any(marker in message for marker in (
        "custom_emoji_invalid",
        "button_custom_emoji_invalid",
        "custom_emoji_id_invalid",
        "custom_emoji_not_found",
        "custom emoji not found",
        "custom emoji id is invalid",
        "custom emoji is invalid",
        "custom emoji cannot be used",
        "custom emoji can't be used",
    )) or ("unsupported start tag" in message and "tg-emoji" in message)


def _fallback_custom_emoji_payload(function, args, kwargs):
    safe_args = list(args)
    safe = dict(kwargs)
    changed = False
    for field in ("text", "caption"):
        value = safe.get(field)
        if isinstance(value, str):
            fallback = fallback_custom_emoji_html(value)
            if fallback != value:
                safe[field] = fallback
                changed = True
    for field in ("entities", "caption_entities"):
        value = safe.get(field)
        if value is not None:
            fallback = fallback_custom_emoji_entities(value)
            if len(fallback) != len(value):
                safe[field] = fallback
                changed = True
    for field in ("reply_markup", "markup"):
        value = safe.get(field)
        if any(
            getattr(item, "icon_custom_emoji_id", None)
            for row in getattr(value, "inline_keyboard", [])
            for item in row
        ):
            safe[field] = fallback_custom_emoji_keyboard(value)
            changed = True
    for index, value in enumerate(safe_args):
        if isinstance(value, InlineKeyboardMarkup) and any(
            getattr(item, "icon_custom_emoji_id", None)
            for row in value.inline_keyboard
            for item in row
        ):
            safe_args[index] = fallback_custom_emoji_keyboard(value)
            changed = True

    # Positional Pyrogram, Richgram and callback adapters have different
    # signatures; only touch argument strings that actually contain this tag.
    for index, value in enumerate(safe_args):
        if isinstance(value, str) and "<tg-emoji" in value.casefold():
            fallback = fallback_custom_emoji_html(value)
            if fallback != value:
                safe_args[index] = fallback
                changed = True
    return safe_args, safe, changed


async def visual_call(function, *args, **kwargs):
    """Apply definite, bounded Telegram visual fallbacks without replaying actions."""
    from pyrogram.errors import BadRequest, MessageNotModified

    safe_args = list(args)
    safe = dict(kwargs)
    for field in ("reply_markup", "markup"):
        if safe.get(field) is not None:
            safe[field] = icon_keyboard(safe[field])
    for index, value in enumerate(safe_args):
        if isinstance(value, InlineKeyboardMarkup):
            safe_args[index] = icon_keyboard(value)
    custom_fallback_used = False
    style_fallback_used = False
    for _ in range(3):
        try:
            return await function(*safe_args, **safe)
        except MessageNotModified:
            return None
        except BadRequest as error:
            if _is_custom_emoji_rejection(error) and not custom_fallback_used:
                safe_args, safe, changed = _fallback_custom_emoji_payload(function, safe_args, safe)
                if changed:
                    custom_fallback_used = True
                    logging.getLogger(__name__).info(
                        "Telegram rejected a custom emoji; retrying once with catalogued Unicode fallbacks"
                    )
                    continue
            if _is_button_style_rejection(error) and not style_fallback_used:
                changed = False
                for field in ("reply_markup", "markup"):
                    markup = safe.get(field)
                    if any(
                        getattr(item, "style", None) not in (None, enums.ButtonStyle.DEFAULT)
                        for row in getattr(markup, "inline_keyboard", [])
                        for item in row
                    ):
                        safe[field] = unstyled_keyboard(markup)
                        changed = True
                for index, markup in enumerate(safe_args):
                    if isinstance(markup, InlineKeyboardMarkup) and any(
                        getattr(item, "style", None) not in (None, enums.ButtonStyle.DEFAULT)
                        for row in markup.inline_keyboard
                        for item in row
                    ):
                        safe_args[index] = unstyled_keyboard(markup)
                        changed = True
                if changed:
                    style_fallback_used = True
                    logging.getLogger(__name__).info(
                        "Telegram rejected button styling; retrying without optional styles"
                    )
                    continue
            raise
