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


def audio_quality() -> AudioQuality:
    """Return the configured uplink preset; malformed values safely use Studio."""
    return PRESETS.get(str(getattr(config, "VOICE_AUDIO_QUALITY", "high")).casefold(), AudioQuality.HIGH)


def audio_quality_label() -> str:
    """A human-readable label for the now-playing card and diagnostics."""
    key = str(getattr(config, "VOICE_AUDIO_QUALITY", "studio")).casefold()
    return LABELS.get(key, LABELS["high"])
