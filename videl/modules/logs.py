"""
Videl — Proper Logs Module — owner-only /logs /sysinfo with rich UI
Uses logger.py (LOGGER_ID) + Rich formatting.
"""
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType
import config
LOGGER_ID = getattr(config, "LOGGER_ID", 0) or getattr(config, "LOG_CHANNEL_ID", 0)
from videl.utils.rich_ui import rich_heading, rich_kv_table, rich_note, rich_code, rich_pre, rich_button, rich_send, rich_edit, rich_details
import psutil
import platform
from datetime import datetime, timezone
import time

START_TS = time.time()

def is_owner(uid: int) -> bool:
    return bool(config.OWNER_ID and uid == config.OWNER_ID)

async def sysinfo_rows():
    try:
        up = int(time.time() - START_TS)
        d, r = divmod(up, 86400); h, r = divmod(r, 3600); m, s = divmod(r, 60)
        uptime = f"{d}d {h}h {m}m {s}s"
        cpu = psutil.cpu_percent(interval=0.2)
        vm = psutil.virtual_memory()
        du = psutil.disk_usage("/")
        return [
            ("uptime", f"<code>{uptime}</code>"),
            ("platform", f"<code>{platform.system()} {platform.release()}</code>"),
            ("python", f"<code>{platform.python_version()}</code>"),
            ("cpu", f"<code>{cpu}% • {psutil.cpu_count()} cores</code>"),
            ("ram", f"<code>{vm.percent}% • {vm.used//1_000_000} / {vm.total//1_000_000} MB</code>"),
            ("disk", f"<code>{du.percent}% • {du.used//1_000_000_000} / {du.total//1_000_000_000} GB</code>"),
            ("procs", f"<code>{len(psutil.pids())}</code>"),
        ]
    except Exception as e:
        return [("error", f"<code>{e}</code>")]

@Client.on_message(filters.command(["logs","log"]) & filters.private)
async def logs_cmd(client: Client, m: Message):
    if not is_owner(m.from_user.id):
        return await rich_send(client, m.chat.id, rich_heading(" access denied ", 3) + rich_note("owner only — you are not the owner."), reply_to=m.id)
    args = (m.text or "").split()
    filt = args[1].lower() if len(args) > 1 else "all"  # all/start/stop/error/other
    # fetch log.txt tail (last 30 lines)
    tail = ""
    try:
        import pathlib
        p = pathlib.Path("log.txt")
        if p.exists():
            lines = p.read_text(errors="ignore").splitlines()[-30:]
            tail = "\n".join(lines)[-3500:]
        else:
            tail = "log.txt not found (Render ephemeral)"
    except Exception as e:
        tail = f"read fail: {e}"
    # filter tail
    if filt != "all":
        # simple filter
        keywords = {
            "start": ["started","startup","Booted","loaded","Flask"],
            "stop": ["stopped","shutdown","stopping","signal","idle exit"],
            "error": ["error","fail","exception","traceback","❌"],
            "other": ["new chat","new user","cmd","pinned","left"],
        }.get(filt, [])
        if keywords:
            fl = []
            for l in tail.splitlines():
                if any(k.lower() in l.lower() for k in keywords):
                    fl.append(l)
            tail = "\n".join(fl[-30:]) or f"no {filt} lines in last 30"
    # mongo errors
    extra = ""
    try:
        from videl.utils.db import _db
        if _db is not None:
            col = _db["error_logs"]
            docs = list(col.find({}).sort("ts", -1).limit(5))
            if docs:
                for d in docs:
                    extra += f"\n• <code>{d.get('where','?')} — {str(d.get('error',''))[:120]}</code> <i>{d.get('time','')}</i>"
    except Exception:
        pass
    body = (
        rich_heading(f" videl logs — {filt} ", 1)
        + rich_kv_table([
            ("logger", f"<code>{LOGGER_ID or 'not set'}</code>"),
            ("filter", f"<code>{filt}</code> — try /logs start | stop | error | other"),
            ("time", f"<code>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</code>"),
            ("uptime", f"<code>{int(time.time()-START_TS)}s</code>"),
            ("storage", "<code>MongoDB + log.txt</code>"),
        ], headers=["key","value"])
        + rich_details("📄 log.txt tail (30 lines)", rich_pre(tail or "empty", "log"), open=(filt != "all"))
        + (rich_details("❌ mongo errors (5)", extra or "<i>no mongo errors</i>", open=False) if extra or filt in ("all","error") else "")
        + rich_note(" live start/stop/error/other → your LOGGER_ID channel • /sysinfo for system • /logs error for errors only")
    )
    try:
        await rich_send(client, m.chat.id, body, reply_to=m.id)
    except Exception as e:
        await m.reply_text(f"logs: {e}\n{tail[:1000]}")

@Client.on_message(filters.command(["sysinfo","sys","stats"]) & filters.private)
async def sysinfo_cmd(client: Client, m: Message):
    if not is_owner(m.from_user.id):
        return await rich_send(client, m.chat.id, rich_heading(" access denied ", 3) + rich_note("owner only."), reply_to=m.id)
    rows = await sysinfo_rows()
    body = (
        rich_heading(" system info ", 1)
        + rich_kv_table(rows, headers=["metric","value"])
        + rich_note(f" bot started <code>{datetime.fromtimestamp(START_TS, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</code>")
        + rich_details("more", f"LOGGER_ID <code>{LOGGER_ID}</code> • OWNER_ID <code>{config.OWNER_ID}</code>", open=False)
    )
    await rich_send(client, m.chat.id, body, reply_to=m.id)

@Client.on_message(filters.command(["uptime","up"]) & filters.private)
async def uptime_cmd(client: Client, m: Message):
    rows = await sysinfo_rows()
    up = next((v for k,v in rows if k=="uptime"), "<code>?</code>")
    await rich_send(client, m.chat.id, rich_heading(" uptime ", 2) + rich_kv_table([("uptime", up)]), reply_to=m.id)

# ── Auto loggers — start/stop handled in __main__, here: other/new_chat/error/commands ──
# Log ALL commands to LOGGER_ID (group -1, doesn't block others)
@Client.on_message(filters.regex(r"^/\w+") & ~filters.me, group=-1)
async def command_logger(client: Client, m: Message):
    try:
        from videl.utils.logger import log_command
        txt = (m.text or m.caption or "").strip()
        if not txt.startswith("/"): return
        cmd = txt.split()[0].lstrip("/").split("@")[0].lower()
        # skip noisy internal
        if cmd in ("logs","log","sysinfo","sys","stats","uptime","up"): return
        await log_command(client, m, cmd)
    except Exception:
        pass

# Log all new chats (bot added) + new users
@Client.on_message(filters.new_chat_members)
async def new_chat_logger(client: Client, m: Message):
    try:
        from videl.utils.logger import log_new_chat, log_new_user
        me = await client.get_me()
        if any(u.id == me.id for u in (m.new_chat_members or [])):
            await log_new_chat(client, m.chat)
        else:
            for u in (m.new_chat_members or []):
                await log_new_user(client, u)
    except Exception:
        pass

@Client.on_message(filters.left_chat_member)
async def left_chat_logger(client: Client, m: Message):
    try:
        from videl.utils.logger import log_left_chat, log_event
        left = m.left_chat_member
        me = await client.get_me()
        if left and left.id == me.id:
            await log_left_chat(client, m.chat)
        elif left:
            await log_event(client, " member left ", [("user", f"{left.first_name} (<code>{left.id}</code>)"), ("chat", f"<code>{m.chat.id}</code> — {getattr(m.chat,'title','')}")])
    except Exception:
        pass

# Log service messages (pin, etc) as "other"
@Client.on_message(filters.pinned_message)
async def pin_logger(client: Client, m: Message):
    try:
        from videl.utils.logger import log_event
        await log_event(client, "📌 pinned", [("chat", f"<code>{m.chat.id}</code>"), ("by", f"<code>{m.from_user.id if m.from_user else '?'}</code>")], note=f"<code>{(m.text or '')[:80]}</code>")
    except: pass
