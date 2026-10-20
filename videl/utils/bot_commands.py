"""Single command menu shared by startup and the Studio's Sync Commands action."""

PUBLIC_COMMANDS = (
    ("start", "Open Videl Studio"),
    ("help", "Music and group command guide"),
    ("modernhelp", "New Telegram tools and poll options"),
    ("play", "Play audio in your group voice chat"),
    ("vplay", "Play video in your group voice chat"),
    ("queue", "Show the playback queue"),
    ("setup", "Set up group moderation"),
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
    ("logs", "Owner: inspect bot runtime logs"),
)


def command_menu(owner=False):
    return [
        {"command": name, "description": description}
        for name, description in (OWNER_COMMANDS if owner else PUBLIC_COMMANDS)
    ]
