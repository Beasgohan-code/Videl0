"""Private member preferences for optional updates and reminder quiet hours."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import re

DEFAULTS = {
    "notifications_enabled": False,
    "quiet_hours": {"enabled": False, "start": "22:00", "end": "07:00", "utc_offset_minutes": 0},
    "language": "en",
}
_TIME = re.compile(r"^(\d{2}):(\d{2})$")


def parse_time(value: str) -> int | None:
    if not isinstance(value, str):
        return None
    match = _TIME.fullmatch(value)
    if not match:
        return None
    hour, minute = map(int, match.groups())
    return hour * 60 + minute if hour < 24 and minute < 60 else None


def normalize_quiet_hours(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    start = raw.get("start", "22:00")
    end = raw.get("end", "07:00")
    offset = raw.get("utc_offset_minutes", 0)
    if (parse_time(start) is None or parse_time(end) is None or start == end
            or type(offset) is not int or not -720 <= offset <= 840):
        return dict(DEFAULTS["quiet_hours"])
    return {"enabled": raw.get("enabled") is True, "start": start, "end": end,
            "utc_offset_minutes": offset}


def read(db, user_id: int) -> dict:
    result = {**DEFAULTS, "quiet_hours": dict(DEFAULTS["quiet_hours"])}
    if db is None or type(user_id) is not int or user_id <= 0:
        return result
    try:
        doc = db["user_preferences"].find_one({"_id": user_id}) or {}
        result["notifications_enabled"] = doc.get("notifications_enabled") is True
        result["quiet_hours"] = normalize_quiet_hours(doc.get("quiet_hours"))
        language = doc.get("language")
        if isinstance(language, str) and language in {"en", "ml", "hi", "ta"}:
            result["language"] = language
    except Exception:
        pass
    return result


def update(db, user_id: int, **changes) -> dict | None:
    if db is None or type(user_id) is not int or user_id <= 0:
        return None
    allowed = {"notifications_enabled", "quiet_hours", "language"}
    if not changes or set(changes) - allowed:
        return None
    values = {}
    if "notifications_enabled" in changes:
        if type(changes["notifications_enabled"]) is not bool:
            return None
        values["notifications_enabled"] = changes["notifications_enabled"]
    if "quiet_hours" in changes:
        quiet = changes["quiet_hours"]
        normalized = normalize_quiet_hours(quiet)
        if not isinstance(quiet, dict) or normalized != quiet:
            return None
        values["quiet_hours"] = normalized
    if "language" in changes:
        if changes["language"] not in {"en", "ml", "hi", "ta"}:
            return None
        values["language"] = changes["language"]
    try:
        db["user_preferences"].update_one({"_id": user_id}, {"$set": values}, upsert=True)
        return read(db, user_id)
    except Exception:
        return None


def opted_in_private_chats(db, private_chats) -> tuple[list[dict], int]:
    """Apply opt-in to private broadcast recipients; database errors fail closed."""
    chats = list(private_chats)
    if db is None:
        return [], len(chats)
    try:
        allowed = {int(row["_id"]) for row in db["user_preferences"].find(
            {"notifications_enabled": True}, {"_id": 1})}
        selected = [doc for doc in chats if int(doc["chat_id"]) in allowed]
        return selected, len(chats) - len(selected)
    except Exception:
        return [], len(chats)


def next_allowed_delivery(now: datetime, quiet: dict) -> datetime:
    """Return the first UTC instant outside a member's fixed-offset quiet window."""
    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime")
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    quiet = normalize_quiet_hours(quiet)
    if not quiet["enabled"]:
        return now
    offset = timezone(timedelta(minutes=quiet["utc_offset_minutes"]))
    local = now.astimezone(offset)
    minute = local.hour * 60 + local.minute
    start, end = parse_time(quiet["start"]), parse_time(quiet["end"])
    in_window = start <= minute < end if start < end else minute >= start or minute < end
    if not in_window:
        return now
    end_day = local.date() + timedelta(days=1) if start > end and minute >= start else local.date()
    hour, mins = divmod(end, 60)
    local_end = datetime.combine(end_day, time(hour, mins), tzinfo=offset)
    return local_end.astimezone(timezone.utc)
