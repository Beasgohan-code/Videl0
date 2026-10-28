"""Curated production modules; demo, entertainment and AI modules are excluded."""
ALL_MODULES = [
    "group_view", "application",
    # Telegram voice-chat music. These are the real PyTgCalls handlers, not the
    # retired simulated music_pro adapter.
    "play", "cplay", "autoplay", "smartqueue", "playlist", "effects",
    "seek",  "lyrics", "downloader",
    "block",
    # MongoDB-backed group management and distinct moderation features.
    "federation", "blocklist", "approve", "group_manager",
    # General operations, owner diagnostics and live command telemetry.
    # Runs before every other handler group: enforces per-group command switches.
    "command_gate",
    "bot", "callbacks", "misc", "broadcast",
    "analytics", "owner_utils", "activity",
    # Curated, implemented professional utility commands.
    "plugins_loader", "api_tools", "voice_admin",
]
