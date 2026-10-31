"""Validated, bounded named snapshots for group queue-session settings."""
from __future__ import annotations

MAX_PRESETS = 10
MAX_NAME = 32


def normalize(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    result, seen = [], set()
    for item in raw[:MAX_PRESETS]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        name = name.strip()[:MAX_NAME]
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        loop = item.get("loop")
        result.append({"name": name,
                       "loop": loop if loop in {"off", "one", "all"} else "off",
                       "shuffle": item.get("shuffle") is True,
                       "requests": item.get("requests") is not False,
                       "approval": item.get("approval") is True})
    return result


def add(raw, name: str, values: dict) -> list[dict]:
    if not isinstance(name, str):
        raise ValueError("Enter a preset name.")
    name = name.strip()
    if not name or len(name) > MAX_NAME:
        raise ValueError(f"Preset names must be 1–{MAX_NAME} characters.")
    items = normalize(raw)
    if any(item["name"].casefold() == name.casefold() for item in items):
        raise ValueError("That preset name already exists.")
    if len(items) >= MAX_PRESETS:
        raise ValueError(f"This group already has {MAX_PRESETS} presets. Delete one first.")
    snapshot = normalize([{**values, "name": name}])
    if not snapshot:
        raise ValueError("Preset settings are invalid.")
    return items + snapshot


def remove(raw, index: int) -> list[dict]:
    items = normalize(raw)
    if type(index) is not int or not 1 <= index <= len(items):
        raise ValueError("That preset no longer exists.")
    del items[index - 1]
    return items


def get(raw, index: int) -> dict | None:
    items = normalize(raw)
    if type(index) is not int or not 1 <= index <= len(items):
        return None
    return items[index - 1]
