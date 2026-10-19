# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Background tasks: DB cleanup, download cleanup, empty-VC auto-leave
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio
import os
import time
from pathlib import Path

from videl import LOGGER, call_py
from videl.core.queue import is_empty, queue_size

# chat_id -> last time we saw activity / non-empty queue
_vc_idle_since: dict[int, float] = {}
DOWNLOAD_DIR = Path("downloads")
CLEANUP_INTERVAL = 6 * 3600       # run heavy cleanup every 6 hours
DOWNLOAD_MAX_AGE = 2 * 3600       # delete download files older than 2h
VC_IDLE_LEAVE = 10 * 60           # leave VC after 10 min idle (empty queue)
DB_CLEANUP_DAYS = 30


async def _cleanup_downloads() -> int:
    """Remove old files from downloads/ folder."""
    if not DOWNLOAD_DIR.exists():
        return 0
    now = time.time()
    removed = 0
    try:
        for p in DOWNLOAD_DIR.iterdir():
            try:
                if p.is_file() and (now - p.stat().st_mtime) > DOWNLOAD_MAX_AGE:
                    p.unlink(missing_ok=True)
                    removed += 1
            except Exception:
                pass
    except Exception as e:
        LOGGER.warning(f"[watcher] download cleanup error: {e}")
    if removed:
        LOGGER.info(f"[watcher] Removed {removed} old download file(s)")
    return removed


async def _cleanup_database() -> dict:
    try:
        from videl.utils.db import cleanup_old_data
        return cleanup_old_data(days=DB_CLEANUP_DAYS)
    except Exception as e:
        LOGGER.warning(f"[watcher] DB cleanup error: {e}")
        return {}


async def _auto_leave_idle_vcs() -> None:
    """Leave voice chats that have been empty for VC_IDLE_LEAVE seconds."""
    try:
        # call_py may expose active calls differently depending on version
        active = []
        try:
            import inspect
            calls = getattr(call_py, "calls", None)
            # pytgcalls may expose calls as async — await or skip
            if inspect.iscoroutine(calls):
                try:
                    calls = await calls
                except Exception:
                    calls = None
            elif callable(calls) and not isinstance(calls, (dict, list)):
                calls = None
            if isinstance(calls, dict):
                active = list(calls.keys())
            elif isinstance(calls, (list, set, tuple)):
                active = list(calls)
        except Exception:
            active = []

        now = time.time()
        for chat_id in list(active):
            try:
                cid = int(chat_id)
            except Exception:
                continue

            if queue_size(cid) > 0 or not is_empty(cid):
                _vc_idle_since.pop(cid, None)
                continue

            since = _vc_idle_since.get(cid)
            if since is None:
                _vc_idle_since[cid] = now
                continue

            if now - since >= VC_IDLE_LEAVE:
                try:
                    await call_py.leave_call(cid)
                    LOGGER.info(f"[watcher] Auto-left idle VC {cid}")
                except Exception as e:
                    LOGGER.debug(f"[watcher] leave_call {cid}: {e}")
                _vc_idle_since.pop(cid, None)
    except Exception as e:
        LOGGER.debug(f"[watcher] auto-leave error: {e}")


async def watchdog() -> None:
    """
    Background loop:
      - every 5 min: auto-leave idle VCs + light download sweep
      - every 6 h: full download + 30-day DB cleanup
    """
    LOGGER.info("[watcher] Background cleanup task started (DB 30d, downloads, idle VC)")
    last_heavy = 0.0

    while True:
        try:
            await _auto_leave_idle_vcs()
            await _cleanup_downloads()

            now = time.time()
            if now - last_heavy >= CLEANUP_INTERVAL:
                stats = await _cleanup_database()
                if stats:
                    LOGGER.info(f"[watcher] Periodic DB cleanup: {stats}")
                last_heavy = now
        except Exception as e:
            LOGGER.warning(f"[watcher] loop error: {e}")

        await asyncio.sleep(300)  # 5 minutes
