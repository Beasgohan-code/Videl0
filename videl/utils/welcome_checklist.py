"""Validation and safe rendering inputs for short, admin-authored welcome links."""
from __future__ import annotations

from urllib.parse import urlsplit

MAX_LINKS = 4
MAX_LABEL = 32
MAX_URL = 1000


def validate(raw: str) -> list[dict[str, str]]:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Add at least one HTTPS checklist link.")
    rows = []
    for line in raw.splitlines():
        if len(rows) >= MAX_LINKS:
            raise ValueError("A welcome checklist can contain at most four links.")
        label, separator, url = line.partition("|")
        label, url = label.strip(), url.strip()
        try:
            parsed = urlsplit(url)
            _ = parsed.port
        except ValueError:
            parsed = None
        if (not separator or not label or len(label) > MAX_LABEL or not url or len(url) > MAX_URL
                or any(char.isspace() or ord(char) < 32 for char in url)
                or parsed is None or parsed.scheme.casefold() != "https" or not parsed.hostname
                or parsed.username or parsed.password):
            raise ValueError("Each line must be Short label | https://example.com/path; use up to four HTTPS links and labels no longer than 32 characters.")
        rows.append({"label": label, "url": url})
    if not rows:
        raise ValueError("Add at least one HTTPS checklist link.")
    return rows


def safe_stored(value) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    safe = []
    for item in value[:MAX_LINKS]:
        if not isinstance(item, dict):
            continue
        label, url = item.get("label"), item.get("url")
        if not isinstance(label, str) or not isinstance(url, str):
            continue
        try:
            parsed = urlsplit(url)
            _ = parsed.port
        except ValueError:
            continue
        if (not label or len(label) > MAX_LABEL or len(url) > MAX_URL
                or any(char.isspace() or ord(char) < 32 for char in url)
                or parsed.scheme.casefold() != "https" or not parsed.hostname
                or parsed.username or parsed.password):
            continue
        safe.append({"label": label, "url": url})
    return safe
