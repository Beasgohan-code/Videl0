"""Single command menu shared by startup and the Studio's Sync Commands action."""

PUBLIC_COMMANDS = (
    ("start", "Open Videl Studio"),
    ("commands", "Browse or search every supported command"),
    ("copy", "Create a native copy-text button"),
    ("help", "Music and group command guide"),
    ("pollstop", "Admin: close a replied bot poll"),
    ("topicrename", "Admin: rename the current forum topic"),
    ("modernhelp", "New Telegram tools and poll options"),
    ("play", "Play audio in your group voice chat"),
    ("vplay", "Play video in your group voice chat"),
    ("queue", "Show the playback queue"),
    ("setup", "Set up group moderation"),
    ("permissions", "Admin: diagnose missing bot permissions"),
    ("locks", "Review group protection rules"),
    ("poll", "Create a poll with editable options"),
    ("quiz", "Create a quiz; mark correct answers with *"),
    ("react", "Admin: react to a replied message"),
    ("topicnew", "Admin: create a forum topic"),
    ("ping", "Check bot latency and uptime"),
    ("stats", "Show live bot and database totals"),
)
OWNER_COMMANDS = PUBLIC_COMMANDS + (
    ("apiinfo", "Owner: verify Telegram API identity"),
    ("emojiinfo", "Owner: inspect or validate custom emoji IDs"),
    ("watchdog", "Owner: maintenance health and checks"),
    ("dbcleanup", "Owner: preview safe database retention"),
)


def command_menu(owner=False):
    return [
        {"command": name, "description": description}
        for name, description in (OWNER_COMMANDS if owner else PUBLIC_COMMANDS)
    ]
