"""Bounded in-process pending music requests for optional admin approval."""
from __future__ import annotations
from collections import defaultdict
from secrets import token_urlsafe

MAX_PENDING_PER_CHAT = 50
_pending: dict[int, list[dict]] = defaultdict(list)


def submit(chat_id: int, song: dict) -> str | None:
    items = _pending[int(chat_id)]
    if len(items) >= MAX_PENDING_PER_CHAT:
        return None
    token = token_urlsafe(6).replace("-", "a").replace("_", "b")[:8]
    items.append({"id": token, "song": dict(song)})
    return token


def list_pending(chat_id: int) -> list[dict]:
    return [dict(item) for item in _pending.get(int(chat_id), ())]


def take(chat_id: int, request_id: str) -> dict | None:
    items = _pending.get(int(chat_id), [])
    for index, item in enumerate(items):
        if item["id"] == request_id:
            return items.pop(index)["song"]
    return None


def clear(chat_id: int) -> None:
    _pending.pop(int(chat_id), None)
