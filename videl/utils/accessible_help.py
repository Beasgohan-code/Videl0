"""Plain, linear command-help rendering for screen readers and low-bandwidth clients."""
from __future__ import annotations

from html import escape

EXAMPLES = {
    "play": "/play song name",
    "playnext": "/playnext song name",
    "warn": "/warn repeated spam (reply to a member)",
    "lock": "/lock links",
    "setwelcome": "/setwelcome Welcome {name} to {title}!",
    "setchecklist": "/setchecklist Start here | https://example.com/start",
    "remind": "/remind 10m take a break",
    "preferences": "/preferences notifications on",
    "mydata": "/mydata (in a private chat)",
    "help": "/help plain",
}


def render(entries, *, title="Accessible command help", limit=18):
    """Return simple HTML with one spoken-friendly command per line."""
    items = list(entries)
    rows = items[:max(1, min(int(limit), 20))]
    lines = [f"<b>{escape(title)}</b>"]
    for entry in rows:
        name = str(entry.get("name", "")).strip().lstrip("/")
        summary = str(entry.get("summary", "")).strip()
        if not name:
            continue
        lines.append(f"/{escape(name)} — {escape(summary or 'Command details not available.')}")
        example = EXAMPLES.get(name)
        if example:
            lines.append(f"Example: <code>{escape(example)}</code>")
    if not rows:
        lines.append("No matching commands. Try /help plain or /commands plain preferences.")
    if len(items) > len(rows):
        lines.append(f"Showing {len(rows)} commands. Narrow the list with /commands plain search words.")
    return "\n".join(lines)
