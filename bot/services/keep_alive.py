"""
Videl0 • Keep-Alive — FastAPI + watchdog ping
"""
import asyncio, logging, aiohttp, time
from bot.config import KEEPALIVE_URL, WATCHDOG_INTERVAL
log=logging.getLogger("videl.keepalive")

async def self_ping_loop():
    if not KEEPALIVE_URL: return
    log.info(f"Keepalive pinging {KEEPALIVE_URL} every {WATCHDOG_INTERVAL}s")
    while True:
        await asyncio.sleep(WATCHDOG_INTERVAL)
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(KEEPALIVE_URL, timeout=10) as r:
                    log.debug(f"Keepalive ping {r.status}")
        except Exception as e:
            log.warning(f"Keepalive ping fail: {e}")

async def send_log(bot, text: str):
    from bot.config import LOG_CHANNEL_ID
    if not LOG_CHANNEL_ID: return
    try:
        await bot.send_message(LOG_CHANNEL_ID, text)
    except Exception as e:
        log.warning(f"log send fail: {e}")
