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
    "help": "/help · /help music",
    "commands": "/commands [query]",
    "whois": "/whois (reply or @user)",
    "font": "/font <bold|italic|script|mono> <text>",
    "kang": "/kang (reply to a sticker)",
    "hug": "/hug [reply or @user]",
    "kiss": "/kiss [reply or @user]",
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
    "lock": "/lock <type>",
    "unlock": "/unlock <type>",
    "afk": "/afk [reason]",
    "remind": "/remind 10m <text>",
    "invite": "/invite [title]",
    "playnext": "/playnext <song name or link>",
    "addsudo": "/addsudo <@user|user_id> [duration] (owner, private chat)",
    "sudolist": "/sudolist (owner, private chat) — shows grant expiry",
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
    "addblacklist": "Add a user to the anti-spam blocklist",
    "addblsticker": "Block a sticker pack from being sent",
    "apiinfo": "Show Telegram API and library versions",
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
    "topicclose": "Close a forum topic",
    "topicnew": "Create a forum topic",
    "topicopen": "Reopen a forum topic",
    "topicrename": "Rename a forum topic",
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
export type CommandContext = "group" | "chat" | "private";
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
