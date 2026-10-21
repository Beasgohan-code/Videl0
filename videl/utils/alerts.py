"""One way to tell the owner something from the backend.

Used for failures that happen before or outside the bot's own startup log — a
bot that cannot start cannot announce itself. It posts to the configured log
channel with the Bot API directly, and it never raises: an alert about an
outage must not become a second outage.
"""
from __future__ import annotations

import logging

from videl.utils.bot_api import call_bot_api

log = logging.getLogger(__name__)


def owner_channel() -> int:
    try:
        import config
        return int(getattr(config, "LOG_CHANNEL_ID", 0) or 0)
    except Exception:
        return 0


def notify(message: str, *, title: str = "Videl") -> bool:
    """Post one HTML message to the log channel. ``False`` if it could not."""
    channel = owner_channel()
    if not channel or not message:
        return False
    text = f"<b>{title}</b>\n{message}"[:4000]
    try:
        status, _ = call_bot_api(
            "sendMessage",
            {"chat_id": channel, "text": text, "parse_mode": "HTML",
             "link_preview_options": {"is_disabled": True}},
        )
        return status == 200
    except Exception:
        log.debug("owner alert failed", exc_info=True)
        return False
