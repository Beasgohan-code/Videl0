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

from pyrogram import filters
from pyrogram.types import Message

import config
from videl import bot
from videl.core.queue import add_to_queue, get_queue, queue_size
from videl.modules.block import group_allowed, user_allowed
from videl.utils.db import (
    delete_playlist,
    get_playlist,
    list_playlists,
    save_playlist,
)
from videl.utils.permissions import is_user_authorized
from videl.utils.rich_ui import (
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_send,
)


def _owner_id(message: Message, group: bool = False) -> int:
    if group and message.chat:
        return message.chat.id
    return message.from_user.id if message.from_user else 0


@bot.on_message(
    filters.command(["saveplaylist", "savepl"])
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
            await rich_send(bot, chat_id, rich_heading("❌ Only admins can save group playlists", level=3))
            return

    if not name or len(name) > 40:
        await rich_send(bot, chat_id, rich_heading("❌ Invalid name (1–40 chars)", level=3))
        return

    queue = get_queue(chat_id)
    if not queue:
        await rich_send(bot, chat_id, rich_heading("❌ Queue is empty", level=3))
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
            rich_heading("✅ Playlist saved", level=3)
            + rich_kv_table([
                ("Name", rich_esc(name)),
                ("Songs", str(len(songs))),
                ("Type", "Group" if is_group else "Personal"),
            ]),
        )
    else:
        await rich_send(bot, chat_id, rich_heading("❌ Failed to save (DB error)", level=3))


@bot.on_message(
    filters.command(["playlist", "loadplaylist", "loadpl"])
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
    pl = get_playlist(owner, name)
    if not pl or not pl.get("songs"):
        # try the other type as fallback
        alt_owner = (message.from_user.id if message.from_user else 0) if is_group else chat_id
        pl = get_playlist(alt_owner, name)
        if not pl or not pl.get("songs"):
            await rich_send(bot, chat_id, rich_heading("❌ Playlist not found", level=3))
            return

    added = 0
    requester = message.from_user.first_name if message.from_user else "User"
    requester_id = message.from_user.id if message.from_user else 0

    for s in pl["songs"]:
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
        add_to_queue(chat_id, song)
        added += 1

    await rich_send(
        bot, chat_id,
        rich_heading("📥 Playlist loaded", level=3)
        + rich_kv_table([
            ("Name", rich_esc(pl.get("display_name") or name)),
            ("Added", str(added)),
            ("Queue size", str(queue_size(chat_id))),
        ])
        + rich_note("Use <code>/play</code> or wait for autoplay if something is already playing."),
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
    filters.command(["playlists", "myplaylists", "listpl"])
    & group_allowed
    & user_allowed
)
async def list_playlists_cmd(_, message: Message) -> None:
    chat_id = message.chat.id if message.chat else 0
    uid = message.from_user.id if message.from_user else 0

    personal = list_playlists(uid)
    group = list_playlists(chat_id) if message.chat and message.chat.type.name != "PRIVATE" else []

    lines = []
    if personal:
        lines.append("<b>👤 Your playlists</b>")
        for p in personal[:15]:
            n = len(p.get("songs") or [])
            lines.append(f"• <code>{rich_esc(p.get('display_name') or p.get('name'))}</code> ({n})")
    if group:
        lines.append("\n<b>👥 Group playlists</b>")
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
    filters.command(["deleteplaylist", "delpl", "rmplaylist"])
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
            await rich_send(bot, chat_id, rich_heading("❌ Only admins can delete group playlists", level=3))
            return
        owner = chat_id
    else:
        owner = message.from_user.id if message.from_user else 0

    if delete_playlist(owner, name):
        await rich_send(bot, chat_id, rich_heading("✅ Playlist deleted", level=3) + rich_kv_table([("Name", rich_esc(name))]))
    else:
        await rich_send(bot, chat_id, rich_heading("❌ Playlist not found", level=3))
