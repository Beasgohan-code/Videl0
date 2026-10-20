# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

import config

logger = logging.getLogger(__name__)

# ── Client ─────────────────────────────────────────────────────────────────────
_client: Optional[MongoClient] = None
_db = None


def start_mongo() -> bool:
    global _client, _db

    if not config.MONGO_DB_URL:
        logger.warning("MONGO_DB_URL not set — database features disabled.")
        return False

    try:
        _client = MongoClient(config.MONGO_DB_URL, serverSelectionTimeoutMS=5000,
                              connectTimeoutMS=5000, socketTimeoutMS=10000)
        _client.admin.command("ping")
        # Prefer env name; default "Videl" (matches existing Atlas DB — case matters)
        db_name = (os.environ.get("MONGO_DB_NAME") or "Videl").strip() or "Videl"
        try:
            existing = set(_client.list_database_names())
            # If opposite case already exists, reuse it to avoid code 13297
            if db_name not in existing:
                lower, title = db_name.lower(), db_name[:1].upper() + db_name[1:]
                if lower in existing:
                    db_name = lower
                elif title in existing:
                    db_name = title
                elif "Videl" in existing:
                    db_name = "Videl"
                elif "videl" in existing:
                    db_name = "videl"
        except Exception:
            pass
        _db = _client[db_name]
        ensure_indexes(_db)
        logger.info(f"◍ ᴍᴏɴɢᴏ — ᴄᴏɴɴᴇᴄᴛᴇᴅ (db={db_name}) ◍")
        return True

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"◍ ᴍᴏɴɢᴏ — ғᴀɪʟᴇᴅ: {e} ◍")
        _client = None
        _db = None
        return False

    except Exception as e:
        logger.error(f"◍ ᴍᴏɴɢᴏ — ᴇʀʀᴏʀ: {e} ◍")
        _client = None
        _db = None
        return False


# ── Indexes ───────────────────────────────────────────────────────────────────
# The panel reads one document per served group; without these, every group is
# a collection scan and the fleet view gets slower as the bot is added to more
# chats. Creation is idempotent, quiet and safe to call on every boot.

INDEX_SPECS = {
    "mgmt_chat_settings": [([("chat_id", 1)], {})],
    "mgmt_warnings": [([("chat_id", 1), ("user_id", 1)], {})],
    "mgmt_join_requests": [([("chat_id", 1), ("status", 1)], {})],
    "mgmt_reports": [([("chat_id", 1), ("status", 1)], {})],
    "mgmt_notes": [([("chat_id", 1)], {})],
    "mgmt_filters": [([("chat_id", 1)], {})],
    "blacklist": [([("chat", 1), ("trigger", 1)], {})],
    "approved": [([("chat", 1), ("user", 1)], {})],
    "disabled_cmds": [([("chat", 1), ("cmd", 1)], {})],
    "backups": [([("chat", 1), ("time", -1)], {})],
    "scheduled_posts": [([("owner_id", 1), ("status", 1), ("due_at", 1)], {})],
    "studio_library": [([("owner_id", 1), ("key", 1)], {"unique": True})],
}


def ensure_indexes(db=None) -> dict:
    """Create the query indexes once per process. Failures are not fatal."""
    database = db if db is not None else _db
    if database is None:
        return {}
    created = {}
    for name, specs in INDEX_SPECS.items():
        for keys, options in specs:
            try:
                created[f"{name}:{'+'.join(key for key, _ in keys)}"] = database[name].create_index(keys, **options)
            except Exception:
                logger.debug("[indexes] %s was left as-is", name, exc_info=True)
    return created


def get_db():
    return _db


def is_connected() -> bool:
    return _db is not None


def get_mongo_client() -> Optional[MongoClient]:
    """Return the raw MongoClient (used for dbstats in /stats command)."""
    return _client


# ── Collections ────────────────────────────────────────────────────────────────

def _col(name: str):
    if _db is None:
        return None
    return _db[name]


# ── Served Chats ───────────────────────────────────────────────────────────────

def add_served_chat(chat_id: int) -> None:
    col = _col("served_chats")
    if col is None:
        return
    try:
        col.update_one({"_id": chat_id}, {"$set": {"_id": chat_id}}, upsert=True)
    except Exception as e:
        logger.error(f"[DB] add_served_chat: {e}")


def get_served_chats() -> list:
    col = _col("served_chats")
    if col is None:
        return []
    try:
        return [doc["_id"] for doc in col.find({}, {"_id": 1})]
    except Exception as e:
        logger.error(f"[DB] get_served_chats: {e}")
        return []


def get_served_chats_count() -> int:
    col = _col("served_chats")
    if col is None:
        return 0
    try:
        return col.count_documents({})
    except Exception as e:
        logger.error(f"[DB] get_served_chats_count: {e}")
        return 0


def remove_served_chat(chat_id: int) -> None:
    col = _col("served_chats")
    if col is None:
        return
    try:
        col.delete_one({"_id": chat_id})
    except Exception as e:
        logger.error(f"[DB] remove_served_chat: {e}")


# ── Served Users ───────────────────────────────────────────────────────────────

def add_served_user(user_id: int) -> None:
    col = _col("served_users")
    if col is None:
        return
    try:
        col.update_one({"_id": user_id}, {"$set": {"_id": user_id}}, upsert=True)
    except Exception as e:
        logger.error(f"[DB] add_served_user: {e}")


def get_served_users() -> list:
    col = _col("served_users")
    if col is None:
        return []
    try:
        return [doc["_id"] for doc in col.find({}, {"_id": 1})]
    except Exception as e:
        logger.error(f"[DB] get_served_users: {e}")
        return []


def get_served_users_count() -> int:
    col = _col("served_users")
    if col is None:
        return 0
    try:
        return col.count_documents({})
    except Exception as e:
        logger.error(f"[DB] get_served_users_count: {e}")
        return 0


# ── Blocked Chats (ban) ────────────────────────────────────────────────────────

def ban_chat(chat_id: int) -> None:
    col = _col("banned_chats")
    if col is None:
        return
    try:
        col.update_one({"_id": chat_id}, {"$set": {"_id": chat_id}}, upsert=True)
    except Exception as e:
        logger.error(f"[DB] ban_chat: {e}")


def unban_chat(chat_id: int) -> None:
    col = _col("banned_chats")
    if col is None:
        return
    try:
        col.delete_one({"_id": chat_id})
    except Exception as e:
        logger.error(f"[DB] unban_chat: {e}")


def is_chat_banned(chat_id: int) -> bool:
    col = _col("banned_chats")
    if col is None:
        return False
    try:
        return col.find_one({"_id": chat_id}) is not None
    except Exception:
        return False


def get_banned_chats() -> list:
    col = _col("banned_chats")
    if col is None:
        return []
    try:
        return [doc["_id"] for doc in col.find({}, {"_id": 1})]
    except Exception:
        return []


def get_banned_chats_count() -> int:
    col = _col("banned_chats")
    if col is None:
        return 0
    try:
        return col.count_documents({})
    except Exception:
        return 0


# ── Assistant Joined Chats ─────────────────────────────────────────────────────

def mark_assistant_joined(chat_id: int) -> None:
    col = _col("assistant_chats")
    if col is None:
        return
    try:
        col.update_one({"_id": chat_id}, {"$set": {"_id": chat_id}}, upsert=True)
    except Exception as e:
        logger.error(f"[DB] mark_assistant_joined: {e}")


def is_assistant_joined(chat_id: int) -> bool:
    col = _col("assistant_chats")
    if col is None:
        return False
    try:
        return col.find_one({"_id": chat_id}) is not None
    except Exception:
        return False


# ── Play Stats ─────────────────────────────────────────────────────────────────

def increment_play_count(chat_id: int) -> None:
    col = _col("play_stats")
    if col is None:
        return
    try:
        col.update_one(
            {"_id": chat_id},
            {"$inc": {"count": 1}},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"[DB] increment_play_count: {e}")


def get_total_plays() -> int:
    col = _col("play_stats")
    if col is None:
        return 0
    try:
        result = col.aggregate([{"$group": {"_id": None, "total": {"$sum": "$count"}}}])
        for r in result:
            return r.get("total", 0)
        return 0
    except Exception:
        return 0


def read_live_totals() -> dict:
    """Strict dashboard read: query failures must never masquerade as zero totals."""
    db = get_db()
    if db is None:
        raise RuntimeError("MongoDB is not connected")
    users = db["served_users"].count_documents({})
    chats = db["served_chats"].count_documents({})
    rows = list(db["play_stats"].aggregate([{"$group": {"_id": None, "total": {"$sum": "$count"}}}]))
    plays = int(rows[0].get("total", 0)) if rows else 0
    return {"users": users, "chats": chats, "plays": plays}


# ── Broadcast Chats ────────────────────────────────────────────────────────────

def add_broadcast_chat(chat_id: int, chat_type: str) -> None:
    col = _col("broadcast")
    if col is None:
        return
    try:
        col.update_one(
            {"_id": int(chat_id)},
            {
                "$set": {
                    "_id":     int(chat_id),
                    "chat_id": int(chat_id),
                    "type":    chat_type,
                }
            },
            upsert=True,
        )
    except Exception as e:
        logger.error(f"[DB] add_broadcast_chat: {e}")


def get_broadcast_chats() -> list:
    col = _col("broadcast")
    if col is None:
        return []
    try:
        return list(col.find({}, {"_id": 1, "chat_id": 1, "type": 1}))
    except Exception as e:
        logger.error(f"[DB] get_broadcast_chats: {e}")
        return []


def get_broadcast_count() -> dict:
    col = _col("broadcast")
    if col is None:
        return {"total": 0, "private": 0, "groups": 0}
    try:
        total   = col.count_documents({})
        private = col.count_documents({"type": "private"})
        groups  = col.count_documents({"type": "group"})
        return {"total": total, "private": private, "groups": groups}
    except Exception as e:
        logger.error(f"[DB] get_broadcast_count: {e}")
        return {"total": 0, "private": 0, "groups": 0}


def remove_broadcast_chat(chat_id: int) -> None:
    col = _col("broadcast")
    if col is None:
        return
    try:
        col.delete_one({"_id": int(chat_id)})
    except Exception as e:
        logger.error(f"[DB] remove_broadcast_chat: {e}")


# ── Blocked Groups (gblock) ────────────────────────────────────────────────────

def is_group_blocked(chat_id: int) -> bool:
    col = _col("blocked_groups")
    if col is None:
        return False
    try:
        return col.find_one({"_id": chat_id}) is not None
    except Exception:
        return False


def block_group(chat_id: int) -> None:
    col = _col("blocked_groups")
    if col is None:
        return
    try:
        col.update_one({"_id": chat_id}, {"$set": {"_id": chat_id}}, upsert=True)
    except Exception as e:
        logger.error(f"[DB] block_group: {e}")


def unblock_group(chat_id: int) -> None:
    col = _col("blocked_groups")
    if col is None:
        return
    try:
        col.delete_one({"_id": chat_id})
    except Exception as e:
        logger.error(f"[DB] unblock_group: {e}")


def get_blocked_groups() -> list:
    col = _col("blocked_groups")
    if col is None:
        return []
    try:
        return [doc["_id"] for doc in col.find({}, {"_id": 1})]
    except Exception:
        return []


# ── Blocked Users (ublock) ─────────────────────────────────────────────────────

def is_user_blocked_db(user_id: int) -> bool:
    col = _col("blocked_users")
    if col is None:
        return False
    try:
        return col.find_one({"_id": user_id}) is not None
    except Exception:
        return False


def block_user(user_id: int) -> None:
    col = _col("blocked_users")
    if col is None:
        return
    try:
        col.update_one({"_id": user_id}, {"$set": {"_id": user_id}}, upsert=True)
    except Exception as e:
        logger.error(f"[DB] block_user: {e}")


def unblock_user(user_id: int) -> None:
    col = _col("blocked_users")
    if col is None:
        return
    try:
        col.delete_one({"_id": user_id})
    except Exception as e:
        logger.error(f"[DB] unblock_user: {e}")


def get_blocked_users() -> list:
    col = _col("blocked_users")
    if col is None:
        return []
    try:
        return [doc["_id"] for doc in col.find({}, {"_id": 1})]
    except Exception:
        return []


# ── Chat Effects (speed / bass / effects_on) ───────────────────────────────────

def save_chat_effects(chat_id: int, speed: float, bass: int, enabled: bool) -> None:
    """Save current effect settings for a chat to MongoDB."""
    col = _col("chat_effects")
    if col is None:
        return
    try:
        col.update_one(
            {"_id": chat_id},
            {"$set": {
                "_id":     chat_id,
                "speed":   speed,
                "bass":    bass,
                "enabled": enabled,
            }},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"[DB] save_chat_effects: {e}")


def load_chat_effects(chat_id: int) -> dict:
    """Load effect settings for a chat. Returns defaults if not found."""
    col = _col("chat_effects")
    if col is None:
        return {"speed": 1.0, "bass": 0, "enabled": False}
    try:
        doc = col.find_one({"_id": chat_id})
        if doc:
            return {
                "speed":   doc.get("speed",   1.0),
                "bass":    doc.get("bass",     0),
                "enabled": doc.get("enabled",  False),
            }
    except Exception as e:
        logger.error(f"[DB] load_chat_effects: {e}")
    return {"speed": 1.0, "bass": 0, "enabled": False}


def delete_chat_effects(chat_id: int) -> None:
    """Remove effect settings for a chat."""
    col = _col("chat_effects")
    if col is None:
        return
    try:
        col.delete_one({"_id": chat_id})
    except Exception as e:
        logger.error(f"[DB] delete_chat_effects: {e}")
               
# ── Moderation Filter Settings (NSFW / Bad-word / Link / Document) ───────────
# All four filters live as fields on the same per-chat document so a single
# read/write covers the whole moderation panel. Each defaults to True (ON)
# when unset, so a brand-new group is protected from day one.
#
#   { "_id": chat_id, "nsfw": bool, "badword": bool, "link": bool, "document": bool }
#
# "enabled" is kept in sync with "nsfw" for backward compatibility with any
# older code/data that still reads the original field name directly.

DEFAULT_MOD_SETTINGS = {
    "nsfw":     True,
    "badword":  True,
    "link":     True,
    "document": True,
}


def get_mod_settings(chat_id: int) -> dict:
    """Return all moderation toggles for a chat (defaults True if unset)."""
    col = _col("nsfw_settings")
    if col is None:
        return DEFAULT_MOD_SETTINGS.copy()
    try:
        doc = col.find_one({"_id": chat_id})
        if doc is None:
            return DEFAULT_MOD_SETTINGS.copy()
        settings = DEFAULT_MOD_SETTINGS.copy()
        for key in settings:
            if key in doc:
                settings[key] = doc[key]
            elif key == "nsfw" and "enabled" in doc:
                settings[key] = doc["enabled"]   # legacy field fallback
        return settings
    except Exception as e:
        logger.error(f"[DB] get_mod_settings: {e}")
        return DEFAULT_MOD_SETTINGS.copy()


def set_mod_setting(chat_id: int, key: str, value: bool) -> None:
    if key not in DEFAULT_MOD_SETTINGS:
        return
    col = _col("nsfw_settings")
    if col is None:
        return
    try:
        update = {key: value}
        if key == "nsfw":
            update["enabled"] = value   # keep legacy field in sync
        col.update_one({"_id": chat_id}, {"$set": update}, upsert=True)
    except Exception as e:
        logger.error(f"[DB] set_mod_setting: {e}")


def is_nsfw_enabled(chat_id: int) -> bool:
    return get_mod_settings(chat_id)["nsfw"]


def set_nsfw_enabled(chat_id: int, enabled: bool) -> None:
    set_mod_setting(chat_id, "nsfw", enabled)


def is_badword_enabled(chat_id: int) -> bool:
    return get_mod_settings(chat_id)["badword"]


def set_badword_enabled(chat_id: int, enabled: bool) -> None:
    set_mod_setting(chat_id, "badword", enabled)


def is_link_filter_enabled(chat_id: int) -> bool:
    return get_mod_settings(chat_id)["link"]


def set_link_filter_enabled(chat_id: int, enabled: bool) -> None:
    set_mod_setting(chat_id, "link", enabled)


def is_document_filter_enabled(chat_id: int) -> bool:
    return get_mod_settings(chat_id)["document"]


def set_document_filter_enabled(chat_id: int, enabled: bool) -> None:
    set_mod_setting(chat_id, "document", enabled)


# ── Moderation Approved Users (per-chat whitelist) ───────────────────────────
# An approved user's media/text bypasses ALL moderation filters above
# (NSFW, bad words, links, blocked files) — not just NSFW.

def approve_nsfw_user(chat_id: int, user_id: int) -> None:
    col = _col("nsfw_approved")
    if col is None:
        return
    try:
        col.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$set": {"chat_id": chat_id, "user_id": user_id}},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"[DB] approve_nsfw_user: {e}")


def disapprove_nsfw_user(chat_id: int, user_id: int) -> None:
    col = _col("nsfw_approved")
    if col is None:
        return
    try:
        col.delete_one({"chat_id": chat_id, "user_id": user_id})
    except Exception as e:
        logger.error(f"[DB] disapprove_nsfw_user: {e}")


def is_nsfw_approved(chat_id: int, user_id: int) -> bool:
    col = _col("nsfw_approved")
    if col is None:
        return False
    try:
        return col.find_one({"chat_id": chat_id, "user_id": user_id}) is not None
    except Exception:
        return False


def get_nsfw_approved_users(chat_id: int) -> list:
    col = _col("nsfw_approved")
    if col is None:
        return []
    try:
        return [doc["user_id"] for doc in col.find({"chat_id": chat_id}, {"user_id": 1})]
    except Exception as e:
        logger.error(f"[DB] get_nsfw_approved_users: {e}")
        return []


# ── Warns (per-chat) ───────────────────────────────────────────────────────────
# ``mgmt_warnings`` is the collection /warn writes and
# ``mgmt_chat_settings.warn_threshold`` is the limit it enforces. These helpers
# used to read a parallel store (``warns`` / ``chat_settings``), so the webapp
# could report a different limit from the one the bot applied.
WARN_COLLECTION = "mgmt_warnings"
SETTINGS_COLLECTION = "mgmt_chat_settings"


def add_warn(chat_id: int, user_id: int, reason: str = "") -> int:
    """Add a warn to the store /warn uses and return the new total."""
    col = _col(WARN_COLLECTION)
    if col is None:
        return 0
    try:
        document = col.find_one({"chat_id": chat_id, "user_id": user_id}) or {}
        count = int(document.get("count", 0)) + 1
        col.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {
                "$set": {"count": count, "updated": datetime.now(timezone.utc)},
                "$push": {"reasons": {"reason": reason or "No reason", "ts": datetime.now(timezone.utc).isoformat()}},
                "$setOnInsert": {"chat_id": chat_id, "user_id": user_id},
            },
            upsert=True,
        )
        return count
    except Exception as e:
        logger.error(f"[DB] add_warn: {e}")
        return 0


def warn_reason_text(item) -> str:
    """Reasons are stored as {reason, ts} by /warn; older rows are plain text."""
    if isinstance(item, dict):
        return str(item.get("reason") or "")
    return str(item or "")


def get_warns(chat_id: int, user_id: int) -> dict:
    col = _col(WARN_COLLECTION)
    if col is None:
        return {"count": 0, "reasons": []}
    try:
        doc = col.find_one({"chat_id": chat_id, "user_id": user_id})
        if not doc:
            return {"count": 0, "reasons": []}
        return {
            "count": int(doc.get("count", 0)),
            "reasons": [warn_reason_text(item) for item in doc.get("reasons", [])],
        }
    except Exception as e:
        logger.error(f"[DB] get_warns: {e}")
        return {"count": 0, "reasons": []}


def list_warns(chat_id: int, limit: int = 100, decay_days: int = 0) -> list:
    """Every member with warnings in one chat, newest first.

    ``count`` is what still counts after the decay window; ``total`` is what is
    on record. A group with decay switched off gets identical numbers.
    """
    from videl.utils import warnings as warning_rules

    col = _col(WARN_COLLECTION)
    if col is None:
        return []
    try:
        documents = list(
            col.find({"chat_id": chat_id, "count": {"$gte": 1}}).sort("updated", -1).limit(max(1, min(int(limit), 300)))
        )
    except Exception as e:
        logger.error(f"[DB] list_warns: {e}")
        return []
    rows = []
    for document in documents:
        state = warning_rules.active_warnings(document, decay_days)
        if state["count"] <= 0:
            # Every warning has lapsed; the member is not on the list.
            continue
        rows.append({
            "user_id": int(document.get("user_id") or 0),
            "count": state["count"],
            "total": state["total"],
            "decayed": state["decayed"],
            "reasons": [warn_reason_text(item) for item in (document.get("reasons") or [])][-10:],
        })
    return rows


def reset_warns(chat_id: int, user_id: int) -> None:
    col = _col(WARN_COLLECTION)
    if col is None:
        return
    try:
        col.delete_one({"chat_id": chat_id, "user_id": user_id})
    except Exception as e:
        logger.error(f"[DB] reset_warns: {e}")


def get_warn_limit(chat_id: int) -> int:
    col = _col(SETTINGS_COLLECTION)
    if col is None:
        return 3
    try:
        doc = col.find_one({"chat_id": chat_id})
        value = int((doc or {}).get("warn_threshold", 3) or 3)
        return value if 1 <= value <= 10 else 3
    except Exception:
        return 3


def set_warn_limit(chat_id: int, limit: int) -> None:
    col = _col(SETTINGS_COLLECTION)
    if col is None:
        return
    try:
        col.update_one(
            {"chat_id": chat_id},
            {"$set": {"warn_threshold": max(1, min(int(limit), 10))}},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"[DB] set_warn_limit: {e}")


# ── Welcome / Goodbye ──────────────────────────────────────────────────────────

def get_welcome(chat_id: int) -> dict:
    col = _col("welcome")
    if col is None:
        return {"enabled": False, "text": "", "delete_old": False}
    try:
        doc = col.find_one({"_id": chat_id})
        if not doc:
            return {"enabled": False, "text": "", "delete_old": False}
        return {
            "enabled": bool(doc.get("enabled", False)),
            "text": doc.get("text", ""),
            "delete_old": bool(doc.get("delete_old", False)),
        }
    except Exception as e:
        logger.error(f"[DB] get_welcome: {e}")
        return {"enabled": False, "text": "", "delete_old": False}


def set_welcome(chat_id: int, text: str, enabled: bool = True) -> None:
    col = _col("welcome")
    if col is None:
        return
    try:
        col.update_one(
            {"_id": chat_id},
            {"$set": {"_id": chat_id, "text": text, "enabled": enabled}},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"[DB] set_welcome: {e}")


def set_welcome_enabled(chat_id: int, enabled: bool) -> None:
    col = _col("welcome")
    if col is None:
        return
    try:
        col.update_one(
            {"_id": chat_id},
            {"$set": {"enabled": enabled}},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"[DB] set_welcome_enabled: {e}")


def get_goodbye(chat_id: int) -> dict:
    col = _col("goodbye")
    if col is None:
        return {"enabled": False, "text": ""}
    try:
        doc = col.find_one({"_id": chat_id})
        if not doc:
            return {"enabled": False, "text": ""}
        return {
            "enabled": bool(doc.get("enabled", False)),
            "text": doc.get("text", ""),
        }
    except Exception as e:
        logger.error(f"[DB] get_goodbye: {e}")
        return {"enabled": False, "text": ""}


def set_goodbye(chat_id: int, text: str, enabled: bool = True) -> None:
    col = _col("goodbye")
    if col is None:
        return
    try:
        col.update_one(
            {"_id": chat_id},
            {"$set": {"_id": chat_id, "text": text, "enabled": enabled}},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"[DB] set_goodbye: {e}")


# ── Playlists (user + group) ───────────────────────────────────────────────────

def save_playlist(owner_id: int, name: str, songs: list, is_group: bool = False) -> bool:
    """Save or overwrite a playlist. owner_id is user_id or chat_id."""
    col = _col("playlists")
    if col is None:
        return False
    try:
        col.update_one(
            {"owner_id": owner_id, "name": name.lower()},
            {
                "$set": {
                    "owner_id": owner_id,
                    "name": name.lower(),
                    "display_name": name,
                    "songs": songs[:50],  # hard limit
                    "is_group": is_group,
                    "updated_at": __import__("time").time(),
                }
            },
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f"[DB] save_playlist: {e}")
        return False


def get_playlist(owner_id: int, name: str) -> dict | None:
    col = _col("playlists")
    if col is None:
        return None
    try:
        return col.find_one({"owner_id": owner_id, "name": name.lower()})
    except Exception as e:
        logger.error(f"[DB] get_playlist: {e}")
        return None


def list_playlists(owner_id: int) -> list:
    col = _col("playlists")
    if col is None:
        return []
    try:
        return list(col.find({"owner_id": owner_id}, {"name": 1, "display_name": 1, "songs": 1}))
    except Exception as e:
        logger.error(f"[DB] list_playlists: {e}")
        return []


def delete_playlist(owner_id: int, name: str) -> bool:
    col = _col("playlists")
    if col is None:
        return False
    try:
        res = col.delete_one({"owner_id": owner_id, "name": name.lower()})
        return res.deleted_count > 0
    except Exception as e:
        logger.error(f"[DB] delete_playlist: {e}")
        return False


# ── Chat settings (skip votes, antiflood, locks) ───────────────────────────────

def get_chat_setting(chat_id: int, key: str, default=None):
    col = _col(SETTINGS_COLLECTION)
    if col is None:
        return default
    try:
        doc = col.find_one({"chat_id": chat_id})
        if not doc:
            return default
        return doc.get(key, default)
    except Exception:
        return default


def set_chat_setting(chat_id: int, key: str, value) -> None:
    col = _col(SETTINGS_COLLECTION)
    if col is None:
        return
    try:
        col.update_one(
            {"chat_id": chat_id},
            {"$set": {key: value}},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"[DB] set_chat_setting: {e}")


def get_skip_votes_needed(chat_id: int) -> int:
    """0 = anyone can skip (admins still always can). Default 0."""
    return int(get_chat_setting(chat_id, "skip_votes", 0) or 0)


def set_skip_votes_needed(chat_id: int, n: int) -> None:
    set_chat_setting(chat_id, "skip_votes", max(0, min(n, 20)))


def get_antiflood(chat_id: int) -> dict:
    return get_chat_setting(chat_id, "antiflood", {"enabled": False, "limit": 6, "window": 8}) or {
        "enabled": False, "limit": 6, "window": 8
    }


def set_antiflood(chat_id: int, enabled: bool, limit: int = 6, window: int = 8) -> None:
    set_chat_setting(chat_id, "antiflood", {
        "enabled": enabled,
        "limit": max(3, min(limit, 30)),
        "window": max(3, min(window, 60)),
    })


# ── Linked channel for /cplay ──────────────────────────────────────────────────

def set_linked_channel(chat_id: int, channel_id: int) -> None:
    set_chat_setting(chat_id, "linked_channel", int(channel_id))


def get_linked_channel(chat_id: int):
    val = get_chat_setting(chat_id, "linked_channel", None)
    try:
        return int(val) if val is not None else None
    except Exception:
        return None


def clear_linked_channel(chat_id: int) -> None:
    set_chat_setting(chat_id, "linked_channel", None)


# ── Activity tracking + 30-day auto cleanup ────────────────────────────────────

def touch_chat_activity(chat_id: int) -> None:
    """Mark a chat as active (call on play / commands)."""
    col = _col("chat_activity")
    if col is None:
        return
    try:
        import time as _t
        col.update_one(
            {"_id": chat_id},
            {"$set": {"_id": chat_id, "last_active": _t.time()}},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"[DB] touch_chat_activity: {e}")


def touch_user_activity(user_id: int) -> None:
    col = _col("user_activity")
    if col is None:
        return
    try:
        import time as _t
        col.update_one(
            {"_id": user_id},
            {"$set": {"_id": user_id, "last_active": _t.time()}},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"[DB] touch_user_activity: {e}")


def cleanup_old_data(days: int = 30, *, apply: bool = False) -> dict:
    """Preview by default; prune only disposable telemetry and delivered reminders.

    Never infer that a group left, a user blocked the bot, or a playlist is
    unwanted from age. Settings, memberships, counters, pending work and all
    user-authored content are deliberately outside this allowlist.
    """
    import time
    from datetime import datetime, timezone
    if not isinstance(days, int) or isinstance(days, bool) or not 7 <= days <= 365:
        raise ValueError("Retention must be between 7 and 365 days")
    if _db is None:
        return {"ok": False, "error": "Database unavailable", "applied": False}
    cutoff = time.time() - days * 86400
    filters = {
        "chat_activity": {"last_active": {"$type": "number", "$lt": cutoff}},
        "user_activity": {"last_active": {"$type": "number", "$lt": cutoff}},
        "plugin_reminders": {"status": "sent", "sent_at": {
            "$type": "date", "$lt": datetime.fromtimestamp(cutoff, timezone.utc)}},
    }
    stats = {"ok": True, "applied": apply, "retention_days": days, "counts": {}, "errors": []}
    for name, query in filters.items():
        try:
            collection = _col(name)
            # Delete with the same age/status predicate, not IDs from a stale read.
            stats["counts"][name] = (collection.delete_many(query).deleted_count if apply
                                      else collection.count_documents(query))
        except Exception:
            logger.exception("Safe retention failed for %s", name)
            stats["ok"] = False
            stats["errors"].append(name)
    return stats


# ════════════════════════════════════════════════════════════════════════════════
#  Elite Group Help — better than Rose / GroupHelp
#  Inspired by PaulSonOfLars/tgbot, AnonymousX1025/FallenRobot, botdev72/GroupHelp
#  + AnnieXMusic group management patterns — all credited, none copied
# ════════════════════════════════════════════════════════════════════════════════

# ── Federations (Rose-style fed bans across groups) ───────────────────────────

def create_fed(fed_id: str, name: str, owner_id: int) -> bool:
    col = _col("feds")
    if col is None: return False
    try:
        col.update_one({"_id": fed_id}, {"$set": {"_id": fed_id, "name": name, "owner": owner_id, "created": __import__("time").time()}}, upsert=True)
        col2 = _col("fed_chats"); col2.update_one({"fed": fed_id, "chat": -1}, {"$set": {"fed": fed_id, "chat": -1}}, upsert=True)
        return True
    except Exception as e: logger.error(f"[fed] create: {e}"); return False

def delete_fed(fed_id: str) -> bool:
    col = _col("feds")
    if col is None: return False
    try:
        col.delete_one({"_id": fed_id}); _col("fed_chats").delete_many({"fed": fed_id}); _col("fed_bans").delete_many({"fed": fed_id}); _col("fed_admins").delete_many({"fed": fed_id}); return True
    except Exception as e: logger.error(f"[fed] delete: {e}"); return False

def get_fed(fed_id: str) -> dict | None:
    col = _col("feds")
    if col is None: return None
    try: return col.find_one({"_id": fed_id})
    except: return None

def list_feds() -> list:
    col = _col("feds")
    if col is None: return []
    try: return list(col.find({}))
    except: return []

def join_fed_chat(fed_id: str, chat_id: int) -> bool:
    col = _col("fed_chats")
    if col is None: return False
    try: col.update_one({"fed": fed_id, "chat": chat_id}, {"$set": {"fed": fed_id, "chat": chat_id}}, upsert=True); return True
    except Exception as e: logger.error(f"[fed] join: {e}"); return False

def leave_fed_chat(fed_id: str, chat_id: int) -> bool:
    col = _col("fed_chats")
    if col is None: return False
    try: col.delete_one({"fed": fed_id, "chat": chat_id}); return True
    except: return False

def get_chat_fed(chat_id: int) -> str | None:
    col = _col("fed_chats")
    if col is None: return None
    try:
        doc = col.find_one({"chat": chat_id})
        return doc["fed"] if doc else None
    except: return None

def set_chat_fed(chat_id: int, fed_id: str | None) -> None:
    col = _col("fed_chats")
    if col is None: return
    try:
        if fed_id is None: col.delete_one({"chat": chat_id})
        else: col.update_one({"chat": chat_id}, {"$set": {"fed": fed_id, "chat": chat_id}}, upsert=True)
    except Exception as e: logger.error(f"[fed] set_chat: {e}")

def fban(fed_id: str, user_id: int, reason: str, banner: int) -> bool:
    col = _col("fed_bans")
    if col is None: return False
    try: col.update_one({"fed": fed_id, "user": user_id}, {"$set": {"fed": fed_id, "user": user_id, "reason": reason, "banner": banner, "time": __import__("time").time()}}, upsert=True); return True
    except Exception as e: logger.error(f"[fban]: {e}"); return False

def unfban(fed_id: str, user_id: int) -> bool:
    col = _col("fed_bans")
    if col is None: return False
    try: col.delete_one({"fed": fed_id, "user": user_id}); return True
    except: return False

def get_fban(fed_id: str, user_id: int) -> dict | None:
    col = _col("fed_bans")
    if col is None: return None
    try: return col.find_one({"fed": fed_id, "user": user_id})
    except: return None

def list_fbans(fed_id: str) -> list:
    col = _col("fed_bans")
    if col is None: return []
    try: return list(col.find({"fed": fed_id}))
    except: return []

def is_fbanned_any(user_id: int) -> dict | None:
    col = _col("fed_bans")
    if col is None: return None
    try: return col.find_one({"user": user_id})
    except: return None

def fed_add_admin(fed_id: str, user_id: int) -> None:
    col = _col("fed_admins")
    if col is None: return
    try: col.update_one({"fed": fed_id, "user": user_id}, {"$set": {"fed": fed_id, "user": user_id}}, upsert=True)
    except: pass

def fed_remove_admin(fed_id: str, user_id: int) -> None:
    col = _col("fed_admins")
    if col is None: return
    try: col.delete_one({"fed": fed_id, "user": user_id})
    except: pass

def fed_list_admins(fed_id: str) -> list:
    col = _col("fed_admins")
    if col is None: return []
    try: return [d["user"] for d in col.find({"fed": fed_id})]
    except: return []

def is_fed_admin(fed_id: str, user_id: int) -> bool:
    fed = get_fed(fed_id)
    if not fed: return False
    if fed.get("owner") == user_id: return True
    return user_id in fed_list_admins(fed_id)

def get_fed_chats(fed_id: str) -> list:
    col = _col("fed_chats")
    if col is None: return []
    try: return [d["chat"] for d in col.find({"fed": fed_id, "chat": {"$ne": -1}})]
    except: return []


# ── Blacklist (words + stickers) — FallenRobot style ─────────────────────────

def add_blacklist(chat_id: int, trigger: str, mode: str = "del") -> None:
    col = _col("blacklist")
    if col is None: return
    try: col.update_one({"chat": chat_id, "trigger": trigger.lower()}, {"$set": {"chat": chat_id, "trigger": trigger.lower(), "mode": mode}}, upsert=True)
    except Exception as e: logger.error(f"[bl] add: {e}")

def remove_blacklist(chat_id: int, trigger: str) -> bool:
    col = _col("blacklist")
    if col is None: return False
    try: r=col.delete_one({"chat": chat_id, "trigger": trigger.lower()}); return r.deleted_count>0
    except: return False

def get_blacklist(chat_id: int) -> list:
    col = _col("blacklist")
    if col is None: return []
    try: return list(col.find({"chat": chat_id}))
    except: return []

def get_blacklist_mode(chat_id: int) -> str:
    col = _col(SETTINGS_COLLECTION)
    if col is None: return "del"
    try:
        doc=col.find_one({"chat_id": chat_id})
        return (doc or {}).get("blacklist_mode","del")
    except: return "del"

def set_blacklist_mode(chat_id: int, mode: str) -> None:
    col = _col(SETTINGS_COLLECTION)
    if col is None: return
    try: col.update_one({"chat_id": chat_id}, {"$set": {"blacklist_mode": mode}}, upsert=True)
    except: pass

def add_blacklist_sticker(chat_id: int, file_unique: str) -> None:
    col = _col("bl_stickers")
    if col is None: return
    try: col.update_one({"chat": chat_id, "sticker": file_unique}, {"$set": {"chat": chat_id, "sticker": file_unique}}, upsert=True)
    except: pass

def remove_blacklist_sticker(chat_id: int, file_unique: str) -> bool:
    col = _col("bl_stickers")
    if col is None: return False
    try: r=col.delete_one({"chat": chat_id, "sticker": file_unique}); return r.deleted_count>0
    except: return False

def is_bl_sticker(chat_id: int, file_unique: str) -> bool:
    col = _col("bl_stickers")
    if col is None: return False
    try: return col.find_one({"chat": chat_id, "sticker": file_unique}) is not None
    except: return False

def list_bl_stickers(chat_id: int) -> list:
    col = _col("bl_stickers")
    if col is None: return []
    try: return [d["sticker"] for d in col.find({"chat": chat_id})]
    except: return []


# ── Approve (whitelist from locks/antiflood) ─────────────────────────────────

def approve_user(chat_id: int, user_id: int) -> None:
    col = _col("approved")
    if col is None: return
    try: col.update_one({"chat": chat_id, "user": user_id}, {"$set": {"chat": chat_id, "user": user_id}}, upsert=True)
    except Exception as e: logger.error(f"[approve]: {e}")

def disapprove_user(chat_id: int, user_id: int) -> bool:
    col = _col("approved")
    if col is None: return False
    try: r=col.delete_one({"chat": chat_id, "user": user_id}); return r.deleted_count>0
    except: return False

def is_approved(chat_id: int, user_id: int) -> bool:
    col = _col("approved")
    if col is None: return False
    try: return col.find_one({"chat": chat_id, "user": user_id}) is not None
    except: return False

def list_approved(chat_id: int) -> list:
    col = _col("approved")
    if col is None: return []
    try: return [d["user"] for d in col.find({"chat": chat_id})]
    except: return []


# ── Captcha / verification ────────────────────────────────────────────────────

def get_captcha(chat_id: int) -> dict:
    col = _col("chat_settings")
    if col is None: return {"enabled": False, "mode": "math", "timeout": 120}
    try:
        doc=col.find_one({"_id": chat_id}) or {}
        c=doc.get("captcha", {"enabled": False, "mode": "math", "timeout": 120})
        if isinstance(c, bool): c={"enabled": c, "mode": "math", "timeout": 120}
        return c
    except: return {"enabled": False, "mode": "math", "timeout": 120}

def set_captcha(chat_id: int, enabled: bool, mode: str = "math", timeout: int = 120) -> None:
    col = _col("chat_settings")
    if col is None: return
    try: col.update_one({"_id": chat_id}, {"$set": {"captcha": {"enabled": enabled, "mode": mode, "timeout": timeout}}}, upsert=True)
    except Exception as e: logger.error(f"[captcha] set: {e}")


# ── Disable commands per chat ─────────────────────────────────────────────────

def disable_cmd(chat_id: int, cmd: str) -> None:
    col = _col("disabled_cmds")
    if col is None: return
    try: col.update_one({"chat": chat_id, "cmd": cmd.lower()}, {"$set": {"chat": chat_id, "cmd": cmd.lower()}}, upsert=True)
    except: pass
    _DISABLED_CACHE.pop(chat_id, None)

def enable_cmd(chat_id: int, cmd: str) -> bool:
    col = _col("disabled_cmds")
    _DISABLED_CACHE.pop(chat_id, None)
    if col is None: return False
    try: r=col.delete_one({"chat": chat_id, "cmd": cmd.lower()}); return r.deleted_count>0
    except: return False

# Every group command asks whether it is switched off. A short cache keeps that
# from becoming one Mongo read per command message; the writes below invalidate
# it immediately so the panel's toggle is visible on the next message.
_DISABLED_CACHE = {}
_DISABLED_TTL = 30.0


def _disabled_set(chat_id: int):
    import time as _time
    entry = _DISABLED_CACHE.get(chat_id)
    moment = _time.monotonic()
    if entry and moment - entry[0] < _DISABLED_TTL:
        return entry[1]
    names = {str(name).lower() for name in list_disabled(chat_id)}
    _DISABLED_CACHE[chat_id] = (moment, names)
    while len(_DISABLED_CACHE) > 5000:
        _DISABLED_CACHE.pop(next(iter(_DISABLED_CACHE)))
    return names


def is_disabled(chat_id: int, cmd: str) -> bool:
    if _col("disabled_cmds") is None: return False
    try: return str(cmd).lower() in _disabled_set(chat_id)
    except: return False

def list_disabled(chat_id: int) -> list:
    col = _col("disabled_cmds")
    if col is None: return []
    try: return [d["cmd"] for d in col.find({"chat": chat_id})]
    except: return []


# ── Connections (admin controls group via PM) ─────────────────────────────────

def connect_user(user_id: int, chat_id: int) -> None:
    col = _col("connections")
    if col is None: return
    try: col.update_one({"user": user_id}, {"$set": {"user": user_id, "chat": chat_id}}, upsert=True)
    except: pass

def disconnect_user(user_id: int) -> None:
    col = _col("connections")
    if col is None: return
    try: col.delete_one({"user": user_id})
    except: pass

def get_connected_chat(user_id: int) -> int | None:
    col = _col("connections")
    if col is None: return None
    try:
        doc=col.find_one({"user": user_id})
        return doc["chat"] if doc else None
    except: return None

def allow_connect(chat_id: int, allow: bool) -> None:
    col = _col("chat_settings")
    if col is None: return
    try: col.update_one({"_id": chat_id}, {"$set": {"allow_connect": allow}}, upsert=True)
    except: pass

def is_connect_allowed(chat_id: int) -> bool:
    col = _col("chat_settings")
    if col is None: return False
    try:
        doc=col.find_one({"_id": chat_id})
        return bool(doc.get("allow_connect", False)) if doc else False
    except: return False


# ── Reports / log channel / back-ups / nightmode / cleaner ────────────────────

def set_log_channel(chat_id: int, log_chat: int | None) -> None:
    col = _col("chat_settings")
    if col is None: return
    try: col.update_one({"_id": chat_id}, {"$set": {"log_channel": log_chat}}, upsert=True)
    except: pass

def get_log_channel(chat_id: int) -> int | None:
    col = _col("chat_settings")
    if col is None: return None
    try:
        doc=col.find_one({"_id": chat_id})
        return doc.get("log_channel") if doc else None
    except: return None

def set_reports(chat_id: int, enabled: bool) -> None:
    col = _col("chat_settings")
    if col is None: return
    try: col.update_one({"_id": chat_id}, {"$set": {"reports": enabled}}, upsert=True)
    except: pass

def get_reports(chat_id: int) -> bool:
    col = _col("chat_settings")
    if col is None: return True
    try:
        doc=col.find_one({"_id": chat_id})
        return bool(doc.get("reports", True)) if doc else True
    except: return True

def set_clean_service(chat_id: int, enabled: bool) -> None:
    col = _col("chat_settings")
    if col is None: return
    try: col.update_one({"_id": chat_id}, {"$set": {"clean_service": enabled}}, upsert=True)
    except: pass

def get_clean_service(chat_id: int) -> bool:
    col = _col("chat_settings")
    if col is None: return False
    try:
        doc=col.find_one({"_id": chat_id})
        return bool(doc.get("clean_service", False)) if doc else False
    except: return False

def set_nightmode(chat_id: int, enabled: bool, start: str = "00:00", end: str = "06:00") -> None:
    col = _col("chat_settings")
    if col is None: return
    try: col.update_one({"_id": chat_id}, {"$set": {"nightmode": {"enabled": enabled, "start": start, "end": end}}}, upsert=True)
    except: pass

def get_nightmode(chat_id: int) -> dict:
    col = _col("chat_settings")
    if col is None: return {"enabled": False, "start": "00:00", "end": "06:00"}
    try:
        doc=col.find_one({"_id": chat_id})
        return doc.get("nightmode", {"enabled": False, "start": "00:00", "end": "06:00"}) if doc else {"enabled": False, "start": "00:00", "end": "06:00"}
    except: return {"enabled": False, "start": "00:00", "end": "06:00"}

# ── Automation (quiet hours + warning escalation) ─────────────────────────────
# Stored in the same document the group manager writes, so there is one source
# of truth. Normalisation lives in videl.utils.automation.

def get_automation(chat_id: int) -> dict:
    from videl.utils.automation import normalize
    col = _col(SETTINGS_COLLECTION)
    if col is None:
        return normalize({})
    try:
        document = col.find_one({"chat_id": chat_id}) or {}
    except Exception:
        return normalize({})
    return normalize(document.get("automation"))


def set_automation(chat_id: int, *, quiet_hours=None, escalation=None, protection=None) -> dict:
    """Merge one or more blocks and return the complete normalised config."""
    from videl.utils.automation import normalize
    col = _col(SETTINGS_COLLECTION)
    current = get_automation(chat_id)
    if quiet_hours is not None:
        current["quiet_hours"] = {**current["quiet_hours"], **(quiet_hours or {})}
    if escalation is not None:
        current["escalation"] = {**current["escalation"], **(escalation or {})}
    if protection is not None:
        current["protection"] = {**current.get("protection", {}), **(protection or {})}
    current = normalize(current)
    if col is not None:
        try:
            col.update_one({"chat_id": chat_id}, {"$set": {"automation": current}}, upsert=True)
        except Exception as e:
            logger.error(f"[automation] set: {e}")
    return current


def set_protection_state(chat_id: int, state: dict) -> None:
    """Write only the run state, so a slow tick cannot overwrite fresh settings."""
    from videl.utils.automation import normalize_protection_state
    col = _col(SETTINGS_COLLECTION)
    if col is None:
        return
    try:
        col.update_one(
            {"chat_id": chat_id},
            {"$set": {"automation.protection.state": normalize_protection_state(state)}},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"[automation] protection state: {e}")


def get_escalation(chat_id: int) -> dict:
    return get_automation(chat_id)["escalation"]


def get_quiet_hours(chat_id: int) -> dict:
    return get_automation(chat_id)["quiet_hours"]


def save_backup(chat_id: int, data: dict) -> str:
    col = _col("backups")
    if col is None: return ""
    try:
        bid=__import__("uuid").uuid4().hex[:8]
        col.update_one({"_id": bid}, {"$set": {"_id": bid, "chat": chat_id, "data": data, "time": __import__("time").time()}}, upsert=True)
        return bid
    except: return ""

def get_backup(bid: str) -> dict | None:
    col = _col("backups")
    if col is None: return None
    try: return col.find_one({"_id": bid})
    except: return None

# ── Costume stickers (premium costume per chat event) ─────────────────────────

def set_costume(chat_id: int, event: str, file_id: str) -> None:
    col = _col("costume_stickers")
    if col is None: return
    try: col.update_one({"chat": chat_id, "event": event.lower()}, {"$set": {"chat": chat_id, "event": event.lower(), "file_id": file_id}}, upsert=True)
    except Exception as e: logger.error(f"[costume] set: {e}")

def get_costume(chat_id: int, event: str) -> str | None:
    col = _col("costume_stickers")
    if col is None: return None
    try:
        doc=col.find_one({"chat": chat_id, "event": event.lower()})
        return doc["file_id"] if doc else None
    except: return None

def del_costume(chat_id: int, event: str) -> bool:
    col = _col("costume_stickers")
    if col is None: return False
    try: r=col.delete_one({"chat": chat_id, "event": event.lower()}); return r.deleted_count>0
    except: return False

def list_costumes(chat_id: int) -> list:
    col = _col("costume_stickers")
    if col is None: return []
    try: return list(col.find({"chat": chat_id}))
    except: return []

