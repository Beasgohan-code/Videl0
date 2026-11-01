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
    text: str, url: str = None, callback_data: str = None, style: str = None,
    icon_custom_emoji_id: str = None,
) -> str:
    # Share native semantics with explicit keyboards. Labels are plain text;
    # custom-emoji HTML becomes an optional native icon, never literal markup.
    from videl.utils.bot_ui import button
    if style:
        style = COLOUR_MAP.get(style.lower(), style)
    native = button(text, style=style, icon_custom_emoji_id=icon_custom_emoji_id,
                    **({"callback_data": callback_data} if callback_data else {"url": url} if url else {}))
    return _orig_button(rich_esc(native.text), url=url, callback_data=callback_data,
                        style=native.style.value if native.style else style,
                        icon_custom_emoji_id=native.icon_custom_emoji_id)



# keep old API names for existing videl code which imports from here
__all__ = list(__all__) + ["COLOUR_MAP"]


# One restrained icon per bot-authored heading. Never rewrite user message bodies.
_base_heading = rich_heading


def rich_heading(text: str, level: int = 1) -> str:
    from videl.utils.premium_emojis import FALLBACK, pe
    import re

    # Replace the old cyber ornament prefixes instead of stacking them beside
    # the new semantic premium emoji system.
    clean = re.sub(r"^[\s◍⬪⫶⬩𖦹⦿◎⬢❍✫⌯]+", "", str(text).strip()).strip(" ◍⬪⫶⬩𖦹⦿◎⬢❍✫⌯")
    # A caller may already have selected an exact custom emoji with pe().
    # Preserve it and avoid adding a second, unrelated semantic icon.
    has_custom_emoji_prefix = bool(re.match(r"^<tg-emoji\b", clean, re.I))
    mapping = {
        "✅": "check",
        "❌": "cross",
        "⚠": "rijif_warning",
        "⛔": "ban",
        "🚫": "rijif_forbid",
        "🔇": "boseh_speaker_mute",
        "✨": "spark",
        "👋": "spark",
        "🎉": "fire",
        "🎵": "music",
        "🎶": "music",
        "🎙": "mic",
        "🔒": "lock",
        "🔓": "unlock",
        "🛡": "shield",
        "📊": "stats",
        "ℹ": "info",
        "⚙": "ios_gear",
        "👑": "crown",
        "🔍": "search",
        "🔎": "ios_search",
        "🎥": "boseh_video",
        "📺": "ios_tv",
        "📰": "ios_newspaper",
        "📝": "ios_memo",
        "🗂": "ios_archive",
        "🔁": "ios_repeat",
        "⏩": "ios_arrows",
        "⌨": "ios_keyboard",
        "📎": "ios_paperclip",
        "🔨": "ios_hammer",
        "🚪": "ios_door",
        "🏷": "ios_tag",
        "↩": "ios_reply",
        "📤": "ios_upload",
        "☁": "ios_cloud",
        "🖼": "ios_image",
        "📁": "ios_folder",
        "📄": "ios_file",
        "🗑": "ios_trash",
        "👁": "ios_eye",
        "✈": "ios_plane",
        "🍏": "ios_apple",
        "📌": "pin",
        "➡": "right",
        "⬅": "left",
        "⬇": "down",
    }
    key = None
    if not has_custom_emoji_prefix:
        key = next((value for glyph, value in mapping.items() if clean.startswith(glyph)), None)
        # Any supplied pack emoji used as an authored title badge becomes its
        # matching Premium entity automatically. Longest-first avoids partial
        # matches such as a base emoji consuming its variation-selector form.
        if not key:
            pack_prefixes = sorted(
                ((glyph, name) for name, glyph in FALLBACK.items() if glyph),
                key=lambda item: len(item[0]), reverse=True,
            )
            key = next((name for glyph, name in pack_prefixes if clean.startswith(glyph)), None)
    if has_custom_emoji_prefix:
        pass
    elif key:
        clean = re.sub(r"^[^\w<]+\s*", "", clean)
    else:
        lower = clean.lower()
        for words, candidate in [
            # Music controls get distinct Premium Emoji instead of one generic
            # music badge: each status remains recognizable at a glance.
            (("playback stopped", "stopped"), "ios_close"),
            (("already paused", "playback paused", "paused"), "rijif_pause"),
            (("playback resumed", "already playing", "resumed"), "ios_play"),
            (("upcoming queue cleared", "queue cleared"), "ios_trash"),
            (("shuffle", "shuffled"), "ios_arrows"),
            (("repeat", "loop", "replay", "autoplay"), "ios_repeat"),
            (("skipped", "skip", "next track"), "ios_play"),
            (("playlist", "playlists"), "ios_folder"),
            (("download", "downloading", "downloaded"), "ios_down"),
            (("lyrics",), "ios_memo"),
            (("effect", "speed", "bass", "audio processing"), "ios_controls"),
            (("seek", "seeking", "position"), "ios_arrows"),
            (("channel play", "channel linked", "playing in channel", "queued in channel"), "ios_link"),
            (("failed", "error", "denied", "blocked", "unconfirmed", "not confirmed", "rejected", "banned", "unlinked"), "cross"),
            (("warning", "cooldown", "unavailable", "attention", "invalid", "unsupported", "not supported"), "rijif_warning"),
            (("telegram tools",), "ios_controls"),
            (("verified telegram bot", "telegram bot"), "boseh_person"),
            (("telegram api", "api status", "custom emoji", "emoji lookup"), "ios_symbols"),
            (("ban list", "ban record", "member banned"), "rijif_forbid"),
            (("playing", "music", "queue", "track", "playback", "repeat", "playlist", "lyrics"), "music"),
            (("federation", "federations"), "globe"),
            (("pin", "pinned", "pins"), "pin"),
            (("note", "notes", "filter", "filters"), "ios_memo"),
            (("poll", "quiz", "topic", "vote", "report"), "ios_symbols"),
            (("cleanup", "purge", "deleted", "removed", "remove"), "ios_trash"),
            (("blacklist", "antispam", "captcha", "approval", "approved", "permissions", "access", "security", "administrator", "admin", "group", "moderation", "protection"), "shield"),
            (("owner", "private", "console"), "crown"),
            (("saved", "created", "updated", "restored", "enabled", "started", "cleared", "complete", "applied", "approved", "linked", "pinned", "sent"), "check"),
            (("search", "found", "results", "choose"), "ios_search"),
            (("welcome", "greeting", "goodbye", "thanks", "new group"), "spark"),
            (("settings", "configuration", "setup", "preferences"), "ios_gear"),
            (("sticker", "avatar", "photo", "image", "thumbnail"), "ios_image"),
            (("video", "screen", "display", "stream"), "boseh_video"),
            (("download", "file", "document", "attachment"), "ios_file"),
            (("upload", "share", "export"), "ios_upload"),
            (("invite", "invitation", "link", "url"), "ios_link"),
            (("game", "arcade", "chess", "ludo", "gomoku", "dice"), "boseh_gamepad"),
            (("tools", "toolbox", "utilities"), "ios_controls"),
            (("stat", "analytics", "telemetry"), "stats"),
            (("help", "usage", "info"), "info"),
        ]:
            if any(word in lower for word in words):
                key = candidate
                break
    # Every authored text heading gets a restrained icon; unknown categories use
    # the neutral spark instead of leaving some screens visually unfinished.
    if not key and clean and clean[0].isalpha():
        key = "spark"
    prefix = pe(key) + " " if key else ""
    return _base_heading(prefix + clean, level=level)


_base_table = rich_table
_base_kv_table = rich_kv_table


def rich_table(headers, rows, border: int = 1) -> str:
    """Premium-badge semantic column headers while retaining Richgram layout."""
    from videl.utils.table_ui import decorate_headers
    return _base_table(decorate_headers(headers), rows, border=border)


def rich_kv_table(pairs, headers=None, border: int = 1) -> str:
    """Apply semantic Premium Emoji labels to all key/value tables.

    The underlying Richgram table builder and layout remain unchanged; only
    table labels receive an icon, with readable Unicode fallbacks.
    """
    from videl.utils.table_ui import decorate_pairs
    rows, columns = decorate_pairs(pairs, headers)
    return _base_kv_table(rows, headers=columns, border=border)
