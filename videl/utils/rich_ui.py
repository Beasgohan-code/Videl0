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

def rich_button(text: str, url: str = None, callback_data: str = None, style: str = None) -> str:
    # normalize Videl colour names to Richgram styles
    if style:
        style = COLOUR_MAP.get(style.lower(), style)
    return _orig_button(text, url=url, callback_data=callback_data, style=style)

# keep old API names for existing videl code which imports from here
__all__ = list(__all__) + ["COLOUR_MAP"]
