"""
◍ Vɪᴅᴇʟ — Perfect Production Config
   Single source of truth for BOTH videl/ (Pyrogram) and bot/ (aiogram)
   Cyber Dark • Kurigram + aiogram 3.31 • Supabase • Dropbox • Vercel • AI

   Usage:
     import config  (root)
     from bot.config import *  (re-exports — kept for compat)

   Env: copy sample.env → .env and fill required fields.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ── Load env ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.example")
# .env overrides .env.example (load order matters — dotenv doesn't override by default unless override=True)
load_dotenv(BASE_DIR / ".env", override=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _req(name: str) -> str:
    val = os.getenv(name, "").strip()
    if val:
        return val
    # Allow empty during build/CI where secrets aren't needed
    if os.getenv("ENV") in ("vercel_build", "ci", "test") or os.getenv("VIDEL_SKIP_REQ") == "1":
        return ""
    # In production runtime, warn but don't crash hard — let caller decide
    print(f"⚠️  Missing env: {name} — set it in .env", file=sys.stderr)
    return ""

def _int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except Exception:
        return default

def _float(name: str, default: float = 0) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except Exception:
        return default

def _str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip() or default

def _bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if v in ("1", "true", "yes", "on", "y"):
        return True
    if v in ("0", "false", "no", "off", "n"):
        return False
    return default

def _list_int(name: str) -> list[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    out: list[int] = []
    for x in raw.replace(";", ",").split(","):
        x = x.strip().lstrip("@")
        if x and x.lstrip("-").isdigit():
            out.append(int(x))
    return out

def _list_str(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]

# ── Required — Telegram Core ──────────────────────────────────────────────────
API_ID: int = _int("API_ID", 0)
API_HASH: str = _str("API_HASH", _req("API_HASH"))
BOT_TOKEN: str = _str("BOT_TOKEN", _req("BOT_TOKEN"))
BOT_USERNAME: str = _str("BOT_USERNAME", "Videl0Bot")

# STRING_SESSION — sanitize: strip quotes/spaces, fix padding
_raw_session = _str("STRING_SESSION", "")
if _raw_session:
    _raw_session = _raw_session.strip().strip('"').strip("'").strip()
    _raw_session = "".join(_raw_session.split())
    # Pyrogram sessions are base64 — auto-fix padding for user convenience
    if len(_raw_session) % 4:
        _raw_session += "=" * (4 - len(_raw_session) % 4)
    STRING_SESSION: str = _raw_session
else:
    STRING_SESSION = _req("STRING_SESSION")  # warn if missing

MONGO_DB_URL: str = _str("MONGO_DB_URL", _str("MONGODB_URL", _req("MONGO_DB_URL")))
MONGO_DB_NAME: str = _str("MONGO_DB_NAME", "Videl")

OWNER_ID: int = _int("OWNER_ID", 0)
OWNER_USERNAME: str = _str("OWNER_USERNAME", "Beasgohan")

# ── Bot Identity ──────────────────────────────────────────────────────────────
BOT_NAME: str = _str("BOT_NAME", "Videl Music")
BOT_LINK: str = _str("BOT_LINK", f"https://t.me/{BOT_USERNAME}")
SESSION_NAME: str = _str("SESSION_NAME", "videl")
SUPPORT_CHAT: str = _str("SUPPORT_CHAT", _str("SUPPORT_GROUP", "@VidelSupport"))
SUPPORT_GROUP: str = SUPPORT_CHAT
SUPPORT_CHANNEL: str = _str("SUPPORT_CHANNEL", _str("UPDATES_CHANNEL", "@VidelUpdates"))
UPDATES_CHANNEL: str = SUPPORT_CHANNEL

# ── Logging & Privileges ─────────────────────────────────────────────────────
# LOGGER_ID = private log channel for startup/plays/errors
LOGGER_ID: int = _int("LOGGER_ID", _int("LOG_CHANNEL_ID", 0))
LOG_CHANNEL_ID: int = _int("LOG_CHANNEL_ID", LOGGER_ID)

SUDO_USERS: list[int] = _list_int("SUDO_USERS")
ALL_PRIVILEGED: set[int] = set([OWNER_ID] + SUDO_USERS) if OWNER_ID else set(SUDO_USERS)

def is_owner(uid: int) -> bool:
    return bool(OWNER_ID and uid == OWNER_ID)

def is_sudo(uid: int) -> bool:
    return uid in ALL_PRIVILEGED

def is_privileged(uid: int, chat_admins: list[int] | None = None) -> bool:
    if is_sudo(uid):
        return True
    if chat_admins and uid in chat_admins:
        return True
    return False

# ── Database — Supabase (primary for dashboard) + MongoDB (compat) ───────────
SUPABASE_URL: str = _str("SUPABASE_URL", "")
SUPABASE_KEY: str = _str("SUPABASE_KEY", "")
SUPABASE_SERVICE_KEY: str = _str("SUPABASE_SERVICE_KEY", SUPABASE_KEY)
# Supabase project: hanre-studio / gnfgnwkxomwomgmyvzlq — used by webapp dashboard

# ── Storage — Dropbox ─────────────────────────────────────────────────────────
DROPBOX_ACCESS_TOKEN: str = _str("DROPBOX_ACCESS_TOKEN", "")
DROPBOX_BACKUP_FOLDER: str = _str("DROPBOX_BACKUP_FOLDER", "/Videl0/backups")

# ── Deploy — Vercel + Keep-Alive ────────────────────────────────────────────
VERCEL_TOKEN: str = _str("VERCEL_TOKEN", "")
VERCEL_PROJECT_ID: str = _str("VERCEL_PROJECT_ID", "")
VERCEL_TEAM_ID: str = _str("VERCEL_TEAM_ID", "")
WEBAPP_URL: str = _str("WEBAPP_URL", "https://hosting-bot-dashboard.vercel.app")
WEBHOOK_URL: str = _str("WEBHOOK_URL", "")
WEBHOOK_SECRET: str = _str("WEBHOOK_SECRET", "videl0-webhook")

PORT: int = _int("PORT", 10000)
HOST: str = _str("HOST", "0.0.0.0")
KEEPALIVE_URL: str = _str("KEEPALIVE_URL", "")
WATCHDOG_INTERVAL: int = _int("WATCHDOG_INTERVAL", 300)
ENV: str = _str("ENV", "production")

# ── AI Providers — multi-fallback ───────────────────────────────────────────
OPENAI_API_KEY: str = _str("OPENAI_API_KEY", "")
GROQ_API_KEY: str = _str("GROQ_API_KEY", "")
GEMINI_API_KEY: str = _str("GEMINI_API_KEY", "")
MISTRAL_API_KEY: str = _str("MISTRAL_API_KEY", "")
AI_DEFAULT_MODEL: str = _str("AI_DEFAULT_MODEL", "gpt-4o-mini")
AI_SYSTEM_PROMPT: str = _str(
    "AI_SYSTEM_PROMPT",
    "You are Videl — cyber dark perfect assistant. Help with music, admin, utilities. Be concise warm. Use small caps (◍ ⬪ ⫶) when requested.",
)
AI_MAX_HISTORY: int = _int("AI_MAX_HISTORY", 20)
AI_MAX_TOKENS: int = _int("AI_MAX_TOKENS", 1200)

# ── Music & External APIs ─────────────────────────────────────────────────────
# Eldian = primary (fixes Render bot-check), Shruti = fallback, yt-dlp = last
ELDIAN_API_URL: str = _str("ELDIAN_API_URL", "https://eldian-music-api-production.up.railway.app")
ELDIAN_API_KEY: str = _str("ELDIAN_API_KEY", "")
SHRUTI_API_URL: str = _str("SHRUTI_API_URL", _str("YT_API_URL", "https://api.shrutibots.site"))
SHRUTI_API_KEY: str = _str("SHRUTI_API_KEY", _str("YT_API_KEY", "ShrutiBotsLaL92ySOXsj4xl4k34Jv"))
YT_API_URL: str = SHRUTI_API_URL
YT_API_KEY: str = SHRUTI_API_KEY
SPOTIFY_CLIENT_ID: str = _str("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET: str = _str("SPOTIFY_CLIENT_SECRET", "")
GENIUS_API_KEY: str = _str("GENIUS_API_KEY", "")
YTDLP_COOKIES: str = _str("YTDLP_COOKIES", "/app/cookies.txt")
YT_COOKIES_FILE: str = _str("YT_COOKIES_FILE", YTDLP_COOKIES)
DOWNLOAD_DIR: str = _str("DOWNLOAD_DIR", "downloads")
AUTO_PROXY: str = _str("AUTO_PROXY", "1")
PROXY_URL: str = _str("PROXY_URL", "")
PROXY_LIST: str = _str("PROXY_LIST", "")

# Utilities APIs (optional)
WEATHER_API_KEY: str = _str("WEATHER_API_KEY", "")
NEWS_API_KEY: str = _str("NEWS_API_KEY", "")
REMOVE_BG_API_KEY: str = _str("REMOVE_BG_API_KEY", "")
OCR_API_KEY: str = _str("OCR_API_KEY", "")

# ── Branding & Assets ─────────────────────────────────────────────────────────
START_PHOTOS: list[str] = _list_str("START_PHOTOS") or _list_str("START_PHOTO") or ["https://iili.io/n5ClDil.jpg"]
START_PHOTO: str = START_PHOTOS[0] if START_PHOTOS else "https://iili.io/n5ClDil.jpg"
PING_IMG_URL: str = _str("PING_IMG_URL", "https://files.catbox.moe/ddzvc0.jpg")

# ── Limits & Behaviour ────────────────────────────────────────────────────────
MAX_DURATION_SECONDS: int = _int("MAX_DURATION_SECONDS", 1800)  # 30 min
MUSIC_MAX_DURATION: int = _int("MUSIC_MAX_DURATION", 600)
QUEUE_LIMIT: int = _int("QUEUE_LIMIT", 20)
COOLDOWN: int = _int("COOLDOWN", 5)
PLAYLIST_LIMIT: int = _int("PLAYLIST_LIMIT", 10)
PLAYLIST_SONG_LIMIT: int = _int("PLAYLIST_SONG_LIMIT", 50)
DEFAULT_WARN_LIMIT: int = _int("DEFAULT_WARN_LIMIT", 3)
DEFAULT_FLOOD_LIMIT: int = _int("DEFAULT_FLOOD_LIMIT", 5)
DEFAULT_FLOOD_WINDOW: int = _int("DEFAULT_FLOOD_WINDOW", 6)
RATE_LIMIT_CMDS: int = _int("RATE_LIMIT_CMDS", 8)
WEBAPP_SECRET: str = _str("WEBAPP_SECRET", "videl0-super-secret")
ENCRYPTION_KEY: str = _str("ENCRYPTION_KEY", "")

# ── Aesthetic ─────────────────────────────────────────────────────────────────
CYBER_DARK: bool = _bool("CYBER_DARK", True)
ENABLE_RICH_MESSAGES: bool = _bool("ENABLE_RICH_MESSAGES", True)
ENABLE_BUSINESS: bool = _bool("ENABLE_BUSINESS", True)
ENABLE_PAID_BROADCAST: bool = _bool("ENABLE_PAID_BROADCAST", True)
ENABLE_CHECKLIST: bool = _bool("ENABLE_CHECKLIST", True)
ENABLE_DIRECT_MESSAGES: bool = _bool("ENABLE_DIRECT_MESSAGES", True)

# ── Help Map (for /help) ──────────────────────────────────────────────────────
COMMANDS_HELP: dict[str, list[str]] = {
    "◍ ɢᴇɴᴇʀᴀʟ": ["/start", "/help", "/ping", "/stats", "/id", "/info", "/about", "/repo"],
    "⬪ ᴍᴜsɪᴄ": ["/play", "/vplay", "/playforce", "/queue", "/skip", "/stop", "/pause", "/resume", "/seek", "/shuffle", "/lyrics", "/song", "/playlist", "/autoplay"],
    "⫶ ᴀɪ ᴄʜᴀᴛ": ["/ask", "/gpt", "/ai", "/imagine", "/draw", "/summarize", "/translate", "/tts", "/vision", "/clearhistory"],
    "◎ ᴜᴛɪʟɪᴛʏ": ["/weather", "/news", "/qr", "/shorten", "/calc", "/define", "/wiki", "/carbon", "/removebg", "/sticker", "/steal", "/pdf", "/paste", "/git", "/pinterest", "/speedtest", "/tagall", "/afk"],
    "⬢ ᴀᴅᴍɪɴ": ["/ban", "/unban", "/kick", "/mute", "/unmute", "/pin", "/unpin", "/purge", "/warn", "/warns", "/del", "/lock", "/unlock", "/slowmode", "/setwelcome", "/welcome"],
    "⬩ ᴏᴡɴᴇʀ": ["/broadcast", "/gban", "/ungban", "/gbans", "/block", "/unblock", "/addsudo", "/rmsudo", "/sudolist", "/backup", "/eval", "/exec", "/logs", "/activevc"],
    "𖦹 ғᴜɴ": ["/8ball", "/dice", "/flip", "/ship", "/joke", "/meme", "/quote", "/truth", "/dare", "/roast"],
}

# ── Validate critical ─────────────────────────────────────────────────────────
def validate_or_warn() -> list[str]:
    """Return list of missing required vars — caller can decide to abort or warn."""
    missing = []
    for k in ("API_ID", "API_HASH", "BOT_TOKEN", "MONGO_DB_URL", "OWNER_ID"):
        v = os.getenv(k, "").strip()
        if not v or v == "0":
            missing.append(k)
    if missing:
        print(f"◍ ᴄᴏɴғɪɢ — missing: {', '.join(missing)} ⫶ check .env ◍", file=sys.stderr)
    return missing
