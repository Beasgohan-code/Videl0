# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — All URLs Startup Logger
#  Logs every single URL on startup: webhook, mongo, flask, nextjs, render,
#  telegram bot API, support, updates, webapp — Richgram styled
# --------------------------------------------------------------------------------
from __future__ import annotations
import os
import logging
from datetime import datetime, timezone

import config
from videl.utils.rich_ui import (
    rich_heading, rich_kv_table, rich_note, rich_code,
    rich_esc, rich_details, rich_send, rich_button, rich_pre
)

logger = logging.getLogger("videl.url_logger")

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def _mask_url(url: str) -> str:
    """Mask sensitive parts of URL for logging"""
    if not url:
        return "— not set —"
    # Mask bot token
    if "bot" in url.lower() and len(url) > 30:
        import re
        url = re.sub(r'bot\d+:[A-Za-z0-9_-]+', 'bot****:masked', url)
    # Mask mongo password
    if "mongodb" in url.lower():
        import re
        url = re.sub(r'://[^:]+:[^@]+@', '://***:***@', url)
        # Also truncate long mongo URIs
        if len(url) > 80:
            url = url[:60] + "..." + url[-15:]
    return url

async def log_all_urls(client, me=None, assistant_username: str = "", mongo_ok: bool = False):
    """
    LOG ALL URLS — Comprehensive startup URL logger
    Every single URL the bot uses, logged to LOGGER_ID with Richgram formatting
    Covers: Flask, Next.js, MongoDB, Telegram API, Webhooks, Webapp, Support, etc.
    """
    bot_username = getattr(me, "username", "Videl0Bot") if me else getattr(config, "BOT_USERNAME", "Videl0Bot")
    bot_id = getattr(me, "id", "0") if me else "—"
    
    # ── Collect ALL URLs ──────────────────────────────────────────────────
    port = getattr(config, "PORT", 10000)
    next_port = os.getenv("NEXT_PORT", "3000")
    render_external = os.getenv("RENDER_EXTERNAL_URL", "")
    public_url = render_external or f"https://{bot_username.lower()}.onrender.com" if "videl" in bot_username.lower() else "https://videl0.onrender.com"
    if not render_external:
        # Try to infer from config
        public_url = os.getenv("WEBAPP_URL", "https://videl0.onrender.com")
    
    mongo_url = getattr(config, "MONGO_DB_URL", "") or os.getenv("MONGO_DB_URL", "") or os.getenv("MONGO_URI", "")
    webhook_url = getattr(config, "WEBHOOK_URL", "") or os.getenv("WEBHOOK_URL", "")
    webhook_secret = getattr(config, "WEBHOOK_SECRET", "") or os.getenv("WEBHOOK_SECRET", "videl0-webhook")
    webapp_url = getattr(config, "WEBAPP_URL", "") or os.getenv("WEBAPP_URL", public_url)
    
    # Telegram API URLs
    tg_api_base = f"https://api.telegram.org/bot{bot_username}/"
    tg_file_base = f"https://api.telegram.org/file/bot{bot_username}/"
    
    # Support / Community URLs
    support_chat = getattr(config, "SUPPORT_CHAT", "@VidelSupport")
    support_channel = getattr(config, "SUPPORT_CHANNEL", "@VidelUpdates")
    community_url = os.getenv("COMMUNITY_URL", f"https://t.me/{support_chat.lstrip('@')}" if support_chat else "https://t.me/VidelSupport")
    support_url = os.getenv("SUPPORT_URL", "https://t.me/VidelSupport")
    github_url = os.getenv("GITHUB_URL", "https://github.com/Beasgohan-code/Videl0")
    updates_url = os.getenv("UPDATES_URL", f"https://t.me/{support_channel.lstrip('@')}" if support_channel else "https://t.me/VidelUpdates")
    
    # Flask / Health URLs
    flask_base = f"http://0.0.0.0:{port}"
    flask_health = f"{flask_base}/health"
    flask_api = f"{flask_base}/api"
    public_health = f"{public_url}/health"
    public_api = f"{public_url}/api"
    
    # Next.js URLs
    next_base = f"http://127.0.0.1:{next_port}"
    dashboard_url = f"{public_url}/dashboard"
    chat_url = f"{public_url}/chat"
    post_url = f"{public_url}/post"
    analytics_url = f"{public_url}/analytics"
    groups_url = f"{public_url}/groups"
    automation_url = f"{public_url}/automation"
    settings_url = f"{public_url}/settings"
    
    # Additional service URLs (from KustMusic integration)
    ytdlp_url = "https://github.com/yt-dlp/yt-dlp"
    ntgcalls_url = "https://github.com/pytgcalls/ntgcalls"
    
    # Mask sensitive URLs
    mongo_masked = _mask_url(mongo_url) if mongo_url else "❌ NOT SET"
    webhook_masked = _mask_url(webhook_url) if webhook_url else f"{public_url}/webhook/{webhook_secret} (auto)"
    
    # ── Build Richgram Message ────────────────────────────────────────────
    text = rich_heading(f"◍ Vɪᴅᴇʟ — ᴀʟʟ URLs ʟᴏɢ ◍ — {_now()}", level=1)
    
    # Core Bot URLs
    text += rich_heading("◎ ᴄᴏʀᴇ ʙᴏᴛ URLs", level=2)
    text += rich_kv_table([
        ("ʙᴏᴛ", f"@{rich_esc(bot_username)} (<code>{bot_id}</code>)"),
        ("ʙᴏᴛ ɴᴀᴍᴇ", f"<code>{rich_esc(getattr(config, 'BOT_NAME', 'Videl Music'))}</code>"),
        ("ᴀssɪsᴛᴀɴᴛ", f"@{rich_esc(assistant_username or '— not set —')}"),
        ("ᴏᴡɴᴇʀ", f"<code>{getattr(config, 'OWNER_ID', 0)}</code> — <a href=\"tg://user?id={getattr(config, 'OWNER_ID', 0)}\">owner</a>" if getattr(config, 'OWNER_ID', 0) else "— not set —"),
        ("ᴍᴏɴɢᴏ", f"<code>{rich_esc(mongo_masked)}</code> — {'✅ connected' if mongo_ok else '❌ disconnected'}"),
        ("ᴍᴏɴɢᴏ ᴅʙ", f"<code>{getattr(config, 'MONGO_DB_NAME', 'Videl')}</code>"),
    ], headers=["ᴋᴇʏ", "ᴠᴀʟᴜᴇ"])
    
    # Server & Health URLs
    text += rich_heading("⬢ sᴇʀᴠᴇʀ & ʜᴇᴀʟᴛʜ URLs", level=2)
    text += rich_kv_table([
        ("ғʟᴀsᴋ (ʟᴏᴄᴀʟ)", f"<code>{rich_esc(flask_base)}</code>"),
        ("ғʟᴀsᴋ ʜᴇᴀʟᴛʜ", f"<code>{rich_esc(flask_health)}</code>"),
        ("ғʟᴀsᴋ ᴀᴘɪ", f"<code>{rich_esc(flask_api)}</code>"),
        ("ɴᴇxᴛ.ᴊs (ʟᴏᴄᴀʟ)", f"<code>{rich_esc(next_base)}</code>"),
        ("ᴘᴜʙʟɪᴄ URL", f"<code>{rich_esc(public_url)}</code>"),
        ("ᴘᴜʙʟɪᴄ ʜᴇᴀʟᴛʜ", f"<code>{rich_esc(public_health)}</code>"),
        ("ᴘᴜʙʟɪᴄ ᴀᴘɪ", f"<code>{rich_esc(public_api)}</code>"),
        ("ᴘᴏʀᴛ", f"<code>{port} (Flask) → {next_port} (Next.js)</code>"),
        ("ʀᴇɴᴅᴇʀ URL", f"<code>{rich_esc(render_external or '— not on Render —')}</code>"),
    ], headers=["sᴇʀᴠɪᴄᴇ", "URL"])
    
    # Webapp URLs
    text += rich_heading("◍ ᴡᴇʙᴀᴘᴘ URLs (sɪɴɢʟᴇ URL sʏsᴛᴇᴍ)", level=2)
    text += rich_kv_table([
        ("ᴅᴀsʜʙᴏᴀʀᴅ", f"<code>{rich_esc(dashboard_url)}</code>"),
        ("ᴄʜᴀᴛ (ᴀs ʙᴏᴛ)", f"<code>{rich_esc(chat_url)}</code>"),
        ("ᴘᴏsᴛ sᴛᴜᴅɪᴏ", f"<code>{rich_esc(post_url)}</code>"),
        ("ᴀɴᴀʟʏᴛɪᴄs", f"<code>{rich_esc(analytics_url)}</code>"),
        ("ɢʀᴏᴜᴘs", f"<code>{rich_esc(groups_url)}</code>"),
        ("ᴀᴜᴛᴏᴍᴀᴛɪᴏɴ", f"<code>{rich_esc(automation_url)}</code>"),
        ("sᴇᴛᴛɪɴɢs", f"<code>{rich_esc(settings_url)}</code>"),
        ("ᴀᴜᴛʜ", f"<code>{rich_esc(public_url + '/auth')}</code>"),
        ("ᴡᴇʙᴀᴘᴘ URL", f"<code>{rich_esc(webapp_url)}</code>"),
    ], headers=["ᴘᴀɢᴇ", "URL"])
    
    # Webhook URLs
    text += rich_heading("⚡ ᴡᴇʙʜᴏᴏᴋ URLs", level=2)
    text += rich_kv_table([
        ("ᴡᴇʙʜᴏᴏᴋ URL", f"<code>{rich_esc(webhook_masked)}</code>"),
        ("ᴡᴇʙʜᴏᴏᴋ sᴇᴄʀᴇᴛ", f"<code>{rich_esc(webhook_secret[:8])}****</code>" if len(webhook_secret) > 8 else f"<code>{rich_esc(webhook_secret)}</code>"),
        ("sᴇᴛ ᴡᴇʙʜᴏᴏᴋ", f"<code>POST {rich_esc(tg_api_base)}setWebhook?url={rich_esc(webhook_masked)}</code>"),
        ("ɢᴇᴛ ᴡᴇʙʜᴏᴏᴋ", f"<code>GET {rich_esc(tg_api_base)}getWebhookInfo</code>"),
        ("ᴅᴇʟᴇᴛᴇ ᴡᴇʙʜᴏᴏᴋ", f"<code>POST {rich_esc(tg_api_base)}deleteWebhook</code>"),
    ], headers=["ᴇɴᴅᴘᴏɪɴᴛ", "URL"])
    
    # Telegram API URLs
    text += rich_heading("◍ ᴛᴇʟᴇɢʀᴀᴍ ᴀᴘɪ URLs", level=2)
    text += rich_kv_table([
        ("ʙᴏᴛ ᴀᴘɪ", f"<code>{rich_esc(tg_api_base)}</code>"),
        ("ғɪʟᴇ ᴀᴘɪ", f"<code>{rich_esc(tg_file_base)}</code>"),
        ("ɢᴇᴛᴍᴇ", f"<code>{rich_esc(tg_api_base)}getMe</code>"),
        ("sᴇɴᴅᴍᴇssᴀɢᴇ", f"<code>{rich_esc(tg_api_base)}sendMessage</code>"),
        ("sᴇᴛᴍʏᴄᴏᴍᴍᴀɴᴅs", f"<code>{rich_esc(tg_api_base)}setMyCommands</code>"),
        ("sᴇᴛᴡᴇʙʜᴏᴏᴋ", f"<code>{rich_esc(tg_api_base)}setWebhook</code>"),
    ], headers=["ᴍᴇᴛʜᴏᴅ", "URL"])
    
    # Community & Support URLs
    text += rich_heading("♡ ᴄᴏᴍᴍᴜɴɪᴛʏ & sᴜᴘᴘᴏʀᴛ URLs", level=2)
    text += rich_kv_table([
        ("sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ", f"<code>{rich_esc(support_chat)}</code> → <a href=\"{rich_esc(community_url)}\">{rich_esc(community_url)}</a>"),
        ("ᴜᴘᴅᴀᴛᴇs ᴄʜᴀɴɴᴇʟ", f"<code>{rich_esc(support_channel)}</code> → <a href=\"{rich_esc(updates_url)}\">{rich_esc(updates_url)}</a>"),
        ("ɢɪᴛʜᴜʙ", f"<a href=\"{rich_esc(github_url)}\">{rich_esc(github_url)}</a>"),
        ("ᴄᴏᴍᴍᴜɴɪᴛʏ", f"<a href=\"{rich_esc(community_url)}\">{rich_esc(community_url)}</a>"),
        ("sᴜᴘᴘᴏʀᴛ", f"<a href=\"{rich_esc(support_url)}\">{rich_esc(support_url)}</a>"),
        ("ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", f"<a href=\"https://t.me/{bot_username}?startgroup=true\">https://t.me/{bot_username}?startgroup=true</a>"),
    ], headers=["ᴛʏᴘᴇ", "URL/ʟɪɴᴋ"])
    
    # External Service URLs
    text += rich_heading("⬪ ᴇxᴛᴇʀɴᴀʟ sᴇʀᴠɪᴄᴇ URLs", level=2)
    text += rich_kv_table([
        ("ʏᴛ-ᴅʟᴘ", f"<a href=\"{rich_esc(ytdlp_url)}\">{rich_esc(ytdlp_url)}</a>"),
        ("ɴᴛɢᴄᴀʟʟs", f"<a href=\"{rich_esc(ntgcalls_url)}\">{rich_esc(ntgcalls_url)}</a>"),
        ("ᴘʏᴛɢᴄᴀʟʟs", f"<code>py-tgcalls 2.2.11</code>"),
        ("ʏᴛ ᴀᴘɪ", f"<code>{rich_esc(getattr(config, 'SHRUTI_API_URL', 'https://api.shrutibots.site'))}</code>"),
        ("ᴇʟᴅɪᴀɴ ᴀᴘɪ", f"<code>{rich_esc(getattr(config, 'ELDIAN_API_URL', 'https://eldian-music-api-production.up.railway.app'))}</code>"),
    ], headers=["sᴇʀᴠɪᴄᴇ", "URL"])
    
    # API Endpoints
    text += rich_heading("⚙️ ᴀᴘɪ ᴇɴᴅᴘᴏɪɴᴛs", level=2)
    text += rich_kv_table([
        ("/health", f"<code>{rich_esc(public_health)}</code> — GET health check"),
        ("/api", f"<code>{rich_esc(public_api)}</code> — API index"),
        ("/api/stats", f"<code>{rich_esc(public_url)}/api/stats</code> — bot stats"),
        ("/api/channel", f"<code>{rich_esc(public_url)}/api/channel</code> — POST to channel"),
        ("/api/chat", f"<code>{rich_esc(public_url)}/api/chat</code> — POST as bot/user"),
        ("/api/auth", f"<code>{rich_esc(public_url)}/api/auth</code> — TG login verify"),
        ("/api/gbans", f"<code>{rich_esc(public_url)}/api/gbans</code> — global bans"),
        ("/api/queue", f"<code>{rich_esc(public_url)}/api/queue</code> — music queue"),
        ("/api/analytics", f"<code>{rich_esc(public_url)}/api/analytics</code> — analytics"),
        ("/dashboard", f"<code>{rich_esc(dashboard_url)}</code> — Studio dashboard"),
        ("/chat", f"<code>{rich_esc(chat_url)}</code> — Web chat alias"),
        ("/post", f"<code>{rich_esc(post_url)}</code> — Post studio alias"),
    ], headers=["ᴇɴᴅᴘᴏɪɴᴛ", "URL"])
    
    text += rich_note(f"⬪ All URLs logged at <code>{_now()}</code> • Flask on <code>{port}</code> • Next.js on <code>{next_port}</code> • Single Render URL system ✅")
    text += rich_details(f"◍ Vɪᴅᴇʟ sᴛᴀʀᴛᴇᴅ ◍ — ᴀʟʟ sʏsᴛᴇᴍs ʀᴇᴀᴅʏ", f"Bot <code>@{rich_esc(bot_username)}</code> is live on <code>{rich_esc(public_url)}</code> • MongoDB {'✅' if mongo_ok else '❌'} • Richgram 10.3 ✅ • Have fun!", open=False)
    
    # Send to logger channel
    logger_id = getattr(config, "LOGGER_ID", 0) or getattr(config, "LOG_CHANNEL_ID", 0)
    if not logger_id:
        logger.warning("[url_logger] LOGGER_ID not set — printing to console instead")
        print(text.replace("<code>", "").replace("</code>", "").replace("<a href=", "").replace("</a>", ""))
        return
    
    try:
        # Split into multiple messages if too long (Telegram limit 4096)
        # Richgram messages are InputRichMessage (max ~700 lines), so we need to handle
        max_len = 3800
        if len(text) > max_len:
            # Split by sections
            parts = text.split("◍ ")
            current = ""
            for i, part in enumerate(parts):
                section = ("◍ " + part) if i > 0 else part
                if len(current) + len(section) > max_len:
                    if current:
                        await rich_send(client, int(logger_id), current)
                    current = section
                else:
                    current += section
            if current:
                await rich_send(client, int(logger_id), current)
        else:
            await rich_send(client, int(logger_id), text)
        logger.info(f"[url_logger] ✅ All URLs logged to {logger_id}")
    except Exception as e:
        logger.warning(f"[url_logger] Failed to send URL log: {e}")
        # Fallback: try plain text
        try:
            from pyrogram.types import Message as PMsg
            plain = text.replace("<code>", "`").replace("</code>", "`").replace("<a href=\"", "").replace("\">", " ").replace("</a>", "")
            await client.send_message(int(logger_id), plain[:4000])
        except Exception as e2:
            logger.warning(f"[url_logger] Fallback also failed: {e2}")

def log_urls_sync():
    """Synchronous version for non-async startup logging to console"""
    port = getattr(config, "PORT", 10000)
    next_port = os.getenv("NEXT_PORT", "3000")
    public_url = os.getenv("RENDER_EXTERNAL_URL", "") or os.getenv("WEBAPP_URL", "https://videl0.onrender.com")
    mongo_url = getattr(config, "MONGO_DB_URL", "") or os.getenv("MONGO_DB_URL", "")
    
    print("\n" + "="*60)
    print("◍ Videl — All URLs Startup Log")
    print("="*60)
    print(f"• Bot: @{getattr(config, 'BOT_USERNAME', 'Videl0Bot')} (ID: {getattr(config, 'BOT_TOKEN', '')[:10]}...)")
    print(f"• Flask: http://0.0.0.0:{port}/health")
    print(f"• Next.js: http://127.0.0.1:{next_port}")
    print(f"• Public: {public_url}")
    print(f"• Public Health: {public_url}/health")
    print(f"• Webapp: {public_url}/dashboard")
    print(f"• Chat: {public_url}/chat → /dashboard/chat")
    print(f"• Post: {public_url}/post → /dashboard/channel")
    print(f"• Mongo: {_mask_url(mongo_url) if mongo_url else 'NOT SET'}")
    print(f"• Webhook: {getattr(config, 'WEBHOOK_URL', '') or public_url + '/webhook/***'}")
    print(f"• Support: {getattr(config, 'SUPPORT_CHAT', '@VidelSupport')}")
    print(f"• Updates: {getattr(config, 'SUPPORT_CHANNEL', '@VidelUpdates')}")
    print("="*60 + "\n")
    logger.info("All URLs logged to console")
