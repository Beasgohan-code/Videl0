"""Which Telegram users administer which group, cached and re-checked.

The panel must not trust a claim of admin rights: the bot asks Telegram. Doing
that on every page open would be one request per group per admin, so results are
cached for five minutes, and a write re-checks only the one group it touches.
A demoted admin therefore loses access within minutes, and always before the
next write is accepted.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

CACHE_SECONDS = 300
RIGHTS = ("can_delete_messages", "can_restrict_members", "can_invite_users",
          "can_pin_messages", "can_manage_video_chats")
ADMIN_STATUSES = {"creator", "administrator"}


def _now():
    return datetime.now(timezone.utc)


def _as_utc(value):
    if not isinstance(value, datetime):
        return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def collection(db=None):
    if db is None:
        from videl.utils.db import get_db
        db = get_db()
    return None if db is None else db["chat_admins"]


def _key(chat, user):
    return f"{int(chat)}:{int(user)}"


def _fresh(document, seconds=CACHE_SECONDS):
    checked = _as_utc(document.get("checked_at"))
    return bool(checked and _now() - checked < timedelta(seconds=seconds))


def _store(db, chat, user, status, rights, *, checked=None):
    row = {"_id": _key(chat, user), "chat": int(chat), "user": int(user),
           "status": str(status or "left"),
           "rights": {key: bool(rights.get(key)) for key in RIGHTS},
           "checked_at": checked or _now()}
    try:
        collection(db).update_one({"_id": row["_id"]}, {"$set": row}, upsert=True)
    except Exception:
        pass
    return row


def check(db, api, chat, user, *, force=False):
    """Return the cached or live admin state for one person in one group."""
    col = collection(db)
    document = col.find_one({"_id": _key(chat, user)}) if col is not None else None
    if document and not force and _fresh(document):
        return _answer(document)
    try:
        status, body = api("getChatMember", {"chat_id": int(chat), "user_id": int(user)})
    except Exception:
        status, body = 0, {}
    if status == 200 and isinstance(body, dict) and body.get("ok"):
        member = body.get("result") or {}
        row = _store(db, chat, user, member.get("status"), member)
        return _answer(row)
    # Telegram refused: the person is not in the group (or the chat is gone).
    if status in (400, 403):
        row = _store(db, chat, user, "left", {})
        return _answer(row)
    # Transport failure. A stale answer beats a false 403 for a real admin,
    # because every write re-checks the rights it needs anyway.
    return _answer(document, stale=True)


def _answer(document, *, stale=False):
    document = document or {}
    return {"admin": document.get("status") in ADMIN_STATUSES,
            "status": document.get("status") or "unknown",
            "rights": dict(document.get("rights") or {}),
            "checked_at": _as_utc(document.get("checked_at")),
            "stale": stale}


def forget(db, chat, user):
    try:
        collection(db).delete_one({"_id": _key(chat, user)})
    except Exception:
        pass


def my_groups(db, api, user, *, refresh=False, limit=25):
    """Groups this person administers.

    ``refresh`` asks Telegram for the groups not yet known. It is bounded on
    purpose: a bot in hundreds of groups must not answer a page open with
    hundreds of Bot API calls. The bounded sweep in the watchdog fills the rest.
    """
    if db is None:
        return []
    col = collection(db)
    known = {row["chat"]: row for row in col.find({"user": int(user)})} if col is not None else {}
    checked = 0
    if refresh:
        served = [int(row["_id"]) for row in db["served_chats"].find({}, {"_id": 1})]
        stale = [chat for chat in served
                 if chat not in known or not _fresh(known[chat], 3600)]
        for chat in stale[:max(0, int(limit))]:
            if chat > 0:
                continue
            answer = check(db, api, chat, user, force=True)
            checked += 1
            if answer["admin"]:
                known[chat] = {"chat": chat, "status": answer["status"],
                               "checked_at": answer["checked_at"]}
    groups = []
    for chat, row in known.items():
        if row.get("status") not in ADMIN_STATUSES:
            continue
        groups.append({"id": int(chat), "checked_at": _as_utc(row.get("checked_at"))})
    if not groups:
        return []
    info = {int(doc["_id"]): doc for doc in db["mgmt_chat_info"].find(
        {"_id": {"$in": [group["id"] for group in groups]}})}
    for group in groups:
        cached = info.get(group["id"]) or {}
        group["title"] = cached.get("title") or f"Telegram chat {group['id']}"
        group["members"] = cached.get("members")
        group["type"] = cached.get("type") or "group"
        group["bot_admin"] = cached.get("bot_admin")
    groups.sort(key=lambda group: str(group.get("title") or "").casefold())
    return groups


def sweep(db, api, *, limit=20):
    """Refresh a rolling slice of the fleet, for admins nobody has asked about."""
    if db is None:
        return 0
    col = collection(db)
    served = [int(row["_id"]) for row in db["served_chats"].find({}, {"_id": 1})]
    oldest = []
    for chat in served:
        rows = list(col.find({"chat": chat})) if col is not None else []
        checked = max((_as_utc(row.get("checked_at")) for row in rows), default=None)
        oldest.append((checked is None, checked, chat))
    oldest.sort(key=lambda item: (not item[0], item[1] or datetime.min.replace(tzinfo=timezone.utc)))
    touched = 0
    for _, _, chat in oldest[:limit]:
        try:
            status, body = api("getChatAdministrators", {"chat_id": chat})
        except Exception:
            continue
        if status != 200 or not isinstance(body, dict) or not body.get("ok"):
            continue
        for member in body.get("result") or []:
            user = member.get("user") or {}
            if user.get("is_bot") or not user.get("id"):
                continue
            _store(db, chat, int(user["id"]), member.get("status"), member)
        touched += 1
    return touched
