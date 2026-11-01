"""Command presentation on Badmunda05 Richgram; not a transport monkey patch.

Bodies are trusted Telegram HTML; escape user values before interpolation.
Native keyboards stay explicit so styling never replaces actual actions.
"""
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table, rich_hr
from videl.utils.bot_ui import button as native_button, visual_call
from pyrogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

TITLES = {"success": "Action complete", "error": "Action unavailable",
          "warning": "Attention needed", "info": "Information"}


def notice(body, *, status="info", title=None):
    if status not in TITLES:
        raise ValueError("Unknown notice status")
    label = str(title or TITLES[status]).strip()
    status_icons = {"success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️"}
    if not label.startswith(("✅", "❌", "⚠", "ℹ")):
        label = f"{status_icons[status]} {label}"
    return section(label, rich_note(body), level=3)


def usage(command, explanation):
    from videl.utils.rich_ui import rich_esc
    return notice(f"<code>{rich_esc(command)}</code>\n{rich_esc(explanation)}",
                  title="How to use this command")


def result(title, fields=(), body=""):
    from videl.utils.rich_ui import rich_esc
    rows = [(rich_esc(key), rich_esc(str(value))) for key, value in fields]
    content = (rich_kv_table(rows) if rows else "") + (rich_note(body) if body else "")
    return section(title, content, level=2)


def section(title, content="", *, level=3, divider=False):
    """Compose one compact section from a semantic heading and trusted HTML."""
    rendered = rich_heading(title, level=level) + str(content or "")
    return rendered + (rich_hr() if divider else "")


def progress(title, current, total, *, detail=None, width=10):
    """Render validated determinate progress; unknown totals must use a status notice."""
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (current, total, width)):
        raise ValueError("Progress values must be integers")
    if total <= 0 or current < 0 or current > total or not 1 <= width <= 20:
        raise ValueError("Progress must be within a positive, determinate range")
    completed = round(current * width / total)
    percent = round(current * 100 / total)
    meter = "█" * completed + "░" * (width - completed)
    summary = f"<code>{meter}</code> {percent}% · {current}/{total}"
    if detail:
        from videl.utils.rich_ui import rich_esc
        summary += f"\n{rich_esc(detail)}"
    return section(title, rich_note(summary), level=3)


def action_button(text, *, callback_data=None, url=None, style=None, icon=None, **options):
    """Build one semantic native button while leaving its action fields explicit."""
    return native_button(
        text, callback_data=callback_data, url=url, style=style, icon=icon, **options
    )


def inline_keyboard(rows):
    """Create a fresh keyboard from explicit rows without changing button actions."""
    if isinstance(rows, InlineKeyboardMarkup):
        rows = rows.inline_keyboard
    return InlineKeyboardMarkup([list(row) for row in rows or ()])


def navigation_buttons():
    """Shared, restrained global navigation row used by command surfaces."""
    return [
        action_button("Help center", callback_data="help:home", style="primary", icon="info"),
        action_button("Browse commands", callback_data="cmds:all:0", icon="search"),
    ]


# Explicit presentation adapters used by command modules. The underlying
# Badmunda05 Richgram transport remains responsible for rejection/timeout rules.
import re
from videl.utils.rich_ui import (
    rich_send as _send, rich_reply as _reply, rich_edit as _edit,
    rich_button, rich_button_row,
)


def present(html_text, *, navigation=False):
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


def _has_navigation_keyboard(options):
    """True only when an actual keyboard exposes both global navigation actions."""
    markup = options.get("reply_markup") if options.get("reply_markup") is not None else options.get("markup")
    if isinstance(markup, InlineKeyboardMarkup):
        callbacks = {
            getattr(item, "callback_data", None)
            for row in markup.inline_keyboard
            for item in row
        }
        return {"help:home", "cmds:all:0"}.issubset(callbacks)
    if isinstance(markup, ReplyKeyboardMarkup):
        commands = {
            str(getattr(item, "text", "")).strip().casefold()
            for row in markup.keyboard
            for item in row
        }
        return {"/help", "/commands"}.issubset(commands)
    return False


def _with_navigation_keyboard(options):
    """Add global navigation actions to explicit command keyboards without mutation."""
    updated = dict(options)
    field = "reply_markup" if options.get("reply_markup") is not None else "markup"
    markup = options.get(field)
    if isinstance(markup, ReplyKeyboardMarkup):
        rows = [list(row) for row in markup.keyboard]
        present = {
            str(getattr(item, "text", "")).strip().casefold()
            for row in rows
            for item in row
        }
        missing = [KeyboardButton(command) for command in ("/help", "/commands") if command not in present]
        if not missing:
            return updated
        rows.append(missing)
        keyboard_options = {
            name: getattr(markup, name)
            for name in ("is_persistent", "resize_keyboard", "one_time_keyboard", "input_field_placeholder", "selective")
            if getattr(markup, name, None) is not None
        }
        updated[field] = ReplyKeyboardMarkup(keyboard=rows, **keyboard_options)
        return updated
    if not isinstance(markup, InlineKeyboardMarkup):
        return updated
    rows = [list(row) for row in markup.inline_keyboard]
    callbacks = {getattr(item, "callback_data", None) for row in rows for item in row}
    defaults = navigation_buttons()
    missing = [
        item for item in defaults
        if getattr(item, "callback_data", None) not in callbacks
    ]
    if not missing:
        return updated
    if sum(len(row) for row in rows) + len(missing) > 100 or len(rows) >= 100:
        return updated
    rows.append(missing)
    updated[field] = inline_keyboard(rows)
    return updated


def navigation_markup(markup=None):
    """Return a native inline keyboard with both global navigation actions."""
    if markup is None:
        return inline_keyboard([navigation_buttons()])
    return _with_navigation_keyboard({"reply_markup": markup}).get("reply_markup")


async def rich_send(client, chat_id, html_text, *, navigation=False, **options):
    if navigation:
        options = _with_navigation_keyboard(options)
    return await visual_call(
        _send, client, chat_id,
        present(html_text, navigation=navigation and not _has_navigation_keyboard(options)),
        **options,
    )


async def rich_reply(message, html_text, *, navigation=False, **options):
    if navigation:
        options = _with_navigation_keyboard(options)
    return await visual_call(
        _reply, message,
        present(html_text, navigation=navigation and not _has_navigation_keyboard(options)),
        **options,
    )


async def rich_edit(target, html_text, *, navigation=False, **options):
    # An explicit None on edits means remove the old keyboard; respect it.
    clearing = any(key in options and options[key] is None for key in ("reply_markup", "markup"))
    if navigation and not clearing:
        options = _with_navigation_keyboard(options)
    return await visual_call(
        _edit, target,
        present(html_text, navigation=navigation and not clearing and not _has_navigation_keyboard(options)),
        **options,
    )
