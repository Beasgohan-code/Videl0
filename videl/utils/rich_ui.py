"""
Videl — Rich UI — vendored Richgram (clone & edit)

- Fully cloned from https://github.com/Badmunda05/richgram
- Stored in vendor/richgram for direct editing (no pip indirection)
- Edited for Videl: removed promotional footers, added colour alias mapping,
  fixed Button style fallback for pyrogram (non-kurigram) builds.

Original MIT License preserved in vendor/richgram/LICENSE
"""

from __future__ import annotations
import sys
from pathlib import Path

# Ensure vendor is importable
_VENDOR = Path(__file__).resolve().parents[2] / "vendor"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

from vendor.richgram.richgram.rich_ui import *  # noqa: F401,F403
from vendor.richgram.richgram.rich_ui import __all__  # noqa
from vendor.richgram.richgram import __version__, RICH_AVAILABLE

# Videl colour aliases (allow human names -> Richgram styles)
COLOUR_MAP = {
    "blue": "primary",
    "green": "success",
    "red": "danger",
    "grey": "default",
    "gray": "default",
    "colour": "primary",
    "color": "primary",
}

_orig_button = rich_button  # from vendored


def rich_button(
    text: str, url: str = None, callback_data: str = None, style: str = None
) -> str:
    # normalize Videl colour names to Richgram styles
    if style:
        style = COLOUR_MAP.get(style.lower(), style)
    return _orig_button(text, url=url, callback_data=callback_data, style=style)


# keep old API names for existing videl code which imports from here
__all__ = list(__all__) + ["COLOUR_MAP"]


# One restrained icon per bot-authored heading. Never rewrite user message bodies.
_base_heading = rich_heading


def rich_heading(text: str, level: int = 1) -> str:
    from videl.utils.premium_emojis import pe
    import re

    clean = str(text).strip().strip(" ◍⬪⫶⬩𖦹⦿◎⬢")
    mapping = {
        "✅": "check",
        "❌": "cross",
        "⚠": "warn",
        "🎵": "music",
        "🎶": "music",
        "🎙": "mic",
        "🔒": "lock",
        "🔓": "unlock",
        "🛡": "shield",
        "📊": "stats",
        "ℹ": "info",
        "⚙": "key",
        "👑": "crown",
        "🔍": "search",
        "📌": "pin",
        "➡": "right",
        "⬅": "left",
    }
    key = next(
        (value for glyph, value in mapping.items() if clean.startswith(glyph)), None
    )
    if key:
        clean = re.sub(r"^[^\w<]+\s*", "", clean)
    else:
        lower = clean.lower()
        for words, candidate in [
            (("failed", "error", "denied", "blocked"), "cross"),
            (("warning", "cooldown", "unavailable"), "warn"),
            (("playing", "music", "queue", "track"), "music"),
            (("group", "moderation", "protection"), "shield"),
            (("stat", "analytics", "telemetry"), "stats"),
            (("help", "usage", "info"), "info"),
        ]:
            if any(word in lower for word in words):
                key = candidate
                break
    prefix = pe(key) + " " if key else ""
    return _base_heading(prefix + clean, level=level)
