"""Semantic Premium Emoji labels for every Richgram key/value table."""
from __future__ import annotations

import html
import re

from videl.utils.premium_emojis import FALLBACK, pe

_SUPPLIED_PREFIXES = tuple(sorted(
    ((glyph, key) for key, glyph in FALLBACK.items() if glyph),
    key=lambda pair: len(pair[0]), reverse=True,
))

_RULES = (
    ({"title", "song", "track", "playing", "music"}, "music2"),
    ({"query", "search", "result", "results"}, "ios_search"),
    ({"emoji", "id", "identifier"}, "ios_symbols"),
    ({"duration", "time", "position", "elapsed", "remaining"}, "boseh_clock"),
    ({"queue", "added", "count", "votes", "needed", "songs", "size", "members"}, "stats"),
    ({"playlist", "playlists"}, "ios_folder"),
    ({"url", "link", "channel"}, "ios_link"),
    ({"speed", "bass", "effect", "effects", "volume"}, "ios_controls"),
    ({"loop", "repeat", "shuffle", "mode", "autoplay"}, "ios_repeat"),
    ({"pause", "paused"}, "rijif_pause"),
    ({"resume", "next", "upcoming"}, "ios_play"),
    ({"user", "username", "requester", "member", "owner"}, "boseh_person"),
    ({"admin", "admins", "permission", "permissions", "right", "rights", "role"}, "shield"),
    ({"status", "type", "scope", "format"}, "ios_symbols"),
    ({"file", "document"}, "ios_file"),
    ({"name"}, "ios_tag"),
    ({"usage", "command", "example"}, "ios_keyboard"),
    ({"error", "reason", "warning"}, "rijif_warning"),
    ({"enabled", "active", "connected"}, "ios_check"),
)


def _badge(label: str) -> str:
    """Badge a table label once, retaining supplied Premium Emoji as-is."""
    text = str(label or "")
    if not text.strip() or re.match(r"^\s*<tg-emoji\b", text, re.I):
        return text

    # Upgrade a supplied Unicode badge to its Premium form instead of stacking
    # a second icon beside it. Longest-first handles variation-selector forms.
    for glyph, key in _SUPPLIED_PREFIXES:
        if text.lstrip().startswith(glyph):
            leading = len(text) - len(text.lstrip())
            remainder = text[leading + len(glyph):].lstrip()
            return f"{pe(key)} {remainder}".rstrip()

    plain = html.unescape(re.sub(r"<[^>]*>", " ", text)).lower()
    words = set(re.findall(r"[a-z0-9]+", plain))
    key = next((icon for tokens, icon in _RULES if words & tokens), "info")
    return f"{pe(key)} {text}"


def decorate_pairs(pairs, headers=None):
    """Return decorated immutable-compatible pairs and optional column labels."""
    rows = [(_badge(key), value) for key, value in (pairs or ())]
    cols = decorate_headers(headers)
    return rows, cols


def decorate_headers(headers):
    return [_badge(header) for header in headers] if headers else headers
