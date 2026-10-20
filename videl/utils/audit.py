"""Append-only audit trail for every owner-driven group change.

The web panel is powerful: one click can lock seventeen content types in a
group. Without a record, "who turned antispam off?" is unanswerable. This
module stores one small row per change and never raises into the caller — an
audit failure must not roll back a change that Telegram already confirmed.

Stored rows are plain data: no HTML, no credentials, no message bodies. Text is
collapsed to a single line and truncated before it is written.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from bson import ObjectId

log = logging.getLogger(__name__)

COLLECTION = "mgmt_audit"
RETENTION_DAYS = 180
MAX_DETAIL = 240
MAX_ROWS = 100

# A stable vocabulary keeps the web filter honest: the UI may only offer these.
KINDS = (
    "settings",
    "preset",
    "warn_limit",
    "welcome",
    "goodbye",
    "rules",
    "blacklist",
    "blacklist_mode",
    "note",
    "filter",
    "approval",
    "warn",
    "warn_reset",
    "automation",
    "commands",
    "recording",
    "purge",
    "join_request",
    "report",
)

_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
_SPACES = re.compile(r"\s+")


def clean(value, limit: int = MAX_DETAIL) -> str:
    """One safe line of human text; never markup or control characters."""
    text = _SPACES.sub(" ", _CONTROL.sub(" ", str(value or ""))).strip()
    return text[:limit]


def _col(db):
    return db[COLLECTION] if db is not None else None


def index(db) -> None:
    """Cheap-to-create indexes; three writes at most, ignored when unavailable."""
    col = _col(db)
    if col is None:
        return
    try:
        col.create_index([("chat_id", 1), ("ts", -1)])
        col.create_index("ts", expireAfterSeconds=RETENTION_DAYS * 86400)
    except Exception:
        log.debug("audit indexes were not created", exc_info=True)


def record(db, chat_id: int, kind: str, *, action: str = "", detail: str = "",
           actor=None, source: str = "web") -> bool:
    """Store one event. Returns False instead of raising when storage is down."""
    col = _col(db)
    if col is None or kind not in KINDS:
        return False
    row = {
        "chat_id": int(chat_id),
        "kind": kind,
        "action": clean(action or kind, 48),
        "detail": clean(detail),
        "actor": int(actor) if isinstance(actor, int) else None,
        "source": source if source in {"web", "bulk", "bot", "system"} else "web",
        "ts": datetime.now(timezone.utc),
    }
    try:
        index(db)
        col.insert_one(row)
        return True
    except Exception:
        log.debug("audit write failed", exc_info=True)
        return False


def record_bot(chat_id: int, kind: str, *, action: str = "", detail: str = "", actor=None) -> bool:
    """Best-effort audit row for a change made through the bot.

    The caller already changed something Telegram confirmed; an audit failure
    must never turn that into an error, so this swallows its own exceptions.
    """
    try:
        from videl.utils.db import get_db

        return record(get_db(), chat_id, kind, action=action, detail=detail,
                      actor=actor if isinstance(actor, int) else None, source="bot")
    except Exception:
        log.debug("bot audit write failed", exc_info=True)
        return False


def object_id(value) -> ObjectId | None:
    """Parse a stored row id, or None when the caller sent something else."""
    try:
        return ObjectId(str(value)) if ObjectId.is_valid(str(value)) else None
    except Exception:
        return None


def recent(db, chat_id: int, *, limit: int = 40, kind: str | None = None,
           before: datetime | None = None,
           before_id=None) -> list[dict]:
    """Newest first. A cursor is the last row already shown.

    Mongo stores milliseconds, so a bulk save can produce several rows with
    the same ``ts``. A timestamp-only cursor would skip the rest of that tie
    group; passing the row id as well makes the page boundary exact.
    """
    col = _col(db)
    if col is None:
        return []
    try:
        limit = max(1, min(int(limit), MAX_ROWS))
    except (TypeError, ValueError):
        limit = 40
    query: dict = {"chat_id": int(chat_id)}
    if kind in KINDS:
        query["kind"] = kind
    if isinstance(before, datetime):
        # PyMongo stores UTC without tzinfo; a cursor must match that shape.
        if before.tzinfo is not None:
            before = before.astimezone(timezone.utc).replace(tzinfo=None)
        oid = object_id(before_id) if before_id else None
        if oid is not None:
            query["$or"] = [{"ts": {"$lt": before}}, {"ts": before, "_id": {"$lt": oid}}]
        else:
            query["ts"] = {"$lt": before}
    try:
        rows = list(col.find(query).sort([("ts", -1), ("_id", -1)]).limit(limit))
    except Exception:
        return []
    output = []
    for row in rows:
        stamp = row.get("ts")
        if isinstance(stamp, datetime):
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            stamp = stamp.astimezone(timezone.utc)
        output.append({
            "id": str(row.get("_id", "")),
            "kind": str(row.get("kind", "")),
            "action": str(row.get("action", "")),
            "detail": str(row.get("detail", "")),
            "actor": row.get("actor"),
            "source": str(row.get("source", "web")),
            "at": stamp.isoformat() if isinstance(stamp, datetime) else None,
        })
    return output


def prune(db, chat_id: int, *, days: int = RETENTION_DAYS) -> int:
    """Delete rows past retention for one group; also handled by the TTL index."""
    col = _col(db)
    if col is None:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))
    try:
        return col.delete_many({"chat_id": int(chat_id), "ts": {"$lt": cutoff}}).deleted_count
    except Exception:
        return 0
