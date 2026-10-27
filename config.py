"""
Videl runtime configuration shared by the Pyrogram bot and Render API.
The Next.js control panel is deployed separately on Vercel.

Usage: import config (root module).
   Env: copy sample.env → .env and fill required fields.
"""
from __future__ import annotations
import os
import re
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
BOT_USERNAME: str = _str("BOT_USERNAME", "videlapp")
# Alternate text-command prefixes. Telegram's native command menu still uses '/'.
_raw_command_prefixes = _str("COMMAND_PREFIXES", "/!?&.#~$+")
COMMAND_PREFIXES: str = "".join(dict.fromkeys(
    char for char in _raw_command_prefixes
    if len(char) == 1 and not char.isalnum() and not char.isspace() and char != "@"
)) or "/"
# Pyrogram treats a string as ONE prefix, not a set of prefix characters.
# Keep the joined form for regex parsing and pass this list to filters.command.
COMMAND_PREFIX_LIST: list[str] = list(COMMAND_PREFIXES)
COMMAND_PREFIX_PATTERN: str = f"[{re.escape(COMMAND_PREFIXES)}]"

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

OWNER_ID: int = _int("OWNER_ID", 6265999542)
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

# ── Database — MongoDB only ─────────────────────────────────────────────────

# ── Deploy — Vercel + Keep-Alive ────────────────────────────────────────────
VERCEL_TOKEN: str = _str("VERCEL_TOKEN", "")
VERCEL_PROJECT_ID: str = _str("VERCEL_PROJECT_ID", "")
VERCEL_TEAM_ID: str = _str("VERCEL_TEAM_ID", "")
WEBAPP_URL: str = _str("WEBAPP_URL", "https://videl-studio.vercel.app")
WEBHOOK_URL: str = _str("WEBHOOK_URL", "")
WEBHOOK_SECRET: str = _str("WEBHOOK_SECRET", "videl0-webhook")

PORT: int = _int("PORT", 10000)
HOST: str = _str("HOST", "0.0.0.0")
KEEPALIVE_URL: str = _str("KEEPALIVE_URL", "")
WATCHDOG_INTERVAL: int = _int("WATCHDOG_INTERVAL", 300)
ENV: str = _str("ENV", "production")

# ── Music & External APIs ─────────────────────────────────────────────────────
# Official Eldian API is opt-in: self-host the vendored service or provide a trusted URL+key.
# Built-in Eldian routes on the local Flask server are used by default.
ELDIAN_API_URL: str = _str("ELDIAN_API_URL", f"http://127.0.0.1:{PORT}")
ELDIAN_API_KEY: str = _str("ELDIAN_API_KEY", _str("WEBAPP_SECRET", ""))
# Optional external media downloader API (GET /download, YT_API_URL/KEY).
# The previous .site hostname is being discontinued; keep an env override available.
YT_API_URL: str = _str("YT_API_URL", "https://api.shrutibots.in")
YT_API_KEY: str = _str("YT_API_KEY", "")
YT_API_KEY_FALLBACK: str = _str("YT_API_KEY_FALLBACK", "")
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

# ── Limits & Behaviour ────────────────────────────────────────────────────────
MAX_DURATION_SECONDS: int = _int("MAX_DURATION_SECONDS", 1800)  # 30 min
MUSIC_MAX_DURATION: int = _int("MUSIC_MAX_DURATION", 600)
# PyTgCalls audio uplink preset: studio (96 kbps stereo), high (48 kbps stereo),
# medium (36 kbps mono) or low (24 kbps mono). Studio is the quality-first default.
VOICE_AUDIO_QUALITY: str = _str("VOICE_AUDIO_QUALITY", "high").casefold()
if VOICE_AUDIO_QUALITY not in {"studio", "high", "medium", "low"}:
    VOICE_AUDIO_QUALITY = "high"
QUEUE_LIMIT: int = _int("QUEUE_LIMIT", 20)
COOLDOWN: int = _int("COOLDOWN", 5)
PLAYLIST_LIMIT: int = _int("PLAYLIST_LIMIT", 10)
PLAYLIST_SONG_LIMIT: int = _int("PLAYLIST_SONG_LIMIT", 50)
DEFAULT_WARN_LIMIT: int = _int("DEFAULT_WARN_LIMIT", 3)
DEFAULT_FLOOD_LIMIT: int = _int("DEFAULT_FLOOD_LIMIT", 5)
DEFAULT_FLOOD_WINDOW: int = _int("DEFAULT_FLOOD_WINDOW", 6)
RATE_LIMIT_CMDS: int = _int("RATE_LIMIT_CMDS", 8)
WEBAPP_SECRET: str = _str("WEBAPP_SECRET", "")

# ── Premium emoji configuration ─────────────────────────────────────────────────────────────────
USE_PREMIUM_EMOJI: bool = _bool("USE_PREMIUM_EMOJI", True)

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
