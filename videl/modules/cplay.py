# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Channel play (/cplay) — stream music in a linked channel voice chat
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

"""
/cplay <query>     — play in the linked channel's voice chat
/channelplay       — show / set / clear linked channel
/cvplay <query>    — same as cplay but force video stream
"""

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

import config
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.modules.play import _process_play, _play_local_media, _db_track
from videl.utils.db import (
    clear_linked_channel,
    get_linked_channel,
    set_linked_channel,
)
from videl.utils.permissions import is_user_authorized
from videl.utils.rich_ui import (
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_send,
)


async def _resolve_channel(chat_id: int, arg: str | None = None) -> int | None:
    """Resolve linked channel or argument (@username / id)."""
    if arg:
        arg = arg.strip()
        try:
            if arg.lstrip("-").isdigit():
                return int(arg)
            chat = await bot.get_chat(arg)
            return chat.id
        except Exception as e:
            LOGGER.warning(f"[cplay] resolve channel failed: {e}")
            return None
    return get_linked_channel(chat_id)


@bot.on_message(
    filters.command(["channelplay", "cplayset", "setchannel"])
    & filters.group
    & group_allowed
    & user_allowed
)
async def channelplay_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    args = message.command[1:] if message.command else []

    if not args:
        linked = get_linked_channel(chat_id)
        text = f"<code>{linked}</code>" if linked else "Not set"
        await rich_send(
            bot, chat_id,
            rich_heading("📢 Channel play", level=3)
            + rich_kv_table([("Linked channel", text)])
            + rich_note(
                "<code>/channelplay @channel</code> or <code>/channelplay -100xxxx</code>\n"
                "<code>/channelplay unlink</code> — remove link\n"
                "Then use <code>/cplay song</code> to play in that channel's VC."
            ),
        )
        return

    if not await is_user_authorized(message):
        await rich_send(bot, chat_id, rich_heading("❌ Admins only", level=3))
        return

    if args[0].lower() in ("unlink", "clear", "off", "remove"):
        clear_linked_channel(chat_id)
        await rich_send(bot, chat_id, rich_heading("✅ Channel unlinked", level=3))
        return

    channel_id = await _resolve_channel(chat_id, args[0])
    if not channel_id:
        await rich_send(
            bot, chat_id,
            rich_heading("❌ Invalid channel", level=3)
            + rich_note("Use @username or numeric ID. Bot must be admin in the channel."),
        )
        return

    try:
        chat = await bot.get_chat(channel_id)
        if chat.type not in (ChatType.CHANNEL, ChatType.SUPERGROUP):
            await rich_send(bot, chat_id, rich_heading("❌ Target must be a channel/supergroup", level=3))
            return
    except Exception as e:
        await rich_send(
            bot, chat_id,
            rich_heading("❌ Cannot access channel", level=3)
            + rich_note(f"<code>{rich_esc(str(e))}</code>\nAdd the bot as admin in the channel first."),
        )
        return

    set_linked_channel(chat_id, channel_id)
    title = getattr(chat, "title", None) or str(channel_id)
    await rich_send(
        bot, chat_id,
        rich_heading("✅ Channel linked", level=3)
        + rich_kv_table([
            ("Channel", rich_esc(title)),
            ("ID", f"<code>{channel_id}</code>"),
        ])
        + rich_note("Use <code>/cplay song name</code> to stream there."),
    )


@bot.on_message(
    filters.group
    & filters.regex(r"^/(?P<cmd>c(?:v)?play)(?:@\w+)?(?:\s+(?P<q>.+))?$")
    & group_allowed
    & user_allowed
)
async def cplay_handler(_, message: Message) -> None:
    """
    /cplay  — audio in linked channel VC
    /cvplay — video in linked channel VC
    """
    group_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    _db_track(group_id, user_id)

    match = message.matches[0] if message.matches else None
    cmd = (match.group("cmd") if match else "cplay") or "cplay"
    query = (match.group("q") or "").strip() if match else ""
    force_video = cmd == "cvplay"

    channel_id = get_linked_channel(group_id)
    if not channel_id:
        await rich_send(
            bot, group_id,
            rich_heading("📢 No channel linked", level=3)
            + rich_note(
                "Set one first:\n"
                "<code>/channelplay @YourChannel</code>\n"
                "Bot + assistant must be able to join that channel's voice chat."
            ),
        )
        return

    # Local file reply → play into channel
    if message.reply_to_message:
        # Temporarily treat target chat as channel for queue/player
        # We call _play_local_media with channel_id by monkey-patching via a wrapper
        # Simplest: download path then inject into channel queue
        from videl.core.queue import add_to_queue, queue_size
        from videl.core.player import play_song
        from videl.modules.play import _is_playable_document, _VIDEO_EXTS, _MAX_FILE_MB
        from videl.utils.formatters import fmt_time, short

        reply = message.reply_to_message
        media = (
            reply.video or reply.audio or reply.voice
            or reply.video_note or reply.document
        )
        if not media and reply.document:
            ok, _ = _is_playable_document(reply.document)
            if not ok:
                await rich_send(bot, group_id, rich_heading("❌ Unsupported file", level=3))
                return
        if not media:
            # fall through to query
            pass
        else:
            pm = await rich_send(bot, group_id, rich_heading("⏳ Channel play — downloading...", level=3))
            try:
                fresh = await bot.get_messages(reply.chat.id, reply.id)
                target = (
                    fresh.video or fresh.audio or fresh.voice
                    or fresh.video_note or fresh.document or media
                )
                fp = await bot.download_media(target)
            except Exception as e:
                await rich_send(bot, group_id, rich_heading("❌ Download failed", level=3) + rich_note(str(e)))
                return

            is_video = force_video or bool(reply.video or reply.video_note)
            name = getattr(target, "file_name", None) or "Media"
            if str(fp).lower().endswith(tuple(_VIDEO_EXTS)):
                is_video = True

            song = {
                "url": fp,
                "title": name,
                "duration": fmt_time(getattr(target, "duration", 0) or 0),
                "duration_seconds": getattr(target, "duration", 0) or 0,
                "requester": message.from_user.first_name if message.from_user else "Unknown",
                "requester_id": user_id,
                "thumbnail": None,
                "video": is_video,
                "local_file": True,
                "via_cplay": True,
                "source_group": group_id,
            }
            pos = add_to_queue(channel_id, song)
            # Notify in group
            await rich_send(
                bot, group_id,
                rich_heading("📢 Playing in channel", level=3)
                + rich_kv_table([
                    ("Title", rich_esc(short(name))),
                    ("Channel", f"<code>{channel_id}</code>"),
                    ("Type", "Video" if is_video else "Audio"),
                ]),
            )
            if pos == 1:
                await play_song(channel_id, pm, song)
            return

    if not query:
        await rich_send(
            bot, group_id,
            rich_heading("ℹ️ Usage", level=3)
            + rich_kv_table([
                ("Audio", "<code>/cplay song name</code>"),
                ("Video", "<code>/cvplay song name</code>"),
                ("File", "Reply to mkv/mp4/audio with /cplay"),
                ("Setup", "<code>/channelplay @channel</code>"),
            ]),
        )
        return

    # Reuse search/play pipeline but target channel_id
    # Build a shallow proxy message-like object is messy; call _process_play
    # after swapping chat context by temporarily setting message.chat.id — not possible.
    # Instead: search + queue into channel, then play_song on channel.

    from videl.modules.play import _process_play

    # Monkey: process play for channel by fabricating query flow
    # Easiest path: run _process_play with a message whose chat is the channel.
    # Pyrogram Message is frozen; so duplicate the search logic lightly.

    is_url = any(x in query for x in ("youtube.com", "youtu.be", "playlist?list="))
    pm = await rich_send(bot, group_id, rich_heading("⏳ Channel play — searching...", level=3))

    try:
        from videl.utils.assistant import is_assistant_in, try_join_assistant
        status = await is_assistant_in(channel_id)
        if status == "banned":
            await rich_send(bot, group_id, rich_heading("🚫 Assistant banned in channel", level=3))
            return
        if not status:
            ok = await try_join_assistant(channel_id, pm)
            if not ok:
                await rich_send(
                    bot, group_id,
                    rich_heading("❌ Assistant could not join channel", level=3)
                    + rich_note("Add the assistant account to the channel and grant VC rights."),
                )
                return
    except Exception as e:
        LOGGER.warning(f"[cplay] assistant join: {e}")

    try:
        if not is_url:
            from videl.utils.youtube import search_yt_multi
            from videl.utils.formatters import iso_to_human, iso_to_sec, short
            from videl.core.queue import add_to_queue, peek_current, queue_size
            from videl.core.player import play_song

            results = await search_yt_multi(query, limit=1)
            if not results:
                await rich_send(bot, group_id, rich_heading("❌ No results", level=3))
                return
            r = results[0]
            secs = iso_to_sec(r.get("duration_iso", "PT0S"))
            song = {
                "url": r["url"],
                "title": r["title"],
                "duration": iso_to_human(r.get("duration_iso", "PT0S")),
                "duration_seconds": secs,
                "requester": message.from_user.first_name if message.from_user else "Unknown",
                "requester_id": user_id,
                "thumbnail": r.get("thumbnail", ""),
                "video": force_video,
                "video_id": r.get("video_id", ""),
                "via_cplay": True,
                "source_group": group_id,
            }
            pos = add_to_queue(channel_id, song)
            await rich_send(
                bot, group_id,
                rich_heading("📢 Queued in channel", level=3)
                + rich_kv_table([
                    ("Title", rich_esc(short(r["title"]))),
                    ("Channel", f"<code>{channel_id}</code>"),
                    ("Pos", str(pos)),
                ]),
            )
            if pos == 1:
                await play_song(channel_id, pm, song)
            return

        # URL path
        from videl.utils.youtube import search_yt
        from videl.utils.formatters import iso_to_human, iso_to_sec, short
        from videl.core.queue import add_to_queue
        from videl.core.player import play_song

        result = await search_yt(query)
        if isinstance(result, dict) and "playlist" in result:
            await rich_send(bot, group_id, rich_heading("ℹ️ Use /play for playlists in groups", level=3))
            return
        url, title, dur_iso, thumb = result
        song = {
            "url": url,
            "title": title,
            "duration": iso_to_human(dur_iso),
            "duration_seconds": iso_to_sec(dur_iso),
            "requester": message.from_user.first_name if message.from_user else "Unknown",
            "requester_id": user_id,
            "thumbnail": thumb,
            "video": force_video,
            "via_cplay": True,
            "source_group": group_id,
        }
        pos = add_to_queue(channel_id, song)
        await rich_send(
            bot, group_id,
            rich_heading("📢 Queued in channel", level=3)
            + rich_kv_table([
                ("Title", rich_esc(short(title))),
                ("Channel", f"<code>{channel_id}</code>"),
            ]),
        )
        if pos == 1:
            await play_song(channel_id, pm, song)
    except Exception as e:
        LOGGER.error(f"[cplay] {e}")
        await rich_send(
            bot, group_id,
            rich_heading("❌ Channel play failed", level=3)
            + rich_note(f"<code>{rich_esc(str(e))}</code>"),
        )
