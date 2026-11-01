"""Per-group, admin-configured expiry for resolved member-history records.

Unconfigured categories are preserved. Live moderation state and immutable audit
records are deliberately outside this allowlist.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

CATEGORIES = {
    "case_notes": ("mgmt_case_notes", "ts", None),
    "resolved_reports": ("mgmt_reports", "resolved", {"status": {"$in": ["resolved", "dismissed"]}}),
    "resolved_join_requests": ("mgmt_join_requests", "resolved", None),
    "resolved_appeals": ("mgmt_appeals", "resolved_at", {"status": {"$in": ["accepted", "denied"]}}),
    "resolved_escalations": ("mgmt_escalations", "resolved_at", {"status": {"$in": ["approved", "rejected"]}}),
}
ALLOWED_DAYS = (30, 90, 180, 365)


def normalize(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    return {name: value if type(value) is int and value in ALLOWED_DAYS else None
            for name in CATEGORIES for value in [raw.get(name)]}


def save(db, chat_id: int, category: str, days: int | None) -> dict | None:
    if (db is None or int(chat_id) >= 0 or category not in CATEGORIES
            or (days is not None and (type(days) is not int or days not in ALLOWED_DAYS))):
        return None
    try:
        doc = db["mgmt_chat_settings"].find_one({"chat_id": int(chat_id)}, {"data_retention": 1}) or {}
        current = normalize(doc.get("data_retention"))
        current[category] = days
        db["mgmt_chat_settings"].update_one({"chat_id": int(chat_id)},
            {"$set": {"chat_id": int(chat_id), "data_retention": current}}, upsert=True)
        return current
    except Exception:
        return None


def cleanup_group_history(db, *, apply: bool = False, now: datetime | None = None,
                          chat_id: int | None = None) -> dict:
    """Preview or prune only expired, resolved history in explicitly configured groups."""
    if db is None or (chat_id is not None and (type(chat_id) is not int or chat_id >= 0)):
        return {"ok": False, "applied": apply, "groups": 0, "counts": {}, "errors": ["database or group"]}
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    stats = {"ok": True, "applied": bool(apply), "groups": 0, "counts": {}, "errors": []}
    try:
        selector = {"data_retention": {"$exists": True}}
        if chat_id is not None:
            selector["chat_id"] = int(chat_id)
        groups = db["mgmt_chat_settings"].find(
            selector, {"chat_id": 1, "data_retention": 1})
        for group in groups:
            try:
                chat_id = int(group.get("chat_id"))
                if chat_id >= 0:
                    continue
                stats["groups"] += 1
                policy = normalize(group.get("data_retention"))
                for category, days in policy.items():
                    if days is None:
                        continue
                    collection, timestamp, status_query = CATEGORIES[category]
                    cutoff = now - timedelta(days=days)
                    if category == "resolved_join_requests":
                        query = {"chat_id": chat_id, "$or": [
                            {"status": {"$in": ["approved", "declined"]},
                             "resolved": {"$type": "date", "$lt": cutoff}},
                            {"status": "expired", "ts": {"$type": "date", "$lt": cutoff}},
                        ]}
                    else:
                        query = {"chat_id": chat_id, timestamp: {"$type": "date", "$lt": cutoff}}
                        if status_query:
                            query.update(status_query)
                    col = db[collection]
                    key = f"{chat_id}:{category}"
                    # The same cutoff/status predicates are used for delete, so
                    # a row resolved after preview cannot be removed by stale IDs.
                    stats["counts"][key] = (col.delete_many(query).deleted_count if apply
                                              else col.count_documents(query))
            except Exception as exc:
                stats["ok"] = False
                stats["errors"].append(f"group:{group.get('chat_id', 'unknown')}:{type(exc).__name__}")
    except Exception as exc:
        stats["ok"] = False
        stats["errors"].append(f"settings:{type(exc).__name__}")
    return stats
