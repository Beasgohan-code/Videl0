# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Playlists + Smart Queue helpers
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

"""
User & group playlists:
  /saveplaylist <name>   – save current queue as playlist
  /playlist <name>       – load playlist into queue
  /playlists             – list your / group playlists
  /deleteplaylist <name> – delete a playlist
"""

import re

from pyrogram import filters
from pyrogram.types import Message

import config
from videl import bot
from videl.core.queue import add_to_queue, get_queue, queue_size
from videl.modules.block import group_allowed, user_allowed
from videl.utils.db import (
    PlaylistStorageError,
    delete_playlist,
    get_playlist,
    list_playlists,
    save_playlist,
)
from videl.utils.permissions import is_user_authorized
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note
from videl.utils.command_ui import rich_send
from videl.utils.formatters import parse_dur


def _owner_id(message: Message, group: bool = False) -> int:
    if group and message.chat:
        return message.chat.id
    return message.from_user.id if message.from_user else 0


@bot.on_message(
    filters.command('saveplaylist', prefixes=config.COMMAND_PREFIX_LIST)
    & filters.group
    & group_allowed
    & user_allowed
)
async def save_playlist_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    if len(message.command) < 2:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note(
                "<code>/saveplaylist MyHits</code>\n"
                "Saves the <b>current queue</b> as a playlist.\n"
                "Use <code>/saveplaylist g:Party</code> for a <b>group</b> playlist."
            ),
        )
        return

    raw = " ".join(message.command[1:]).strip()
    is_group = False
    name = raw
    if raw.lower().startswith("g:"):
        is_group = True
        name = raw[2:].strip()
        if not await is_user_authorized(message):
            await rich_send(bot, chat_id, rich_heading(" Only admins can save group playlists", level=3))
            return

    if not name or len(name) > 40:
        await rich_send(bot, chat_id, rich_heading(" Invalid name (1–40 chars)", level=3))
        return

    queue = get_queue(chat_id)
    if not queue:
        await rich_send(bot, chat_id, rich_heading(" Queue is empty", level=3))
        return

    # Store lightweight song info
    songs = []
    for s in queue[:50]:
        songs.append({
            "title": s.get("title", "Unknown"),
            "duration": s.get("duration", "?"),
            "url": s.get("url") or s.get("link") or "",
            "thumbnail": s.get("thumbnail", ""),
            "video_id": s.get("video_id", ""),
        })

    owner = chat_id if is_group else (message.from_user.id if message.from_user else 0)
    ok = save_playlist(owner, name, songs, is_group=is_group)
    if ok:
        await rich_send(
            bot, chat_id,
            rich_heading(" Playlist saved", level=3)
            + rich_kv_table([
                ("Name", rich_esc(name)),
                ("Songs", str(len(songs))),
                ("Type", "Group" if is_group else "Personal"),
            ]),
        )
    else:
        await rich_send(bot, chat_id, rich_heading(" Failed to save (DB error)", level=3))


@bot.on_message(
    filters.command('playlist', prefixes=config.COMMAND_PREFIX_LIST)
    & filters.group
    & group_allowed
    & user_allowed
)
async def load_playlist_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    if len(message.command) < 2:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note(
                "<code>/playlist MyHits</code> — load your playlist\n"
                "<code>/playlist g:Party</code> — load group playlist"
            ),
        )
        return

    raw = " ".join(message.command[1:]).strip()
    is_group = False
    name = raw
    if raw.lower().startswith("g:"):
        is_group = True
        name = raw[2:].strip()

    owner = chat_id if is_group else (message.from_user.id if message.from_user else 0)
    try:
        pl = get_playlist(owner, name)
        if (not pl or not pl.get("songs")) and not is_group:
            # Preserve the legacy unprefixed group-playlist fallback, but an
            # explicit g: request must never silently load a personal playlist.
            pl = get_playlist(chat_id, name)
        if not pl or not pl.get("songs"):
            await rich_send(bot, chat_id, rich_heading(" Playlist not found", level=3))
            return
    except PlaylistStorageError:
        await rich_send(bot, chat_id, rich_heading(" Couldn’t access playlist storage", level=3))
        return

    tracks = pl.get("songs") if isinstance(pl, dict) else None
    if not isinstance(tracks, list) or not tracks:
        await rich_send(bot, chat_id, rich_heading(" Playlist data is invalid", level=3))
        return

    stored_count = len(tracks)
    omitted_tracks = max(0, stored_count - 50)
    tracks = tracks[:50]
    requested = len(tracks)
    valid_tracks = []
    invalid_rows = 0
    skipped_too_long = 0
    for stored_song in tracks:
        if not isinstance(stored_song, dict):
            invalid_rows += 1
            continue
        song = dict(stored_song)
        url = song.get("url") or song.get("link") or ""
        if not isinstance(url, str) or not url.strip():
            video_id = song.get("video_id")
            if isinstance(video_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                url = f"https://www.youtube.com/watch?v={video_id}"
            else:
                invalid_rows += 1
                continue
        song["url"] = url.strip()
        try:
            duration_seconds = int(float(song.get("duration_seconds"))) if song.get("duration_seconds") is not None else parse_dur(str(song.get("duration") or ""))
        except (TypeError, ValueError, OverflowError):
            duration_seconds = 0
        if duration_seconds > config.MAX_DURATION_SECONDS:
            skipped_too_long += 1
            continue
        song["duration_seconds"] = max(0, duration_seconds)
        valid_tracks.append(song)
    if not valid_tracks:
        notices = []
        if invalid_rows:
            notices.append(f"Skipped {invalid_rows} invalid saved track row(s).")
        if skipped_too_long:
            notices.append(f"Skipped {skipped_too_long} track(s) over the {config.MAX_DURATION_SECONDS // 60}-minute duration limit.")
        await rich_send(
            bot, chat_id,
            rich_heading(" Playlist contains no valid tracks", level=3)
            + rich_note(" ".join(notices) or "Nothing was added."),
        )
        return

    added = 0
    requester = message.from_user.first_name if message.from_user else "User"
    requester_id = message.from_user.id if message.from_user else 0

    for s in valid_tracks:
        if queue_size(chat_id) >= config.QUEUE_LIMIT:
            break
        song = {
            "title": s.get("title", "Unknown"),
            "duration": s.get("duration", "?"),
            "url": s.get("url", ""),
            "thumbnail": s.get("thumbnail", ""),
            "video_id": s.get("video_id", ""),
            "requester": requester,
            "requester_id": requester_id,
            "from_playlist": pl.get("display_name") or name,
        }
        position = add_to_queue(chat_id, song)
        if position is None:
            break
        added += 1

    completion_note = rich_note("Use <code>/play</code> or wait for autoplay if something is already playing.")
    if added < len(valid_tracks):
        completion_note += rich_note(f"Queue capacity reached: added {added} of {len(valid_tracks)} valid tracks.")
    if invalid_rows:
        completion_note += rich_note(f"Skipped {invalid_rows} invalid saved track rows.")
    if omitted_tracks:
        completion_note += rich_note(f"Only the first 50 tracks were considered due to the 50-track limit; {omitted_tracks} additional saved rows were ignored.")
    if skipped_too_long:
        noun = "track" if skipped_too_long == 1 else "tracks"
        completion_note += rich_note(f"Skipped {skipped_too_long} {noun} over the {config.MAX_DURATION_SECONDS // 60}-minute duration limit.")

    await rich_send(
        bot, chat_id,
        rich_heading("📥 Playlist loaded", level=3)
        + rich_kv_table([
            ("Name", rich_esc(pl.get("display_name") or name)),
            ("Added", str(added)),
            ("Queue size", str(queue_size(chat_id))),
        ])
        + completion_note,
    )

    # If nothing is playing, start the first song
    from videl.core.queue import peek_current
    from videl.core.player import play_song
    current = peek_current(chat_id)
    if current and added > 0:
        # Only auto-start if we were empty before (rough check)
        try:
            # Let existing autoplay / stream-end handle it if already active
            pass
        except Exception:
            pass


@bot.on_message(
    filters.command('playlists', prefixes=config.COMMAND_PREFIX_LIST)
    & group_allowed
    & user_allowed
)
async def list_playlists_cmd(_, message: Message) -> None:
    chat_id = message.chat.id if message.chat else 0
    uid = message.from_user.id if message.from_user else 0

    try:
        personal = list_playlists(uid)
        group = list_playlists(chat_id) if message.chat and message.chat.type.name != "PRIVATE" else []
    except PlaylistStorageError:
        await rich_send(bot, chat_id or uid, rich_heading(" Couldn’t access playlist storage", level=3))
        return

    lines = []
    if personal:
        lines.append("<b>👤 Your playlists</b>")
        for p in personal[:15]:
            n = len(p.get("songs") or [])
            lines.append(f"• <code>{rich_esc(p.get('display_name') or p.get('name'))}</code> ({n})")
    if group:
        lines.append("\n<b> group playlists</b>")
        for p in group[:15]:
            n = len(p.get("songs") or [])
            lines.append(f"• <code>g:{rich_esc(p.get('display_name') or p.get('name'))}</code> ({n})")

    if not lines:
        await rich_send(
            bot, chat_id or uid,
            rich_heading("📂 No playlists yet", level=3)
            + rich_note("Save the current queue with <code>/saveplaylist Name</code>"),
        )
        return

    await rich_send(
        bot, chat_id or uid,
        rich_heading("📂 Playlists", level=3)
        + rich_note("\n".join(lines))
        + rich_note("Load with <code>/playlist Name</code> or <code>/playlist g:Name</code>"),
    )


@bot.on_message(
    filters.command('deleteplaylist', prefixes=config.COMMAND_PREFIX_LIST)
    & group_allowed
    & user_allowed
)
async def delete_playlist_cmd(_, message: Message) -> None:
    chat_id = message.chat.id if message.chat else 0
    if len(message.command) < 2:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("<code>/deleteplaylist Name</code> or <code>/deleteplaylist g:Name</code>"),
        )
        return

    raw = " ".join(message.command[1:]).strip()
    is_group = raw.lower().startswith("g:")
    name = raw[2:].strip() if is_group else raw

    if is_group:
        if not await is_user_authorized(message):
            await rich_send(bot, chat_id, rich_heading(" Only admins can delete group playlists", level=3))
            return
        owner = chat_id
    else:
        owner = message.from_user.id if message.from_user else 0

    try:
        deleted = delete_playlist(owner, name)
    except PlaylistStorageError:
        await rich_send(bot, chat_id, rich_heading(" Couldn’t access playlist storage", level=3))
        return

    if deleted:
        await rich_send(bot, chat_id, rich_heading(" Playlist deleted", level=3) + rich_kv_table([("Name", rich_esc(name))]))
    else:
        await rich_send(bot, chat_id, rich_heading(" Playlist not found", level=3))
