"""Per-group, explicitly scoped maintenance pauses."""
from __future__ import annotations

FEATURES = ("protection", "onboarding")


def normalize(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    features = raw.get("features") if isinstance(raw.get("features"), (list, tuple, set)) else ()
    return {"enabled": raw.get("enabled") is True,
            "features": sorted({name for name in features if isinstance(name, str) and name in FEATURES})}


def is_paused(db, chat_id: int, feature: str) -> bool:
    if feature not in FEATURES or db is None:
        return False
    try:
        row = db["mgmt_chat_settings"].find_one({"chat_id": int(chat_id)}, {"maintenance": 1}) or {}
        current = normalize(row.get("maintenance"))
        return current["enabled"] and feature in current["features"]
    except Exception:
        # Fail open: maintenance is a pause feature, not an enforcement toggle.
        return False


def save(db, chat_id: int, *, enabled: bool, features) -> dict | None:
    selected = sorted({name for name in features if isinstance(name, str) and name in FEATURES})
    if db is None or type(enabled) is not bool or (enabled and not selected):
        return None
    value = {"enabled": enabled, "features": selected if enabled else []}
    try:
        db["mgmt_chat_settings"].update_one({"chat_id": int(chat_id)},
            {"$set": {"chat_id": int(chat_id), "maintenance": value}}, upsert=True)
        return value
    except Exception:
        return None
