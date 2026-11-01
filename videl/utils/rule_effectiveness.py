"""Aggregate rule-hit and moderator-feedback counters without member IDs."""
from __future__ import annotations

from datetime import datetime, timezone

RULES = ("antiflood", "duplicate_text", "impersonation", "raid", "content_lock")
OUTCOMES = ("confirmed", "false_positive")
COLLECTION = "mgmt_rule_effectiveness"


def record(db, chat_id: int, rule: str, field: str = "hits", count: int = 1) -> bool:
    if db is None or rule not in RULES or field not in {"hits", "confirmed", "false_positive"}:
        return False
    try:
        db[COLLECTION].update_one({"chat_id": int(chat_id), "rule": rule},
            {"$inc": {field: max(1, min(int(count), 1000))},
             "$set": {"updated_at": datetime.now(timezone.utc)}}, upsert=True)
        return True
    except Exception:
        return False


def summary(db, chat_id: int) -> list[dict]:
    if db is None:
        return []
    try:
        rows = db[COLLECTION].find({"chat_id": int(chat_id)})
        by_rule = {str(row.get("rule")): row for row in rows if row.get("rule") in RULES}
        return [{"rule": rule, "hits": int(by_rule.get(rule, {}).get("hits", 0)),
                 "confirmed": int(by_rule.get(rule, {}).get("confirmed", 0)),
                 "false_positives": int(by_rule.get(rule, {}).get("false_positive", 0))}
                for rule in RULES]
    except Exception:
        return []
