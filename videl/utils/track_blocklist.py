"""Bounded per-group music title/artist deny-list."""
from __future__ import annotations

MAX_ENTRIES = 50
MAX_TEXT = 100


def normalize(raw) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    output = []
    seen = set()
    for entry in raw[:MAX_ENTRIES]:
        if not isinstance(entry, dict):
            continue
        kind, value = entry.get("kind"), entry.get("value")
        if kind not in {"track", "artist"} or not isinstance(value, str):
            continue
        value = value.strip()[:MAX_TEXT]
        key = (kind, value.casefold())
        if value and key not in seen:
            seen.add(key)
            output.append({"kind": kind, "value": value})
    return output


def add(raw, kind: str, value: str) -> list[dict[str, str]]:
    if kind not in {"track", "artist"} or not isinstance(value, str):
        raise ValueError("Choose a track title or artist name.")
    value = value.strip()
    if not value or len(value) > MAX_TEXT:
        raise ValueError(f"Enter 1–{MAX_TEXT} characters.")
    items = normalize(raw)
    if any(item["kind"] == kind and item["value"].casefold() == value.casefold() for item in items):
        return items
    if len(items) >= MAX_ENTRIES:
        raise ValueError(f"The list is full ({MAX_ENTRIES} entries). Remove one first.")
    items.append({"kind": kind, "value": value})
    return items


def remove(raw, index: int) -> list[dict[str, str]]:
    items = normalize(raw)
    if type(index) is not int or not 1 <= index <= len(items):
        raise ValueError("That list entry no longer exists.")
    del items[index - 1]
    return items


def matches(raw, song: dict) -> dict[str, str] | None:
    items = normalize(raw)
    title = str(song.get("title") or "").casefold()
    artists = song.get("artists", song.get("artist", ""))
    if isinstance(artists, str):
        artists = [artists]
    elif not isinstance(artists, (tuple, list)):
        artists = []
    artist_text = " ".join(str(value) for value in artists).casefold()
    for item in items:
        needle = item["value"].casefold()
        haystack = title if item["kind"] == "track" else f"{artist_text} {title}"
        if needle in haystack:
            return item
    return None
