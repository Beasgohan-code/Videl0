# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import logging
import os
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
        _client = MongoClient(config.MONGO_DB_URL, serverSelectionTimeoutMS=5000)
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

def add_warn(chat_id: int, user_id: int, reason: str = "") -> int:
    """Add a warn and return new total count for this user in the chat."""
    col = _col("warns")
    if col is None:
        return 0
    try:
        col.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {
                "$inc": {"count": 1},
                "$push": {"reasons": reason or "No reason"},
                "$setOnInsert": {"chat_id": chat_id, "user_id": user_id},
            },
            upsert=True,
        )
        doc = col.find_one({"chat_id": chat_id, "user_id": user_id})
        return int(doc.get("count", 0)) if doc else 1
    except Exception as e:
        logger.error(f"[DB] add_warn: {e}")
        return 0


def get_warns(chat_id: int, user_id: int) -> dict:
    col = _col("warns")
    if col is None:
        return {"count": 0, "reasons": []}
    try:
        doc = col.find_one({"chat_id": chat_id, "user_id": user_id})
        if not doc:
            return {"count": 0, "reasons": []}
        return {"count": int(doc.get("count", 0)), "reasons": list(doc.get("reasons", []))}
    except Exception as e:
        logger.error(f"[DB] get_warns: {e}")
        return {"count": 0, "reasons": []}


def reset_warns(chat_id: int, user_id: int) -> None:
    col = _col("warns")
    if col is None:
        return
    try:
        col.delete_one({"chat_id": chat_id, "user_id": user_id})
    except Exception as e:
        logger.error(f"[DB] reset_warns: {e}")


def get_warn_limit(chat_id: int) -> int:
    col = _col("chat_settings")
    if col is None:
        return 3
    try:
        doc = col.find_one({"_id": chat_id})
        return int(doc.get("warn_limit", 3)) if doc else 3
    except Exception:
        return 3


def set_warn_limit(chat_id: int, limit: int) -> None:
    col = _col("chat_settings")
    if col is None:
        return
    try:
        col.update_one(
            {"_id": chat_id},
            {"$set": {"warn_limit": max(1, min(limit, 20))}},
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
    col = _col("chat_settings")
    if col is None:
        return default
    try:
        doc = col.find_one({"_id": chat_id})
        if not doc:
            return default
        return doc.get(key, default)
    except Exception:
        return default


def set_chat_setting(chat_id: int, key: str, value) -> None:
    col = _col("chat_settings")
    if col is None:
        return
    try:
        col.update_one(
            {"_id": chat_id},
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


def cleanup_old_data(days: int = 30) -> dict:
    """
    Remove inactive / stale data older than `days`.
    Returns counts of deleted documents per collection.
    """
    import time as _t
    cutoff = _t.time() - (days * 86400)
    stats: dict = {}

    if _db is None:
        return {"error": "no db"}

    # Inactive chats
    try:
        col = _col("chat_activity")
        if col is not None:
            stale = list(col.find({"last_active": {"$lt": cutoff}}, {"_id": 1}))
            ids = [d["_id"] for d in stale]
            if ids:
                col.delete_many({"_id": {"$in": ids}})
                for name in ("served_chats", "play_stats", "chat_effects",
                             "chat_settings", "welcome", "goodbye", "nsfw_settings"):
                    c = _col(name)
                    if c is not None:
                        c.delete_many({"_id": {"$in": ids}})
            stats["inactive_chats"] = len(ids)
        else:
            stats["inactive_chats"] = 0
    except Exception as e:
        logger.error(f"[cleanup] chats: {e}")
        stats["inactive_chats"] = 0

    # Inactive users
    try:
        col = _col("user_activity")
        if col is not None:
            stale = list(col.find({"last_active": {"$lt": cutoff}}, {"_id": 1}))
            ids = [d["_id"] for d in stale]
            if ids:
                col.delete_many({"_id": {"$in": ids}})
                su = _col("served_users")
                if su is not None:
                    su.delete_many({"_id": {"$in": ids}})
            stats["inactive_users"] = len(ids)
        else:
            stats["inactive_users"] = 0
    except Exception as e:
        logger.error(f"[cleanup] users: {e}")
        stats["inactive_users"] = 0

    # Old playlists
    try:
        col = _col("playlists")
        if col is not None:
            res = col.delete_many({"updated_at": {"$lt": cutoff}})
            stats["old_playlists"] = res.deleted_count
        else:
            stats["old_playlists"] = 0
    except Exception as e:
        logger.error(f"[cleanup] playlists: {e}")
        stats["old_playlists"] = 0

    logger.info(f"[cleanup] {days}-day cleanup done: {stats}")
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
    col = _col("chat_settings")
    if col is None: return "del"
    try:
        doc=col.find_one({"_id": chat_id})
        return doc.get("blacklist_mode","del") if doc else "del"
    except: return "del"

def set_blacklist_mode(chat_id: int, mode: str) -> None:
    col = _col("chat_settings")
    if col is None: return
    try: col.update_one({"_id": chat_id}, {"$set": {"blacklist_mode": mode}}, upsert=True)
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

def enable_cmd(chat_id: int, cmd: str) -> bool:
    col = _col("disabled_cmds")
    if col is None: return False
    try: r=col.delete_one({"chat": chat_id, "cmd": cmd.lower()}); return r.deleted_count>0
    except: return False

def is_disabled(chat_id: int, cmd: str) -> bool:
    col = _col("disabled_cmds")
    if col is None: return False
    try: return col.find_one({"chat": chat_id, "cmd": cmd.lower()}) is not None
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

