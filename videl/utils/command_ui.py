"""Command presentation on Badmunda05 Richgram; not a transport monkey patch.

Bodies are trusted Telegram HTML; escape user values before interpolation.
Native keyboards stay explicit so styling never replaces actual actions.
"""
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table
from videl.utils.bot_ui import button as native_button, visual_call
from pyrogram.types import InlineKeyboardMarkup

TITLES = {"success": "Action complete", "error": "Action unavailable",
          "warning": "Attention needed", "info": "Information"}


def notice(body, *, status="info", title=None):
    if status not in TITLES:
        raise ValueError("Unknown notice status")
    label = str(title or TITLES[status]).strip()
    status_icons = {"success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️"}
    if not label.startswith(("✅", "❌", "⚠", "ℹ")):
        label = f"{status_icons[status]} {label}"
    return rich_heading(label, level=3) + rich_note(body)


def usage(command, explanation):
    from videl.utils.rich_ui import rich_esc
    return notice(f"<code>{rich_esc(command)}</code>\n{rich_esc(explanation)}",
                  title="How to use this command")


def result(title, fields=(), body=""):
    from videl.utils.rich_ui import rich_esc
    rows = [(rich_esc(key), rich_esc(str(value))) for key, value in fields]
    return rich_heading(title, level=2) + (rich_kv_table(rows) if rows else "") + (rich_note(body) if body else "")


# Explicit presentation adapters used by command modules. The underlying
# Badmunda05 Richgram transport remains responsible for rejection/timeout rules.
import re
from videl.utils.rich_ui import (
    rich_send as _send, rich_reply as _reply, rich_edit as _edit,
    rich_button, rich_button_row,
)


def present(html_text, *, navigation=True):
    """Frame authored feedback without rewriting its body or existing actions.

    Never call this for user-authored delivery payloads (saved notes, broadcasts,
    photos/files, polls). They deliberately keep their native delivery paths.
    """
    if not html_text:
        return html_text
    text = str(html_text)
    from videl.utils.post_format import post_text_length

    has_heading = bool(re.search(r"<h[1-6]\b", text, re.I))
    has_rich_body = bool(
        re.search(r"<(?:blockquote|table|details|aside|ul|ol|pre|p|tg-button-row)\b", text, re.I)
        or re.search(r"<tg-button\b", text, re.I)
    )
    # Detect structure before inserting our own heading; otherwise that heading
    # masks a plain body and prevents the body from getting its readable callout.
    if not has_heading:
        body = text if has_rich_body else rich_note(text)
        framed = rich_heading("✨ Videl · Update", level=3) + body
        if post_text_length(framed, "HTML") <= 4096:
            text = framed
    # Preserve authored headings and wrap only their otherwise-unstructured
    # short body. Existing tables, callouts, details, and buttons stay untouched.
    elif has_heading and not has_rich_body and post_text_length(text, "HTML") <= 3900:
        text = rich_note(text)
    if navigation:
        # Keep Help and Browse commands visible even when the command already
        # authored its own action buttons. Do not duplicate either callback.
        missing = []
        if not re.search(r'<tg-button\b[^>]*\bdata=["\']help:home["\']', text, re.I):
            missing.append(rich_button("Help center", callback_data="help:home", style="primary"))
        if not re.search(r'<tg-button\b[^>]*\bdata=["\']cmds:all:0["\']', text, re.I):
            missing.append(rich_button("Browse commands", callback_data="cmds:all:0"))
        if missing:
            footer = rich_button_row(*missing)
            # Inline Richgram buttons count toward Telegram's message limit too.
            if post_text_length(text + footer, "HTML") <= 4096:
                text += footer
    return text


def _has_keyboard(options):
    return options.get("reply_markup") is not None or options.get("markup") is not None


def _with_navigation_keyboard(options):
    """Add the same safe help row to explicit command keyboards without mutation."""
    updated = dict(options)
    field = "reply_markup" if options.get("reply_markup") is not None else "markup"
    markup = options.get(field)
    if not isinstance(markup, InlineKeyboardMarkup):
        return updated
    rows = [list(row) for row in markup.inline_keyboard]
    callbacks = {getattr(item, "callback_data", None) for row in rows for item in row}
    missing = []
    if "help:home" not in callbacks:
        missing.append(native_button("Help center", callback_data="help:home", style="primary", icon="info"))
    if "cmds:all:0" not in callbacks:
        missing.append(native_button("Browse commands", callback_data="cmds:all:0", icon="search"))
    if not missing:
        return updated
    if sum(len(row) for row in rows) + len(missing) > 100 or len(rows) >= 100:
        return updated
    rows.append(missing)
    updated[field] = InlineKeyboardMarkup(rows)
    return updated


def navigation_markup(markup=None):
    """Return a native inline keyboard with both global navigation actions."""
    if markup is None:
        return InlineKeyboardMarkup([[
            native_button("Help center", callback_data="help:home", style="primary", icon="info"),
            native_button("Browse commands", callback_data="cmds:all:0", icon="search"),
        ]])
    return _with_navigation_keyboard({"reply_markup": markup}).get("reply_markup")


async def rich_send(client, chat_id, html_text, *, navigation=True, **options):
    if navigation:
        options = _with_navigation_keyboard(options)
    return await visual_call(
        _send, client, chat_id,
        present(html_text, navigation=navigation and not _has_keyboard(options)),
        **options,
    )


async def rich_reply(message, html_text, *, navigation=True, **options):
    if navigation:
        options = _with_navigation_keyboard(options)
    return await visual_call(
        _reply, message,
        present(html_text, navigation=navigation and not _has_keyboard(options)),
        **options,
    )


async def rich_edit(target, html_text, *, navigation=True, **options):
    # An explicit None on edits means remove the old keyboard; respect it.
    explicit = "reply_markup" in options or "markup" in options
    clearing = any(key in options and options[key] is None for key in ("reply_markup", "markup"))
    if navigation and not clearing:
        options = _with_navigation_keyboard(options)
    return await visual_call(
        _edit, target,
        present(html_text, navigation=navigation and not explicit),
        **options,
    )
