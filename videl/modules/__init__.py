"""Curated production modules; demo, entertainment and AI modules are excluded."""
ALL_MODULES = [
    # Telegram voice-chat music. These are the real PyTgCalls handlers, not the
    # retired simulated music_pro adapter.
    "play", "cplay", "autoplay", "smartqueue", "playlist", "effects",
    "seek", "pause", "resume", "skip", "stop", "lyrics", "downloader",
    "block",
    # MongoDB-backed group management and distinct moderation features.
    "management_core", "federation", "blocklist", "approve", "wizard",
    # General operations, owner diagnostics and live command telemetry.
    "bot", "callbacks", "start", "misc", "ping", "broadcast",
    "utils_extra", "analytics", "logs", "owner_utils",
    # Curated, implemented professional utility commands.
    "plugins_loader", "professional", "api_tools",
]
