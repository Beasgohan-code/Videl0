"""
Videl0 • Config — aiogram 3.31 + Richgram + ShizuMusic + Full Stack
All env in one place. Supports both polling & webhook via Vercel/keep-alive.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.example")

def _int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except:
        return default

def _float(name: str, default: float = 0) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except:
        return default

def _list_int(name: str) -> list[int]:
    raw = os.getenv(name, "")
    if not raw:
        return []
    out=[]
    for x in raw.split(","):
        x=x.strip()
        if x and (x.lstrip("-").isdigit()):
            out.append(int(x))
    return out

def _bool(name: str, default=False):
    v=os.getenv(name,"").lower()
    if v in ("1","true","yes","on"): return True
    if v in ("0","false","no","off"): return False
    return default

# ── Telegram Core ──────────────────────────────────────────────────────────
API_ID: int = _int("API_ID", 0)        # for MTProto (Shizu assistant VC)
API_HASH: str = os.getenv("API_HASH","")
BOT_TOKEN: str = os.getenv("BOT_TOKEN","")
BOT_USERNAME: str = os.getenv("BOT_USERNAME","Videl0Bot")
OWNER_ID: int = _int("OWNER_ID", 0)
OWNER_USERNAME: str = os.getenv("OWNER_USERNAME","Beasgohan")
SUDO_USERS: list[int] = _list_int("SUDO_USERS")
LOG_CHANNEL_ID: int = _int("LOG_CHANNEL_ID", 0)  # -100...
LOGGER_ID: int = _int("LOGGER_ID", LOG_CHANNEL_ID)
SUPPORT_CHAT: str = os.getenv("SUPPORT_CHAT", "@VidelSupport")
SUPPORT_CHANNEL: str = os.getenv("SUPPORT_CHANNEL", "@VidelUpdates")
UPDATES_CHANNEL: str = os.getenv("UPDATES_CHANNEL", SUPPORT_CHANNEL)

ALL_PRIVILEGED: set[int] = set([OWNER_ID]+SUDO_USERS) if OWNER_ID else set(SUDO_USERS)

def is_owner(uid: int) -> bool: return uid == OWNER_ID
def is_sudo(uid: int) -> bool: return uid in ALL_PRIVILEGED
def is_privileged(uid:int, chat_admins:list[int]|None=None) -> bool:
    if is_sudo(uid): return True
    if chat_admins and uid in chat_admins: return True
    return False

# ── Sessions ───────────────────────────────────────────────────────────────
STRING_SESSION: str = os.getenv("STRING_SESSION","")
SESSION_NAME: str = os.getenv("SESSION_NAME","Videl0")
BOT_NAME: str = os.getenv("BOT_NAME","Videl0")
BOT_LINK: str = os.getenv("BOT_LINK", f"https://t.me/{BOT_USERNAME}")

# ── Supabase ───────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL","")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY","")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", SUPABASE_KEY)

# ── MongoDB (Shizu compat — optional, fallback to Supabase) ────────────────
MONGO_DB_URL: str = os.getenv("MONGO_DB_URL", os.getenv("MONGODB_URL",""))

# ── Dropbox ────────────────────────────────────────────────────────────────
DROPBOX_ACCESS_TOKEN: str = os.getenv("DROPBOX_ACCESS_TOKEN","")
DROPBOX_BACKUP_FOLDER: str = os.getenv("DROPBOX_BACKUP_FOLDER","/Videl0/backups")

# ── Vercel ─────────────────────────────────────────────────────────────────
VERCEL_TOKEN: str = os.getenv("VERCEL_TOKEN","")
VERCEL_PROJECT_ID: str = os.getenv("VERCEL_PROJECT_ID","")
VERCEL_TEAM_ID: str = os.getenv("VERCEL_TEAM_ID","")
WEBAPP_URL: str = os.getenv("WEBAPP_URL","https://hosting-bot-dashboard.vercel.app")
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL","")  # if empty → polling
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET","videl0-webhook")

# ── AI Providers ───────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY","")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY","")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY","")
MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY","")
AI_DEFAULT_MODEL: str = os.getenv("AI_DEFAULT_MODEL","gpt-4o-mini")
AI_SYSTEM_PROMPT: str = os.getenv("AI_SYSTEM_PROMPT",
    "You are Videl — witty, helpful, Telegram-native AI. You help with music, group admin, utilities. Be concise but warm. You speak as Videl0.")

# ── Music / External APIs ──────────────────────────────────────────────────
YT_API_URL: str = os.getenv("YT_API_URL","https://api.shrutibots.site")
YT_API_KEY: str = os.getenv("YT_API_KEY","ShrutiBotsLaL92ySOXsj4xl4k34Jv")
DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR","downloads")
YT_COOKIES_FILE: str = os.getenv("YT_COOKIES_FILE","")
YT_TOKEN_TIMEOUT: int = _int("YT_TOKEN_TIMEOUT",10)
YT_STREAM_TIMEOUT: int = _int("YT_STREAM_TIMEOUT",900)
SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID","")
SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET","")
GENIUS_API_KEY: str = os.getenv("GENIUS_API_KEY","")

# ── Utilities APIs ─────────────────────────────────────────────────────────
WEATHER_API_KEY: str = os.getenv("WEATHER_API_KEY","")
NEWS_API_KEY: str = os.getenv("NEWS_API_KEY","")
REMOVE_BG_API_KEY: str = os.getenv("REMOVE_BG_API_KEY","")
OCR_API_KEY: str = os.getenv("OCR_API_KEY","")

# ── Branding / Assets ──────────────────────────────────────────────────────
START_PHOTOS: list[str] = [
    os.getenv("START_PHOTO","https://files.catbox.moe/jgt2vm.png"),
    "https://files.catbox.moe/f084wg.png",
]
PING_IMG_URL: str = os.getenv("PING_IMG_URL","https://files.catbox.moe/ddzvc0.jpg")

# ── Limits & Behaviour ─────────────────────────────────────────────────────
MAX_DURATION_SECONDS: int = _int("MAX_DURATION_SECONDS",1800)  # 30 min
QUEUE_LIMIT: int = _int("QUEUE_LIMIT",20)
COOLDOWN: int = _int("COOLDOWN",3)
PLAYLIST_LIMIT: int = _int("PLAYLIST_LIMIT",10)
PLAYLIST_SONG_LIMIT: int = _int("PLAYLIST_SONG_LIMIT",50)
DEFAULT_WARN_LIMIT: int = _int("DEFAULT_WARN_LIMIT",3)
DEFAULT_FLOOD_LIMIT: int = _int("DEFAULT_FLOOD_LIMIT",5)
DEFAULT_FLOOD_WINDOW: int = _int("DEFAULT_FLOOD_WINDOW",6)
RATE_LIMIT_CMDS: int = _int("RATE_LIMIT_CMDS",8)
MUSIC_MAX_DURATION: int = _int("MUSIC_MAX_DURATION",600)
AI_MAX_HISTORY: int = _int("AI_MAX_HISTORY",20)
AI_MAX_TOKENS: int = _int("AI_MAX_TOKENS",1200)

# ── Server / Watchdog ──────────────────────────────────────────────────────
PORT: int = _int("PORT",8000)
HOST: str = os.getenv("HOST","0.0.0.0")
KEEPALIVE_URL: str = os.getenv("KEEPALIVE_URL","")
WATCHDOG_INTERVAL: int = _int("WATCHDOG_INTERVAL",300)
ENV: str = os.getenv("ENV","production")

WEBAPP_SECRET: str = os.getenv("WEBAPP_SECRET","videl0-super-secret")
ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY","")

# ── Bot API 10.3 Features toggle ───────────────────────────────────────────
ENABLE_RICH_MESSAGES: bool = _bool("ENABLE_RICH_MESSAGES", True)
ENABLE_BUSINESS: bool = _bool("ENABLE_BUSINESS", True)
ENABLE_PAID_BROADCAST: bool = _bool("ENABLE_PAID_BROADCAST", True)
ENABLE_CHECKLIST: bool = _bool("ENABLE_CHECKLIST", True)
ENABLE_DIRECT_MESSAGES: bool = _bool("ENABLE_DIRECT_MESSAGES", True)

# ── Help map ───────────────────────────────────────────────────────────────
COMMANDS_HELP = {
    "🚀 General": ["/start","/help","/ping","/stats","/id","/info","/about","/repo"],
    "🎵 Music": ["/play","/vplay","/playforce","/queue","/skip","/stop","/pause","/resume","/seek","/shuffle","/lyrics","/song","/playlist","/nowplaying","/thumbnail","/autoplay","/clear"],
    "🤖 AI Chat": ["/ask","/gpt","/ai","/imagine","/draw","/summarize","/translate","/tts","/vision","/clearhistory"],
    "🧰 Utility": ["/weather","/news","/qr","/shorten","/calc","/define","/wiki","/carbon","/removebg","/sticker","/steal","/pdf","/paste","/git","/pinterest","/ud","/speedtest","/tagall","/afk"],
    "🛡️ Group Admin": ["/ban","/unban","/kick","/mute","/unmute","/pin","/unpin","/purge","/warn","/warns","/rmwarn","/del","/lock","/unlock","/slowmode","/setwelcome","/welcome","/goodbye","/filter","/filters","/note","/notes","/rules","/setrules","/staff","/report","/setlang"],
    "👑 Owner/Sudo": ["/broadcast","/gban","/ungban","/gbans","/block","/unblock","/addsudo","/rmsudo","/sudolist","/backup","/update","/restart","/eval","/exec","/shell","/logs","/stats","/activevc","/leave"],
    "🎲 Fun": ["/8ball","/dice","/flip","/ship","/joke","/meme","/quote","/truth","/dare","/roast"],
}
