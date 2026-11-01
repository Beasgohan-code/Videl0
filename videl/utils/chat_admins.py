"""Which Telegram users administer which group, cached and re-checked.

The panel must not trust a claim of admin rights: the bot asks Telegram. Doing
that on every page open would be one request per group per admin, so results are
cached for five minutes, and a write re-checks only the one group it touches.
A demoted admin therefore loses access within minutes, and always before the
next write is accepted.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

CACHE_SECONDS = 300
RIGHTS = ("can_delete_messages", "can_restrict_members", "can_invite_users",
          "can_pin_messages", "can_manage_video_chats", "can_promote_members",
          "can_change_info", "can_manage_topics", "can_manage_chat", "can_post_messages",
          "can_edit_messages", "can_send_messages")
ADMIN_STATUSES = {"creator", "administrator"}
CHAT_PERMISSIONS = ("can_send_messages", "can_send_audios", "can_send_documents", "can_send_photos",
                    "can_send_videos", "can_send_video_notes", "can_send_voice_notes", "can_send_polls",
                    "can_send_other_messages", "can_add_web_page_previews", "can_manage_topics")


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


def _group_key(chat):
    return f"group:{int(chat)}"


def acquire_refresh_lock(db, chat, token, *, ttl_seconds=120):
    """Claim a cross-process refresh lease in the existing admin-cache collection."""
    col = collection(db)
    if col is None:
        return False
    now = _now()
    lease = {"_id": f"reload:{int(chat)}", "kind": "reload_lock", "chat": int(chat),
             "owner_token": str(token), "expires_at": now + timedelta(seconds=ttl_seconds),
             "checked_at": now}
    try:
        result = col.update_one(
            {"_id": lease["_id"], "$or": [{"expires_at": {"$lte": now}}, {"expires_at": {"$exists": False}}]},
            {"$set": lease}, upsert=True,
        )
        return bool(getattr(result, "modified_count", 0) or getattr(result, "upserted_id", None))
    except Exception:
        # A duplicate-key exception means another instance owns the live lease;
        # database failures also fail closed rather than proceeding unlocked.
        return False


def refresh_in_progress(db, chat):
    col = collection(db)
    if col is None:
        return False
    try:
        return bool(col.find_one({"_id": f"reload:{int(chat)}", "expires_at": {"$gt": _now()}}))
    except Exception:
        return True


def release_refresh_lock(db, chat, token):
    col = collection(db)
    if col is None:
        return False
    try:
        result = col.delete_one({"_id": f"reload:{int(chat)}", "owner_token": str(token)})
        return bool(getattr(result, "deleted_count", 0))
    except Exception:
        return False


def replace_group_snapshot(db, chat, admins, bot_member=None, chat_permissions=None):
    """Atomically replace a group's Telegram-visible admin/permission snapshot.

    One document is the visibility boundary: failed refreshes leave the prior
    snapshot intact, and concurrent readers never observe a half-written roster.
    """
    col = collection(db)
    if col is None:
        raise RuntimeError("admin cache is unavailable")
    normalized = {}
    for member in admins:
        if not isinstance(member, dict):
            continue
        user = member.get("user") or {}
        try:
            user_id = int(user.get("id"))
        except (TypeError, ValueError):
            continue
        if user_id <= 0:
            continue
        status = str(member.get("status") or "unknown")
        rights = {key: bool(member.get(key)) for key in RIGHTS}
        normalized[user_id] = {"user": user_id, "status": status, "rights": rights,
                               "is_bot": bool(user.get("is_bot"))}
    bot = None
    if isinstance(bot_member, dict):
        bot = {"status": str(bot_member.get("status") or "unknown"),
               "rights": {key: bool(bot_member.get(key)) for key in RIGHTS}}
    key = _group_key(chat)
    previous = col.find_one({"_id": key}) or {}
    now = _now()
    if bot is None:
        bot = previous.get("bot")
        bot_checked_at = previous.get("bot_checked_at")
    else:
        bot_checked_at = now
    if chat_permissions is None:
        chat_permissions = previous.get("chat_permissions")
        chat_permissions_checked_at = previous.get("chat_permissions_checked_at")
    elif isinstance(chat_permissions, dict):
        chat_permissions = {name: bool(chat_permissions.get(name)) for name in CHAT_PERMISSIONS}
        chat_permissions_checked_at = now
    else:
        chat_permissions = {}
        chat_permissions_checked_at = now
    snapshot = {"_id": key, "kind": "group_snapshot", "chat": int(chat),
                "admins": list(normalized.values()), "bot": bot,
                "bot_checked_at": bot_checked_at,
                "chat_permissions": chat_permissions,
                "chat_permissions_checked_at": chat_permissions_checked_at,
                "checked_at": now}
    result = col.update_one({"_id": snapshot["_id"]}, {"$set": snapshot}, upsert=True)
    if result is not None and getattr(result, "acknowledged", True) is False:
        raise RuntimeError("admin cache update was not acknowledged")
    return snapshot


def bot_statuses(db, chats, *, seconds=CACHE_SECONDS):
    """Fresh Bot API status/rights to overlay on profile-only admin UI caches."""
    col = collection(db)
    if col is None:
        return {}
    keys = [_group_key(chat) for chat in chats]
    try:
        snapshots = list(col.find({"_id": {"$in": keys}, "kind": "group_snapshot"}))
    except Exception:
        return {}
    result = {}
    for snapshot in snapshots:
        bot = snapshot.get("bot")
        if not isinstance(bot, dict) or not _fresh({"checked_at": snapshot.get("bot_checked_at")}, seconds):
            continue
        try:
            chat = int(snapshot["chat"])
        except (KeyError, TypeError, ValueError):
            continue
        status = str(bot.get("status") or "unknown")
        result[chat] = {"status": status, "admin": status in ADMIN_STATUSES,
                        "rights": dict(bot.get("rights") or {}),
                        "checked_at": _as_utc(snapshot.get("bot_checked_at"))}
    return result


def _snapshot_member(snapshot, user):
    for row in snapshot.get("admins") or []:
        try:
            if int(row.get("user")) == int(user):
                return {"status": row.get("status"), "rights": row.get("rights") or {},
                        "checked_at": snapshot.get("checked_at")}
        except (TypeError, ValueError):
            continue
    return {"status": "member", "rights": {}, "checked_at": snapshot.get("checked_at")}


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


def _individual_cache_write_allowed(db, chat, baseline_snapshot):
    if refresh_in_progress(db, chat):
        return False
    col = collection(db)
    if col is None:
        return False
    try:
        current = col.find_one({"_id": _group_key(chat)}) or {}
    except Exception:
        return False
    baseline = _as_utc((baseline_snapshot or {}).get("checked_at"))
    current_stamp = _as_utc(current.get("checked_at"))
    return not (current.get("kind") == "group_snapshot" and current_stamp
                and (baseline is None or current_stamp > baseline))


def check(db, api, chat, user, *, force=False):
    """Return the cached or live admin state for one person in one group."""
    col = collection(db)
    document = col.find_one({"_id": _key(chat, user)}) if col is not None else None
    snapshot = col.find_one({"_id": _group_key(chat)}) if col is not None else None
    baseline_snapshot = snapshot
    if snapshot and snapshot.get("kind") == "group_snapshot" and _fresh(snapshot):
        member = _snapshot_member(snapshot, user)
        member_checked = _as_utc((document or {}).get("checked_at"))
        snapshot_checked = _as_utc(snapshot.get("checked_at"))
        if not force and (member_checked is None or member_checked <= snapshot_checked):
            return _answer(member)
    if document and not force and _fresh(document):
        return _answer(document)
    try:
        status, body = api("getChatMember", {"chat_id": int(chat), "user_id": int(user)})
    except Exception:
        status, body = 0, {}
    if status == 200 and isinstance(body, dict) and body.get("ok"):
        member = body.get("result") or {}
        if _individual_cache_write_allowed(db, chat, baseline_snapshot):
            row = _store(db, chat, user, member.get("status"), member)
        else:
            row = {"status": str(member.get("status") or "unknown"),
                   "rights": {key: bool(member.get(key)) for key in RIGHTS}, "checked_at": _now()}
        return _answer(row)
    # Telegram refused: the person is not in the group (or the chat is gone).
    if status in (400, 403):
        if _individual_cache_write_allowed(db, chat, baseline_snapshot):
            row = _store(db, chat, user, "left", {})
        else:
            row = {"status": "left", "rights": {}, "checked_at": _now()}
        return _answer(row)
    # Transport failure. Retain the newest known fact for display, marked stale;
    # mutation endpoints still perform their own Telegram-side authorization.
    fallback = document
    if snapshot and snapshot.get("kind") == "group_snapshot":
        snapshot_member = _snapshot_member(snapshot, user)
        if (_as_utc(snapshot_member.get("checked_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= \
           (_as_utc((document or {}).get("checked_at")) or datetime.min.replace(tzinfo=timezone.utc)):
            fallback = snapshot_member
    return _answer(fallback, stale=True)


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
    records = list(col.find({"$or": [{"user": int(user)}, {"kind": "group_snapshot"}]})) if col is not None else []
    known = {int(row["chat"]): row for row in records if row.get("user") == int(user) and row.get("chat") is not None}
    snapshots = {int(row["chat"]): row for row in records if row.get("kind") == "group_snapshot" and row.get("chat") is not None}
    if refresh:
        served = [int(row["_id"]) for row in db["served_chats"].find({}, {"_id": 1})]
        stale = [chat for chat in served if (
            (chat not in known and chat not in snapshots)
            or (chat in known and not _fresh(known[chat], 3600))
            or (chat in snapshots and not _fresh(snapshots[chat], 3600))
        )]
        for chat in stale[:max(0, int(limit))]:
            if chat > 0 or refresh_in_progress(db, chat):
                continue
            if chat in snapshots:
                token = secrets.token_urlsafe(16)
                if not acquire_refresh_lock(db, chat, token):
                    continue
                try:
                    status, response = api("getChatAdministrators", {"chat_id": chat})
                    if status != 200 or not isinstance(response, dict) or not response.get("ok"):
                        continue
                    snapshot = replace_group_snapshot(db, chat, response.get("result") or [])
                    snapshots[chat] = snapshot
                except Exception:
                    continue
                finally:
                    release_refresh_lock(db, chat, token)
            else:
                answer = check(db, api, chat, user, force=True)
                if answer["admin"]:
                    known[chat] = {"chat": chat, "status": answer["status"],
                                   "checked_at": answer["checked_at"]}
    groups = []
    for chat, snapshot in snapshots.items():
        # A group snapshot supersedes older per-user cache rows, including a
        # removed admin, until the snapshot itself expires and is refreshed.
        member = _snapshot_member(snapshot, user)
        if member.get("status") in ADMIN_STATUSES:
            groups.append({"id": chat, "checked_at": _as_utc(snapshot.get("checked_at"))})
    for chat, row in known.items():
        if chat in snapshots:
            continue
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
        snapshot = snapshots.get(group["id"])
        bot = snapshot.get("bot") if snapshot else None
        bot_fresh = bool(snapshot and _fresh({"checked_at": snapshot.get("bot_checked_at")}))
        group["bot_admin"] = (str(bot.get("status") or "") in ADMIN_STATUSES
                              if isinstance(bot, dict) and bot_fresh else cached.get("bot_admin"))
        if isinstance(bot, dict) and bot_fresh:
            group["bot_rights"] = dict(bot.get("rights") or {})
            group["permissions_checked_at"] = _as_utc(snapshot.get("bot_checked_at"))
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
        token = secrets.token_urlsafe(16)
        if not acquire_refresh_lock(db, chat, token):
            continue
        try:
            status, body = api("getChatAdministrators", {"chat_id": chat})
            if status != 200 or not isinstance(body, dict) or not body.get("ok"):
                continue
            replace_group_snapshot(db, chat, body.get("result") or [])
            touched += 1
        except Exception:
            continue
        finally:
            release_refresh_lock(db, chat, token)
    return touched
