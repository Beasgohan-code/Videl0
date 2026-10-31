"""Privacy-minimal command telemetry helpers and bounded owner summaries."""
from __future__ import annotations

import hashlib
import hmac
from collections import Counter
from datetime import datetime, timedelta, timezone

import config

MAX_EVENTS = 20_000
EVENT_SCHEMA_VERSION = 1


def _salt() -> str:
    return str(getattr(config, "ANALYTICS_SALT", "") or getattr(config, "WEBAPP_SECRET", "") or "").strip()


def fingerprint(kind: str, identifier) -> str | None:
    """Return a keyed, domain-separated digest; never fall back to raw IDs."""
    secret = _salt()
    if not secret or identifier is None:
        return None
    payload = f"videl-analytics-v1:{kind}:{identifier}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def command_event(command: str, chat_id, user_id, chat_type: str, *, at=None) -> dict:
    event = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "at": at or datetime.now(timezone.utc),
        "command": str(command or "")[:64].casefold(),
        "chat_type": str(chat_type or "unknown")[:24],
    }
    chat_key = fingerprint("chat", chat_id)
    user_key = fingerprint("user", user_id)
    if chat_key:
        event["chat_key"] = chat_key
    if user_key:
        event["user_key"] = user_key
    return event


def recent_events(db, *, limit: int = 20, hours: int = 24, now=None) -> dict:
    """Versioned, bounded operations feed with no chat or user identifiers."""
    if db is None:
        return {"ok": False, "schema_version": EVENT_SCHEMA_VERSION, "events": []}
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=max(1, min(int(hours), 24)))
    limit = max(1, min(int(limit), 20))
    try:
        rows = db["command_events"].find(
            {"schema_version": EVENT_SCHEMA_VERSION, "at": {"$gte": since}},
            {"_id": 0, "schema_version": 1, "at": 1, "command": 1, "chat_type": 1},
        ).sort("at", -1).limit(limit)
        events = []
        for row in rows:
            at = row.get("at")
            if not isinstance(at, datetime):
                continue
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            command = str(row.get("command") or "")[:64].casefold()
            if not command or not all(char.isalnum() or char == "_" for char in command):
                continue
            chat_type = str(row.get("chat_type") or "unknown")
            if chat_type not in {"private", "group", "supergroup", "channel"}:
                chat_type = "unknown"
            events.append({"schema_version": EVENT_SCHEMA_VERSION,
                           "type": "command", "command": command,
                           "chat_type": chat_type, "at": at.astimezone(timezone.utc).isoformat()})
        return {"ok": True, "schema_version": EVENT_SCHEMA_VERSION, "events": events}
    except Exception:
        return {"ok": False, "schema_version": EVENT_SCHEMA_VERSION, "events": []}


def summarize(db, *, hours: int = 24, now=None) -> dict:
    """Return bounded aggregates with pseudonymous labels, never raw IDs."""
    if db is None:
        return {"ok": False, "error": "MongoDB is not connected"}
    hours = max(1, min(int(hours), 24))
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)
    selector = {"at": {"$gte": since}}
    try:
        collection = db["command_events"]
        total = int(collection.count_documents(selector))
        events = list(collection.find(
            selector,
            {"_id": 0, "at": 1, "command": 1, "chat_key": 1, "user_key": 1,
             "chat_id": 1, "user_id": 1},
        ).sort("at", -1).limit(MAX_EVENTS))
        events.reverse()
        bucket_count = max(1, min(24, hours))
        step = max(1, hours // bucket_count)
        first_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=bucket_count - 1)
        series = []
        for offset in range(bucket_count):
            point = first_hour + timedelta(hours=offset * step)
            series.append({"time": point.strftime("%H:%M"), "commands": 0})
        series_index = {first_hour + timedelta(hours=i * step): i for i in range(bucket_count)}
        chat_counts = Counter()
        command_counts = Counter()
        user_keys = set()
        for event in events:
            dt = event.get("at")
            if dt is None:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(timezone.utc)
            bucket = first_hour + timedelta(hours=((dt - first_hour).total_seconds() // (step * 3600)) * step)
            index = series_index.get(bucket)
            if index is not None:
                series[index]["commands"] += 1
            command = str(event.get("command") or "")[:64]
            if command:
                command_counts[command] += 1
            chat_key = event.get("chat_key") or fingerprint("chat", event.get("chat_id"))
            if chat_key:
                chat_counts[str(chat_key)] += 1
            user_key = event.get("user_key") or fingerprint("user", event.get("user_id"))
            if user_key:
                user_keys.add(str(user_key))
        top_chats = [
            {"id": f"chat-{key[:12]}", "commands": count}
            for key, count in chat_counts.most_common(10)
        ]
        return {
            "ok": True,
            "window_hours": hours,
            "total_commands": total,
            "active_users": len(user_keys) if _salt() and total <= len(events) else None,
            "series": series,
            "top_chats": top_chats,
            "top_commands": [{"command": name, "count": count} for name, count in command_counts.most_common(10)],
            "truncated": total > len(events),
            "identity_mode": "pseudonymous" if _salt() else "aggregate_only",
        }
    except Exception:
        return {"ok": False, "error": "Analytics could not be read"}
