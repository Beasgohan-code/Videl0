"""Command presentation on Badmunda05 Richgram; not a transport monkey patch.

Bodies are trusted Telegram HTML; escape user values before interpolation.
Native keyboards stay explicit so styling never replaces actual actions.
"""
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table

TITLES = {"success": "Action complete", "error": "Action unavailable",
          "warning": "Attention needed", "info": "Information"}


def notice(body, *, status="info", title=None):
    if status not in TITLES:
        raise ValueError("Unknown notice status")
    return rich_heading(title or TITLES[status], level=3) + rich_note(body)


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

    if not re.search(r"<h[1-6]\b", text, re.I):
        # Do not push a previously valid full-length body over Telegram’s limit.
        framed = rich_heading("Videl · Update", level=3) + text
        if post_text_length(framed, "HTML") <= 4096:
            text = framed
    if navigation and not re.search(r"<tg-button\b", text, re.I):
        footer = rich_button_row(
            rich_button("Help", callback_data="help:home", style="primary"),
            rich_button("Commands", callback_data="cmds:all:0"),
        )
        # Inline Richgram buttons count toward Telegram's message limit too.
        # Keep concise actions discoverable without making long results invalid.
        if post_text_length(text + footer, "HTML") <= 4096:
            text += footer
    return text


def _has_keyboard(options):
    return options.get("reply_markup") is not None or options.get("markup") is not None


async def rich_send(client, chat_id, html_text, *, navigation=True, **options):
    return await _send(client, chat_id, present(html_text, navigation=navigation and not _has_keyboard(options)), **options)


async def rich_reply(message, html_text, *, navigation=True, **options):
    return await _reply(message, present(html_text, navigation=navigation and not _has_keyboard(options)), **options)


async def rich_edit(target, html_text, *, navigation=True, **options):
    # An explicit None on edits means remove the old keyboard; respect it.
    explicit = "reply_markup" in options or "markup" in options
    return await _edit(target, present(html_text, navigation=navigation and not explicit), **options)
