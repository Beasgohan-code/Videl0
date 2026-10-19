"""
Videl0 • Extended DB helpers — chat settings, locks, blocks, language, channels
Imported into database.py via monkey patch or direct import.
"""
import json, logging
from bot.database import db as _db
log=logging.getLogger("videl.db.ext")

# add to existing db instance
async def get_chat_settings(self, chat_id: int) -> dict:
    if self.use_supabase:
        try:
            r=self.supabase.table("videl_chats").select("settings").eq("id", chat_id).limit(1).execute()
            if r.data: return r.data[0].get("settings") or {}
        except: pass
    if self._sqlite:
        cur=self._sqlite.execute("SELECT settings FROM videl_chats WHERE id=?", (chat_id,))
        row=cur.fetchone()
        if row:
            try: return json.loads(row[0] or "{}")
            except: return {}
    return {}

async def set_chat_settings(self, chat_id:int, settings: dict):
    if self.use_supabase:
        try:
            self.supabase.table("videl_chats").upsert({"id":chat_id,"settings":settings}, on_conflict="id").execute()
            return
        except Exception as e: log.warning(f"set_chat_settings {e}")
    if self._sqlite:
        self._sqlite.execute("INSERT OR REPLACE INTO videl_chats (id, settings) VALUES (?,?)", (chat_id, json.dumps(settings)))
        self._sqlite.commit()

async def get_chat_lang(self, chat_id:int) -> str:
    s=await self.get_chat_settings(chat_id)
    return s.get("lang","en")

async def set_chat_lang(self, chat_id:int, lang:str):
    s=await self.get_chat_settings(chat_id)
    s["lang"]=lang
    await self.set_chat_settings(chat_id,s)

# locks
async def get_locks(self, chat_id:int) -> dict:
    s=await self.get_chat_settings(chat_id)
    return s.get("locks",{})

async def set_lock(self, chat_id:int, lock_type:str, locked:bool):
    s=await self.get_chat_settings(chat_id)
    locks=s.get("locks",{})
    locks[lock_type]=locked
    s["locks"]=locks
    await self.set_chat_settings(chat_id,s)

# block/ban lists (Shizu compat)
async def is_user_blocked(self, user_id:int) -> bool:
    return await self.is_gbanned(user_id) is not None

async def is_chat_blocked(self, chat_id:int) -> bool:
    s=await self.get_chat_settings(chat_id)
    return s.get("blocked",False)

async def block_user(self, user_id:int, reason:str, banned_by:int): await self.gban(user_id, reason, banned_by)
async def unblock_user(self, user_id:int): await self.ungban(user_id)
async def block_chat(self, chat_id:int):
    s=await self.get_chat_settings(chat_id); s["blocked"]=True; await self.set_chat_settings(chat_id,s)
async def unblock_chat(self, chat_id:int):
    s=await self.get_chat_settings(chat_id); s["blocked"]=False; await self.set_chat_settings(chat_id,s)

# welcome/goodbye
async def get_welcome(self, chat_id:int) -> tuple[str|None,str|None]:
    s=await self.get_chat_settings(chat_id); return s.get("welcome"), s.get("welcome_media")
async def set_welcome(self, chat_id:int, text:str, media:str|None=None):
    s=await self.get_chat_settings(chat_id); s["welcome"]=text; s["welcome_media"]=media; await self.set_chat_settings(chat_id,s)
async def get_goodbye(self, chat_id:int): 
    s=await self.get_chat_settings(chat_id); return s.get("goodbye")
async def set_goodbye(self, chat_id:int, text:str):
    s=await self.get_chat_settings(chat_id); s["goodbye"]=text; await self.set_chat_settings(chat_id,s)

# rules
async def get_rules(self, chat_id:int): 
    s=await self.get_chat_settings(chat_id); return s.get("rules")
async def set_rules(self, chat_id:int, text:str):
    s=await self.get_chat_settings(chat_id); s["rules"]=text; await self.set_chat_settings(chat_id,s)

# channel link
async def get_channel(self, chat_id:int):
    s=await self.get_chat_settings(chat_id); return s.get("channel_id")
async def set_channel(self, chat_id:int, channel_id:int|None):
    s=await self.get_chat_settings(chat_id); s["channel_id"]=channel_id; await self.set_chat_settings(chat_id,s)

# thumbnail / autoplay toggles (Shizu parity)
async def is_thumbnail_enabled(self, chat_id:int) -> bool:
    s=await self.get_chat_settings(chat_id); return s.get("thumbnail", True)
async def set_thumbnail(self, chat_id:int, on:bool):
    s=await self.get_chat_settings(chat_id); s["thumbnail"]=on; await self.set_chat_settings(chat_id,s)
async def is_autoplay(self, chat_id:int) -> bool:
    s=await self.get_chat_settings(chat_id); return s.get("autoplay", False)
async def set_autoplay(self, chat_id:int, on:bool):
    s=await self.get_chat_settings(chat_id); s["autoplay"]=on; await self.set_chat_settings(chat_id,s)

# playlist
async def add_playlist(self, user_id:int, name:str, tracks:list):
    if self.use_supabase:
        try:
            self.supabase.table("videl_playlists").upsert({"user_id":user_id,"name":name.lower(),"tracks":tracks}, on_conflict="user_id,name").execute()
            return
        except: pass
    if self._sqlite:
        self._sqlite.execute("INSERT OR REPLACE INTO videl_playlists (user_id,name,tracks) VALUES (?,?,?)", (user_id, name.lower(), json.dumps(tracks)))
        self._sqlite.commit()

async def get_playlist(self, user_id:int, name:str):
    if self.use_supabase:
        try:
            r=self.supabase.table("videl_playlists").select("*").eq("user_id",user_id).eq("name",name.lower()).limit(1).execute()
            return r.data[0] if r.data else None
        except: pass
    if self._sqlite:
        cur=self._sqlite.execute("SELECT * FROM videl_playlists WHERE user_id=? AND name=?", (user_id, name.lower()))
        row=cur.fetchone()
        if row:
            d=dict(row)
            try: d["tracks"]=json.loads(d["tracks"])
            except: d["tracks"]=[]
            return d
    return None

# patch db
for fn in [get_chat_settings,set_chat_settings,get_chat_lang,set_chat_lang,get_locks,set_lock,is_user_blocked,is_chat_blocked,block_user,unblock_user,block_chat,unblock_chat,get_welcome,set_welcome,get_goodbye,set_goodbye,get_rules,set_rules,get_channel,set_channel,is_thumbnail_enabled,set_thumbnail,is_autoplay,set_autoplay,add_playlist,get_playlist]:
    setattr(_db.__class__, fn.__name__, fn)

