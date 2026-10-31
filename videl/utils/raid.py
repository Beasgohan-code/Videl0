"""In-memory activity detector for temporary, configurable raid response.

This module only detects bursts. It never bans or deletes messages; callers can
use an activation signal to apply reversible group protections and notify admins.
"""
from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

_DEFAULTS = {"enabled": False, "window_seconds": 30, "join_threshold": 8,
             "message_threshold": 20, "duration_minutes": 15}
_events = defaultdict(lambda: {"joins": deque(), "messages": deque(), "until": 0.0})
_lock = Lock()


def normalize(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    def bounded(name, default, low, high):
        try:
            value = int(raw.get(name, default))
        except (TypeError, ValueError):
            value = default
        return max(low, min(value, high))
    return {
        "enabled": raw.get("enabled") is True,
        "window_seconds": bounded("window_seconds", 30, 5, 300),
        "join_threshold": bounded("join_threshold", 8, 2, 500),
        "message_threshold": bounded("message_threshold", 20, 2, 1000),
        "duration_minutes": bounded("duration_minutes", 15, 1, 240),
    }


def record(chat_id: int, kind: str, config, now: float | None = None) -> dict:
    """Record one join/message and report whether this event started a raid.

    Events are bounded by each group's configured sliding window. A transition
    to active is signalled once; while active, no repeated activation is sent.
    """
    settings = normalize(config)
    if kind not in {"joins", "messages"}:
        raise ValueError("kind must be joins or messages")
    now = monotonic() if now is None else float(now)
    with _lock:
        key = int(chat_id)
        if key not in _events and len(_events) >= 10000:
            _events.pop(next(iter(_events)), None)
        state = _events[key]
        was_active = state["until"] > now
        cutoff = now - settings["window_seconds"]
        events = state[kind]
        events.append(now)
        while events and events[0] < cutoff:
            events.popleft()
        active = was_active
        if settings["enabled"] and not was_active:
            threshold = settings["join_threshold" if kind == "joins" else "message_threshold"]
            if len(events) >= threshold:
                state["until"] = now + settings["duration_minutes"] * 60
                active = True
        if state["until"] <= now:
            state["until"] = 0.0
            active = False
        return {"active": active, "started": active and not was_active,
                "until_monotonic": state["until"], "count": len(events)}


def status(chat_id: int, now: float | None = None) -> dict:
    now = monotonic() if now is None else float(now)
    with _lock:
        state = _events.get(int(chat_id))
        if not state or state["until"] <= now:
            return {"active": False, "remaining_seconds": 0}
        return {"active": True, "remaining_seconds": max(0, int(state["until"] - now))}


def clear(chat_id: int) -> None:
    with _lock:
        _events.pop(int(chat_id), None)
