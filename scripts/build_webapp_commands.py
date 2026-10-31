"""Build the webapp command guide from the registered bot routes.

The studio has a public Guide panel that mirrors what the bot actually
registers. Generating the data file (instead of hand-writing it in
TypeScript) keeps the website honest: adding or renaming a command in
``videl/utils/command_catalog.py`` and re-running this script updates the guide.

Usage::

    python scripts/build_webapp_commands.py

The output is ``webapp/src/lib/commands.ts``. ``tests/test_plugins.py``
checks the same source of truth for the bot side, so the two cannot drift
silently — run this script whenever ``docs/COMMAND_REFERENCE.md`` changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TARGET = ROOT / "webapp" / "src" / "lib" / "commands.ts"

# Short, accurate usage hints for commands that take arguments. Commands not
# listed here simply show ``/<name>`` in the guide.
USAGE = {
    "start": "/start · /start music",
    "tagall": "/tagall [message] · /tagall stop (group admin; paced at 5 seconds per member)",
    "help": "/help · /help music",
    "commands": "/commands [query]",
    "whois": "/whois (reply or @user)",
    "kang": "/kang (reply to a sticker)",
    "warn": "/warn [reason] (reply)",
    "dwarn": "/dwarn [reason] (reply)",
    "tban": "/tban <duration> [reason]",
    "tmute": "/tmute <duration> [reason]",
    "mute": "/mute [duration]",
    "ban": "/ban [reason]",
    "kick": "/kick [reason]",
    "purge": "/purge (reply to a message)",
    "cleanup": "/cleanup <count>",
    "slowmode": "/slowmode <seconds|off>",
    "poll": "/poll question | option | option",
    "appeal": "/appeal <group ID> <reason> (private chat; currently banned or muted members)",
    "appeals": "/appeals (connected group admin)",
    "appealresolve": "/appealresolve <appeal ID> accept|deny (connected group admin)",
    "quiz": "/quiz question | answer | option",
    "save": "/save <name> <content>",
    "get": "/get <name>",
    "delnote": "/delnote <name>",
    "filter": "/filter <keyword> <reply>",
    "stopfilter": "/stopfilter <keyword>",
    "setwelcome": "/setwelcome <text>",
    "setgoodbye": "/setgoodbye <text>",
    "setrules": "/setrules <text>",
    "setwarnlimit": "/setwarnlimit <count>",
    "setreason": "/setreason <action> <template>",
    "reason": "/reason (group admin)",
    "commandpreset": "/commandpreset [community|music|moderation] (group admin)",
    "reviewer": "/reviewer [add|remove USER_ID] (group admin)",
    "modqueue": "/modqueue (group admin or read-only reviewer)",
    "adminsummary": "/adminsummary HH:MM|status|off (UTC, group admin)",
    "maintenance": "/maintenance status|on protection,onboarding|off (group admin)",
    "forgetmember": "/forgetmember USER_ID confirm (group admin)",
    "mydata": "/mydata (private chat)",
    "feedback": "/feedback your suggestion (private chat)",
    "feedbacklist": "/feedbacklist (owner, private chat)",
    "preferences": "/preferences notifications on|off · /preferences quiet 22:00-07:00 UTC+05:30",
    "setchecklist": "/setchecklist Label | https://example.com/start (group admin; up to four HTTPS links)",
    "retention": "/retention status|preview|notes|reports|requests|appeals|escalations 30|90|180|365|off (group admin)",
    "raidmode": "/raidmode on [window] [joins] [messages] [minutes] | off",
    "handoff": "/handoff [note text] (group admin)",
    "rulefeedback": "/rulefeedback <rule> <confirmed|false_positive>",
    "lock": "/lock <type>",
    "unlock": "/unlock <type>",
    "afk": "/afk [reason]",
    "remind": "/remind 10m <text>",
    "invite": "/invite [title]",
    "playnext": "/playnext <song name or link>",
    "remove": "/remove <upcoming position> (group admin)",
    "move": "/move <from position> <to position> (group admin)",
    "jump": "/jump <upcoming position> (group admin)",
    "clearqueue": "/clearqueue (group admin; preserves current playback)",
    "addsudo": "/addsudo <@user|user_id> [duration] (owner, private chat)",
    "sudolist": "/sudolist (owner, private chat) — shows grant expiry",
    "setbotphoto": "/setbotphoto (owner, private chat) — use the bundled image, a replied photo, or a direct HTTPS image URL",
    "setbotname": "/setbotname <name> (owner, private chat; maximum 64 characters)",
    "setbotdescription": "/setbotdescription <text> (owner, private chat; maximum 512 characters)",
    "setbotshortdescription": "/setbotshortdescription <text> (owner, private chat; maximum 120 characters)",
    "voicequality": "/voicequality [studio|high|medium|low] (owner or bot sudo, private chat; global, saved preset)",
    "voicehealth": "/voicehealth (owner or bot sudo, private chat)",
    "restart": "/restart (owner, private chat; disconnects active voice chats)",
    "delsudo": "/delsudo <@user|user_id> (owner, private chat)",
    "rmsudo": "/rmsudo <@user|user_id> (owner, private chat)",
}

# The legacy modules document themselves with terse docstrings ("Addbl").
# The website deserves readable copy, so those entries are retitled here while
# the category, context and owner flag still come from the registered source.
SUMMARY_OVERRIDES = {
    "active": "Show whether the bot is online",
    "adminlist": "List group administrators (Rose-compatible alias for /admins)",
    "addsudo": "Grant limited bot-blocklist operator access to a trusted user",
    "delsudo": "Revoke a bot sudo operator",
    "rmsudo": "Revoke a bot sudo operator",
    "sudolist": "List bot sudo operators and remove access inline",
    "sudohelp": "Show the limited bot sudo command scope",
    "tagall": "Mention every accessible human member one-by-one at a 5-second pace; /tagall stop cancels (admin only)",
    "addblacklist": "Add a user to the anti-spam blocklist",
    "addblsticker": "Block a sticker pack from being sent",
    "apiinfo": "Show Telegram API and library versions",
    "setbotname": "Change the bot display name",
    "setbotdescription": "Change the bot About description",
    "setbotshortdescription": "Change the bot short description",
    "voicequality": "Change global voice-chat audio quality",
    "voicehealth": "Check assistant, PyTgCalls, FFmpeg and downloader readiness",
    "restart": "Restart the bot process (owner only)",
    "approval": "Show the invite-approval queue",
    "approve": "Approve a pending join request",
    "approved": "List members allowed through approval",
    "autoplay": "Continue with a recommended track when the queue ends",
    "bass": "Boost low frequencies during playback",
    "bassoff": "Turn the bass boost off",
    "blacklist": "List blocked users and chats",
    "blacklistmode": "Choose whether blocked users are kicked or banned",
    "blocklist": "List blocked users and chats",
    "blstickers": "List blocked sticker packs",
    "broadcast": "Send a message to every chat the bot owns",
    "channelplay": "Play audio in a linked channel voice chat",
    "chatfed": "Link this chat to a federation",
    "copy": "Add a tap-to-copy button to a message",
    "cplay": "Play audio into a linked channel's voice chat",
    "cvplay": "Play video into a linked channel's voice chat",
    "dbcleanup": "Delete stored data for a chat",
    "deleteplaylist": "Delete a saved playlist",
    "delfed": "Delete a federation you own",
    "delblacklist": "Remove a user from the blocklist",
    "delblsticker": "Unblock a sticker pack",
    "download": "Download the replied audio or video file",
    "effectoff": "Turn every audio effect off",
    "effecton": "Turn every audio effect on",
    "effects": "Show the active audio effects",
    "emojiinfo": "Inspect a custom emoji and its file id",
    "faddadmin": "Add a federation admin",
    "fban": "Ban a user from every federation chat",
    "fdemote": "Remove a federation admin",
    "fedbanlist": "List federation bans",
    "fedchats": "List chats in a federation",
    "fedinfo": "Show federation details",
    "fedstat": "Show federation statistics",
    "fpromote": "Promote a federation admin",
    "fremadmin": "Remove a federation admin",
    "gblock": "Block the bot from a group",
    "gcast": "Broadcast to groups only",
    "group": "Open the group management panel",
    "commandpreset": "Preview and apply a group-specific command profile",
    "reviewer": "Grant or revoke read-only moderation queue access",
    "modqueue": "Send a read-only queue summary to your private chat",
    "adminsummary": "Schedule a daily private admin digest in UTC",
    "maintenance": "Pause selected protections or onboarding during an incident",
    "forgetmember": "Remove selected member records from this group",
    "mydata": "Download a private export of your stored Videl data",
    "feedback": "Send anonymous private feedback",
    "feedbacklist": "Read anonymous feedback (owner only)",
    "preferences": "Manage opt-in private updates and reminder quiet hours",
    "setchecklist": "Add HTTPS links to the new-member welcome checklist",
    "retention": "Review or configure how long resolved group history is kept",
    "gunblock": "Allow a blocked group again",
    "joinfed": "Join a federation",
    "leavefed": "Leave a federation",
    "lyrics": "Find lyrics for the current track",
    "permissions": "Show or edit a member's permissions",
    "play": "Play a track, album or playlist from a link or search",
    "playnext": "Play a track right after the currently playing track",
    "playlist": "Load a saved playlist into the queue",
    "playlists": "List your saved playlists",
    "pollstop": "Stop a poll the bot posted and show the result",
    "react": "React to the replied message with an emoji",
    "report": "Report a message to the group admins",
    "rmblacklist": "Remove a user from the blocklist",
    "saveplaylist": "Save the current queue as a playlist",
    "seek": "Jump forward in the current track",
    "seekback": "Jump backward in the current track",
    "song": "Download an audio track",
    "speed": "Change playback speed",
    "speedreset": "Reset playback speed to normal",
    "sysinfo": "Show host and runtime information",
    "ublock": "Block a user from using the bot",
    "unapprove": "Remove a member from the approved list",
    "unfban": "Lift a federation ban",
    "uunblock": "Unblock a user",
    "voteskip": "Start a vote to skip the current track",
    "vsong": "Download a video",
    "watchdog": "Show keep-alive watchdog status",
    "pause": "Pause playback",
    "resume": "Resume playback",
    "loop": "Set the loop mode",
    "shuffle": "Shuffle the upcoming queue",
    "clear": "Clear the upcoming queue",
    "skip": "Skip the current track",
    "stop": "Stop playback and clear the queue",
    "end": "Stop playback and leave the voice chat",
    "resetplayer": "Reset the player after an error",
    "replay": "Replay the current track",
}

CATEGORY_LABELS = {
    "music": "Music & playlists",
    "manage": "Groups & protection",
    "tools": "Telegram tools",
    "owner": "Owner operations",
}

CONTEXT_COPY = {
    "group": "Groups",
    "group_private": "Groups & private chats",
    "chat": "Any chat",
    "private": "DM only",
}


def command_rows() -> list[dict[str, object]]:
    from videl.utils.command_catalog import commands

    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for command in commands():
        name = command["name"].lstrip("/")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "usage": USAGE.get(name, f"/{name}"),
                "summary": SUMMARY_OVERRIDES.get(name, command["summary"]).strip().capitalize(),
                "category": command["category"],
                "context": command["context"],
                "owner": bool(command["owner"]),
            }
        )
    rows.sort(key=lambda row: (row["category"], row["name"]))  # type: ignore[index]
    return rows


def render(rows: list[dict[str, object]]) -> str:
    categories = [key for key in ("manage", "music", "tools", "owner") if any(r["category"] == key for r in rows)]
    payload = json.dumps(rows, indent=2, ensure_ascii=False)
    labels = json.dumps({key: CATEGORY_LABELS[key] for key in categories}, ensure_ascii=False)
    contexts = json.dumps(CONTEXT_COPY, ensure_ascii=False)
    return f'''// Generated by scripts/build_webapp_commands.py — do not edit by hand.
// Source: videl/utils/command_catalog.py (the commands the bot really registers).
export type CommandCategory = "music" | "manage" | "tools" | "owner";
export type CommandContext = "group" | "group_private" | "chat" | "private";
export type BotCommand = {{
  name: string;
  usage: string;
  summary: string;
  category: CommandCategory;
  context: CommandContext;
  owner: boolean;
}};

export const BOT_COMMANDS: BotCommand[] = {payload};

export const COMMAND_CATEGORIES = {labels} as const;

export const COMMAND_CONTEXTS = {contexts} as const;

export const COMMAND_COUNT = BOT_COMMANDS.length;
'''


def main() -> None:
    rows = command_rows()
    if not rows:
        raise SystemExit("no commands registered — refusing to write an empty guide")
    TARGET.write_text(render(rows), encoding="utf-8")
    print(f"Wrote {len(rows)} commands to {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
