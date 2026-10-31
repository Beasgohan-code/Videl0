"""Bounded self-service export and group-scoped member-record removal."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

EXPORT_LIMIT = 250
FEEDBACK_LIMIT = 1000
FEEDBACK_RETENTION_DAYS = 180


def _safe_value(value, depth=0):
    if depth>3:return None
    if isinstance(value,datetime):return value.replace(tzinfo=value.tzinfo or timezone.utc).isoformat()
    if isinstance(value,(str,int,float,bool)) or value is None:return value
    if isinstance(value,dict):
        return {str(key)[:40]:_safe_value(item,depth+1) for key,item in list(value.items())[:30]
                if str(key).casefold() not in {"file_id","file_unique_id","token","secret"}}
    if isinstance(value,(list,tuple)):
        return [_safe_value(item,depth+1) for item in value[:100]
                if isinstance(item,(dict,list,tuple,str,int,float,bool)) or item is None]
    return None


def _safe_rows(collection, query, projection=None, limit=EXPORT_LIMIT):
    result=[]
    for row in collection.find(query, projection or {}).limit(limit):
        clean={}
        for key,value in row.items():
            if key == "_id":clean["record_id"] = str(value)
            else:clean[key]=_safe_value(value)
        result.append(clean)
    return result


def export_user_data(db, user_id: int) -> dict:
    """Export bounded records indexed to the requesting member only."""
    if db is None or int(user_id)<=0 or int(user_id)>2**63-1:
        raise ValueError("A valid member and database are required")
    uid=int(user_id)
    data={"format":"videl-member-export","version":1,"generated_at":datetime.now(timezone.utc).isoformat(),
          "telegram_user_id":uid,"records":{}}
    data["records"]["warnings"]=_safe_rows(db["mgmt_warnings"],{"user_id":uid})
    data["records"]["ban_records"]=_safe_rows(db["mgmt_banned_users"],{"user_id":uid})
    data["records"]["approved_memberships"]=_safe_rows(db["approved"],{"user":uid})
    data["records"]["case_notes"]=_safe_rows(db["mgmt_case_notes"],{"user_id":uid})
    data["records"]["join_requests"]=_safe_rows(db["mgmt_join_requests"],{"user":uid})
    data["records"]["appeals"]=_safe_rows(db["mgmt_appeals"],{"user_id":uid},
        {"_id":1,"chat_id":1,"reason":1,"action_type":1,"status":1,"ts":1,"resolved":1})
    data["records"]["reports_filed"]=_safe_rows(db["mgmt_reports"],{"$or":[{"reporter":uid},{"reporter_id":uid}]},
        {"_id":1,"chat_id":1,"reason":1,"status":1,"ts":1,"decision":1,"resolved":1})
    data["records"]["reports_about_member"]=_safe_rows(db["mgmt_reports"],{"$or":[{"target":uid},{"target_id":uid}]},
        {"_id":1,"chat_id":1,"reason":1,"status":1,"ts":1,"decision":1,"resolved":1})
    data["records"]["reminders"]=_safe_rows(db["plugin_reminders"],{"user_id":uid},
        {"_id":1,"chat_id":1,"message_thread_id":1,"text":1,"due_at":1,"status":1,"sent_at":1})
    data["records"]["last_active_record"]=_safe_rows(db["user_activity"],{"_id":uid},
        {"_id":1,"last_active":1})
    data["records"]["recorded_messages"]=_safe_rows(db["group_view_messages"],{"sender_id":uid},
        {"_id":1,"chat_id":1,"message_id":1,"date":1,"text":1,"caption":1},limit=EXPORT_LIMIT)
    return data


def delete_member_group_data(db, chat_id: int, user_id: int) -> dict:
    """Delete selected member-linked records in one group; keep immutable audit."""
    if db is None or int(chat_id)>=0 or int(user_id)<=0 or int(user_id)>2**63-1:
        raise ValueError("Choose a group and valid member ID")
    cid,uid=int(chat_id),int(user_id)
    counts={}
    for name,query in (
        ("warnings",{"chat_id":cid,"user_id":uid}),
        ("ban_records",{"chat_id":cid,"user_id":uid}),
        ("approved_members",{"chat":cid,"user":uid}),
        ("case_notes",{"chat_id":cid,"user_id":uid}),
        ("join_requests",{"chat_id":cid,"user":uid}),
        ("appeals",{"chat_id":cid,"user_id":uid}),
    ):
        try:
            counts[name]=getattr(db[{"warnings":"mgmt_warnings","ban_records":"mgmt_banned_users",
                "approved_members":"approved","case_notes":"mgmt_case_notes",
                "join_requests":"mgmt_join_requests","appeals":"mgmt_appeals"}[name]].delete_many(query),"deleted_count",0)
        except Exception:
            counts[name]="error"
    try:
        result=db["mgmt_reports"].delete_many({"chat_id":cid,"$or":[{"target":uid},{"target_id":uid},{"reporter":uid},{"reporter_id":uid}]})
        counts["reports"]=int(getattr(result,"deleted_count",0))
    except Exception:
        counts["reports"]="error"
    try:
        pending=db["mgmt_escalations"].update_many({"chat_id":cid,"user_id":uid,"status":"open"},
            {"$set":{"status":"cancelled_data_request","resolved_at":datetime.now(timezone.utc)}})
        counts["pending_reviews_cancelled"]=int(getattr(pending,"modified_count",0))
    except Exception:
        counts["pending_reviews_cancelled"]="error"
    # mgmt_audit and recorded inbox messages are intentionally retained: only
    # the bot owner may manage group-view recordings, and audits are immutable.
    counts["audit_records_retained"]=True
    return counts


def submit_feedback(db,text) -> str | None:
    """Save anonymous feedback without persisting Telegram sender/chat IDs."""
    if db is None or not isinstance(text,str) or not text.strip() or len(text.strip())>FEEDBACK_LIMIT:
        return None
    identifier=uuid.uuid4().hex
    try:
        col=db["anonymous_feedback"]
        col.create_index("created_at",expireAfterSeconds=FEEDBACK_RETENTION_DAYS*86400)
        col.insert_one({"_id":identifier,"text":text.strip(),"created_at":datetime.now(timezone.utc)})
        return identifier
    except Exception:
        return None


def feedback_rows(db,limit=20) -> list[dict]:
    if db is None:return []
    limit=max(1,min(int(limit),100))
    try:
        cutoff=datetime.now(timezone.utc)-timedelta(days=FEEDBACK_RETENTION_DAYS)
        rows=list(db["anonymous_feedback"].find({"created_at":{"$gte":cutoff}},
            {"text":1,"created_at":1}).sort("created_at",-1).limit(limit))
        return [{"id":str(row.get("_id") or ""),"text":str(row.get("text") or "")[:FEEDBACK_LIMIT],
                 "created_at":row.get("created_at").isoformat() if isinstance(row.get("created_at"),datetime) else None}
                for row in rows]
    except Exception:
        return []
