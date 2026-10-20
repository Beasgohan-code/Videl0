"""Scheduled protection windows: locks that turn themselves on by the clock.

The owner picks a window and a set of locks. Inside the window the bot turns
those locks on; when the window closes it turns off only the locks it turned
on itself. A lock the owner already had on, or switched on by hand during the
window, is never released by the window ending.

State lives in the same ``automation`` document as the window config, so a
restart cannot lose the list of locks that still need releasing. The watchdog
calls :func:`run_once` every minute; the function is safe to call more often.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from videl.utils import audit as audit_log
from videl.utils.automation import in_protection_window, normalize_protection, normalize_protection_state
from videl.utils.moderation import LOCK_TYPES

LOGGER = logging.getLogger(__name__)

MAX_CHATS = 500
LOCK_KEYS = tuple("lock_forwards" if kind == "forward" else f"lock_{kind}" for kind in LOCK_TYPES)


def lock_label(key: str) -> str:
    return key.removeprefix("lock_").replace("_", " ")


def _summary(keys) -> str:
    names = [lock_label(key) for key in keys]
    if len(names) <= 4:
        return ", ".join(names)
    return f"{', '.join(names[:4])} and {len(names) - 4} more"


def plan(protection_raw, settings, tz_offset: int = 0, now: datetime | None = None) -> tuple[dict, dict]:
    """Pure decision for one group: ``({lock_key: on/off}, new_state)``.

    ``settings`` is the raw stored group document (or the lock subset), so a
    lock value that is not exactly ``True`` is treated as off and the window
    may turn it on. Nothing here writes or calls Telegram.
    """
    protection = normalize_protection(protection_raw)
    state = protection["state"]
    values = settings if isinstance(settings, dict) else {}
    inside = in_protection_window(protection, tz_offset, now)

    if inside:
        wanted = list(protection["locks"])
        changes: dict[str, bool] = {}
        applied = list(state["applied"])
        for key in wanted:
            if values.get(key) is not True:
                changes[key] = True
                if key not in applied:
                    applied.append(key)
        # A lock removed from the window while it is open is released now
        # instead of lingering until the window closes.
        released = [key for key in applied if key not in wanted]
        for key in released:
            applied.remove(key)
            if values.get(key) is True:
                changes[key] = False
        if not changes and state["active"] and applied == state["applied"]:
            return {}, state
        return changes, normalize_protection_state({
            "active": True,
            "applied": applied,
            "since": state["since"] or datetime.now(timezone.utc).isoformat(),
        })

    # Outside the window, or switched off: release exactly what is recorded.
    if not state["active"]:
        return {}, normalize_protection_state({"active": False, "applied": [], "since": None})
    changes = {key: False for key in state["applied"] if values.get(key) is True}
    return changes, normalize_protection_state({"active": False, "applied": [], "since": None})


def run_once(db=None, now: datetime | None = None) -> dict:
    """Apply every stored window. Never raises for one bad group."""
    if db is None:
        from videl.utils.db import get_db

        db = get_db()
    result = {"ok": True, "checked": 0, "active": 0, "applied": 0, "released": 0, "failed": 0}
    if db is None:
        result.update(ok=False, error="MongoDB is not connected")
        return result

    from videl.utils.db import set_chat_setting, set_protection_state

    try:
        chat_ids = []
        for row in db["served_chats"].find({}, {"_id": 1}).limit(MAX_CHATS):
            try:
                chat_ids.append(int(row.get("_id")))
            except (TypeError, ValueError):
                continue
        if not chat_ids:
            return result
        documents = list(db["mgmt_chat_settings"].find({"chat_id": {"$in": chat_ids}}))
    except Exception:
        LOGGER.exception("[protection] window read failed")
        result.update(ok=False, error="MongoDB read failed")
        return result

    for document in documents:
        chat_id = document.get("chat_id")
        automation = document.get("automation") or {}
        if not isinstance(automation, dict):
            continue
        raw = automation.get("protection")
        protection = normalize_protection(raw)
        if not protection["enabled"] and not protection["state"]["active"]:
            continue
        result["checked"] += 1
        try:
            quiet = automation.get("quiet_hours") or {}
            try:
                tz_offset = int(quiet.get("tz_offset", 0))
            except (TypeError, ValueError):
                tz_offset = 0
            changes, state = plan(raw, document, tz_offset, now)
            if changes:
                for key, value in changes.items():
                    set_chat_setting(int(chat_id), key, value)
            if state != protection["state"]:
                set_protection_state(int(chat_id), state)
            if changes:
                turned_on = [key for key, value in changes.items() if value]
                turned_off = [key for key, value in changes.items() if not value]
                if turned_on:
                    result["applied"] += len(turned_on)
                    detail = (f"Window {protection['start']}–{protection['end']} turned on "
                              f"{len(turned_on)} locks: {_summary(turned_on)}.")
                else:
                    detail = f"Window closed; released {_summary(turned_off)}."
                if turned_off:
                    result["released"] += len(turned_off)
                    if turned_on:
                        detail += f" Released {_summary(turned_off)}."
                audit_log.record(db, int(chat_id), "automation", action="protection_window",
                                 detail=detail, source="system")
            if state["active"]:
                result["active"] += 1
        except Exception:
            result["failed"] += 1
            LOGGER.exception("[protection] window failed for chat %s", chat_id)

    return result
