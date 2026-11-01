"""Bounded, privacy-minimizing repeated-text signal detector."""
from __future__ import annotations

from collections import deque
from hashlib import sha256
import re
from threading import Lock
from time import monotonic

_WINDOW_SECONDS = 90
_MIN_CHARS = 24
_seen: dict[tuple[int, str], deque] = {}
_alerted: dict[tuple[int, str], float] = {}
_lock = Lock()


def fingerprint(text) -> str | None:
    value = re.sub(r"\s+", " ", str(text or "")).strip().casefold()
    if len(value) < _MIN_CHARS:
        return None
    return sha256(value.encode("utf-8", "ignore")).hexdigest()


def observe(chat_id: int, user_id: int, text, *, now: float | None = None,
            window: int = _WINDOW_SECONDS, min_senders: int = 3) -> dict:
    """Flag a fingerprint repeated by distinct senders; store only its hash."""
    digest = fingerprint(text)
    if digest is None:
        return {"flagged": False, "distinct_senders": 0, "fingerprint": None}
    now = monotonic() if now is None else float(now)
    key = (int(chat_id), digest)
    with _lock:
        events = _seen.setdefault(key, deque(maxlen=200))
        events.append((now, int(user_id)))
        cutoff = now - max(5, min(int(window), 600))
        while events and events[0][0] < cutoff:
            events.popleft()
        senders = {sender for _, sender in events}
        flagged = len(senders) >= max(2, min(int(min_senders), 20))
        alert = flagged and now - _alerted.get(key, float("-inf")) >= max(5, min(int(window), 600))
        if alert:
            _alerted[key] = now
        # Bound memory even if a group sends unique text continuously.
        if len(_seen) > 5000:
            oldest = next(iter(_seen))
            if oldest != key:
                _seen.pop(oldest, None)
                _alerted.pop(oldest, None)
        return {"flagged": flagged, "alert": alert, "distinct_senders": len(senders), "fingerprint": digest}


def clear() -> None:
    with _lock:
        _seen.clear()
