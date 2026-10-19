"""
Videl0 • Main — aiogram 3.31 Dispatcher + Bot + Webhook/Polling
All external repos used: aiogram (Telegram Bot API 10.3), richgram (Rich UI), ShizuMusic (Music core)
All connectors used: Supabase (DB), Dropbox (backup), Vercel (webapp hosting + webhook)
"""
import asyncio, logging, os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

# ensure env loaded
import bot.config as cfg
from bot.config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET, PORT, HOST, LOG_CHANNEL_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()],
)
log=logging.getLogger("videl.main")
# quiet noisy
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def set_commands(bot: Bot):
    cmds=[
        BotCommand(command="start", description="Start bot"),
        BotCommand(command="help", description="Help menu"),
        BotCommand(command="ping", description="Pong + stats"),
        BotCommand(command="play", description="Play music"),
        BotCommand(command="queue", description="Queue"),
        BotCommand(command="skip", description="Skip"),
        BotCommand(command="stop", description="Stop & clear"),
        BotCommand(command="pause", description="Pause"),
        BotCommand(command="resume", description="Resume"),
        BotCommand(command="ask", description="AI chat"),
        BotCommand(command="imagine", description="Generate image"),
        BotCommand(command="ban", description="Ban user"),
        BotCommand(command="mute", description="Mute"),
        BotCommand(command="warn", description="Warn"),
        BotCommand(command="filter", description="Add filter"),
        BotCommand(command="note", description="Save note"),
        BotCommand(command="rules", description="Chat rules"),
        BotCommand(command="stats", description="Bot stats"),
        BotCommand(command="id", description="IDs"),
        BotCommand(command="weather", description="Weather"),
        BotCommand(command="qr", description="QR code"),
        BotCommand(command="tagall", description="Tag all"),
        BotCommand(command="broadcast", description="[owner] Broadcast"),
        BotCommand(command="gban", description="[owner] Global ban"),
    ]
    try: await bot.set_my_commands(cmds)
    except Exception as e: log.warning(f"set_commands fail: {e}")

def create_bot() -> Bot:
    if not BOT_TOKEN or ":" not in BOT_TOKEN:
        # use dummy for build verification when no token set (CI)
        log.warning("BOT_TOKEN not set — using dummy token for scaffolding. Bot will not start without real token.")
        dummy="123456789:AAF_dummy_token_for_ci_build"
        return Bot(token=dummy, default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))
    return Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))

def create_dispatcher() -> Dispatcher:
    from bot.handlers import setup_all
    from bot.middlewares.logging_mw import LoggingMiddleware
    from bot.middlewares.tracker import TrackerMiddleware
    dp = Dispatcher()
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.message.middleware(TrackerMiddleware())
    # register all handlers
    router = setup_all()
    dp.include_router(router)
    return dp

async def on_startup(bot: Bot):
    log.info(f"🚀 Videl0 starting — Bot API 10.3 • aiogram 3.31 • Richgram • ShizuMusic")
    await set_commands(bot)
    # log channel notify
    if LOG_CHANNEL_ID:
        try:
            me=await bot.get_me()
            await bot.send_message(LOG_CHANNEL_ID, f"✅ <b>Videl0 started</b> @{me.username} | Polling={not bool(WEBHOOK_URL)} | Env={cfg.ENV}")
        except: pass
    # watchdog + keepalive
    try:
        from bot.services.keep_alive import self_ping_loop
        from bot.services.watchdog import start_background
        asyncio.create_task(self_ping_loop())
        start_background(bot)
    except Exception as e: log.warning(f"background tasks fail: {e}")
    # assistant VC startup if enabled
    try:
        from bot.services.music_service import assistant, call_py
        if assistant and call_py:
            try:
                await assistant.start()
                await call_py.start()
                log.info("Assistant + calls started")
                if LOG_CHANNEL_ID:
                    try: await assistant.send_message(LOG_CHANNEL_ID, "🎧 Assistant connected for VC")
                    except: pass
            except Exception as e: log.warning(f"Assistant start fail: {e}")
    except: pass

async def main_polling():
    bot = create_bot()
    is_dummy = "dummy" in bot.token
    dp = create_dispatcher()
    await on_startup(bot)
    if is_dummy:
        log.info("Dummy token — skipping polling. Code is valid. Set BOT_TOKEN to run.")
        # keep alive short to verify build
        await asyncio.sleep(2)
        return
    log.info("Starting polling…")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

# ── Webhook path — FastAPI server mounts dp.feed_webhook_update ──────────────
async def feed_webhook_update(bot: Bot, dp: Dispatcher, update: dict):
    from aiogram.types import Update
    try: await dp.feed_update(bot, Update.model_validate(update))
    except Exception as e: log.warning(f"feed_webhook_update fail: {e}")

if __name__ == "__main__":
    asyncio.run(main_polling())
