# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Proper: resilient imports — never crash Render on missing optional deps
# --------------------------------------------------------------------------------

import logging
import time

# Telegram client: pyrogram stable, kurigram fallback (both installed via deps)
try:
    from pyrogram import Client
    from pyrogram.enums import ParseMode
    _TG_IMPL = "pyrogram"
except ImportError:
    from kurigram import Client
    from kurigram.enums import ParseMode
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
    call_py = PyTgCalls(assistant)
else:
    call_py = None
