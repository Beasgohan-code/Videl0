"""
config.py — Perfect Production Ready Videl
Based on Beasgohan-code/videl upstream + Videl0 full-stack extensions
Cyber Dark • aiogram 3.31 + Kurigram • Supabase • Dropbox • Vercel • AI
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Support both .env and .env.example
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.example")

def _req(name: str) -> str:
    val = os.getenv(name, "").strip()
    # In production allow missing during webapp build — don't exit if ENV==build
    if not val:
        if os.getenv("ENV") in ("vercel_build", "ci"):
            return ""
        print(f"❌ Missing required env: {name}", file=sys.stderr)
        # Don't exit in web/build context, only runtime
        if "pytest" not in sys.modules and os.getenv("VIDEL_SKIP_REQ") != "1":
            # allow fallback for Videl0 dashboard build
            return ""
        sys.exit(1)
    return val

def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except:
        return default

def _list_int(name: str):
    raw = os.getenv(name, "")
    if not raw: return []
    out=[]
    for x in raw.split(","):
        x=x.strip()
        if x.lstrip("-").isdigit():
            out.append(int(x))
    return out

def _bool(name: str, default=False):
    v=os.getenv(name,"").lower()
    if v in ("1","true","yes","on"): return True
    if v in ("0","false","no","off"): return False
    return default

# ── Required (upstream strict) ──────────────────────────────────────────────
try:
    API_ID = int(_req("API_ID")) if os.getenv("API_ID") else _int("API_ID", 0)
except ValueError:
    print("❌ API_ID must be a number", file=sys.stderr)
    sys.exit(1)

API_HASH = os.getenv("API_HASH", _req("API_HASH") if os.getenv("API_HASH") or os.getenv("BUILD") != "1" else "")
BOT_TOKEN = os.getenv("BOT_TOKEN", _req("BOT_TOKEN") if os.getenv("BOT_TOKEN") or os.getenv("BUILD")!="1" else "")
_raw_session = os.getenv("STRING_SESSION","")
if _raw_session:
    _raw_session = _raw_session.strip().strip('"').strip("'")
    _raw_session = "".join(_raw_session.split())
    if len(_raw_session) % 4:
        _raw_session += "=" * (4 - len(_raw_session) % 4)
    STRING_SESSION = _raw_session
else:
    STRING_SESSION = os.getenv("STRING_SESSION","")  # allow empty for web build

MONGO_DB_URL = os.getenv("MONGO_DB_URL", os.getenv("MONGODB_URL",""))

try:
    OWNER_ID = int(_req("OWNER_ID")) if os.getenv("OWNER_ID") else _int("OWNER_ID", 0)
except:
    OWNER_ID = _int("OWNER_ID", 0)

# ── Optional (upstream + Videl0 extensions) ─────────────────────────────────
BOT_NAME = os.getenv("BOT_NAME", "Videl Music")
BOT_LINK = os.getenv("BOT_LINK", "https://t.me/VidelMusicBot")
BOT_USERNAME = os.getenv("BOT_USERNAME", "Videl0Bot")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "Beasgohan")
UPDATES_CHANNEL = os.getenv("UPDATES_CHANNEL", "https://t.me/BeasgohanUpdates")
SUPPORT_GROUP = os.getenv("SUPPORT_GROUP", "https://t.me/BeasgohanSupport")
SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", SUPPORT_GROUP)
SUPPORT_CHANNEL = UPDATES_CHANNEL
LOGGER_ID = int(os.getenv("LOGGER_ID", "0") or "0")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", str(LOGGER_ID)) or "0")
PING_IMG_URL = os.getenv("PING_IMG_URL", "https://files.catbox.moe/ddzvc0.jpg")
SESSION_NAME = os.getenv("SESSION_NAME", "videl")
PORT = int(os.getenv("PORT", "10000"))

START_PHOTOS = [p.strip() for p in os.getenv("START_PHOTOS", "https://iili.io/n5ClDil.jpg").split(",") if p.strip()] or ["https://iili.io/n5ClDil.jpg"]

MAX_DURATION_SECONDS = int(os.getenv("MAX_DURATION_SECONDS", "1800"))
QUEUE_LIMIT = int(os.getenv("QUEUE_LIMIT", "20"))
COOLDOWN = int(os.getenv("COOLDOWN", "10"))

# Extensions — AI / Music / Utils
SUDO_USERS = _list_int("SUDO_USERS")
ALL_PRIVILEGED = set([OWNER_ID] + SUDO_USERS) if OWNER_ID else set(SUDO_USERS)
def is_owner(uid:int): return uid == OWNER_ID
def is_sudo(uid:int): return uid in ALL_PRIVILEGED

# Supabase (Videl0 full-stack)
SUPABASE_URL = os.getenv("SUPABASE_URL","")
SUPABASE_KEY = os.getenv("SUPABASE_KEY","")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", SUPABASE_KEY)

# Dropbox
DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN","")
DROPBOX_BACKUP_FOLDER = os.getenv("DROPBOX_BACKUP_FOLDER","/Videl0/backups")

# Vercel / Webapp
VERCEL_TOKEN = os.getenv("VERCEL_TOKEN","")
VERCEL_PROJECT_ID = os.getenv("VERCEL_PROJECT_ID","")
VERCEL_TEAM_ID = os.getenv("VERCEL_TEAM_ID","")
WEBAPP_URL = os.getenv("WEBAPP_URL","https://hosting-bot-dashboard.vercel.app")
WEBHOOK_URL = os.getenv("WEBHOOK_URL","")

# AI providers
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","")
GROQ_API_KEY = os.getenv("GROQ_API_KEY","")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY","")
AI_DEFAULT_MODEL = os.getenv("AI_DEFAULT_MODEL","gpt-4o-mini")
AI_SYSTEM_PROMPT = os.getenv("AI_SYSTEM_PROMPT","You are Videl — cyber dark perfect assistant. Help with music, admin, utilities. Be concise but warm. Speak in small caps aesthetic when told.")

# Cyber Dark Aesthetic toggle
CYBER_DARK = _bool("CYBER_DARK", True)
ENABLE_RICH_MESSAGES = _bool("ENABLE_RICH_MESSAGES", True)

# Music extras
YT_API_URL = os.getenv("YT_API_URL","https://api.shrutibots.site")
YT_API_KEY = os.getenv("YT_API_KEY","ShrutiBotsLaL92ySOXsj4xl4k34Jv")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID","")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET","")
GENIUS_API_KEY = os.getenv("GENIUS_API_KEY","")

# Keep-alive / watchdog
KEEPALIVE_URL = os.getenv("KEEPALIVE_URL","")
WATCHDOG_INTERVAL = _int("WATCHDOG_INTERVAL",300)
ENV = os.getenv("ENV","production")

# Eldian / Shruti (upstream)
ELDIAN_API_URL = os.getenv("ELDIAN_API_URL","https://eldian-music-api-production.up.railway.app")
ELDIAN_API_KEY = os.getenv("ELDIAN_API_KEY","")
SHRUTI_API_URL = os.getenv("SHRUTI_API_URL", YT_API_URL)
SHRUTI_API_KEY = os.getenv("SHRUTI_API_KEY", YT_API_KEY)
YTDLP_COOKIES = os.getenv("YTDLP_COOKIES","/app/cookies.txt")
AUTO_PROXY = os.getenv("AUTO_PROXY","1")

# Limits mirrored from bot/config.py for aiogram side
DEFAULT_WARN_LIMIT = _int("DEFAULT_WARN_LIMIT",3)
DEFAULT_FLOOD_LIMIT = _int("DEFAULT_FLOOD_LIMIT",5)
