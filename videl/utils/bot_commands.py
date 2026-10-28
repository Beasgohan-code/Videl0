"""Single command menu shared by startup and the Studio's Sync Commands action."""

PUBLIC_COMMANDS = (
    ("start", "Open Videl Studio"),
    ("help", "Help center: music, groups, tools"),
    ("commands", "Search or browse every installed command"),
    ("adminlist", "List group administrators (Rose-style alias)"),
    ("play", "Play audio in your group voice chat"),
    ("vplay", "Play video in your group voice chat"),
    ("queue", "Show the playback queue"),
    ("permissions", "Admin: diagnose missing bot permissions"),
    ("locks", "Review content locks and anti-flood"),
    ("lock", "Admin: block a content type"),
    ("warn", "Admin: warn a member"),
    ("warnings", "Show a member's warning history"),
    ("ban", "Admin: ban a member"),
    ("mute", "Admin: mute a member"),
    ("purge", "Admin: delete a range of messages"),
    ("pin", "Admin: pin a replied message"),
    ("slowmode", "Admin: set group slow mode"),
    ("promote", "Admin: promote a member"),
    ("rules", "Show the group rules"),
    ("notes", "List saved notes"),
    ("filters", "List automatic answers"),
    ("welcome", "Admin: toggle welcome messages"),
    ("poll", "Create a poll"),
    ("quiz", "Create a quiz with one correct answer"),
    ("afk", "Set an away status with auto-replies"),
    ("remind", "Schedule a reminder"),
    ("id", "Read chat and user identifiers"),
    ("whois", "Show a member's profile"),
    ("kang", "Save a replied sticker to your personal pack"),
    ("font", "Style text in bold, italic, script or monospace"),
    ("hug", "Send a friendly hug"),
    ("kiss", "Send a playful, respectful kiss"),
    ("like", "Send an animated appreciation reaction"),
    ("wave", "Send an animated hello"),
    ("highfive", "Share an animated high five"),
    ("dance", "Start an animated dance break"),
    ("stats", "Stored data and uptime"),
    ("ping", "Measure an honest Telegram round trip"),
    ("about", "Policies, stack and credits"),
)
OWNER_COMMANDS = PUBLIC_COMMANDS + (
    ("apiinfo", "Owner: verify Telegram API identity"),
    ("emojiinfo", "Owner: browse packs, copy aliases and validate custom emoji IDs"),
    ("setbotphoto", "Owner: update the bot profile photo; reply to an image or pass a direct HTTPS image URL"),
    ("watchdog", "Owner: maintenance health and checks"),
    ("dbcleanup", "Owner: preview safe database retention"),
)


def command_menu(owner=False):
    return [
        {"command": name, "description": description}
        for name, description in (OWNER_COMMANDS if owner else PUBLIC_COMMANDS)
    ]
