#  Videl © 2026 | Beasgohan-code
"""Everyday tools: identifiers, profiles, latency and source credits."""
from __future__ import annotations

import asyncio
import os
import time
from datetime import timedelta
from pathlib import Path

import psutil
from pyrogram.types import InlineKeyboardMarkup

import config
from videl import bot_start_time
from videl.app.router import Command, CommandError, Screen
from videl.plugins import base
from videl.plugins.base import body, escape, heading, table, target_link
from videl.utils.bot_ui import button

REPOSITORY = "https://github.com/Beasgohan-code/Videl0"
_PING_PROCESS = psutil.Process()


def _bytes(value: int) -> str:
    amount = max(0, int(value))
    if amount >= 1024**3:
        return f"{amount / 1024**3:.2f} GiB"
    return f"{amount / 1024**2:.0f} MiB"


def _meter(value: float) -> str:
    percent = max(0.0, min(100.0, float(value)))
    filled = round(percent / 10)
    return f"{'■' * filled}{'□' * (10 - filled)} {percent:.0f}%"


def _cgroup_memory() -> tuple[int, int] | None:
    """Return the container memory use/limit when a finite cgroup limit exists."""
    candidates = (
        ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory.max"),
        ("/sys/fs/cgroup/memory/memory.usage_in_bytes", "/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    )
    host_total = int(psutil.virtual_memory().total)
    for usage_path, limit_path in candidates:
        try:
            usage_text = Path(usage_path).read_text(encoding="ascii").strip()
            limit_text = Path(limit_path).read_text(encoding="ascii").strip()
            if limit_text == "max":
                continue
            usage, limit = int(usage_text), int(limit_text)
            # cgroup v1 reports an effectively unlimited sentinel on some hosts.
            if usage >= 0 and limit > 0 and limit <= host_total * 10:
                return usage, limit
        except (OSError, ValueError):
            continue
    return None


def _cpu_limit() -> float | None:
    """Return cgroup-v2 CPU quota in cores, if the container has one."""
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text(encoding="ascii").split()[:2]
        if quota == "max":
            return None
        quota_us, period_us = int(quota), int(period)
        return quota_us / period_us if quota_us > 0 and period_us > 0 else None
    except (OSError, ValueError, ZeroDivisionError):
        return None


def _resource_snapshot() -> dict:
    """Small, bounded process/host snapshot; never returns names or paths."""
    process = _PING_PROCESS
    logical_cpus = max(1, psutil.cpu_count(logical=True) or 1)
    cpu = psutil.cpu_percent(interval=0.15)
    process_cpu = process.cpu_percent(interval=0.15) / logical_cpus
    memory = psutil.virtual_memory()
    cgroup = _cgroup_memory()
    if cgroup:
        memory_used, memory_total = cgroup
        memory_percent = memory_used * 100 / memory_total
        memory_label = "Container RAM"
    else:
        memory_used, memory_total = int(memory.used), int(memory.total)
        memory_percent = float(memory.percent)
        memory_label = "System RAM"
    try:
        disk = psutil.disk_usage(os.path.abspath(os.sep))
        disk_row = ("Disk", f"{_meter(disk.percent)} · {_bytes(disk.free)} free")
    except (OSError, PermissionError):
        disk_row = ("Disk", "Unavailable")
    try:
        load = os.getloadavg()
        load_text = " · ".join(f"{value:.2f}" for value in load)
    except (AttributeError, OSError):
        load_text = "Unavailable"
    try:
        threads = process.num_threads()
    except (psutil.Error, OSError):
        threads = None
    try:
        process_memory = process.memory_info()
        rss, vms = int(process_memory.rss), int(process_memory.vms)
    except (psutil.Error, OSError):
        rss = vms = 0
    try:
        file_descriptors = process.num_fds()
    except (AttributeError, psutil.Error, OSError):
        file_descriptors = None
    return {
        "cpu": float(cpu),
        "process_cpu": float(process_cpu),
        "logical_cpus": logical_cpus,
        "cpu_limit": _cpu_limit(),
        "load": load_text,
        "memory_label": memory_label,
        "memory_used": memory_used,
        "memory_total": memory_total,
        "memory_percent": memory_percent,
        "rss": rss,
        "vms": vms,
        "disk": disk_row[1],
        "threads": threads,
        "file_descriptors": file_descriptors,
    }


async def _database_probe() -> tuple[str, int | None]:
    from videl.utils.db import get_mongo_client

    client = get_mongo_client()
    if client is None:
        return "Offline", None
    started = time.perf_counter()
    try:
        await asyncio.wait_for(asyncio.to_thread(client.admin.command, "ping"), timeout=3)
        return "Connected", round((time.perf_counter() - started) * 1000)
    except Exception:
        return "Unreachable", None


async def identifiers(ctx) -> Screen:
    message = ctx.message
    user = getattr(message, "from_user", None)
    rows = [
        ("Chat ID", f"<code>{message.chat.id}</code>"),
        ("Message ID", f"<code>{message.id}</code>"),
        ("Your user ID", f"<code>{user.id}</code>" if user else "anonymous sender"),
    ]
    argument = ctx.command.arguments.strip()
    if argument:
        if len(argument.split()) != 1:
            return Screen(heading("Identifiers", 3) + body("Use <code>/id @username</code>, <code>/id 12345</code> or reply to a message."))
        try:
            target = await ctx.client.get_users(int(argument) if argument.isdecimal() else argument)
        except Exception:
            raise CommandError("Telegram could not resolve that user.") from None
        rows.extend([("Resolved user", target_link(target)), ("Resolved ID", f"<code>{target.id}</code>")])
    reply = getattr(message, "reply_to_message", None)
    if reply is not None:
        rows.append(("Replied message", f"<code>{reply.id}</code>"))
        author = getattr(reply, "from_user", None) or getattr(reply, "sender_chat", None)
        if author is not None:
            rows.append(("Replied author", f"<code>{author.id}</code>"))
    return Screen(heading("Identifiers", 3) + table(rows))


async def whois(ctx) -> Screen:
    user, _ = await base.resolve_target(ctx.client, ctx.message, ctx.command.arguments.split())
    if user is None:
        user = getattr(ctx.message, "from_user", None)
    if user is None:
        raise CommandError("Reply to a member or pass @username.")
    rows = [
        ("Name", escape(" ".join(filter(None, [getattr(user, "first_name", None), getattr(user, "last_name", None)])))),
        ("ID", f"<code>{user.id}</code>"),
        ("Username", "@" + escape(user.username) if getattr(user, "username", None) else "—"),
        ("Mention", target_link(user)),
    ]
    if getattr(user, "is_bot", False):
        rows.append(("Account", "bot"))
    if base.is_group(ctx.message):
        try:
            member = await ctx.client.get_chat_member(ctx.message.chat.id, user.id)
            rows.append(("Membership", escape(str(getattr(member.status, "value", member.status)))))
        except Exception:
            rows.append(("Membership", "not a member"))
    return Screen(heading("Member profile", 3) + table(rows))


async def ping(ctx) -> Screen:
    """Measured Telegram round trip plus safe, low-cost live runtime diagnostics."""
    telegram_ms: int | None = None
    started = time.perf_counter()
    try:
        await asyncio.wait_for(ctx.client.get_me(), timeout=8)
        telegram_ms = round((time.perf_counter() - started) * 1000)
    except Exception:
        pass

    try:
        metrics = await asyncio.to_thread(_resource_snapshot)
    except Exception:
        metrics = {}
    try:
        database, database_ms = await _database_probe()
    except Exception:
        database, database_ms = "Unknown", None

    try:
        from videl.core.watcher import watchdog_status
        watchdog = watchdog_status()
        watchdog_text = "Healthy" if watchdog.get("healthy") else "Starting / degraded"
    except Exception:
        watchdog_text = "Unknown"
    try:
        from videl.utils.assistant import assistant_status
        assistant = assistant_status()
        voice_text = "Ready" if assistant.get("ready") else "Not configured" if not assistant.get("configured") else "Offline"
    except Exception:
        voice_text = "Unknown"
    try:
        from videl import build_revision, bot, call_py
        bot_text = "Online" if getattr(bot, "is_connected", False) else "Disconnected"
        if call_py is None:
            voice_text = "Unavailable (voice engine missing)"
        revision = str(build_revision or "dev")[:12]
    except Exception:
        bot_text, revision = "Unknown", "unknown"
    try:
        from videl.core.queue import chat_queues
        active_queues = sum(bool(queue) for queue in chat_queues.values())
        queued_tracks = sum(len(queue) for queue in chat_queues.values())
    except Exception:
        active_queues = queued_tracks = 0

    uptime = str(timedelta(seconds=max(0, int(time.time() - bot_start_time))))
    rows: list[tuple[str, object]] = [
        ("Telegram API", f"{telegram_ms} ms" if telegram_ms is not None else "Unreachable"),
        ("Bot", bot_text),
        ("Uptime", uptime),
    ]
    if metrics:
        cpu_limit = metrics.get("cpu_limit")
        cpu_text = f"{_meter(metrics['cpu'])} · process {_meter(metrics['process_cpu'])}"
        if cpu_limit:
            cpu_text += f" · limit {cpu_limit:.2f} cores"
        rows.extend([
            ("CPU", cpu_text),
            (metrics["memory_label"], f"{_meter(metrics['memory_percent'])} · {_bytes(metrics['memory_used'])}/{_bytes(metrics['memory_total'])}"),
            ("Process memory", f"RSS {_bytes(metrics['rss'])} · virtual {_bytes(metrics['vms'])}"),
            ("Load avg (1/5/15m)", metrics["load"]),
            ("Disk", metrics["disk"]),
        ])
        if metrics.get("threads") is not None:
            rows.append(("Process threads", str(metrics["threads"])))
        if metrics.get("file_descriptors") is not None:
            rows.append(("Open file descriptors", str(metrics["file_descriptors"])))
    rows.extend([
        ("MongoDB", f"{database} · {database_ms} ms" if database_ms is not None else database),
        ("Voice assistant", voice_text),
        ("Maintenance", watchdog_text),
        ("Music queue", f"{active_queues} active · {queued_tracks} tracks"),
        ("Build", f"<code>{escape(revision)}</code>"),
    ])
    return Screen(
        heading("Live system health", 3)
        + table(rows)
        + body("Resource readings are best-effort snapshots. Telegram API latency is an acknowledged request; this does not measure voice quality."),
    )


async def source(ctx) -> Screen:
    return Screen(
        heading("Source and credits", 3)
        + body("Videl by Beasgohan-code. Rich UI uses the MIT-licensed Badmunda05 Richgram fork. "
               "Eldian music components keep their original attribution.")
        + table([("Repository", "github.com/Beasgohan-code/Videl0"), ("Bot", "@" + escape(getattr(config, "BOT_USERNAME", "videlapp")))]),
        InlineKeyboardMarkup([[button("Open repository", url=REPOSITORY, style="primary")]]),
    )


COMMANDS = (
    Command("id", identifiers, "Read chat, message and user identifiers", category="tools", block_policy="user"),
    Command("whois", whois, "Show a member's profile and membership", category="tools"),
    Command("ping", ping, "Telegram round-trip and live system diagnostics", category="tools"),
    Command("repo", source, "Source code and third-party credits", category="tools", block_policy="user"),
)
