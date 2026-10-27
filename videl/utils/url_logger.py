# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Startup & Architecture URL Logger
#  Logs Render backend, Eldian music API, MongoDB, and single-URL Vercel WebApp
# --------------------------------------------------------------------------------
from __future__ import annotations
import os
import re
import logging
from datetime import datetime, timezone

import config
from videl.utils.rich_ui import (
    rich_heading, rich_kv_table, rich_note,
    rich_esc, rich_details, rich_send,
)

logger = logging.getLogger("videl.url_logger")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _mask_url(url: str) -> str:
    if not url:
        return "— not set —"
    if "bot" in url.lower() and len(url) > 30:
        url = re.sub(r"bot\d+:[A-Za-z0-9_-]+", "bot****:masked", url)
    if "mongodb" in url.lower():
        url = re.sub(r"://[^:]+:[^@]+@", "://***:***@", url)
        if len(url) > 80:
            url = url[:60] + "..." + url[-15:]
    return url


async def log_all_urls(client, me=None, assistant_username: str = "", mongo_ok: bool = False):
    bot_username = getattr(me, "username", "videlapp") if me else getattr(config, "BOT_USERNAME", "videlapp")
    bot_id = getattr(me, "id", "0") if me else "—"

    port = getattr(config, "PORT", 10000)
    render_url = (os.getenv("RENDER_EXTERNAL_URL", "") or f"http://127.0.0.1:{port}").rstrip("/")
    webapp_url = (getattr(config, "WEBAPP_URL", "") or "https://videl0-control-panel.vercel.app").rstrip("/")
    mongo_url = getattr(config, "MONGO_DB_URL", "") or os.getenv("MONGO_DB_URL", "")
    eldian_url = (getattr(config, "ELDIAN_API_URL", "") or f"http://127.0.0.1:{port}").rstrip("/")

    support_chat = getattr(config, "SUPPORT_CHAT", "@VidelSupport")
    support_channel = getattr(config, "SUPPORT_CHANNEL", "@VidelUpdates")
    support_url = f"https://t.me/{support_chat.lstrip('@')}" if support_chat.startswith("@") else support_chat
    updates_url = f"https://t.me/{support_channel.lstrip('@')}" if support_channel.startswith("@") else support_channel

    text = rich_heading(f"👑 Videl Studio · Architecture & URLs — {_now()}", level=1)
    text += rich_kv_table([
        ("Bot", f"@{rich_esc(bot_username)} (<code>{bot_id}</code>)"),
        ("Assistant", f"@{rich_esc(assistant_username or '— not set —')}"),
        ("MongoDB", f"<code>{rich_esc(_mask_url(mongo_url))}</code> · {'connected' if mongo_ok else 'disconnected'}"),
        ("Vercel Web App (Single URL)", f"<code>{rich_esc(webapp_url)}</code>"),
        ("Render Backend Health", f"<code>{rich_esc(render_url)}/health</code>"),
        ("Eldian Music API", f"<code>{rich_esc(eldian_url)}/v1/track/by-video-id</code>"),
        ("Support", f"<a href=\"{rich_esc(support_url)}\">{rich_esc(support_url)}</a>"),
        ("Updates", f"<a href=\"{rich_esc(updates_url)}\">{rich_esc(updates_url)}</a>"),
    ], headers=["Service", "Endpoint"])
    text += rich_note(
        f"Single-URL Vercel Studio: <code>{rich_esc(webapp_url)}</code> hosts Home, Smart Chat, Post Studio, "
        f"Group Manager, Automation, Analytics, Broadcast & Bot Settings in one unified interface."
    )
    text += rich_details(
        "👑 Videl Studio Ready",
        f"Bot <code>@{rich_esc(bot_username)}</code> online · WebApp <code>{rich_esc(webapp_url)}</code>",
        open=False,
    )

    logger_id = getattr(config, "LOGGER_ID", 0) or getattr(config, "LOG_CHANNEL_ID", 0)
    if not logger_id:
        return
    try:
        await rich_send(client, int(logger_id), text)
    except Exception as e:
        logger.warning("[url_logger] Failed to send URL log: %s", e)


def log_urls_sync():
    port = getattr(config, "PORT", 10000)
    webapp_url = (getattr(config, "WEBAPP_URL", "") or "https://videl0-control-panel.vercel.app").rstrip("/")
    render_url = (os.getenv("RENDER_EXTERNAL_URL", "") or f"http://0.0.0.0:{port}").rstrip("/")
    logger.info("Videl Studio Single WebApp URL: %s | Render Backend: %s/health", webapp_url, render_url)
