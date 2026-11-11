"""Pure validation and policy for public browser listening rooms.

This module is intentionally independent of Telegram voice playback, the
Telegram music queue, the Arcade game-room store, and owner-only Studio APIs.
It contains no persistence or route registration.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
ROOM_CODE = re.compile(r"^[A-HJ-NP-Z2-9]{8}$")
MAX_MEMBERS = 8
MAX_QUEUE = 100
MAX_TITLE = 200
MAX_CHANNEL = 120
MAX_DURATION = 24
MAX_ROOM_HOURS = 12
MAX_POSITION_SECONDS = 24 * 60 * 60


class ListeningRoomError(ValueError):
    """A caller supplied data or an action outside the room policy."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def normalize_code(value):
    code = str(value or "").strip().upper()
    if not ROOM_CODE.fullmatch(code):
        raise ListeningRoomError("That listening-room invite is not valid")
    return code


def normalize_track(value):
    """Return a small, safe metadata record; never accept stream URLs/tokens."""
    if not isinstance(value, dict):
        raise ListeningRoomError("Choose a valid track")
    video_id = str(value.get("video_id") or "")
    title = " ".join(str(value.get("title") or "").split())[:MAX_TITLE]
    if not VIDEO_ID.fullmatch(video_id) or not title:
        raise ListeningRoomError("Choose a valid track")
    provider = value.get("provider")
    if provider not in (None, "videl", "typetube"):
        raise ListeningRoomError("That track source is not supported in rooms")
    channel = " ".join(str(value.get("channel") or "").split())[:MAX_CHANNEL]
    duration = " ".join(str(value.get("duration") or "").split())[:MAX_DURATION]
    # Derive the image URL from the validated ID; do not persist a caller URL.
    return {
        "video_id": video_id,
        "title": title,
        "channel": channel,
        "duration": duration,
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "provider": provider if provider == "typetube" else "videl",
    }


def normalize_queue(value):
    if not isinstance(value, list):
        raise ListeningRoomError("A track queue is required")
    if len(value) > MAX_QUEUE:
        raise ListeningRoomError(f"A room queue can contain at most {MAX_QUEUE} tracks")
    tracks = [normalize_track(track) for track in value]
    ids = [track["video_id"] for track in tracks]
    if len(ids) != len(set(ids)):
        raise ListeningRoomError("A track may appear only once in a room queue")
    return tracks


def normalize_members(value):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_MEMBERS:
        raise ListeningRoomError(f"A room must have between 1 and {MAX_MEMBERS} members")
    normalized = []
    seen = set()
    for row in value:
        if not isinstance(row, dict):
            raise ListeningRoomError("A room member is invalid")
        user = row.get("user")
        if not isinstance(user, int) or isinstance(user, bool) or user <= 0 or user in seen:
            raise ListeningRoomError("A room member identity is invalid")
        seen.add(user)
        name = " ".join(str(row.get("name") or "Listener").split())[:64] or "Listener"
        member = {"user": user, "name": name}
        member_id = row.get("member_id")
        if isinstance(member_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{16}", member_id):
            member["member_id"] = member_id
        normalized.append(member)
    return normalized


def require_member(room, actor):
    members = room.get("members") if isinstance(room, dict) else None
    if not isinstance(members, list) or not any(
        isinstance(member, dict) and member.get("user") == actor for member in members
    ):
        raise ListeningRoomError("You are not a member of this room", 403)


def require_host(room, actor):
    require_member(room, actor)
    if room.get("host") != actor:
        raise ListeningRoomError("Only the host can change shared playback", 403)


def playback_position(intent, now=None):
    """Estimate seconds from a server-anchored intent, clamped to track length."""
    if not isinstance(intent, dict):
        raise ListeningRoomError("Playback state is unavailable")
    try:
        position = float(intent.get("position", 0))
        duration = float(intent.get("duration", 0))
        anchor = intent.get("anchored_at")
        if isinstance(anchor, str):
            anchor = datetime.fromisoformat(anchor.replace("Z", "+00:00"))
        if not isinstance(anchor, datetime):
            raise ValueError
        anchor = anchor.replace(tzinfo=timezone.utc) if anchor.tzinfo is None else anchor.astimezone(timezone.utc)
        current = now or datetime.now(timezone.utc)
        current = current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        raise ListeningRoomError("Playback state is invalid") from None
    if not 0 <= position <= MAX_POSITION_SECONDS or not 0 <= duration <= MAX_POSITION_SECONDS:
        raise ListeningRoomError("Playback position is outside the supported range")
    if intent.get("playing") is True:
        position += max(0.0, (current - anchor).total_seconds())
    return min(position, duration) if duration > 0 else position


def room_expiry(created_at, now=None):
    """Return the hard expiry; cleanup jobs are not relied on for enforcement."""
    if not isinstance(created_at, datetime):
        raise ListeningRoomError("Room creation time is invalid")
    created_at = created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else created_at.astimezone(timezone.utc)
    expiry = created_at + timedelta(hours=MAX_ROOM_HOURS)
    current = now or datetime.now(timezone.utc)
    current = current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)
    if expiry <= current:
        raise ListeningRoomError("This listening room has expired")
    return expiry
