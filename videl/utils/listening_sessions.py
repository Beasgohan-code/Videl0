"""Persistent, bounded one-time scheduled listening-session announcements."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

MAX_TITLE = 100
MAX_AHEAD = timedelta(days=30)


def parse_schedule(text: str, *, now: datetime | None = None) -> tuple[datetime, str]:
    if not isinstance(text, str) or "|" not in text:
        raise ValueError("Reply in this format: YYYY-MM-DD HH:MM UTC | Session title")
    when_text, title = (part.strip() for part in text.split("|", 1))
    if not when_text.upper().endswith(" UTC"):
        raise ValueError("Include the UTC timezone explicitly: YYYY-MM-DD HH:MM UTC | Session title")
    when_text = when_text[:-4].strip()
    try:
        due = datetime.strptime(when_text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("Use a valid UTC date and time: YYYY-MM-DD HH:MM UTC | Session title") from None
    title = title.strip()
    if not title or len(title) > MAX_TITLE:
        raise ValueError(f"Session titles must be 1–{MAX_TITLE} characters.")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if due < now + timedelta(minutes=1) or due > now + MAX_AHEAD:
        raise ValueError("Choose a start time at least one minute from now and within the next 30 days.")
    return due, title


def schedule(db, chat_id: int, actor_id: int, due: datetime, title: str) -> str | None:
    if db is None or int(chat_id) >= 0 or not isinstance(due, datetime) or due.tzinfo is None:
        return None
    try:
        col = db["listening_sessions"]
        existing = col.count_documents({"chat_id": int(chat_id), "status": {"$in": ["scheduled", "sending"]}})
        if existing >= 5:
            return None
        identifier = token_urlsafe(9).replace("-", "a").replace("_", "b")
        col.insert_one({"_id": identifier, "chat_id": int(chat_id), "actor_id": int(actor_id),
                        "due_at": due.astimezone(timezone.utc), "title": title.strip()[:MAX_TITLE],
                        "status": "scheduled", "attempts": 0, "created_at": datetime.now(timezone.utc)})
        return identifier
    except Exception:
        return None


def pending(db, chat_id: int) -> list[dict]:
    if db is None:
        return []
    try:
        return list(db["listening_sessions"].find(
            {"chat_id": int(chat_id), "status": "scheduled"},
            {"_id": 1, "due_at": 1, "title": 1}).sort("due_at", 1).limit(5))
    except Exception:
        return []


def cancel(db, chat_id: int, identifier: str) -> bool:
    if db is None or not isinstance(identifier, str):
        return False
    try:
        result = db["listening_sessions"].update_one(
            {"_id": identifier, "chat_id": int(chat_id), "status": "scheduled"},
            {"$set": {"status": "cancelled", "finished_at": datetime.now(timezone.utc)}})
        return bool(result.modified_count)
    except Exception:
        return False


def claim_due(db, *, now: datetime | None = None) -> dict | None:
    if db is None:
        return None
    now = now or datetime.now(timezone.utc)
    stale = now - timedelta(minutes=5)
    try:
        from pymongo import ReturnDocument
        return db["listening_sessions"].find_one_and_update(
            {"due_at": {"$lte": now}, "attempts": {"$lt": 3},
             "$or": [{"status": "scheduled"}, {"status": "sending", "claimed_at": {"$lt": stale}}]},
            {"$set": {"status": "sending", "claimed_at": now}, "$inc": {"attempts": 1}},
            sort=[("due_at", 1)], return_document=ReturnDocument.AFTER)
    except Exception:
        return None


def finish(db, identifier: str, *, sent: bool) -> bool:
    if db is None:
        return False
    try:
        doc = db["listening_sessions"].find_one({"_id": identifier, "status": "sending"}, {"attempts": 1})
        if not doc:
            return False
        status = "sent" if sent else ("failed" if int(doc.get("attempts", 0)) >= 3 else "scheduled")
        result = db["listening_sessions"].update_one(
            {"_id": identifier, "status": "sending"},
            {"$set": {"status": status,
                       "finished_at": datetime.now(timezone.utc) if status in {"sent", "failed"} else None}})
        return bool(result.modified_count)
    except Exception:
        return False
