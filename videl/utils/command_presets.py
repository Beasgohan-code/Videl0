"""Group-scoped, explicit command-set presets with previewable plans."""
from __future__ import annotations

PRESETS = {
    "community": {"label": "Community", "description": "Keep group management and utilities; pause music commands.", "disable": {"music"}},
    "music": {"label": "Music-friendly", "description": "Allow the registered group command set, including music.", "disable": set()},
    "moderation": {"label": "Moderation-focused", "description": "Keep moderation and essential help; pause music and nonessential utilities.", "disable": {"music", "tools"}},
}
CORE = {"start", "help", "commands", "id", "ping"}


def plan(entries, current_disabled, preset: str) -> dict:
    if preset not in PRESETS:
        raise ValueError("Choose community, music or moderation.")
    eligible = {entry["name"]: entry for entry in entries
                if not entry.get("owner") and entry.get("context") != "private"}
    current = {str(name) for name in current_disabled}
    target = set(current)
    categories = PRESETS[preset]["disable"]
    for name, entry in eligible.items():
        if name not in CORE and entry.get("category") in categories:
            target.add(name)
        else:
            target.discard(name)
    return {"preset": preset, "disable": sorted(target - current),
            "enable": sorted(current - target), "result": sorted(target)}
