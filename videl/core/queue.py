"""Per-chat in-memory playback queues and restart-safe upcoming metadata.

The active track is recorded as an interrupted summary only. On process restart
it is never replayed; admins can explicitly restore saved upcoming tracks after
starting fresh playback. Persisted records contain YouTube IDs and display
metadata only—never stream URLs, temporary paths, or requester identities.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

chat_queues: dict[int, list] = {}
_recoverable: dict[int, dict] = {}
_revisions: dict[int, int] = {}
_persist_locks: dict[int, asyncio.Lock] = {}
_persist_tasks: set[asyncio.Task] = set()
log = logging.getLogger(__name__)
MAX_PERSISTED_UPCOMING = 100


def _video_id(song: dict) -> str | None:
    candidate = str(song.get("video_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
        url = str(song.get("url") or "")
        try:
            parsed = urlparse(url)
            if parsed.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
                candidate = parse_qs(parsed.query).get("v", [""])[0]
            elif parsed.hostname in {"youtu.be", "www.youtu.be"}:
                candidate = parsed.path.strip("/").split("/")[0]
        except Exception:
            candidate = ""
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate or "") else None


def _record(song: dict) -> dict | None:
    video_id = _video_id(song)
    if not video_id:
        return None
    try:
        seconds = max(0, min(int(float(song.get("duration_seconds") or 0)), 7 * 24 * 3600))
    except (TypeError, ValueError, OverflowError):
        seconds = 0
    return {
        "video_id": video_id,
        "title": str(song.get("title") or "Untitled track")[:200],
        "duration": str(song.get("duration") or "Live")[:24],
        "duration_seconds": seconds,
        "video": bool(song.get("video")),
    }


def _recovered_song(record: dict) -> dict:
    return {
        **record,
        "url": f"https://www.youtube.com/watch?v={record['video_id']}",
        "requester": "Restored queue",
        "requester_id": 0,
    }


def _schedule_persist(chat_id: int) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_persist_latest(chat_id))
    _persist_tasks.add(task)
    task.add_done_callback(_persist_tasks.discard)


def note_queue_mutation(chat_id: int) -> None:
    """Persist a queue mutation; safe to call from synchronous queue helpers."""
    _revisions[chat_id] = _revisions.get(chat_id, 0) + 1
    _schedule_persist(chat_id)


def _write_snapshot(chat_id: int, revision: int, tracks: list) -> None:
    from videl.utils.db import get_db
    db = get_db()
    if db is None:
        return
    active = _record(tracks[0]) if tracks else None
    upcoming = [item for song in tracks[1:] if (item := _record(song)) is not None][:MAX_PERSISTED_UPCOMING]
    doc = {
        "_id": int(chat_id), "version": 1, "revision": int(revision),
        "active_interrupted": active, "upcoming": upcoming,
        "updated_at": datetime.now(timezone.utc),
    }
    collection = db["music_queue_recovery"]
    try:
        collection.update_one(
            {"_id": int(chat_id), "revision": {"$lt": int(revision)}},
            {"$set": doc}, upsert=True,
        )
    except Exception as exc:
        # A duplicate-key race means another writer already has a newer revision.
        if type(exc).__name__ != "DuplicateKeyError":
            raise


async def _persist_latest(chat_id: int) -> None:
    lock = _persist_locks.setdefault(chat_id, asyncio.Lock())
    async with lock:
        revision = _revisions.get(chat_id, 0)
        snapshot = list(chat_queues.get(chat_id, ()))
        try:
            await asyncio.to_thread(_write_snapshot, chat_id, revision, snapshot)
        except Exception as exc:
            log.info("Queue recovery snapshot unavailable (%s)", type(exc).__name__)


async def initialize_recovery() -> int:
    """Load safe pending snapshots into memory without starting or joining calls."""
    from videl.utils.db import get_db
    db = get_db()
    if db is None:
        return 0
    def read():
        return list(db["music_queue_recovery"].find(
            {"version": 1, "upcoming": {"$exists": True, "$ne": []}},
            {"_id": 1, "revision": 1, "active_interrupted": 1, "upcoming": 1},
        ).limit(1000))
    try:
        docs = await asyncio.to_thread(read)
    except Exception as exc:
        log.info("Queue recovery scan unavailable (%s)", type(exc).__name__)
        return 0
    loaded = 0
    for doc in docs:
        chat_id = doc.get("_id")
        upcoming = doc.get("upcoming")
        if not isinstance(chat_id, int) or not isinstance(upcoming, list):
            continue
        safe = []
        for row in upcoming[:MAX_PERSISTED_UPCOMING]:
            if not isinstance(row, dict):
                continue
            parsed = _record(row)
            # Stored rows use video_id rather than a URL; validate directly.
            video_id = row.get("video_id")
            if not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                continue
            if parsed is None:
                parsed = {
                    "video_id": video_id,
                    "title": str(row.get("title") or "Untitled track")[:200],
                    "duration": str(row.get("duration") or "Live")[:24],
                    "duration_seconds": max(0, min(int(row.get("duration_seconds") or 0), 7 * 24 * 3600)),
                    "video": bool(row.get("video")),
                }
            safe.append(parsed)
        if safe:
            _recoverable[chat_id] = {"tracks": safe, "active_interrupted": doc.get("active_interrupted"), "revision": int(doc.get("revision", 0))}
            _revisions[chat_id] = max(_revisions.get(chat_id, 0), int(doc.get("revision", 0)))
            loaded += 1
    return loaded


def recovery_info(chat_id: int) -> dict | None:
    data = _recoverable.get(int(chat_id))
    return {"count": len(data["tracks"]), "active_interrupted": data.get("active_interrupted")} if data else None


def restore_upcoming(chat_id: int) -> int:
    """Append saved upcoming tracks only while a fresh track is already active."""
    data = _recoverable.get(int(chat_id))
    tracks = chat_queues.get(int(chat_id))
    if not data or not tracks:
        return 0
    restored = [_recovered_song(row) for row in data["tracks"]]
    tracks.extend(restored)
    _recoverable.pop(int(chat_id), None)
    note_queue_mutation(int(chat_id))
    return len(restored)


def get_queue(chat_id: int) -> list:
    return chat_queues.get(chat_id, [])


def add_to_queue(chat_id: int, song: dict) -> int:
    queue = chat_queues.setdefault(chat_id, [])
    queue.append(song)
    note_queue_mutation(chat_id)
    return len(queue)


def insert_next(chat_id: int, song: dict, *, offset: int = 0) -> int:
    """Insert after the current item, preserving order for a batch of tracks."""
    queue = chat_queues.setdefault(chat_id, [])
    index = min(1 + max(0, int(offset)), len(queue)) if queue else 0
    queue.insert(index, song)
    note_queue_mutation(chat_id)
    return index + 1


def pop_current(chat_id: int) -> dict | None:
    queue = chat_queues.get(chat_id)
    if not queue:
        return None
    result = queue.pop(0)
    note_queue_mutation(chat_id)
    return result


def remove_from_queue(chat_id: int, index: int) -> dict | None:
    queue = chat_queues.get(chat_id)
    if not queue or index < 0 or index >= len(queue):
        return None
    result = queue.pop(index)
    note_queue_mutation(chat_id)
    return result


def peek_current(chat_id: int) -> dict | None:
    queue = chat_queues.get(chat_id)
    return queue[0] if queue else None


def peek_next(chat_id: int) -> dict | None:
    queue = chat_queues.get(chat_id)
    return queue[1] if queue and len(queue) >= 2 else None


def remove_upcoming(chat_id: int, position: int) -> dict | None:
    tracks = chat_queues.get(chat_id)
    position = int(position)
    if tracks is None or position < 1 or position >= len(tracks):
        return None
    result = tracks.pop(position)
    note_queue_mutation(chat_id)
    return result


def move_upcoming(chat_id: int, source: int, destination: int) -> bool:
    tracks = chat_queues.get(chat_id)
    source, destination = int(source), int(destination)
    if tracks is None or source < 1 or destination < 1 or source >= len(tracks) or destination >= len(tracks) or source == destination:
        return False
    tracks.insert(destination, tracks.pop(source))
    note_queue_mutation(chat_id)
    return True


def promote_upcoming(chat_id: int, position: int) -> dict | None:
    tracks = chat_queues.get(chat_id)
    position = int(position)
    if tracks is None or position < 1 or position >= len(tracks):
        return None
    selected = tracks.pop(position)
    tracks.insert(1, selected)
    note_queue_mutation(chat_id)
    return selected


def restore_snapshot(chat_id: int, snapshot: list) -> None:
    tracks = chat_queues.setdefault(chat_id, [])
    tracks[:] = list(snapshot)
    note_queue_mutation(chat_id)


def clear_queue(chat_id: int) -> list:
    removed = chat_queues.pop(chat_id, [])
    note_queue_mutation(chat_id)
    return removed


def queue_size(chat_id: int) -> int:
    return len(chat_queues.get(chat_id, []))


def is_empty(chat_id: int) -> bool:
    return queue_size(chat_id) == 0


def clear_pending(chat_id: int) -> list:
    queue = chat_queues.get(chat_id)
    if not queue:
        return []
    removed = queue[1:]
    del queue[1:]
    note_queue_mutation(chat_id)
    return removed
