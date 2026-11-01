"""Persistent review queue for severe warning-ladder actions."""
from __future__ import annotations

from datetime import datetime, timezone

SEVERE_ACTIONS = frozenset({"kick", "ban"})


def queue_review(db, chat_id: int, user_id: int, action: str, warning_count: int,
                 reason: str, actor: int | None = None, source: str = "bot") -> str:
    """Create or refresh one pending severe action per member and group."""
    if db is None:
        raise RuntimeError("MongoDB is unavailable")
    if action not in SEVERE_ACTIONS or int(chat_id) >= 0 or int(user_id) <= 0:
        raise ValueError("Invalid escalation review target")
    col = db["mgmt_escalations"]
    now = datetime.now(timezone.utc)
    selector = {"chat_id": int(chat_id), "user_id": int(user_id), "status": "open"}
    fields = {
        "action": action,
        "warning_count": max(1, int(warning_count)),
        "reason": str(reason or "Warning limit reached")[:400],
        "requested_by": int(actor) if isinstance(actor, int) and actor > 0 else None,
        "updated_at": now,
    }
    existing = col.find_one(selector, {"_id": 1})
    if existing:
        col.update_one(selector, {"$set": fields})
        identifier = str(existing["_id"])
    else:
        try:
            inserted = col.insert_one({**selector, **fields, "created_at": now})
            identifier = str(inserted.inserted_id)
        except Exception:
            # A second simultaneous request may win the partial unique index.
            existing = col.find_one(selector, {"_id": 1})
            if not existing:
                raise
            col.update_one(selector, {"$set": fields})
            identifier = str(existing["_id"])
    try:
        from videl.utils.audit import record
        record(db, int(chat_id), "escalation", action="review_requested",
               detail=f"member {int(user_id)}: {action} after {max(1, int(warning_count))} warnings",
               actor=actor if isinstance(actor, int) else None, source=source)
    except Exception:
        pass
    return identifier
