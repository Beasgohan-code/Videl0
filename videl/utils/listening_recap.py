"""Bounded in-memory summary of tracks acknowledged in the current call session."""
from __future__ import annotations
from collections import defaultdict, deque
from threading import RLock
from datetime import datetime, timezone

_MAX_TRACKS = 50
_history = defaultdict(lambda: deque(maxlen=_MAX_TRACKS))
_lock = RLock()


def record(chat_id: int, song: dict, *, at=None) -> None:
    row = {"title": str(song.get("title") or "Untitled track")[:160],
           "requester": str(song.get("requester") or "Unknown")[:64],
           "at": at or datetime.now(timezone.utc)}
    with _lock:
        _history[int(chat_id)].append(row)


def get(chat_id: int) -> list[dict]:
    with _lock:
        return [dict(row) for row in _history.get(int(chat_id), ())]


def clear(chat_id: int) -> list[dict]:
    with _lock:
        return [dict(row) for row in _history.pop(int(chat_id), ())]
