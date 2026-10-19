"""
Videl0 • Database Layer
Supabase-first with SQLite fallback for local dev / offline.
All tables prefixed videl_* to avoid collision with existing hanre-studio schema.
"""
import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from bot.config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY

log = logging.getLogger("videl.db")

try:
    from supabase import create_client, Client  # type: ignore
    _has_supabase = True
except ImportError:
    _has_supabase = False

DB_PATH = Path(__file__).parent.parent / "videl.db"

# ── SQLite fallback setup ─────────────────────────────────────────────────
SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS videl_users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, is_banned INTEGER DEFAULT 0, is_sudo INTEGER DEFAULT 0, credits INTEGER DEFAULT 100, lang TEXT DEFAULT 'en', created_at TEXT DEFAULT CURRENT_TIMESTAMP, last_seen TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS videl_chats (id INTEGER PRIMARY KEY, title TEXT, type TEXT, is_disabled INTEGER DEFAULT 0, settings TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS videl_warnings (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER, reason TEXT, warned_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS videl_filters (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, keyword TEXT, reply_text TEXT, reply_media TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(chat_id, keyword));
CREATE TABLE IF NOT EXISTS videl_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, name TEXT, content TEXT, media_file_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(chat_id, name));
CREATE TABLE IF NOT EXISTS videl_music_queue (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, title TEXT, url TEXT, thumbnail TEXT, duration INTEGER, requested_by INTEGER, position INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS videl_ai_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, chat_id INTEGER, role TEXT, content TEXT, model TEXT DEFAULT 'gpt-4o-mini', tokens INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS videl_afk (user_id INTEGER PRIMARY KEY, reason TEXT, since TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS videl_gbans (user_id INTEGER PRIMARY KEY, reason TEXT, banned_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS videl_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, level TEXT, event TEXT, chat_id INTEGER, user_id INTEGER, meta TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS videl_stats (id INTEGER PRIMARY KEY AUTOINCREMENT, command TEXT, chat_id INTEGER, user_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS videl_playlists (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, tracks TEXT DEFAULT '[]', created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, name));
CREATE TABLE IF NOT EXISTS videl_giveaways (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, prize TEXT, winners_count INTEGER DEFAULT 1, participants TEXT DEFAULT '[]', ends_at TEXT, is_active INTEGER DEFAULT 1, created_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""

class Database:
    def __init__(self):
        self.supabase: Optional[Any] = None
        self.use_supabase = False
        self._sqlite: Optional[sqlite3.Connection] = None

        # Try Supabase
        if _has_supabase and SUPABASE_URL and SUPABASE_KEY:
            try:
                key = SUPABASE_SERVICE_KEY or SUPABASE_KEY
                self.supabase = create_client(SUPABASE_URL, key)
                # test query
                self.supabase.table("videl_users").select("id").limit(1).execute()
                self.use_supabase = True
                log.info("◍ sᴜᴘᴀʙᴀsᴇ — ᴄᴏɴɴᴇᴄᴛᴇᴅ ◍")
            except Exception as e:
                log.warning(f"Supabase init failed, falling back to SQLite: {e}")
                self.supabase = None

        if not self.use_supabase:
            self._init_sqlite()

    def _init_sqlite(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._sqlite = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._sqlite.row_factory = sqlite3.Row
        self._sqlite.executescript(SQLITE_SCHEMA)
        self._sqlite.commit()
        log.info(f"SQLite ready at {DB_PATH}")

    # ── Generic helpers ─────────────────────────────────────────────────
    async def add_user(self, user_id: int, username: str | None, first_name: str | None):
        data = {"id": user_id, "username": username, "first_name": first_name, "last_seen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        if self.use_supabase:
            try:
                self.supabase.table("videl_users").upsert(data, on_conflict="id").execute()
                return
            except Exception as e:
                log.warning(f"add_user supabase err: {e}")
        if self._sqlite:
            try:
                self._sqlite.execute("INSERT OR REPLACE INTO videl_users (id, username, first_name, last_seen) VALUES (?,?,?,?)",
                                     (user_id, username, first_name, data["last_seen"]))
                self._sqlite.commit()
            except Exception as e:
                log.warning(f"add_user sqlite err: {e}")

    async def add_chat(self, chat_id: int, title: str | None, type_: str):
        data = {"id": chat_id, "title": title, "type": type_}
        if self.use_supabase:
            try:
                self.supabase.table("videl_chats").upsert(data, on_conflict="id").execute()
                return
            except Exception as e:
                log.warning(f"add_chat supabase err: {e}")
        if self._sqlite:
            try:
                self._sqlite.execute("INSERT OR REPLACE INTO videl_chats (id, title, type) VALUES (?,?,?)",
                                     (chat_id, title, type_))
                self._sqlite.commit()
            except Exception as e:
                log.warning(f"add_chat sqlite err: {e}")

    async def log_event(self, level: str, event: str, chat_id: int | None = None, user_id: int | None = None, meta: dict | None = None):
        row = {"level": level, "event": event, "chat_id": chat_id, "user_id": user_id, "meta": meta or {}}
        if self.use_supabase:
            try:
                self.supabase.table("videl_logs").insert(row).execute()
                return
            except Exception:
                pass
        if self._sqlite:
            try:
                self._sqlite.execute("INSERT INTO videl_logs (level, event, chat_id, user_id, meta) VALUES (?,?,?,?,?)",
                                     (level, event, chat_id, user_id, json.dumps(meta or {})))
                self._sqlite.commit()
            except Exception:
                pass

    async def inc_stat(self, command: str, chat_id: int | None, user_id: int | None):
        row = {"command": command, "chat_id": chat_id, "user_id": user_id}
        if self.use_supabase:
            try:
                self.supabase.table("videl_stats").insert(row).execute()
                return
            except Exception:
                pass
        if self._sqlite:
            try:
                self._sqlite.execute("INSERT INTO videl_stats (command, chat_id, user_id) VALUES (?,?,?)",
                                     (command, chat_id, user_id))
                self._sqlite.commit()
            except Exception:
                pass

    # ── Warnings ──
    async def add_warn(self, chat_id: int, user_id: int, reason: str, warned_by: int) -> int:
        if self.use_supabase:
            try:
                self.supabase.table("videl_warnings").insert({"chat_id": chat_id, "user_id": user_id, "reason": reason, "warned_by": warned_by}).execute()
                res = self.supabase.table("videl_warnings").select("id", count="exact").eq("chat_id", chat_id).eq("user_id", user_id).execute()
                return res.count or 0
            except Exception as e:
                log.warning(f"add_warn supabase: {e}")
        if self._sqlite:
            self._sqlite.execute("INSERT INTO videl_warnings (chat_id, user_id, reason, warned_by) VALUES (?,?,?,?)",
                                 (chat_id, user_id, reason, warned_by))
            self._sqlite.commit()
            cur = self._sqlite.execute("SELECT COUNT(*) FROM videl_warnings WHERE chat_id=? AND user_id=?", (chat_id, user_id))
            return cur.fetchone()[0]
        return 0

    async def get_warns(self, chat_id: int, user_id: int) -> list[dict]:
        if self.use_supabase:
            try:
                res = self.supabase.table("videl_warnings").select("*").eq("chat_id", chat_id).eq("user_id", user_id).execute()
                return res.data or []
            except Exception:
                pass
        if self._sqlite:
            cur = self._sqlite.execute("SELECT * FROM videl_warnings WHERE chat_id=? AND user_id=?", (chat_id, user_id))
            return [dict(r) for r in cur.fetchall()]
        return []

    async def clear_warns(self, chat_id: int, user_id: int):
        if self.use_supabase:
            try:
                self.supabase.table("videl_warnings").delete().eq("chat_id", chat_id).eq("user_id", user_id).execute()
                return
            except Exception:
                pass
        if self._sqlite:
            self._sqlite.execute("DELETE FROM videl_warnings WHERE chat_id=? AND user_id=?", (chat_id, user_id))
            self._sqlite.commit()

    # ── Filters / Notes ──
    async def add_filter(self, chat_id: int, keyword: str, reply_text: str, reply_media: str | None = None):
        if self.use_supabase:
            try:
                self.supabase.table("videl_filters").upsert({"chat_id": chat_id, "keyword": keyword.lower(), "reply_text": reply_text, "reply_media": reply_media}, on_conflict="chat_id,keyword").execute()
                return
            except Exception as e:
                log.warning(f"add_filter: {e}")
        if self._sqlite:
            self._sqlite.execute("INSERT OR REPLACE INTO videl_filters (chat_id, keyword, reply_text, reply_media) VALUES (?,?,?,?)",
                                 (chat_id, keyword.lower(), reply_text, reply_media))
            self._sqlite.commit()

    async def get_filters(self, chat_id: int) -> list[dict]:
        if self.use_supabase:
            try:
                res = self.supabase.table("videl_filters").select("*").eq("chat_id", chat_id).execute()
                return res.data or []
            except Exception:
                pass
        if self._sqlite:
            cur = self._sqlite.execute("SELECT * FROM videl_filters WHERE chat_id=?", (chat_id,))
            return [dict(r) for r in cur.fetchall()]
        return []

    async def delete_filter(self, chat_id: int, keyword: str):
        if self.use_supabase:
            try:
                self.supabase.table("videl_filters").delete().eq("chat_id", chat_id).eq("keyword", keyword.lower()).execute()
                return
            except Exception:
                pass
        if self._sqlite:
            self._sqlite.execute("DELETE FROM videl_filters WHERE chat_id=? AND keyword=?", (chat_id, keyword.lower()))
            self._sqlite.commit()

    async def add_note(self, chat_id: int, name: str, content: str, media_file_id: str | None = None):
        if self.use_supabase:
            try:
                self.supabase.table("videl_notes").upsert({"chat_id": chat_id, "name": name.lower(), "content": content, "media_file_id": media_file_id}, on_conflict="chat_id,name").execute()
                return
            except Exception as e:
                log.warning(f"add_note: {e}")
        if self._sqlite:
            self._sqlite.execute("INSERT OR REPLACE INTO videl_notes (chat_id, name, content, media_file_id) VALUES (?,?,?,?)",
                                 (chat_id, name.lower(), content, media_file_id))
            self._sqlite.commit()

    async def get_note(self, chat_id: int, name: str) -> dict | None:
        if self.use_supabase:
            try:
                res = self.supabase.table("videl_notes").select("*").eq("chat_id", chat_id).eq("name", name.lower()).limit(1).execute()
                return res.data[0] if res.data else None
            except Exception:
                pass
        if self._sqlite:
            cur = self._sqlite.execute("SELECT * FROM videl_notes WHERE chat_id=? AND name=?", (chat_id, name.lower()))
            row = cur.fetchone()
            return dict(row) if row else None
        return None

    async def delete_note(self, chat_id: int, name: str):
        if self.use_supabase:
            try:
                self.supabase.table("videl_notes").delete().eq("chat_id", chat_id).eq("name", name.lower()).execute()
                return
            except Exception:
                pass
        if self._sqlite:
            self._sqlite.execute("DELETE FROM videl_notes WHERE chat_id=? AND name=?", (chat_id, name.lower()))
            self._sqlite.commit()

    # ── Music queue ──
    async def queue_add(self, chat_id: int, title: str, url: str, thumbnail: str | None, duration: int, requested_by: int) -> int:
        # get max position
        pos = 0
        if self.use_supabase:
            try:
                res = self.supabase.table("videl_music_queue").select("position").eq("chat_id", chat_id).order("position", desc=True).limit(1).execute()
                if res.data:
                    pos = (res.data[0].get("position") or 0) + 1
                self.supabase.table("videl_music_queue").insert({"chat_id": chat_id, "title": title, "url": url, "thumbnail": thumbnail, "duration": duration, "requested_by": requested_by, "position": pos}).execute()
                return pos
            except Exception as e:
                log.warning(f"queue_add supabase: {e}")
        if self._sqlite:
            cur = self._sqlite.execute("SELECT MAX(position) FROM videl_music_queue WHERE chat_id=?", (chat_id,))
            mx = cur.fetchone()[0]
            pos = (mx + 1) if mx is not None else 0
            self._sqlite.execute("INSERT INTO videl_music_queue (chat_id, title, url, thumbnail, duration, requested_by, position) VALUES (?,?,?,?,?,?,?)",
                                 (chat_id, title, url, thumbnail, duration, requested_by, pos))
            self._sqlite.commit()
            return pos
        return pos

    async def queue_list(self, chat_id: int) -> list[dict]:
        if self.use_supabase:
            try:
                res = self.supabase.table("videl_music_queue").select("*").eq("chat_id", chat_id).order("position").execute()
                return res.data or []
            except Exception:
                pass
        if self._sqlite:
            cur = self._sqlite.execute("SELECT * FROM videl_music_queue WHERE chat_id=? ORDER BY position", (chat_id,))
            return [dict(r) for r in cur.fetchall()]
        return []

    async def queue_pop(self, chat_id: int) -> dict | None:
        lst = await self.queue_list(chat_id)
        if not lst:
            return None
        first = lst[0]
        if self.use_supabase:
            try:
                self.supabase.table("videl_music_queue").delete().eq("id", first["id"]).execute()
            except Exception:
                pass
        if self._sqlite:
            try:
                self._sqlite.execute("DELETE FROM videl_music_queue WHERE id=?", (first["id"],))
                self._sqlite.commit()
            except Exception:
                pass
        return first

    async def queue_clear(self, chat_id: int):
        if self.use_supabase:
            try:
                self.supabase.table("videl_music_queue").delete().eq("chat_id", chat_id).execute()
                return
            except Exception:
                pass
        if self._sqlite:
            self._sqlite.execute("DELETE FROM videl_music_queue WHERE chat_id=?", (chat_id,))
            self._sqlite.commit()

    async def queue_shuffle(self, chat_id: int):
        import random
        lst = await self.queue_list(chat_id)
        if len(lst) < 2:
            return
        # keep first, shuffle rest
        keep = lst[0]
        rest = lst[1:]
        random.shuffle(rest)
        new_order = [keep] + rest
        if self.use_supabase:
            for idx, item in enumerate(new_order):
                try:
                    self.supabase.table("videl_music_queue").update({"position": idx}).eq("id", item["id"]).execute()
                except Exception:
                    pass
            return
        if self._sqlite:
            for idx, item in enumerate(new_order):
                self._sqlite.execute("UPDATE videl_music_queue SET position=? WHERE id=?", (idx, item["id"]))
            self._sqlite.commit()

    # ── AI history ──
    async def ai_add(self, user_id: int, chat_id: int, role: str, content: str, model: str = "gpt-4o-mini"):
        if self.use_supabase:
            try:
                self.supabase.table("videl_ai_history").insert({"user_id": user_id, "chat_id": chat_id, "role": role, "content": content, "model": model}).execute()
                return
            except Exception:
                pass
        if self._sqlite:
            self._sqlite.execute("INSERT INTO videl_ai_history (user_id, chat_id, role, content, model) VALUES (?,?,?,?,?)",
                                 (user_id, chat_id, role, content, model))
            self._sqlite.commit()

    async def ai_history(self, user_id: int, limit: int = 10) -> list[dict]:
        if self.use_supabase:
            try:
                res = self.supabase.table("videl_ai_history").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
                return list(reversed(res.data or []))
            except Exception:
                pass
        if self._sqlite:
            cur = self._sqlite.execute("SELECT * FROM videl_ai_history WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))
            rows = [dict(r) for r in cur.fetchall()]
            return list(reversed(rows))
        return []

    async def ai_clear(self, user_id: int):
        if self.use_supabase:
            try:
                self.supabase.table("videl_ai_history").delete().eq("user_id", user_id).execute()
                return
            except Exception:
                pass
        if self._sqlite:
            self._sqlite.execute("DELETE FROM videl_ai_history WHERE user_id=?", (user_id,))
            self._sqlite.commit()

    # ── Gbans ──
    async def gban(self, user_id: int, reason: str, banned_by: int):
        if self.use_supabase:
            try:
                self.supabase.table("videl_gbans").upsert({"user_id": user_id, "reason": reason, "banned_by": banned_by}, on_conflict="user_id").execute()
                return
            except Exception as e:
                log.warning(f"gban: {e}")
        if self._sqlite:
            self._sqlite.execute("INSERT OR REPLACE INTO videl_gbans (user_id, reason, banned_by) VALUES (?,?,?)",
                                 (user_id, reason, banned_by))
            self._sqlite.commit()

    async def ungban(self, user_id: int):
        if self.use_supabase:
            try:
                self.supabase.table("videl_gbans").delete().eq("user_id", user_id).execute()
                return
            except Exception:
                pass
        if self._sqlite:
            self._sqlite.execute("DELETE FROM videl_gbans WHERE user_id=?", (user_id,))
            self._sqlite.commit()

    async def is_gbanned(self, user_id: int) -> dict | None:
        if self.use_supabase:
            try:
                res = self.supabase.table("videl_gbans").select("*").eq("user_id", user_id).limit(1).execute()
                return res.data[0] if res.data else None
            except Exception:
                pass
        if self._sqlite:
            cur = self._sqlite.execute("SELECT * FROM videl_gbans WHERE user_id=?", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        return None

    async def list_gbans(self) -> list[dict]:
        if self.use_supabase:
            try:
                res = self.supabase.table("videl_gbans").select("*").execute()
                return res.data or []
            except Exception:
                pass
        if self._sqlite:
            cur = self._sqlite.execute("SELECT * FROM videl_gbans")
            return [dict(r) for r in cur.fetchall()]
        return []

    # ── Stats ──
    async def get_stats(self) -> dict:
        if self.use_supabase:
            try:
                u = self.supabase.table("videl_users").select("id", count="exact").execute()
                c = self.supabase.table("videl_chats").select("id", count="exact").execute()
                s = self.supabase.table("videl_stats").select("id", count="exact").execute()
                return {"users": u.count or 0, "chats": c.count or 0, "commands": s.count or 0}
            except Exception as e:
                log.warning(f"get_stats supabase: {e}")
        if self._sqlite:
            u = self._sqlite.execute("SELECT COUNT(*) FROM videl_users").fetchone()[0]
            c = self._sqlite.execute("SELECT COUNT(*) FROM videl_chats").fetchone()[0]
            s = self._sqlite.execute("SELECT COUNT(*) FROM videl_stats").fetchone()[0]
            return {"users": u, "chats": c, "commands": s}
        return {"users": 0, "chats": 0, "commands": 0}

    # ── AFK ──
    async def set_afk(self, user_id: int, reason: str):
        if self.use_supabase:
            try:
                self.supabase.table("videl_afk").upsert({"user_id": user_id, "reason": reason}, on_conflict="user_id").execute()
                return
            except Exception:
                pass
        if self._sqlite:
            self._sqlite.execute("INSERT OR REPLACE INTO videl_afk (user_id, reason) VALUES (?,?)", (user_id, reason))
            self._sqlite.commit()

    async def get_afk(self, user_id: int) -> dict | None:
        if self.use_supabase:
            try:
                res = self.supabase.table("videl_afk").select("*").eq("user_id", user_id).limit(1).execute()
                return res.data[0] if res.data else None
            except Exception:
                pass
        if self._sqlite:
            cur = self._sqlite.execute("SELECT * FROM videl_afk WHERE user_id=?", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        return None

    async def rm_afk(self, user_id: int):
        if self.use_supabase:
            try:
                self.supabase.table("videl_afk").delete().eq("user_id", user_id).execute()
                return
            except Exception:
                pass
        if self._sqlite:
            self._sqlite.execute("DELETE FROM videl_afk WHERE user_id=?", (user_id,))
            self._sqlite.commit()

# Singleton
db = Database()
