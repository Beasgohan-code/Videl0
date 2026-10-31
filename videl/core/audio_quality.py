"""Quality presets shared by every Telegram voice-chat music stream."""
from __future__ import annotations

import config
from pytgcalls.types import AudioQuality

PRESETS = {
    "studio": AudioQuality.STUDIO,
    "high": AudioQuality.HIGH,
    "medium": AudioQuality.MEDIUM,
    "low": AudioQuality.LOW,
}
LABELS = {
    "studio": "Studio · 96 kbps stereo",
    "high": "High · 48 kbps stereo",
    "medium": "Medium · 36 kbps mono",
    "low": "Low · 24 kbps mono",
}
_SETTING_KEY = "voice_audio_quality"
_runtime_quality: str | None = None


def current_quality() -> str:
    """Return the persisted runtime override or the environment-configured preset."""
    configured = _runtime_quality or str(getattr(config, "VOICE_AUDIO_QUALITY", "high")).casefold()
    return configured if configured in PRESETS else "high"


def set_runtime_quality(value: str) -> bool:
    """Set an in-process preset after validating it; persistence is handled by the caller."""
    global _runtime_quality
    normalized = str(value or "").strip().casefold()
    if normalized not in PRESETS:
        return False
    _runtime_quality = normalized
    return True


def clear_runtime_quality() -> None:
    """Return to the environment preset; primarily useful for isolated tests."""
    global _runtime_quality
    _runtime_quality = None


def load_saved_quality() -> str:
    """Load the owner's saved preset once during startup, falling back to env config."""
    try:
        from videl.utils.db import get_bot_setting
        saved = get_bot_setting(_SETTING_KEY)
        if saved in PRESETS:
            set_runtime_quality(saved)
    except Exception:
        # An unavailable database must not prevent voice playback from starting.
        pass
    return current_quality()


def audio_quality() -> AudioQuality:
    """Return the configured uplink preset; malformed values safely use High."""
    return PRESETS[current_quality()]


def audio_quality_label() -> str:
    """A human-readable label for the now-playing card and diagnostics."""
    return LABELS[current_quality()]
