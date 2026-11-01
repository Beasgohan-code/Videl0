"""Managed maintenance watchdog. Never restarts Telegram or deletes saved content."""
import asyncio
import inspect
import time
from pathlib import Path

from videl import LOGGER, bot, call_py
from videl.core.queue import chat_queues, queue_size

DOWNLOAD_DIR = Path("downloads")
CLEANUP_INTERVAL = 6 * 3600
DOWNLOAD_MAX_AGE = 2 * 3600
VC_IDLE_LEAVE = 10 * 60
DB_CLEANUP_DAYS = 30
_vc_idle_since = {}
_task = None
_state = {"last_tick": None, "checks": {}}
_BOT_RESTART_AFTER_FAILURES = 2
_BOT_RESTART_COOLDOWN = 300
_bot_disconnected_checks = 0
_bot_last_restart = 0.0
_bot_restart_lock = None


def watchdog_status():
    stamp = _state["last_tick"]
    running = _task is not None and not _task.done()
    return {"running": running, "healthy": bool(running and stamp and time.time()-stamp < 180
                       and _state["checks"] and all(value == "ok" for value in _state["checks"].values())),
            "last_tick": stamp, "checks": dict(_state["checks"])}


def _sweep_downloads(protected):
    if not DOWNLOAD_DIR.exists():
        return 0
    now, removed = time.time(), 0
    for path in DOWNLOAD_DIR.iterdir():
        try:
            # Never follow symlinks or delete files used by active/queued songs.
            if path.is_symlink() or not path.is_file() or path.resolve() in protected:
                continue
            if now-path.stat().st_mtime > DOWNLOAD_MAX_AGE:
                path.unlink(missing_ok=True)
                removed += 1
        except OSError:
            LOGGER.warning("[watchdog] Download sweep skipped an unavailable file")
    return removed


async def _cleanup_downloads():
    # Take the queue snapshot on its owning event loop.
    # Defer media deletion while playback/download work is queued. This also
    # protects resolver/effect cache paths that are not stored in song metadata.
    if any(chat_queues.values()):
        return 0
    protected = set()
    for songs in list(chat_queues.values()):
        for song in list(songs):
            for key in ("file", "file_path", "path", "audio_path", "video_path"):
                value = song.get(key)
                if isinstance(value, str) and not value.startswith(("http://", "https://")):
                    protected.add(Path(value).resolve())
    return await asyncio.to_thread(_sweep_downloads, protected)


async def _cleanup_database():
    from videl.utils.db import cleanup_old_data, get_db
    from videl.utils.retention import cleanup_group_history
    result = await asyncio.to_thread(cleanup_old_data, DB_CLEANUP_DAYS, apply=True)
    history = await asyncio.to_thread(cleanup_group_history, get_db(), apply=True)
    if not result.get("ok") or not history.get("ok"):
        raise RuntimeError("Database retention unavailable")
    return {"activity": result, "group_history": history}


async def _auto_leave_idle_vcs():
    calls = getattr(call_py, "calls", None)
    if inspect.isawaitable(calls):
        calls = await calls
    if isinstance(calls, dict):
        active = set(calls)
    elif isinstance(calls, (list, set, tuple)):
        active = set(calls)
    else:
        return
    now = time.monotonic()
    for stale in set(_vc_idle_since)-active:
        _vc_idle_since.pop(stale, None)
    for cid in active:
        if queue_size(cid):
            _vc_idle_since.pop(cid, None)
        elif now-_vc_idle_since.setdefault(cid, now) >= VC_IDLE_LEAVE:
            await call_py.leave_call(cid)
            _vc_idle_since.pop(cid, None)


async def _check_database():
    from videl.utils.db import get_mongo_client, start_mongo

    client = get_mongo_client()
    if client is not None:
        try:
            await asyncio.to_thread(client.admin.command, "ping")
            return
        except Exception:
            LOGGER.warning("[watchdog] Mongo ping failed; reconnecting")
    # A dropped or never-established connection used to stay dead until the
    # process restarted, so every /internal/* route answered 503 and the web
    # app showed a backend error. Reconnect here instead.
    if not await asyncio.to_thread(start_mongo):
        raise RuntimeError("Database reconnect failed")


async def _dispatch_scheduled():
    from videl.utils.scheduled_posts import dispatch_one
    await asyncio.to_thread(dispatch_one)


async def _dispatch_listening_session():
    from videl.utils.db import get_db
    from videl.utils.listening_sessions import claim_due, finish
    session = await asyncio.to_thread(claim_due, get_db())
    if not session:
        return
    chat_id = int(session["chat_id"])
    try:
        from videl.plugins import base
        if not base.set_setting(chat_id, "music_requests_enabled", True):
            raise RuntimeError("Could not open group music requests")
        title = str(session.get("title", "Listening session"))
        due = session.get("due_at")
        when = due.strftime("%Y-%m-%d %H:%M UTC") if hasattr(due, "strftime") else "now"
        await bot.send_message(chat_id, f"🎧 Listening session: {title} · starts {when}. Music requests are now open!")
        await asyncio.to_thread(finish, get_db(), str(session["_id"]), sent=True)
    except asyncio.CancelledError:
        raise
    except Exception:
        await asyncio.to_thread(finish, get_db(), str(session["_id"]), sent=False)
        raise


async def _sweep_arcade():
    """Abandon rooms nobody came back to. Deadlines themselves settle lazily."""
    from videl.games import store
    await asyncio.to_thread(store.sweep)


async def _dispatch_event_reminder():
    from videl.games.community_events import dispatch_reminder
    await asyncio.to_thread(dispatch_reminder)


async def _dispatch_admin_digest():
    from videl.utils.admin_digest import dispatch_one
    from videl.utils.bot_api import call_bot_api
    from videl.utils.db import get_db
    result = await asyncio.to_thread(dispatch_one, get_db(), call_bot_api)
    if not result.get("ok"):
        raise RuntimeError(result.get("reason", "admin digest worker failed"))


async def _sync_chat_admins():
    """Refresh a small slice of the admin cache so group lists open fast."""
    from videl.utils.bot_api import call_bot_api
    from videl.utils.chat_admins import sweep
    from videl.utils.db import get_db
    await asyncio.to_thread(sweep, get_db(), call_bot_api, limit=5)


async def _check_bot():
    """Recover the Telegram client after sustained transport loss.

    Render already restarts the whole process when it exits unexpectedly. For a
    bot-only disconnect, restart the Pyrogram client in place after two failed
    health ticks, with a five-minute cooldown to avoid a restart loop.
    """
    global _bot_disconnected_checks, _bot_last_restart, _bot_restart_lock
    if getattr(bot, "is_connected", False):
        _bot_disconnected_checks = 0
        return

    _bot_disconnected_checks += 1
    if _bot_disconnected_checks < _BOT_RESTART_AFTER_FAILURES:
        raise RuntimeError("Telegram transport disconnected; waiting for a second failed health check")

    now = time.monotonic()
    if _bot_last_restart and now - _bot_last_restart < _BOT_RESTART_COOLDOWN:
        raise RuntimeError("Telegram transport remains disconnected; automatic restart cooldown is active")

    if _bot_restart_lock is None:
        _bot_restart_lock = asyncio.Lock()
    async with _bot_restart_lock:
        if getattr(bot, "is_connected", False):
            _bot_disconnected_checks = 0
            return
        restart = getattr(bot, "restart", None)
        if not callable(restart):
            raise RuntimeError("Telegram client does not expose restart recovery")
        _bot_last_restart = time.monotonic()
        LOGGER.warning("[watchdog] Telegram disconnected after %s checks; restarting the client", _bot_disconnected_checks)
        try:
            await asyncio.wait_for(restart(), timeout=40)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise RuntimeError(f"Telegram client restart failed ({type(error).__name__})") from error
        if not getattr(bot, "is_connected", False):
            raise RuntimeError("Telegram client restart returned but transport is still disconnected")
        _bot_disconnected_checks = 0
        LOGGER.info("[watchdog] Telegram client recovered after automatic restart")


async def _check_captcha():
    from videl.utils.captcha import start_captcha_worker
    start_captcha_worker()  # Idempotent; restarts only a finished worker.


async def _run_check(name, operation):
    previous = _state["checks"].get(name)
    try:
        await asyncio.wait_for(operation(), timeout=45)
        _state["checks"][name] = "ok"
        if previous == "failed":
            LOGGER.info("[watchdog] %s recovered", name)
        return True
    except asyncio.CancelledError:
        raise
    except Exception:
        _state["checks"][name] = "failed"
        if previous != "failed":
            LOGGER.warning("[watchdog] %s failed; next check will retry", name)
        return False


async def _apply_protection_windows():
    from videl.modules.protection_windows import run_once

    outcome = await asyncio.to_thread(run_once)
    if not outcome.get("ok", False):
        raise RuntimeError(outcome.get("error", "protection window store unavailable"))
    if outcome.get("failed"):
        LOGGER.warning("[protection] %s group windows failed this tick", outcome["failed"])


async def watchdog():
    last_cleanup = 0
    while True:
        # Isolate each job so a failed DB cannot prevent idle-call maintenance.
        await asyncio.gather(*(_run_check(name, job) for name, job in (
            ("database", _check_database), ("telegram", _check_bot),
            ("captcha", _check_captcha), ("idle_calls", _auto_leave_idle_vcs),
            ("scheduled_posts", _dispatch_scheduled), ("listening_sessions", _dispatch_listening_session), ("arcade", _sweep_arcade),
            ("event_reminders", _dispatch_event_reminder), ("admin_digests", _dispatch_admin_digest),
            ("chat_admins", _sync_chat_admins), ("protection_windows", _apply_protection_windows))))
        if time.monotonic()-last_cleanup >= CLEANUP_INTERVAL or not last_cleanup:
            await _run_check("downloads", _cleanup_downloads)
            if await _run_check("retention", _cleanup_database):
                last_cleanup = time.monotonic()
        _state["last_tick"] = time.time()
        await asyncio.sleep(60)


def start_watchdog():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(watchdog(), name="videl-maintenance-watchdog")
    return _task


async def stop_watchdog():
    global _task
    if _task is not None:
        _task.cancel()
        await asyncio.gather(_task, return_exceptions=True)
        _task = None
