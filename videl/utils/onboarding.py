"""Privacy-light daily onboarding totals: aggregate counters only, no member IDs."""
from datetime import datetime, timedelta, timezone

RETENTION_DAYS = 90
COUNTERS = ("joins", "challenged", "verified", "timed_out")


def record(chat_id: int, counter: str, *, at=None, db=None) -> bool:
    if counter not in COUNTERS:
        return False
    if db is None:
        from videl.utils.db import get_db
        db = get_db()
    if db is None:
        return False
    moment = at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    day = moment.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    day_key = day.strftime("%Y-%m-%d")
    identifier = f"{int(chat_id)}:{day_key}"
    try:
        db["onboarding_daily"].update_one(
            {"_id": identifier},
            {"$setOnInsert": {"chat_id": int(chat_id), "day": day}, "$inc": {counter: 1}},
            upsert=True,
        )
        return True
    except Exception:
        return False


def summary(db=None, *, days=7, now=None):
    if db is None:
        from videl.utils.db import get_db
        db = get_db()
    if db is None:
        return {"ok": False, "error": "MongoDB is not connected"}
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    since = moment.astimezone(timezone.utc) - timedelta(days=max(1, min(int(days), 30)))
    try:
        rows = list(db["onboarding_daily"].find({"day": {"$gte": since}},
                                                 {"_id": 0, "chat_id": 1, "day": 1, **{key: 1 for key in COUNTERS}}))
    except Exception:
        return {"ok": False, "error": "Onboarding totals are temporarily unavailable"}
    totals = {key: 0 for key in COUNTERS}
    by_day = {}
    active_groups = set()
    for row in rows:
        day = row.get("day")
        if not isinstance(day, datetime):
            continue
        key = day.astimezone(timezone.utc).strftime("%Y-%m-%d")
        bucket = by_day.setdefault(key, {"day": key, **{name: 0 for name in COUNTERS}})
        for name in COUNTERS:
            value = max(0, int(row.get(name) or 0))
            totals[name] += value
            bucket[name] += value
        if int(row.get("joins") or 0) > 0:
            active_groups.add(int(row.get("chat_id") or 0))
    return {"ok": True, "window_days": max(1, min(int(days), 30)), "totals": totals,
            "groups_with_joins": len(active_groups), "series": [by_day[key] for key in sorted(by_day)]}
