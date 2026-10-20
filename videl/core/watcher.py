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
    from videl.utils.db import cleanup_old_data
    result = await asyncio.to_thread(cleanup_old_data, DB_CLEANUP_DAYS, apply=True)
    if not result.get("ok"):
        raise RuntimeError("Database retention unavailable")
    return result


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


async def _check_bot():
    if not getattr(bot, "is_connected", False):
        raise RuntimeError("Telegram transport disconnected")


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


async def watchdog():
    last_cleanup = 0
    while True:
        # Isolate each job so a failed DB cannot prevent idle-call maintenance.
        await asyncio.gather(*(_run_check(name, job) for name, job in (
            ("database", _check_database), ("telegram", _check_bot),
            ("captcha", _check_captcha), ("idle_calls", _auto_leave_idle_vcs),
            ("scheduled_posts", _dispatch_scheduled))))
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
