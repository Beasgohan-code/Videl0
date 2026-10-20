"""Quiet hours, scheduled protection windows and the warning escalation.

Both settings are stored inside the same document the rest of the group
manager writes (``mgmt_chat_settings``) under an ``automation`` key, so there is
exactly one source of truth and one place to audit.

Nothing here guesses: the window is computed from a fixed UTC offset that the
owner chooses, and the escalation action is one of four values the enforcement
code actually performs.
"""
from __future__ import annotations

from datetime import datetime, timezone

QUIET_DEFAULT = {"enabled": False, "start": "22:00", "end": "07:00", "tz_offset": 0}
ESCALATION_DEFAULT = {"enabled": True, "action": "ban", "mute_hours": 6}
PROTECTION_DEFAULT = {"enabled": False, "start": "22:00", "end": "07:00", "locks": []}
MAX_WINDOW_LOCKS = 24
ESCALATION_ACTIONS = ("ban", "mute", "kick", "none")
OFFSET_RANGE = (-840, 840)  # UTC-14:00 … UTC+14:00
MUTE_RANGE = (1, 168)


def parse_hhmm(value) -> int | None:
    """Minutes since midnight, or None for anything that is not a real time."""
    if not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if len(parts) != 2 or not all(part.isdigit() and len(part) <= 2 for part in parts):
        return None
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def format_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def normalize_quiet(raw) -> dict:
    """Always returns a complete, safe quiet-hours block."""
    source = raw if isinstance(raw, dict) else {}
    start = parse_hhmm(source.get("start"))
    end = parse_hhmm(source.get("end"))
    if start is None:
        start = parse_hhmm(QUIET_DEFAULT["start"])
    if end is None:
        end = parse_hhmm(QUIET_DEFAULT["end"])
    try:
        offset = int(source.get("tz_offset", 0))
    except (TypeError, ValueError):
        offset = 0
    offset = max(OFFSET_RANGE[0], min(offset, OFFSET_RANGE[1]))
    return {
        "enabled": source.get("enabled") is True,
        "start": format_hhmm(start),
        "end": format_hhmm(end),
        "tz_offset": offset,
    }


def normalize_escalation(raw) -> dict:
    source = raw if isinstance(raw, dict) else {}
    action = source.get("action")
    if action not in ESCALATION_ACTIONS:
        action = ESCALATION_DEFAULT["action"]
    try:
        hours = int(source.get("mute_hours", ESCALATION_DEFAULT["mute_hours"]))
    except (TypeError, ValueError):
        hours = ESCALATION_DEFAULT["mute_hours"]
    hours = max(MUTE_RANGE[0], min(hours, MUTE_RANGE[1]))
    # ``enabled`` defaults to True so an untouched group keeps the historic
    # behaviour: reach the warning limit and the member is removed.
    enabled = source.get("enabled")
    return {
        "enabled": True if enabled is None else enabled is True,
        "action": action,
        "mute_hours": hours,
    }


def protection_lock_keys() -> tuple[str, ...]:
    """Every lock the enforcement pass understands, as stored keys.

    Imported lazily: moderation owns the canonical list and automation is
    imported by modules that must not pull message handling in at import time.
    """
    from videl.utils.moderation import LOCK_TYPES

    return tuple("lock_forwards" if kind == "forward" else f"lock_{kind}" for kind in LOCK_TYPES)


def normalize_protection(raw) -> dict:
    """Scheduled window that turns locks on, then releases only its own locks.

    ``state`` records what the last run applied. Keeping it inside the same
    document means a restart cannot lose the list of locks to release, and a
    lock the owner set by hand is never turned off by the window ending.
    """
    source = raw if isinstance(raw, dict) else {}
    start = parse_hhmm(source.get("start"))
    end = parse_hhmm(source.get("end"))
    if start is None:
        start = parse_hhmm(PROTECTION_DEFAULT["start"])
    if end is None:
        end = parse_hhmm(PROTECTION_DEFAULT["end"])
    allowed = set(protection_lock_keys())
    locks: list[str] = []
    raw_locks = source.get("locks")
    if isinstance(raw_locks, list):
        for item in raw_locks[:MAX_WINDOW_LOCKS]:
            if isinstance(item, str) and item in allowed and item not in locks:
                locks.append(item)
    return {
        "enabled": source.get("enabled") is True,
        "start": format_hhmm(start),
        "end": format_hhmm(end),
        "locks": locks,
        "state": normalize_protection_state(source.get("state")),
    }


def normalize_protection_state(raw) -> dict:
    source = raw if isinstance(raw, dict) else {}
    applied: list[str] = []
    allowed = set(protection_lock_keys())
    raw_applied = source.get("applied")
    if isinstance(raw_applied, list):
        for item in raw_applied[:MAX_WINDOW_LOCKS]:
            if isinstance(item, str) and item in allowed and item not in applied:
                applied.append(item)
    since = source.get("since")
    return {
        "active": source.get("active") is True,
        "applied": applied,
        "since": since if isinstance(since, str) and len(since) <= 40 else None,
    }


def normalize(raw) -> dict:
    source = raw if isinstance(raw, dict) else {}
    return {
        "quiet_hours": normalize_quiet(source.get("quiet_hours")),
        "escalation": normalize_escalation(source.get("escalation")),
        "protection": normalize_protection(source.get("protection")),
    }


def local_minutes(config: dict, now: datetime | None = None) -> int:
    """Minute of day in the group's chosen offset."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    shifted = moment.astimezone(timezone.utc) + _offset(config)
    return shifted.hour * 60 + shifted.minute


def _offset(config: dict):
    from datetime import timedelta

    try:
        minutes = int((config or {}).get("tz_offset", 0))
    except (TypeError, ValueError):
        minutes = 0
    minutes = max(OFFSET_RANGE[0], min(minutes, OFFSET_RANGE[1]))
    return timedelta(minutes=minutes)


def in_quiet_hours(quiet, now: datetime | None = None) -> bool:
    """True when ``now`` falls inside the configured window.

    A window that starts and ends at the same minute is treated as off rather
    than "all day" — an accidental 22:00–22:00 must not silence a group.
    """
    config = normalize_quiet(quiet)
    if not config["enabled"]:
        return False
    start = parse_hhmm(config["start"])
    end = parse_hhmm(config["end"])
    if start is None or end is None or start == end:
        return False
    return inside_window(start, end, local_minutes(config, now))


def inside_window(start: int, end: int, current: int) -> bool:
    """Half-open minute-of-day comparison; equal ends mean "never"."""
    if start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end  # wraps midnight


def in_protection_window(protection, tz_offset: int = 0, now: datetime | None = None) -> bool:
    """True when the scheduled lock window is enabled and currently open."""
    config = normalize_protection(protection)
    if not config["enabled"]:
        return False
    start = parse_hhmm(config["start"])
    end = parse_hhmm(config["end"])
    if start is None or end is None or start == end:
        return False
    return inside_window(start, end, local_minutes({"tz_offset": tz_offset}, now))


def describe_quiet(quiet) -> str:
    """A short sentence the UI and the bot can both reuse."""
    config = normalize_quiet(quiet)
    if not config["enabled"]:
        return "Quiet hours are off."
    offset = config["tz_offset"]
    sign = "+" if offset >= 0 else "-"
    zone = f"UTC{sign}{abs(offset) // 60:02d}:{abs(offset) % 60:02d}"
    return f"Members' messages are removed from {config['start']} to {config['end']} ({zone})."
