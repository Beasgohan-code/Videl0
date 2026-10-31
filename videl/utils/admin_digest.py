"""Per-admin UTC digests for open group queues; aggregate counts only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

COLLECTION = "mgmt_admin_digests"


def parse_time(value: str) -> tuple[int, int] | None:
    if not isinstance(value, str) or len(value.strip()) != 5:
        return None
    try:
        hour, minute = map(int, value.strip().split(":"))
    except (ValueError, TypeError):
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def subscribe(db, chat_id: int, user_id: int, time_utc: str) -> bool:
    parsed = parse_time(time_utc)
    if db is None or parsed is None or int(chat_id) >= 0 or int(user_id) <= 0:
        return False
    hour, minute = parsed
    try:
        db[COLLECTION].create_index([("chat_id", 1), ("user_id", 1)], unique=True)
        db[COLLECTION].create_index([("enabled", 1), ("hour_utc", 1), ("minute_utc", 1), ("last_attempt_date", 1)])
        db[COLLECTION].update_one({"chat_id": int(chat_id), "user_id": int(user_id)},
            {"$set": {"chat_id": int(chat_id), "user_id": int(user_id),
                      "hour_utc": hour, "minute_utc": minute, "enabled": True},
             "$unset": {"claim_until": ""}}, upsert=True)
        return True
    except Exception:
        return False


def unsubscribe(db, chat_id: int, user_id: int) -> bool:
    try:
        return bool(db[COLLECTION].delete_one({"chat_id": int(chat_id), "user_id": int(user_id)}).deleted_count)
    except Exception:
        return False


def dispatch_one(db, api, now: datetime | None = None) -> dict:
    """Dispatch at most one due digest; pre-claim prevents multi-instance duplicates."""
    if db is None:
        return {"ok": False, "reason": "database unavailable"}
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    day = now.date().isoformat()
    current_minute = now.hour * 60 + now.minute
    col = db[COLLECTION]
    try:
        due = list(col.find({"enabled": True, "last_attempt_date": {"$ne": day}})
                   .sort([("hour_utc", 1), ("minute_utc", 1)]).limit(100))
    except Exception:
        return {"ok": False, "reason": "digest schedule unavailable"}
    for row in due:
        scheduled = int(row.get("hour_utc", 24)) * 60 + int(row.get("minute_utc", 60))
        if scheduled > current_minute:
            continue
        selector = {"_id": row["_id"], "enabled": True,
                    "last_attempt_date": {"$ne": day},
                    "$or": [{"claim_until": {"$exists": False}}, {"claim_until": {"$lt": now}}]}
        claim = col.update_one(selector, {"$set": {"claim_until": now + timedelta(minutes=3),
            "last_attempt_date": day, "last_delivery": "sending"}})
        if not getattr(claim, "modified_count", 0):
            continue
        chat_id, user_id = int(row["chat_id"]), int(row["user_id"])
        try:
            status, membership = api("getChatMember", {"chat_id": chat_id, "user_id": user_id})
            member = (membership or {}).get("result") or {}
            if status != 200 or not (membership or {}).get("ok") or member.get("status") not in {"creator", "administrator"}:
                col.update_one({"_id": row["_id"]}, {"$set": {"enabled": False, "last_delivery": "disabled; admin status not confirmed"}, "$unset": {"claim_until": ""}})
                return {"ok": True, "sent": False, "reason": "admin status not confirmed"}
            reports = db["mgmt_reports"].count_documents({"chat_id": chat_id, "status": "open"})
            requests = db["mgmt_join_requests"].count_documents({"chat_id": chat_id, "status": "pending"})
            reviews = db["mgmt_escalations"].count_documents({"chat_id": chat_id, "status": "open"})
            incidents = db["mgmt_audit"].count_documents({"chat_id": chat_id, "ts": {"$gte": now - timedelta(hours=24)},
                "kind": {"$in": ["moderation", "report", "escalation", "warn"]}})
            title = str((db["served_chats"].find_one({"_id": chat_id}) or {}).get("title") or "your group")[:80]
            text = (f"Daily admin summary · {title} · {day} UTC\n"
                    f"Open reports: {reports}\nPending join requests: {requests}\n"
                    f"Pending action reviews: {reviews}\nModeration incidents in the last 24h: {incidents}")
            sent, result = api("sendMessage", {"chat_id": user_id, "text": text, "disable_web_page_preview": True})
            confirmed = sent == 200 and isinstance(result, dict) and result.get("ok") is True
            col.update_one({"_id": row["_id"]}, {"$set": {"last_delivery": "delivered" if confirmed else "unconfirmed"},
                           "$unset": {"claim_until": ""}})
            return {"ok": True, "sent": confirmed, "reason": "delivered" if confirmed else "delivery unconfirmed"}
        except Exception:
            # Do not automatically retry an uncertain private send: it could
            # have reached Telegram before the network response was lost.
            try:
                col.update_one({"_id": row["_id"]}, {"$set": {"last_delivery": "unconfirmed"}, "$unset": {"claim_until": ""}})
            except Exception:
                pass
            return {"ok": False, "sent": False, "reason": "delivery unconfirmed"}
    return {"ok": True, "sent": False, "reason": "nothing due"}
