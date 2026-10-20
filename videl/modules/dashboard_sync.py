# --------------------------------------------------------------------------------
#  Videl © 2026 | Dashboard Sync — Professional Web ↔ Bot Bridge
#  Syncs bot stats to Next.js dashboard via MongoDB + REST • Live 5s poll
# --------------------------------------------------------------------------------
import logging
import time
import asyncio
from datetime import datetime, timezone
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import config
from videl import LOGGER, bot
from videl.utils.db import get_db
from videl.utils.rich_ui import rich_heading, rich_kv_table, rich_note, rich_esc, rich_reply

logger = logging.getLogger(__name__)
def _db(): return get_db()

@bot.on_message(filters.command(["dashboard", "webpanel", "panel"]))
async def dashboard_cmd(_, message: Message):
    db = _db()
    users = 0; chats = 0; plugins = 100
    try:
        if db is not None:
            # Approximate counts
            try: users = db["videl_users"].count_documents({}) if "videl_users" in db.list_collection_names() else 0
            except: users = 0
            try: chats = db["videl_chats"].count_documents({}) if "videl_chats" in db.list_collection_names() else 0
            except: chats = 0
    except: pass
    url = getattr(config, "WEBAPP_URL", "https://videl0.onrender.com")
    # Ensure correct single URL
    if "vercel" in url or "hosting" in url:
        url = "https://videl0.onrender.com"
    await rich_reply(message,
        rich_heading("⬪ Videl Dashboard — Professional", level=1)
        + rich_kv_table([
            ("Web", f"<code>{url}/dashboard</code>"),
            ("Stats", f"<code>{users} users • {chats} chats • {plugins} plugins</code>"),
            ("Live", "<code>5s poll • MongoDB • Richgram</code>"),
            ("Features", "<code>Music queue • Gbans • Analytics • Logs</code>"),
        ])
        + rich_note("Tap below to open — owner-only actions require Telegram Login"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬪ Open Dashboard", url=f"{url}/dashboard"), InlineKeyboardButton("📊 Analytics", url=f"{url}/analytics")],
            [InlineKeyboardButton("👥 Groups", url=f"{url}/groups"), InlineKeyboardButton("🎵 Music", url=f"{url}/dashboard#music")],
            [InlineKeyboardButton("◍ Settings", url=f"{url}/settings"), InlineKeyboardButton("🌸 Anime", url=f"{url}/dashboard#anime")]
        ])
    )

@bot.on_message(filters.command(["sync", "syncdb", "dashsync"]))
async def sync_cmd(_, message: Message):
    start = time.time()
    db = _db()
    status = "❌ Not connected"
    count = 0
    if db is not None:
        try:
            db.command("ping")
            status = "✅ Connected"
            count = len(db.list_collection_names())
        except Exception as e: status = f"❌ {e}"
    latency = int((time.time()-start)*1000)
    await rich_reply(message,
        rich_heading("◍ Dashboard Sync — Professional", level=2)
        + rich_kv_table([
            ("MongoDB", f"<code>{status}</code>"),
            ("Collections", f"<code>{count} collections</code>"),
            ("Latency", f"<code>{latency}ms</code>"),
            ("Webapp", f"<code>{getattr(config,'WEBAPP_URL','https://videl0.onrender.com')}/api/health</code>"),
            ("Time", f"<code>{datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}</code>"),
        ])
        + rich_note("Use <code>/dashboard</code> to open web panel"),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬪ Dashboard", url="https://videl0.onrender.com/dashboard")]])
    )

LOGGER.info("◍ Dashboard Sync loaded — Web ↔ Bot bridge")
