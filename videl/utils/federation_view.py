"""Read model for federations, the one part of the bot that had no web surface.

Federations are a real feature (`/newfed`, `/fban`, `/fedstat`) that could only
be driven by memorising syntax. This module exposes the same stored records to
the owner panel: which federations exist, which groups belong to each, and who
is banned. It never invents a member count it cannot read.
"""
from __future__ import annotations

from datetime import datetime, timezone

MAX_BANS = 300


def _stamp(value):
    if isinstance(value, datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc).isoformat()
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def overview(db) -> dict:
    """Every federation with its chat count and ban count, newest first."""
    if db is None:
        return {"ok": True, "federations": [], "total": 0}
    try:
        feds = list(db["feds"].find({}))
    except Exception:
        feds = []
    chats_by_fed: dict[str, list[int]] = {}
    try:
        for row in db["fed_chats"].find({"chat": {"$ne": -1}}):
            chats_by_fed.setdefault(str(row.get("fed")), []).append(int(row.get("chat")))
    except Exception:
        chats_by_fed = {}
    bans_by_fed: dict[str, int] = {}
    try:
        for row in db["fed_bans"].aggregate([{"$group": {"_id": "$fed", "total": {"$sum": 1}}}]):
            bans_by_fed[str(row.get("_id"))] = int(row.get("total") or 0)
    except Exception:
        bans_by_fed = {}
    admins_by_fed: dict[str, list[int]] = {}
    try:
        for row in db["fed_admins"].find({}):
            admins_by_fed.setdefault(str(row.get("fed")), []).append(int(row.get("user")))
    except Exception:
        admins_by_fed = {}
    titles = chat_titles(db, {chat for chats in chats_by_fed.values() for chat in chats})
    entries = []
    for fed in feds:
        identifier = str(fed.get("_id"))
        chat_ids = chats_by_fed.get(identifier, [])
        entries.append({
            "id": identifier,
            "name": str(fed.get("name") or identifier),
            "owner": fed.get("owner"),
            "created": _stamp(fed.get("created")),
            "chats": [{"id": chat, "title": titles.get(chat) or f"Telegram chat {chat}"} for chat in chat_ids],
            "chat_count": len(chat_ids),
            "bans": bans_by_fed.get(identifier, 0),
            "admins": admins_by_fed.get(identifier, []),
        })
    entries.sort(key=lambda item: (item["created"] or "", item["name"]), reverse=True)
    return {"ok": True, "federations": entries, "total": len(entries)}


def chat_titles(db, chat_ids) -> dict[int, str]:
    """Titles from the group-manager cache; missing chats stay unnamed."""
    if db is None or not chat_ids:
        return {}
    try:
        return {int(row["_id"]): str(row.get("title") or "") for row in
                db["mgmt_chat_info"].find({"_id": {"$in": list(chat_ids)}})}
    except Exception:
        return {}


def detail(db, fed_id: str) -> dict:
    """One federation with its bans and groups. Reasons are stored text, escaped by the UI."""
    if db is None:
        raise LookupError("MongoDB is not connected")
    fed = db["feds"].find_one({"_id": fed_id})
    if not fed:
        raise LookupError("This federation no longer exists")
    bans = []
    try:
        for row in db["fed_bans"].find({"fed": fed_id}).sort("time", -1).limit(MAX_BANS):
            bans.append({
                "user": row.get("user"),
                "reason": str(row.get("reason") or "")[:200],
                "by": row.get("banner"),
                "at": _stamp(row.get("time")),
            })
    except Exception:
        bans = []
    chats = []
    try:
        chat_ids = [int(row.get("chat")) for row in db["fed_chats"].find({"fed": fed_id, "chat": {"$ne": -1}})]
    except Exception:
        chat_ids = []
    titles = chat_titles(db, set(chat_ids))
    chats = [{"id": chat, "title": titles.get(chat) or f"Telegram chat {chat}"} for chat in chat_ids]
    try:
        admins = [int(row.get("user")) for row in db["fed_admins"].find({"fed": fed_id})]
    except Exception:
        admins = []
    return {
        "ok": True,
        "federation": {
            "id": fed_id,
            "name": str(fed.get("name") or fed_id),
            "owner": fed.get("owner"),
            "created": _stamp(fed.get("created")),
            "chats": chats,
            "admins": admins,
            "bans": bans,
        },
    }


def unban(db, fed_id: str, user_id: int) -> dict:
    """Lift one federation ban. The bot re-applies bans from this table, so this is the real source."""
    if db is None:
        raise LookupError("MongoDB is not connected")
    result = db["fed_bans"].delete_one({"fed": fed_id, "user": int(user_id)})
    return {"ok": True, "removed": bool(result.deleted_count), "user": int(user_id)}
