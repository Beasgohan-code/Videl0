"""Minimal guest-mode help with no identity lookup, storage or provider calls."""
from __future__ import annotations

import logging
import time
from collections import OrderedDict, deque

from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent

logger = logging.getLogger(__name__)
_WINDOW_SECONDS = 60.0
_MAX_PER_WINDOW = 20
_SEEN_TTL = 600.0
_MAX_SEEN = 2048
_TIMES: deque[float] = deque()
_SEEN: "OrderedDict[str, float]" = OrderedDict()

_RESPONSE = (
    "Videl guest help: I can provide this general guide without collecting an account identity. "
    "Group controls require adding Videl to a Telegram group; ask a current group admin to configure it. "
    "Guest messages do not access group settings, member records or AI features."
)


def _allowed(query_id: str, now: float) -> bool:
    while _TIMES and now - _TIMES[0] >= _WINDOW_SECONDS:
        _TIMES.popleft()
    for key, stamp in list(_SEEN.items()):
        if now - stamp >= _SEEN_TTL:
            _SEEN.pop(key, None)
    if query_id in _SEEN or len(_TIMES) >= _MAX_PER_WINDOW:
        return False
    _TIMES.append(now)
    _SEEN[query_id] = now
    _SEEN.move_to_end(query_id)
    while len(_SEEN) > _MAX_SEEN:
        _SEEN.popitem(last=False)
    return True


async def handle_guest_message(client, message) -> bool:
    """Answer with static help only; ignore guest content entirely."""
    query_id = str(getattr(message, "guest_query_id", "") or "").strip()
    if not query_id or len(query_id) > 128:
        return False
    if not _allowed(query_id, time.monotonic()):
        return False
    result = InlineQueryResultArticle(
        id="videl-guest-help",
        title="Videl guest help",
        description="A short privacy-preserving guide to Videl.",
        input_message_content=InputTextMessageContent(_RESPONSE),
    )
    try:
        await client.answer_guest_query(query_id, result)
        return True
    except Exception as error:
        logger.warning("Guest help answer was not confirmed (%s)", type(error).__name__)
        return False
