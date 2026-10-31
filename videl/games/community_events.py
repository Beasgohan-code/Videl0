"""Telegram group events with RSVP-only follow-through and reminders."""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
EVENT_CODE = re.compile(r"^[A-HJ-NP-Z2-9]{8}$")
ROOM_CODE = re.compile(r"^[A-HJ-NP-Z2-9]{4,8}$")
MAX_TITLE = 100
MAX_DESCRIPTION = 700
REMINDERS = (("24h", 86400), ("1h", 3600), ("15m", 900))


class EventError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _collection():
    from videl.utils.db import get_db
    db = get_db()
    if db is None:
        raise EventError("Events are temporarily unavailable", 503)
    return db["community_events"]


def _now():
    return datetime.now(timezone.utc)


def _code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


def _start_value(value):
    try:
        starts = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise EventError("Choose a valid event date and time with a timezone") from None
    if starts.tzinfo is None or starts.utcoffset() is None:
        raise EventError("Event time must include a timezone")
    return starts.astimezone(timezone.utc)


def _reminder_rows(starts, now):
    return [{"key": key, "due_at": starts - timedelta(seconds=seconds), "status": "pending"}
            for key, seconds in REMINDERS if starts - timedelta(seconds=seconds) > now]


def _clean(doc, viewer=None):
    if not doc:
        return None
    out = dict(doc)
    out.pop("_id", None)
    out["id"] = str(doc.get("code", ""))
    creator_id = int(doc.get("creator_id", 0))
    out.pop("creator_id", None)
    out["creator"] = str(doc.get("creator_name") or "Host")
    out["can_manage"] = viewer is not None and int(viewer) == creator_id
    starts = doc.get("starts_at")
    if isinstance(starts, datetime):
        if starts.tzinfo is None:
            starts = starts.replace(tzinfo=timezone.utc)
        out["starts_at"] = starts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    attendees = list(doc.get("attendees", []))
    counts = {"going": 0, "maybe": 0, "not_going": 0}
    mine = None
    for attendee in attendees:
        status = attendee.get("status")
        if status in counts:
            counts[status] += 1
        if viewer is not None and int(attendee.get("user_id", -1)) == int(viewer):
            mine = status
    out["rsvp_counts"] = counts
    out["rsvp_total"] = sum(counts.values())
    out["my_rsvp"] = mine
    out["attendees"] = [{"name": str(item.get("name") or "Member"), "status": "going"}
                         for item in attendees if item.get("status") == "going"]
    out.pop("attendees_private", None)
    out["rsvps"] = []
    return out


def create(creator_id, creator_name, body, chat_id, chat_title):
    title = str(body.get("title", "")).strip()[:MAX_TITLE]
    description = str(body.get("description", "")).strip()[:MAX_DESCRIPTION]
    if not title:
        raise EventError("Add an event title")
    starts = _start_value(body.get("starts_at"))
    now = _now()
    if starts < now + timedelta(minutes=5) or starts > now + timedelta(days=90):
        raise EventError("Events must be at least 5 minutes and no more than 90 days away")
    game_room = str(body.get("game_room", "")).strip().upper()
    if game_room and not ROOM_CODE.fullmatch(game_room):
        raise EventError("Enter a valid Arcade room code")
    code = _code()
    doc = {
        "_id": code, "code": code, "creator_id": int(creator_id), "creator_name": str(creator_name or "Host")[:100],
        "chat_id": int(chat_id), "chat_title": str(chat_title or "Telegram group")[:150],
        "title": title, "description": description, "starts_at": starts,
        "music_query": str(body.get("music_query", "")).strip()[:120], "game_room": game_room,
        "status": "upcoming", "created_at": now, "attendees": [],
        "reminders": _reminder_rows(starts, now),
    }
    _collection().insert_one(doc)
    return _clean(doc, creator_id)


def get(event_id, viewer=None):
    code = str(event_id).upper()
    if not EVENT_CODE.fullmatch(code):
        raise EventError("That event link is not valid")
    doc = _collection().find_one({"_id": code})
    if not doc:
        raise EventError("This event could not be found", 404)
    return _clean(doc, viewer)


def list_for(user_id):
    uid = int(user_id)
    cursor = _collection().find({"$or": [{"creator_id": uid}, {"attendees.user_id": uid}]}).sort("starts_at", 1).limit(100)
    return [_clean(doc, uid) for doc in cursor if doc.get("status") != "cancelled" or doc.get("creator_id") == uid]


def rsvp(event_id, user_id, display_name, status):
    if status not in ("going", "maybe", "not_going"):
        raise EventError("Choose Going, Maybe, or Can't go")
    event = get(event_id, user_id)
    if event.get("status") == "cancelled":
        raise EventError("This event has been cancelled", 409)
    collection = _collection()
    collection.update_one({"_id": event["id"]}, {"$pull": {"attendees": {"user_id": int(user_id)}}})
    collection.update_one({"_id": event["id"]}, {"$push": {"attendees": {
        "user_id": int(user_id), "name": str(display_name or "Member")[:100], "status": status, "updated_at": _now()
    }}})
    return get(event_id, user_id)


def update(event_id, actor_id, body):
    event = get(event_id, actor_id)
    if not event["can_manage"]:
        raise EventError("Only the event host can edit it", 403)
    if event.get("status") != "upcoming":
        raise EventError("Only upcoming events can be edited", 409)
    title = str(body.get("title", "")).strip()[:MAX_TITLE]
    if not title:
        raise EventError("Add an event title")
    starts = _start_value(body.get("starts_at"))
    now = _now()
    if starts < now + timedelta(minutes=5) or starts > now + timedelta(days=90):
        raise EventError("Events must be at least 5 minutes and no more than 90 days away")
    room = str(body.get("game_room", "")).strip().upper()
    if room and not ROOM_CODE.fullmatch(room):
        raise EventError("Enter a valid Arcade room code")
    _collection().update_one({"_id": event["id"], "creator_id": int(actor_id), "status": "upcoming"}, {"$set": {
        "title": title, "description": str(body.get("description", "")).strip()[:MAX_DESCRIPTION],
        "starts_at": starts, "music_query": str(body.get("music_query", "")).strip()[:120],
        "game_room": room, "reminders": _reminder_rows(starts, now), "updated_at": now,
    }})
    return get(event_id, actor_id)


def cancel(event_id, actor_id):
    event = get(event_id, actor_id)
    if not event["can_manage"]:
        raise EventError("Only the event host can cancel it", 403)
    if event.get("status") == "cancelled":
        return event
    result = _collection().update_one({"_id": event["id"], "status": "upcoming"}, {"$set": {
        "status": "cancelled", "cancelled_at": _now(), "reminders.$[reminder].status": "cancelled"
    }}, array_filters=[{"reminder.status": "pending"}])
    if hasattr(result, "matched_count") and not result.matched_count:
        raise EventError("This event can no longer be cancelled", 409)
    return get(event_id, actor_id)


def dispatch_reminder():
    """Claim and deliver one due reminder; retries after Telegram failures."""
    from pymongo import ReturnDocument
    from videl.utils.bot_api import call_bot_api
    now = _now()
    collection = _collection()
    event = collection.find_one_and_update(
        {"status": "upcoming", "reminders": {"$elemMatch": {"status": "pending", "due_at": {"$lte": now}}}},
        {"$set": {"reminders.$.status": "sending"}},
        sort=[("starts_at", 1)], return_document=ReturnDocument.AFTER,
    )
    if not event:
        return False
    reminder = next((item for item in event.get("reminders", []) if item.get("status") == "sending"), None)
    if not reminder:
        return False
    start = event["starts_at"]
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    minutes = max(1, round((start - now).total_seconds() / 60))
    text = f"Reminder: {event['title']} starts in about {minutes} minutes ({start.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}). RSVP: https://videl.studio/?tab=arcade&event={event['_id']}"
    status, result = call_bot_api("sendMessage", {"chat_id": int(event["chat_id"]), "text": text, "disable_web_page_preview": True})
    delivered = status == 200 and isinstance(result, dict) and result.get("ok")
    collection.update_one({"_id": event["_id"], "reminders.key": reminder["key"]}, {"$set": {
        "reminders.$.status": "sent" if delivered else "pending",
        "reminders.$.sent_at": now if delivered else None,
        "reminders.$.last_attempt_at": now,
    }})
    return bool(delivered)


def summary(event):
    """Summarize only the event's RSVP records, never group message history."""
    counts = event.get("rsvp_counts") or {}
    return {"going": int(counts.get("going", 0)), "maybe": int(counts.get("maybe", 0)),
            "not_going": int(counts.get("not_going", 0)), "responded": int(sum(counts.values()))}
