# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Owner Utils ✦ Perfect
#  Owner-only operational commands using the configured MongoDB and runtime.
#  Commands: /sysinfo, /logs, /restart, /update, /shell, /eval, /active, /broadcast_pro
#  Owner access is checked against OWNER_ID and SUDO_USERS.
# --------------------------------------------------------------------------------
from __future__ import annotations

import asyncio
import io
import os
import platform
import sys
import textwrap
import time
import traceback
from datetime import datetime
from pathlib import Path

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup
from videl.utils.bot_ui import button as InlineKeyboardButton
from pyrogram.enums import ParseMode

import config
from videl import bot, LOGGER
# compat: old code used `userbot` alias for assistant
try:
    from videl import userbot
except ImportError:
    from videl import assistant as userbot
from videl.utils.formatters import sc, sb, short
from videl.utils.rich_ui import (
    rich_heading,
    rich_kv_table,
    rich_table,
    rich_note,
    rich_code,
    rich_pre,
    rich_button,
    rich_send,
    rich_edit,
    rich_esc,
    rich_send_blocks,
)

try:
    from videl.utils.premium_emojis import pe
except Exception:
    def pe(k, fb=""):
        return fb

try:
    import psutil
    _HAS_PSUTIL = True
except Exception:
    _HAS_PSUTIL = False

START_TIME = time.time()

def _is_owner(uid: int) -> bool:
    owner = int(getattr(config, "OWNER_ID", 0) or 0)
    sudo = set(getattr(config, "SUDO_USERS", []) or [])
    return uid == owner or uid in sudo

def _owner_only(func):
    async def wrapper(_, m: Message):
        if not m.from_user or not _is_owner(m.from_user.id):
            return await rich_send(bot, m.chat.id, rich_heading(pe("warn","⚠️") + " " + sc("owner only"), level=3) + rich_note(pe("line","") + " " + sc("this command is restricted to bot owners") + "<br>" + pe("small","") + " " + sc("contact") + f" <a href=\"tg://user?id={config.OWNER_ID}\">{sc('owner')}</a>"))
        return await func(_, m)
    return wrapper

def _hdr(t: str, lvl: int = 3):
    return rich_heading(pe("orb","") + " " + t + " " + pe("spark",""), level=lvl)

def _log_to_channel(text: str):
    ch = getattr(config, "LOG_CHANNEL_ID", None)
    if not ch:
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(bot.send_message(int(ch), text, parse_mode=ParseMode.HTML))
        else:
            asyncio.run(bot.send_message(int(ch), text, parse_mode=ParseMode.HTML))
    except Exception as e:
        LOGGER.debug(f"log_channel fail: {e}")

# ── /sysinfo — professional system stats ─────────────────────────────────────

@bot.on_message(filters.command(["sysinfo", "sys", "hostinfo"]) & ~filters.forwarded)
@_owner_only
async def sysinfo_handler(_, m: Message):
    up = time.time() - START_TIME
    hrs, rem = divmod(int(up), 3600)
    mins, secs = divmod(rem, 60)
    up_str = f"{hrs}h {mins}m {secs}s"

    cpu = mem = disk = "—"
    if _HAS_PSUTIL:
        try:
            cpu = f"{psutil.cpu_percent(interval=0.5):.1f}%"
            vm = psutil.virtual_memory()
            mem = f"{vm.percent:.1f}% ({vm.used/1024/1024/1024:.1f} / {vm.total/1024/1024/1024:.1f} GB)"
            du = psutil.disk_usage("/")
            disk = f"{du.percent:.1f}% ({du.free/1024/1024/1024:.1f} GB free)"
        except Exception as e:
            LOGGER.warning(f"psutil fail: {e}")

    py_ver = platform.python_version()
    plat = platform.platform()
    body = _hdr(pe("hex","") + " " + sc("system info") + " • " + pe("circle","") + " " + sc("live"), 2)
    body += rich_kv_table([
        (pe("diamond","") + " " + sc("uptime"), f"<code>{up_str}</code>"),
        (pe("hex","") + " " + sc("python"), f"<code>{py_ver}</code>"),
        (pe("circle","") + " " + sc("platform"), f"<code>{rich_esc(plat[:60])}</code>"),
        (pe("orb","") + " " + sc("cpu"), f"<code>{cpu}</code>"),
        (pe("small","") + " " + sc("memory"), f"<code>{mem}</code>"),
        (pe("pin","📌") + " " + sc("disk"), f"<code>{disk}</code>"),
        (pe("spark","") + " " + sc("bot"), f"<code>{sb('videl perfect')} • @Videl0Bot</code>"),
    ], headers=[pe("check","✅") + " " + sc("host"), sc("value")])
    body += "<p>" + rich_button(pe("target","") + " " + sc("logs"), callback_data="owner:logs") + " " + rich_button(pe("fire","🔥") + " " + sc("restart"), callback_data="owner:restart") + "</p>"
    await rich_send(bot, m.chat.id, body)
    _log_to_channel(f"ℹ️ /sysinfo by {m.from_user.id} in {m.chat.id}")


@bot.on_message(filters.command(["ping", "alive"]) & ~filters.forwarded)
async def ping_handler(_, m: Message):
    t0 = time.time()
    msg = await rich_send(bot, m.chat.id, _hdr(pe("circle","") + " " + sc("pinging"),3))
    ping_ms = (time.time() - t0) * 1000
    up = time.time() - START_TIME
    hrs, rem = divmod(int(up), 3600)
    mins, secs = divmod(rem, 60)
    body = _hdr(pe("check","✅") + " " + sc("alive") + f" • {ping_ms:.0f} ms", 2)
    body += rich_kv_table([
        (pe("diamond","") + " " + sc("ping"), f"<code>{ping_ms:.0f} ms</code>"),
        (pe("hex","") + " " + sc("uptime"), f"<code>{hrs}h {mins}m {secs}s</code>"),
        (pe("orb","") + " " + sc("bot"), "<code>@Videl0Bot • kurigram + pytgcalls</code>"),
    ])
    await rich_edit(msg, body)

# ── /logs — professional log viewer ──────────────────────────────────────────

@bot.on_message(filters.command(["logs", "getlogs", "log"]) & ~filters.forwarded)
@_owner_only
async def logs_handler(_, m: Message):
    paths = [Path("log.txt"), Path("/tmp/videl.log"), Path("logs/bot.log"), Path("bot.log")]
    log_file = next((p for p in paths if p.exists()), None)
    if not log_file:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("no logs found"),3) + rich_note(sc("log file not found — check Docker volume mount")))

    try:
        size_kb = log_file.stat().st_size / 1024
        if size_kb > 300:
            # Send as document
            caption = _hdr(pe("target","") + " " + sc("logs") + f" • {size_kb:.0f} KB", 2) + rich_note(pe("line","") + f" <code>{rich_esc(str(log_file))}</code> • {size_kb:.1f} KB<br>" + pe("small","") + " " + sc("full log attached as document"))
            await bot.send_document(m.chat.id, document=str(log_file), caption=caption, parse_mode=ParseMode.HTML, reply_to_message_id=m.id)
        else:
            content = await asyncio.to_thread(log_file.read_text, encoding="utf-8", errors="ignore")
            content = content[-3000:]
            body = _hdr(pe("pin","📌") + " " + sc("recent logs") + f" • {size_kb:.0f} KB", 2)
            body += rich_pre(content[-2000:], "log")
            await rich_send(bot, m.chat.id, body)
        _log_to_channel(f"📄 /logs requested by {m.from_user.id}")
    except Exception as e:
        LOGGER.error(f"logs fail: {e}", exc_info=True)
        await rich_send(bot, m.chat.id, _hdr(pe("cross","❌") + " " + sc("logs failed"),3) + rich_pre(str(e)))

# ── /shell — secure shell (owner only, timeout, sanitized) ─────────────────

@bot.on_message(filters.command(["shell", "sh", "bash", "exec"]) & ~filters.forwarded)
@_owner_only
async def shell_handler(_, m: Message):
    cmd = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not cmd and m.reply_to_message and m.reply_to_message.text:
        cmd = m.reply_to_message.text.strip()
    if not cmd:
        return await rich_send(bot, m.chat.id, _hdr(pe("hex","") + " " + sc("shell") + " • " + pe("circle","") + " " + sc("owner only"),3) + rich_note("<code>/shell &lt;command&gt;</code><br>" + pe("small","") + " <code>/shell ps aux | head</code><br>" + pe("small","") + " <code>/shell df -h</code><br>" + pe("warn","⚠️") + " " + sc("timeout 15s, logged to channel")))

    # Security: block destructive commands
    dangerous = ["rm -rf /", ":(){:|:&};:", "mkfs", "dd if=", "shutdown", "reboot", "chmod 777 /"]
    if any(d in cmd for d in dangerous):
        _log_to_channel(f"🚨 Blocked dangerous shell by {m.from_user.id}: <code>{cmd[:100]}</code>")
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("blocked dangerous command"),3))

    status = await rich_send(bot, m.chat.id, _hdr(pe("circle","") + " " + sc("executing") + f" • <code>{rich_esc(cmd[:40])}</code>",3) + rich_note(pe("diamond","") + " " + sc("timeout") + ": 15s…"))

    try:
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return await rich_edit(status, _hdr(pe("warn","⚠️") + " " + sc("timeout"),3) + rich_note(sc("command timed out after 15s")))
        out = (stdout.decode(errors="ignore") + stderr.decode(errors="ignore")).strip()
        if not out:
            out = f"Done (exit {proc.returncode}) — no output"
        if len(out) > 3800:
            # Send as file
            bio = io.BytesIO(out.encode())
            bio.name = "shell_output.txt"
            await bot.send_document(m.chat.id, document=bio, caption=_hdr(pe("check","✅") + f" <code>{rich_esc(cmd[:50])}</code> • exit {proc.returncode}",3), parse_mode=ParseMode.HTML, reply_to_message_id=m.id)
            await status.delete()
        else:
            body = _hdr(pe("check","✅") + f" <code>{rich_esc(cmd[:40])}</code> • exit {proc.returncode}",3)
            body += rich_pre(out[:3500], "bash")
            await rich_edit(status, body)
        _log_to_channel(f"💻 /shell by {m.from_user.id}: <code>{rich_esc(cmd[:80])}</code> → exit {proc.returncode}")
    except Exception as e:
        LOGGER.error(f"shell error: {e}", exc_info=True)
        await rich_edit(status, _hdr(pe("cross","❌") + " " + sc("shell failed"),3) + rich_pre(traceback.format_exc()[-3000:], "log"))


# ── /eval — secure python eval with timeout ──────────────────────────────────

@bot.on_message(filters.command(["eval", "py", "python"]) & ~filters.forwarded)
@_owner_only
async def eval_handler(_, m: Message):
    code = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not code and m.reply_to_message:
        code = m.reply_to_message.text or m.reply_to_message.caption or ""
    if not code:
        return await rich_send(bot, m.chat.id, _hdr(pe("hex","") + " " + sc("python eval"),3) + rich_note("<code>/eval &lt;code&gt;</code><br>" + pe("small","") + " <code>/eval await bot.get_me()</code><br>" + pe("small","") + " <code>/eval 2**10</code>"))

    if code.startswith("```"):
        code = "\n".join(code.split("\n")[1:-1]) if "```" in code else code.strip("`")

    old_stdout = sys.stdout
    buf = io.StringIO()
    try:
        sys.stdout = buf
        ctx = {"bot": bot, "m": m, "message": m, "config": config, "db": None, "asyncio": asyncio, "Path": Path, "os": os}
        # Try as expression, fallback to exec
        try:
            res = eval(code, ctx)
            if asyncio.iscoroutine(res):
                res = await asyncio.wait_for(res, timeout=10)
            out = str(res)
        except SyntaxError:
            exec("async def __fn():\n" + textwrap.indent(code, "    "), ctx)
            res = await asyncio.wait_for(ctx["__fn"](), timeout=10)
            out = str(res) if res is not None else ""
        stdout = buf.getvalue()
        text = (stdout + "\n" + out).strip() or " Done — no output"
        if len(text) > 3500:
            bio = io.BytesIO(text.encode())
            bio.name = "eval_output.txt"
            await bot.send_document(m.chat.id, document=bio, caption=_hdr(pe("check","✅") + " " + sc("eval done"),3), parse_mode=ParseMode.HTML, reply_to_message_id=m.id)
        else:
            body = _hdr(pe("check","✅") + " " + sc("eval done"),3)
            body += rich_pre(text[:3500], "python")
            await rich_send(bot, m.chat.id, body, reply_to_message_id=m.id)
        _log_to_channel(f"🐍 /eval by {m.from_user.id}: <code>{rich_esc(code[:80])}</code>")
    except Exception:
        await rich_send(bot, m.chat.id, _hdr(pe("cross","❌") + " " + sc("eval error"),3) + rich_pre(traceback.format_exc()[-3000:], "python"))
    finally:
        sys.stdout = old_stdout


# ── /active — active voice chats & chats ──────────────────────────────────────

@bot.on_message(filters.command(["active", "activevc", "activechats"]) & ~filters.forwarded)
@_owner_only
async def active_handler(_, m: Message):
    from videl.core.queue import QUEUE
    try:
        # Gather active queues (voice chats)
        active = []
        for cid, q in QUEUE.items():
            if q:
                cur = q[0] if q else {}
                active.append((cid, len(q), cur.get("title", "?")[:30]))
        if not active:
            return await rich_send(bot, m.chat.id, _hdr(pe("circle","") + " " + sc("no active chats"),3) + rich_note(sc("no voice chats playing right now")))
        body = _hdr(pe("diamond","") + f" {sc('active chats')} • {len(active)}", 2)
        body += rich_table([sc("chat id"), sc("queue"), sc("now playing")], [(f"<code>{cid}</code>", str(n), rich_esc(t)) for cid, n, t in active[:20]])
        body += rich_note(pe("small","") + f" {len(active)} " + sc("active voice chats") + " " + pe("hex",""))
        await rich_send(bot, m.chat.id, body)
    except Exception as e:
        LOGGER.error(f"active fail: {e}", exc_info=True)
        await rich_send(bot, m.chat.id, rich_pre(str(e)))


# ── /restart — graceful restart (Docker-aware) ───────────────────────────────

@bot.on_message(filters.command(["restart", "reboot"]) & ~filters.forwarded)
@_owner_only
async def restart_handler(_, m: Message):
    msg = await rich_send(bot, m.chat.id, _hdr(pe("fire","🔥") + " " + sc("restarting") + "…",3) + rich_note(pe("diamond","") + " " + sc("bot will restart in 3 seconds") + "<br>" + pe("small","") + " " + sc("Docker will auto-restart if HEALTHCHECK fails")))
    _log_to_channel(f"🔄 /restart by {m.from_user.id} in {m.chat.id}")
    await asyncio.sleep(2)
    try:
        await rich_edit(msg, _hdr(pe("check","✅") + " " + sc("restarting now"),3))
    except Exception:
        pass
    # Docker-aware: exit, let orchestrator restart
    os._exit(0)


# ── /update — git pull + restart ─────────────────────────────────────────────

@bot.on_message(filters.command(["update", "gitpull"]) & ~filters.forwarded)
@_owner_only
async def update_handler(_, m: Message):
    status = await rich_send(bot, m.chat.id, _hdr(pe("circle","") + " " + sc("updating"),3) + rich_note(sc("git pull + pip install — please wait…")))
    try:
        proc = await asyncio.create_subprocess_shell("git pull --ff-only && pip install -q -r requirements.txt", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        out = (stdout.decode() + stderr.decode()).strip()[-2000:] or "No output"
        body = _hdr(pe("check","✅") + " " + sc("updated") + f" • exit {proc.returncode}",2)
        body += rich_pre(out[-1500:], "bash")
        body += rich_note(pe("small","") + " " + sc("restarting to apply…"))
        await rich_edit(status, body)
        await asyncio.sleep(2)
        os._exit(0)
    except Exception as e:
        LOGGER.error(f"update fail: {e}", exc_info=True)
        await rich_edit(status, _hdr(pe("cross","❌") + " " + sc("update failed"),3) + rich_pre(str(e)))


# ── /broadcast_pro — professional broadcast with rich UI ──────────────────────

@bot.on_message(filters.command(["broadcast_pro", "bcast", "announce"]) & ~filters.forwarded)
@_owner_only
async def broadcast_pro_handler(_, m: Message):
    text = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not text and m.reply_to_message:
        text = m.reply_to_message.text or m.reply_to_message.caption or ""
    if not text:
        return await rich_send(bot, m.chat.id, _hdr(sc("broadcast"),3) + rich_note("<code>/broadcast_pro &lt;text&gt;</code> — reply to message to broadcast that<br>" + pe("small","") + " " + sc("sends to all known chats via MongoDB")))
    from videl.utils.db import get_served_chats
    try:
        chats = await asyncio.to_thread(get_served_chats)
    except Exception as e:
        chats = []
        LOGGER.warning(f"broadcast gather chats fail: {e}")

    if not chats:
        return await rich_send(bot, m.chat.id, _hdr(pe("warn","⚠️") + " " + sc("no chats found"),3))
    sent = 0
    failed = 0
    prog = await rich_send(bot, m.chat.id, _hdr(pe("diamond","") + f" {sc('broadcasting')} → {len(chats)} " + sc("chats") + "…",3))
    for cid in chats:
        try:
            await bot.send_message(int(cid), text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.04)
        if sent % 25 == 0:
            try:
                await rich_edit(prog, _hdr(pe("diamond","") + f" {sent}/{len(chats)}…",3))
            except Exception:
                pass
    body = _hdr(pe("check","✅") + " " + sc("broadcast done"),2)
    body += rich_kv_table([(pe("check","✅") + " " + sc("sent"), f"<code>{sent}</code>"), (pe("cross","❌") + " " + sc("failed"), f"<code>{failed}</code>"), (pe("orb","") + " " + sc("total"), f"<code>{len(chats)}</code>")])
    await rich_edit(prog, body)
    _log_to_channel(f"📢 /broadcast_pro by {m.from_user.id}: sent {sent}/{len(chats)} — {text[:80]}")


LOGGER.info(" owner utils — perfect ")
