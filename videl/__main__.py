# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio
import importlib
import os
import re
import sys
import threading
import time

import requests
from flask import Flask, jsonify
from pyrogram import idle
from pyrogram.types import BotCommand

import config
from videl import LOGGER, assistant, bot, call_py
from videl.modules import ALL_MODULES
from videl.utils.rich_ui import (
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_send,
)

ASSISTANT_USERNAME: str = ""

# ── Flask health + built-in Eldian-compatible download API ────────────────────

_flask = Flask(__name__)


@_flask.route("/")
def _home():
    return jsonify(
        {
            "service": "Videl Music",
            "status": "running",
            "api": {
                "status": "/api/status",
                "audio": "/api/stream_audio?url=YOUTUBE_URL",
                "video": "/api/download?url=YOUTUBE_URL",
                "eldian_v1": "POST /v1/track/by-video-id",
            },
            "credit": "Beasgohan-code · Eldian-compatible API built-in",
        }
    ), 200


@_flask.route("/health")
def _health():
    return jsonify({"status": "ok", "service": "videl"}), 200


# Register Eldian-style download routes (same process as the bot)
try:
    from videl.api.eldian_routes import register_eldian_routes

    register_eldian_routes(_flask)
except Exception as _api_err:
    LOGGER.warning(f"Built-in download API not loaded: {_api_err}")


def _run_flask() -> None:
    port = int(os.getenv("PORT", str(config.PORT)))
    LOGGER.info(f"Binding health+API server on 0.0.0.0:{port}")
    _flask.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)


# ── Keep-Alive ────────────────────────────────────────────────────────────────

def _keep_alive() -> None:
    url = os.getenv("RENDER_EXTERNAL_URL", f"http://0.0.0.0:{config.PORT}")
    while True:
        try:
            requests.get(url, timeout=10)
            LOGGER.info(f"Keep-alive ping sent → {url}")
        except Exception as e:
            LOGGER.warning(f"Keep-alive ping failed: {e}")
        time.sleep(300)


# ── Startup notification ──────────────────────────────────────────────────────


async def _notify_owner(me, assistant_username: str) -> None:
    """Notify logger group + send DM to owner when bot starts."""
    content = (
        rich_heading("🎵 Videl Started", level=3)
        + rich_kv_table([
            ("Bot", f"@{rich_esc(me.username or 'N/A')}"),
            ("Assistant", f"@{rich_esc(assistant_username)}"),
            ("Owner", str(config.OWNER_ID)),
        ])
    )

    # Logger group (if set)
    if config.LOGGER_ID:
        try:
            await rich_send(bot, config.LOGGER_ID, content)
        except Exception as e:
            LOGGER.warning(f"Logger notification error: {e}")

    # Owner DM
    try:
        await bot.send_message(
            config.OWNER_ID,
            (
                f"🚀 <b>{config.BOT_NAME}</b> is now online!\n\n"
                f"• Bot: @{me.username or 'N/A'}\n"
                f"• Assistant: @{assistant_username or 'N/A'}\n"
                f"• ID: <code>{me.id}</code>\n\n"
                f"<i>All systems ready. Have fun!</i>"
            ),
        )
        LOGGER.info(f"Startup DM sent to owner {config.OWNER_ID}")
    except Exception as e:
        LOGGER.warning(f"Owner DM notification error: {e}")

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # 1. MongoDB
    try:
        from videl.utils.db import start_mongo
        ok = start_mongo()
        if ok:
            LOGGER.info("MongoDB ready.")
        else:
            LOGGER.warning("MongoDB not connected — continuing without DB.")
    except Exception as e:
        LOGGER.warning(f"MongoDB startup error: {e} — continuing without DB.")

    # 2. Flask
    threading.Thread(target=_run_flask, daemon=True).start()
    LOGGER.info(f"Flask health server on port {config.PORT}")

    # 3. Keep-alive ping
    threading.Thread(target=_keep_alive, daemon=True).start()
    LOGGER.info("Keep-alive thread started")

    # ── 4–12. Start clients in correct order on ONE event loop ───────────────
    # Order matters:
    #   1) bot Client
    #   2) assistant Client
    #   3) PyTgCalls (bound to assistant)
    # Mixing sync starts + run_until_complete on different loops causes:
    #   "belongs to an event loop that is not running"

    async def _boot() -> None:
        global ASSISTANT_USERNAME

        # Bot
        for attempt in range(10):
            try:
                await bot.start()
                LOGGER.info("Bot client started")
                break
            except Exception as e:
                if "FLOOD_WAIT" in str(e):
                    m = re.search(r"(\d+)", str(e))
                    wait = min(int(m.group(1)) + 5 if m else 300, 1800)
                    LOGGER.warning(f"FLOOD_WAIT — sleeping {wait}s (attempt {attempt + 1}/10)")
                    await asyncio.sleep(wait)
                else:
                    LOGGER.error(f"Bot start failed: {e}")
                    raise SystemExit(1) from e
        else:
            LOGGER.error("Bot failed to start after 10 attempts")
            raise SystemExit(1)

        me = await bot.get_me()
        LOGGER.info(f"Bot: @{me.username}")

        # Bot commands
        try:
            await bot.set_bot_commands([
                BotCommand("start",  "Start the bot"),
                BotCommand("help",   "Help menu"),
                BotCommand("play",   "Play a song (audio)"),
                BotCommand("vplay",  "Play video in VC"),
                BotCommand("cplay",  "Play in linked channel"),
                BotCommand("pause",  "Pause playback"),
                BotCommand("resume", "Resume playback"),
                BotCommand("skip",   "Skip song"),
                BotCommand("stop",   "Stop & clear"),
                BotCommand("queue",  "Show queue"),
                BotCommand("lyrics", "Song lyrics"),
                BotCommand("ping",   "Bot stats"),
                BotCommand("ban",    "Ban a user"),
                BotCommand("mute",   "Mute a user"),
                BotCommand("warn",   "Warn a user"),
                BotCommand("admins", "List admins"),
            ])
            LOGGER.info("Bot commands set")
        except Exception as e:
            LOGGER.warning(f"Could not set bot commands: {e}")

        # Assistant FIRST (before PyTgCalls)
        try:
            if not assistant.is_connected:
                await assistant.start()
            am = await assistant.get_me()
            ASSISTANT_USERNAME = am.username or ""
            LOGGER.info(f"Assistant started: @{ASSISTANT_USERNAME}")
        except Exception as e:
            LOGGER.error(
                "❌ Assistant failed to start.\n"
                "STRING_SESSION is invalid or not a Pyrogram session for this API_ID/API_HASH.\n"
                f"Error: {e}"
            )
            raise SystemExit(1) from e

        # PyTgCalls AFTER assistant is connected
        try:
            await call_py.start()
            LOGGER.info("PyTgCalls started")
        except Exception as e:
            LOGGER.error(f"❌ PyTgCalls start failed: {e}")
            raise SystemExit(1) from e

        # Block middleware
        try:
            from videl.utils.decorators import register_block_middleware
            register_block_middleware()
            LOGGER.info("Block middleware registered")
        except Exception as e:
            LOGGER.warning(f"Block middleware load failed: {e}")

        # Load modules
        for mod in ALL_MODULES:
            try:
                importlib.import_module(f"videl.modules.{mod}")
                LOGGER.info(f"Loaded module: {mod}")
            except Exception as e:
                LOGGER.error(f"Failed to load module {mod}: {e}")

        # Stream-end handler
        try:
            import videl.core.call  # noqa: F401
        except Exception as e:
            LOGGER.error(f"Failed to load call handler: {e}")

        # Owner / logger notify (same loop)
        try:
            await _notify_owner(me, ASSISTANT_USERNAME)
        except Exception as e:
            LOGGER.warning(f"Startup notify failed: {e}")

        # Watchdog
        try:
            from videl.core.watcher import watchdog
            asyncio.create_task(watchdog())
            LOGGER.info("Watchdog started")
        except Exception as e:
            LOGGER.warning(f"Watchdog failed: {e}")

        LOGGER.info("Videl is running")
        # Keep process alive on the same loop the clients were started on
        try:
            # Kurigram/Pyrogram idle may be sync or async depending on version
            result = idle()
            if hasattr(result, "__await__"):
                await result
        except TypeError:
            # Some builds expect no call from async context — just wait forever
            await asyncio.Event().wait()

    try:
        asyncio.get_event_loop().run_until_complete(_boot())
    except RuntimeError:
        # Python 3.10+ may need a fresh loop in some environments
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_boot())

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    try:
        bot.stop()
    except Exception:
        pass

    try:
        assistant.stop()
    except Exception:
        pass

    LOGGER.info("✧ videl stopped ✧")

            
