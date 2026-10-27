# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Proper: resilient imports — never crash Render on missing optional deps
# --------------------------------------------------------------------------------

import logging
import os
import time

# Kurigram is the maintained client, imported through its pyrogram namespace.
from pyrogram import Client
from pyrogram.enums import ParseMode
_TG_IMPL = "kurigram"

# PyTgCalls: optional — if ntgcalls missing, bot still runs (VC disabled)
try:
    from pytgcalls import PyTgCalls
except Exception as _e:  # ImportError or native load failure
    PyTgCalls = None
    _PYTG_ERR = str(_e)
else:
    _PYTG_ERR = None

import config

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()],
    level=logging.INFO,
)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)

LOGGER         = logging.getLogger(__name__)
bot_start_time = time.time()
# Render sets RENDER_GIT_COMMIT on every deploy; /health exposes the first 12
# characters so a stale backend is obvious from the outside.
build_revision = (
    os.environ.get("RENDER_GIT_COMMIT")
    or os.environ.get("GIT_COMMIT")
    or os.environ.get("VERCEL_GIT_COMMIT_SHA")
    or "dev"
)[:12]

# ── Bot client ────────────────────────────────────────────────────────────────
bot = Client(
    config.SESSION_NAME,
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    parse_mode=ParseMode.DEFAULT,
    in_memory=True,
)

# ── Assistant (userbot) for voice chats ───────────────────────────────────────
assistant = Client(
    "assistant",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    session_string=config.STRING_SESSION,
    in_memory=True,
)

# ── PyTgCalls ─────────────────────────────────────────────────────────────────
if PyTgCalls:
    # Follow Badmunda05/ShizuMusic's shorter call cache to avoid stale call state
    # when Render restarts or Telegram ends/recreates a group voice chat.
    call_py = PyTgCalls(assistant, cache_duration=100)
else:
    call_py = None
