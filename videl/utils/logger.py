"""
Videl — Proper Centralized Logger — Rich + New Bot API 10.3
Logs ALL important events to LOGGER_ID channel with rich formatting:
- startup / shutdown / new chat / left chat / new user / commands / errors / watchdog
- also persists errors to MongoDB error_logs for owner diagnostics
Uses rich_ui (InputRichMessage when Kurigram available, else HTML fallback).
MongoDB only — no file spam.
"""
from __future__ import annotations
import asyncio
import html
import time
import logging
from datetime import datetime, timezone

import config
from videl.utils.rich_ui import (
    rich_heading, rich_kv_table, rich_note, rich_code, rich_pre,
    rich_esc, rich_details, rich_send, rich_button
)

logger = logging.getLogger("videl.logger")

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def _owner_mention() -> str:
    if config.OWNER_ID:
        return f'<a href="tg://user?id={config.OWNER_ID}">owner</a> (<code>{config.OWNER_ID}</code>)'
    return "owner not set"

async def _log(client, html_text: str):
    """Send to LOGGER_ID if set, else silently ignore."""
    chat_id = getattr(config, "LOGGER_ID", 0) or getattr(config, "LOG_CHANNEL_ID", 0)
    if not chat_id:
        logger.debug(f"[logger] LOGGER_ID not set — skip log")
        return
    try:
        await rich_send(client, int(chat_id), html_text)
    except Exception as e:
        logger.warning(f"[logger] failed to send log: {e}")

def _save_error_mongo(where: str, err: str, context: str = ""):
    """Persist error to MongoDB error_logs for owner diagnostics — best effort."""
    try:
        from videl.utils.db import _db
        if _db is None:
            return
        col = _db["error_logs"]
        col.insert_one({
            "where": where,
            "error": str(err)[:2000],
            "context": context[:500],
            "time": datetime.now(timezone.utc).isoformat(),
            "ts": time.time(),
        })
        # cap at 200 docs
        if col.count_documents({}) > 200:
            oldest = col.find({}, {"_id": 1}).sort("ts", 1).limit(50)
            ids = [d["_id"] for d in oldest]
            col.delete_many({"_id": {"$in": ids}})
    except Exception:
        pass

# ── Startup — Enhanced with ALL URL Logging ─────────────────────────────────
async def log_startup(client, me, assistant_username: str = "", mongo_ok: bool = False):
    # First log the standard startup
    text = (
        rich_heading(f"◍ Vɪᴅᴇʟ sᴛᴀʀᴛᴇᴅ ◍ — {_now()}", level=1)
        + rich_kv_table([
            ("ʙᴏᴛ", f"@{rich_esc(me.username or '?')} (<code>{me.id}</code>)"),
            ("ᴀssɪsᴛᴀɴᴛ", f"@{rich_esc(assistant_username or '—')}"),
            ("ᴏᴡɴᴇʀ", _owner_mention()),
            ("ᴍᴏɴɢᴏ", f"<code>{'connected' if mongo_ok else 'disconnected'}</code>"),
            ("ᴠᴇʀsɪᴏɴ", f"<code>Videl 2.0 • Professional • Richgram ✅</code>"),
            ("ғʟᴀsᴋ", f"<code>:{config.PORT} /health</code>"),
        ], headers=["ᴋᴇʏ", "ᴠᴀʟᴜᴇ"])
        + rich_note(f"⬪ Flask alive on <code>{config.PORT}</code> • watchdog active • health /health")
        + rich_details("◍ ᴀʟʟ sʏsᴛᴇᴍs ʀᴇᴀᴅʏ ◍", f"<code>up at {_now()}</code> — have fun!", open=False)
    )
    await _log(client, text)
    logger.info(f"[logger] ✅ startup logged to {config.LOGGER_ID}")

    # NOW log ALL URLs via dedicated URL logger (comprehensive)
    try:
        from videl.utils.url_logger import log_all_urls
        await log_all_urls(client, me, assistant_username, mongo_ok)
    except Exception as e:
        logger.debug(f"URL logger fail: {e}")
        # Fallback inline URL logging
        import os
        port = getattr(config, "PORT", 10000)
        webapp_url = (getattr(config, "WEBAPP_URL", "") or "https://videl0-control-panel.vercel.app").rstrip("/")
        render_url = (os.getenv("RENDER_EXTERNAL_URL", "") or f"http://0.0.0.0:{port}").rstrip("/")
        fallback = (
            rich_heading("👑 Videl Studio — Service Endpoints", level=2)
            + rich_kv_table([
                ("Render Health", f"<code>{rich_esc(render_url)}/health</code>"),
                ("Vercel Web App", f"<code>{rich_esc(webapp_url)}</code>"),
                ("MongoDB", f"<code>{'connected' if mongo_ok else 'disconnected'}</code>"),
            ])
        )
        await _log(client, fallback)

# ── Full URL Dump (sync, for console) ────────────────────────────────────
def log_all_urls_sync():
    """Log all URLs to console (sync version)"""
    try:
        from videl.utils.url_logger import log_urls_sync
        log_urls_sync()
    except Exception as e:
        logger.debug(f"sync URL log fail: {e}")

async def log_restart(client, me):
    text = rich_heading(f"⟳ Vɪᴅᴇʟ ʀᴇsᴛᴀʀᴛᴇᴅ ⟳ — {_now()}", level=2) + rich_note(f"Bot @{rich_esc(me.username or '?')} restarted at <code>{_now()}</code>")
    await _log(client, text)
    logger.info("[logger] restart logged")

# ── New chat / left chat / user ──────────────────────────────────────────
async def log_new_chat(client, chat):
    try:
        title = getattr(chat, "title", None) or getattr(chat, "first_name", "Private")
        cid = chat.id
        ctype = getattr(chat, "type", "unknown")
        count = getattr(chat, "members_count", None)
        text = (
            rich_heading("⬪ ɴᴇᴡ ᴄʜᴀᴛ ⬪", level=3)
            + rich_kv_table([
                ("ᴛɪᴛʟᴇ", f"<code>{rich_esc(title)}</code>"),
                ("ɪᴅ", f"<code>{cid}</code>"),
                ("ᴛʏᴘᴇ", f"<code>{ctype}</code>"),
                ("ᴍᴇᴍʙᴇʀs", f"<code>{count or '?'}</code>"),
                ("ᴛɪᴍᴇ", f"<code>{_now()}</code>"),
            ])
        )
        await _log(client, text)
    except Exception as e:
        logger.debug(f"log_new_chat fail: {e}")

async def log_left_chat(client, chat):
    try:
        title = getattr(chat, "title", None) or str(chat.id)
        text = (
            rich_heading("⬪ ʟᴇғᴛ ᴄʜᴀᴛ ⬪", level=3)
            + rich_kv_table([
                ("ᴛɪᴛʟᴇ", f"<code>{rich_esc(title)}</code>"),
                ("ɪᴅ", f"<code>{chat.id}</code>"),
                ("ᴛɪᴍᴇ", f"<code>{_now()}</code>"),
            ])
        )
        await _log(client, text)
    except Exception as e:
        logger.debug(f"log_left_chat fail: {e}")

async def log_new_user(client, user):
    try:
        name = getattr(user, "first_name", "user")
        uid = user.id
        username = getattr(user, "username", "—")
        text = (
            rich_heading("◍ ɴᴇᴡ ᴜsᴇʀ ◍", level=3)
            + rich_kv_table([
                ("ɴᴀᴍᴇ", rich_esc(name)),
                ("ɪᴅ", f"<code>{uid}</code>"),
                ("ᴜsᴇʀɴᴀᴍᴇ", f"@{rich_esc(username)}" if username != "—" else "—"),
                ("ᴛɪᴍᴇ", f"<code>{_now()}</code>"),
            ])
        )
        await _log(client, text)
    except Exception as e:
        logger.debug(f"log_new_user fail: {e}")

# ── Command / generic event ──────────────────────────────────────────────
async def log_command(client, message, cmd: str):
    try:
        u = message.from_user
        chat = message.chat
        is_private = getattr(chat, "type", "") == "private" if hasattr(chat, "type") else False
        # avoid spamming for every command? Log only if not too frequent? For now log all but truncate
        text = (
            rich_heading(f"◎ ᴄᴍᴅ /{rich_esc(cmd)} ◎", level=3)
            + rich_kv_table([
                ("ᴜsᴇʀ", f"{rich_esc(u.first_name) if u else '?'} (<code>{u.id if u else '?'}</code>) {('@'+rich_esc(u.username) if u and getattr(u,'username',None) else '')}"),
                ("ᴄʜᴀᴛ", f"<code>{chat.id}</code> — {rich_esc(getattr(chat, 'title', None) or getattr(chat,'first_name','pm') or 'pm')}"),
                ("ᴛᴇxᴛ", f"<code>{rich_esc((message.text or message.caption or '')[:90])}</code>"),
                ("ᴛɪᴍᴇ", f"<code>{_now()}</code>"),
            ])
        )
        await _log(client, text)
    except Exception as e:
        logger.debug(f"log_command fail: {e}")

async def log_event(client, title: str, rows: list[tuple[str,str]], note: str = ""):
    try:
        text = rich_heading(title, level=3) + rich_kv_table(rows)
        if note:
            text += rich_note(note)
        await _log(client, text)
    except Exception as e:
        logger.debug(f"log_event fail: {e}")

# ── Error ────────────────────────────────────────────────────────────────
async def log_error(client, where: str, error: Exception, context: str = ""):
    try:
        import traceback
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))[-4000:]
        text = (
            rich_heading(f"❌ ᴇʀʀᴏʀ ɪɴ {rich_esc(where)}", level=3)
            + rich_kv_table([
                ("ᴛɪᴍᴇ", f"<code>{_now()}</code>"),
                ("ᴡʜᴇʀᴇ", f"<code>{rich_esc(where)}</code>"),
                ("ᴄᴛx", f"<code>{rich_esc(context[:200])}</code>" if context else "—"),
                ("ᴇʀʀ", f"<code>{rich_esc(str(error)[:200])}</code>"),
            ])
            + rich_details("ᴛʀᴀᴄᴇʙᴀᴄᴋ", rich_pre(tb, "log"), open=False)
        )
        await _log(client, text)
        # also persist to mongo for owner diagnostics
        _save_error_mongo(where, f"{error}\n{tb[:1500]}", context)
    except Exception as e:
        logger.debug(f"log_error fail: {e}")

# ── Watchdog ─────────────────────────────────────────────────────────────
async def log_watchdog(client, stats: dict):
    try:
        rows = [(k, f"<code>{v}</code>") for k, v in stats.items()]
        text = rich_heading("⬢ ᴡᴀᴛᴄʜᴅᴏɢ ⬢", level=3) + rich_kv_table(rows, headers=["ᴄʜᴇᴄᴋ", "ʀᴇsᴜʟᴛ"]) + rich_note(f"<code>{_now()}</code>")
        await _log(client, text)
    except Exception as e:
        logger.debug(f"log_watchdog fail: {e}")

# ── Shutdown ─────────────────────────────────────────────────────────────
async def log_shutdown(client, reason: str = "signal"):
    text = (
        rich_heading("✧ ᴠɪᴅᴇʟ sᴛᴏᴘᴘᴇᴅ ✧", level=2)
        + rich_kv_table([
            ("ʀᴇᴀsᴏɴ", f"<code>{rich_esc(reason)}</code>"),
            ("ᴛɪᴍᴇ", f"<code>{_now()}</code>"),
        ])
        + rich_note("⬪ bye! — will auto-restart on Render if crash • see /health")
    )
    await _log(client, text)
    logger.info(f"[logger] shutdown logged: {reason}")

def setup_async_error_handler(client, loop: asyncio.AbstractEventLoop):
    """Log any unhandled asyncio exception to LOGGER_ID."""
    def handler(loop, context):
        msg = context.get("message", "asyncio error")
        exc = context.get("exception")
        logger.error(f"[asyncio] {msg}: {exc}")
        if exc and client:
            try:
                asyncio.create_task(log_error(client, "asyncio", exc, msg))
            except: pass
        # also default handler
        try:
            loop.default_exception_handler(context)
        except: pass
    try:
        loop.set_exception_handler(handler)
        logger.info("[logger] asyncio exception handler armed")
    except Exception as e:
        logger.debug(f"set_exception_handler fail: {e}")
