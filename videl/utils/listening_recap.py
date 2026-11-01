"""Bounded, in-memory playback history for the current call session."""
from __future__ import annotations

from collections import OrderedDict, deque
from datetime import datetime, timezone
from threading import RLock

_MAX_TRACKS_PER_CHAT = 50
_MAX_CHATS = 256
_history: OrderedDict[int, deque] = OrderedDict()
_lock = RLock()


def record(chat_id: int, song: dict, *, at=None) -> None:
    """Record only track metadata after playback acknowledgement; omit requester IDs/names."""
    row = {
        "title": str(song.get("title") or "Untitled track")[:160],
        "duration": str(song.get("duration") or "Live")[:20],
        "at": at or datetime.now(timezone.utc),
    }
    key = int(chat_id)
    with _lock:
        tracks = _history.setdefault(key, deque(maxlen=_MAX_TRACKS_PER_CHAT))
        tracks.append(row)
        _history.move_to_end(key)
        while len(_history) > _MAX_CHATS:
            _history.popitem(last=False)


def get(chat_id: int) -> list[dict]:
    with _lock:
        return [dict(row) for row in _history.get(int(chat_id), ())]


def clear(chat_id: int) -> list[dict]:
    with _lock:
        return [dict(row) for row in _history.pop(int(chat_id), ())]
