"""Mongo persistence for Videl browser listening rooms (not Telegram playback)."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from .web_music_rooms import (
    MAX_MEMBERS,
    MAX_ROOM_HOURS,
    ListeningRoomError,
    normalize_code,
    normalize_members,
    normalize_queue,
    playback_position,
    require_host,
    require_member,
    room_expiry,
)

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _now():
    return datetime.now(timezone.utc)


def _collection():
    from videl.utils.db import get_db
    database = get_db()
    if database is None:
        raise ListeningRoomError("Listening rooms are temporarily unavailable")
    return database["listening_rooms"]


def ensure_indexes(database):
    """Idempotent room indexes; safe to call during the app's normal index pass."""
    collection = database["listening_rooms"]
    collection.create_index("expires_at", expireAfterSeconds=0)
    collection.create_index([("members.user", 1), ("status", 1)])


def _public(room):
    playback = dict(room.get("playback") or {
        "track_id": None, "playing": False, "position": 0,
        "duration": 0, "anchored_at": room["created_at"],
    })
    if isinstance(playback.get("anchored_at"), datetime):
        playback["anchored_at"] = playback["anchored_at"].isoformat()
    members = normalize_members(room.get("members", []))
    public_members = [{"id": member.get("member_id"), "name": member["name"]} for member in members]
    host_member = next((member for member in members if member["user"] == room["host"]), None)
    return {
        "code": room["_id"],
        "host": host_member.get("member_id") if host_member else None,
        "members": public_members,
        "queue": normalize_queue(room.get("queue", [])),
        "playback": playback,
        "status": room.get("status", "open"),
        "version": int(room.get("version", 0)),
        "expires_at": room["expires_at"].isoformat(),
        "server_time": _now().isoformat(),
    }


def _find(code):
    code = normalize_code(code)
    room = _collection().find_one({"_id": code})
    if not room:
        raise ListeningRoomError("That listening room is unavailable")
    room_expiry(room.get("created_at"), _now())
    if room.get("status") != "open":
        raise ListeningRoomError("That listening room is closed")
    return room


def create(actor, name):
    if not isinstance(actor, int) or isinstance(actor, bool) or actor <= 0:
        raise ListeningRoomError("A signed-in player is required")
    name = " ".join(str(name or "Listener").split())[:64] or "Listener"
    collection = _collection()
    now = _now()
    for _ in range(8):
        code = "".join(secrets.choice(ALPHABET) for _ in range(8))
        document = {
            "_id": code,
            "host": actor,
            "members": [{"user": actor, "member_id": secrets.token_urlsafe(12), "name": name}],
            "queue": [],
            "playback": {"track_id": None, "playing": False, "position": 0,
                         "duration": 0, "anchored_at": now},
            "status": "open",
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(hours=MAX_ROOM_HOURS),
        }
        try:
            collection.insert_one(document)
            return _public(document)
        except Exception as error:
            # Retry only the rare code collision. Storage faults are surfaced.
            if getattr(error, "code", None) == 11000:
                continue
            raise
    raise ListeningRoomError("Could not create a room; try again")


def read(code, actor):
    room = _find(code)
    require_member(room, actor)
    return _public(room)


def join(code, actor, name):
    if not isinstance(actor, int) or isinstance(actor, bool) or actor <= 0:
        raise ListeningRoomError("A signed-in player is required")
    room = _find(code)
    if any(member.get("user") == actor for member in room.get("members", [])):
        return _public(room)
    if len(room.get("members", [])) >= MAX_MEMBERS:
        raise ListeningRoomError("This listening room is full", 409)
    members = normalize_members(room.get("members", []))
    members.append({"user": actor, "member_id": secrets.token_urlsafe(12),
                    "name": " ".join(str(name or "Listener").split())[:64] or "Listener"})
    result = _collection().update_one(
        {"_id": room["_id"], "version": room["version"], "status": "open",
         "expires_at": {"$gt": _now()}, "$expr": {"$lt": [{"$size": "$members"}, MAX_MEMBERS]},
         "members.user": {"$ne": actor}},
        {"$set": {"members": members, "updated_at": _now()}, "$inc": {"version": 1}},
    )
    if not result.modified_count:
        raise ListeningRoomError("The room changed; refresh and try joining again", 409)
    return read(code, actor)


def leave(code, actor):
    room = _find(code)
    require_member(room, actor)
    if room["host"] == actor:
        result = _collection().update_one(
            {"_id": room["_id"], "version": room["version"], "status": "open"},
            {"$set": {"status": "closed", "updated_at": _now()}, "$inc": {"version": 1}},
        )
    else:
        members = [member for member in room["members"] if member.get("user") != actor]
        result = _collection().update_one(
            {"_id": room["_id"], "version": room["version"], "status": "open"},
            {"$set": {"members": members, "updated_at": _now()}, "$inc": {"version": 1}},
        )
    if not result.modified_count:
        raise ListeningRoomError("The room changed; refresh and try again", 409)
    return {"closed": room["host"] == actor}


def mutate(code, actor, body):
    room = _find(code)
    require_host(room, actor)
    if not isinstance(body, dict):
        raise ListeningRoomError("A room action is required")
    action = body.get("action")
    now = _now()
    updates = {"updated_at": now}
    if action == "queue":
        updates["queue"] = normalize_queue(body.get("queue"))
    elif action == "playback":
        track_id = body.get("track_id")
        track = next((item for item in room.get("queue", []) if item.get("video_id") == track_id), None)
        if track is None:
            raise ListeningRoomError("Choose a track from the room queue")
        playing = body.get("playing")
        if not isinstance(playing, bool):
            raise ListeningRoomError("Choose whether playback is playing or paused")
        try:
            position = float(body.get("position", 0))
            duration = float(body.get("duration", 0))
        except (TypeError, ValueError, OverflowError):
            raise ListeningRoomError("Playback position is invalid") from None
        intent = {"track_id": track_id, "playing": playing, "position": position,
                  "duration": duration, "anchored_at": now}
        playback_position(intent, now)
        updates["playback"] = intent
    elif action == "close":
        updates["status"] = "closed"
    else:
        raise ListeningRoomError("Unknown listening-room action")
    result = _collection().update_one(
        {"_id": room["_id"], "version": room["version"], "host": actor,
         "status": "open", "expires_at": {"$gt": now}},
        {"$set": updates, "$inc": {"version": 1}},
    )
    if not result.modified_count:
        raise ListeningRoomError("The room changed; refresh before retrying", 409)
    if action == "close":
        return {"closed": True, "version": room["version"] + 1}
    return read(code, actor)
