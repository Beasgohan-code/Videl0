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
from pyrogram.enums import ChatMemberStatus, ChatType
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
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note
from videl.utils.command_ui import action_button, inline_keyboard, rich_send, rich_edit


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


async def _bot_admin_status(channel_id: int) -> bool | None:
    """Return bot admin status, or None when Telegram status is unavailable."""
    try:
        bot_user = getattr(bot, "me", None) or await bot.get_me()
        member = await bot.get_chat_member(channel_id, bot_user.id)
    except Exception as exc:
        LOGGER.warning("[cplay] cannot verify bot admin rights for target %s (%s)", channel_id, type(exc).__name__)
        return None
    return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)


def cplay_control_keyboard(source_chat_id: int, target_chat_id: int):
    """Build source/target-bound controls for the shared cplay queue."""
    from videl.core import player

    def button(label: str, action: str, **kwargs):
        callback = f"cplayctl:{action}:{int(source_chat_id)}:{int(target_chat_id)}"
        return action_button(label, callback_data=callback, **kwargs)

    paused = player.is_paused(target_chat_id)
    loop = player.get_loop(target_chat_id)
    repeat = {"off": "Repeat: Off", "one": "Repeat: Track", "all": "Repeat: Queue"}.get(loop, "Repeat: Off")
    return inline_keyboard([
        [
            button("Resume" if paused else "Pause", "resume" if paused else "pause", style="success" if paused else "primary", icon="ios_play" if paused else "rijif_pause"),
            button("Skip", "skip", style="primary", icon="ios_play"),
        ],
        [
            button("Queue", "show_queue", icon="stats"),
            button("History", "show_history", icon="music2"),
            button(repeat, "cycle_loop", icon="ios_repeat"),
        ],
        [button("Volume −", "volume_down", icon="speaker"), button("Volume +", "volume_up", icon="speaker")],
        [button("Replay", "replay", icon="ios_repeat"), button("Stop", "stop", style="danger", icon="ios_close")],
    ])


@bot.on_message(
    filters.command('channelplay', prefixes=config.COMMAND_PREFIX_LIST)
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
            rich_heading(" Channel play", level=3)
            + rich_kv_table([("Linked channel", text)])
            + rich_note(
                "<code>/channelplay @channel</code> or <code>/channelplay -100xxxx</code>\n"
                "<code>/channelplay unlink</code> — remove link\n"
                "Then use <code>/cplay song</code> to play in that channel's VC."
            )
            + rich_note("Link changes apply to future /cplay requests only; target queues and active playback are not migrated or stopped."),
        )
        return

    if not await is_user_authorized(message):
        await rich_send(bot, chat_id, rich_heading(" Admins only", level=3))
        return

    if args[0].lower() in ("unlink", "clear", "off", "remove"):
        if not clear_linked_channel(chat_id):
            await rich_send(
                bot, chat_id,
                rich_heading(" Couldn’t update channel link", level=3)
                + rich_note("Unlink could not be confirmed. Check /channelplay status before retrying."),
            )
            return
        await rich_send(
            bot, chat_id,
            rich_heading(" Channel unlinked", level=3)
            + rich_note("Future /cplay requests are no longer routed here. Unlink does not stop active playback or clear the target channel queue."),
        )
        return

    channel_id = await _resolve_channel(chat_id, args[0])
    if not channel_id:
        await rich_send(
            bot, chat_id,
            rich_heading(" Invalid channel", level=3)
            + rich_note("Use @username or numeric ID. Bot must be admin in the channel."),
        )
        return

    try:
        chat = await bot.get_chat(channel_id)
        if chat.type not in (ChatType.CHANNEL, ChatType.SUPERGROUP):
            await rich_send(bot, chat_id, rich_heading(" Target must be a channel/supergroup", level=3))
            return
    except Exception as e:
        LOGGER.exception("Could not access linked channel %s for chat %s", channel_id, chat_id)
        await rich_send(
            bot, chat_id,
            rich_heading("⚠️ Couldn’t access that channel", level=3)
            + rich_note("Check that the bot is a channel admin and can view the channel, then try again."),
        )
        return

    bot_admin = await _bot_admin_status(channel_id)
    if bot_admin is not True:
        if bot_admin is False:
            heading = " Bot must be a channel admin"
            detail = "Nothing was linked. Promote the bot to channel admin, then retry."
        else:
            heading = " Couldn’t verify channel access"
            detail = "Nothing was linked. Add the bot to the channel as an admin, then retry."
        await rich_send(bot, chat_id, rich_heading(heading, level=3) + rich_note(detail))
        return

    if not set_linked_channel(chat_id, channel_id):
        await rich_send(
            bot, chat_id,
            rich_heading(" Couldn’t save channel link", level=3)
            + rich_note("The database did not confirm the update. Check /channelplay status before retrying."),
        )
        return

    title = getattr(chat, "title", None) or str(channel_id)
    await rich_send(
        bot, chat_id,
        rich_heading(" Channel linked", level=3)
        + rich_kv_table([
            ("Channel", rich_esc(title)),
            ("ID", f"<code>{channel_id}</code>"),
        ])
        + rich_note("Use <code>/cplay song name</code> to stream there. This applies to future /cplay requests; queues and playback on a previous target are not migrated or stopped."),
    )


@bot.on_message(
    filters.group
    & filters.regex(rf"^{config.COMMAND_PREFIX_PATTERN}(?P<cmd>c(?:v)?play)(?:@\w+)?(?:\s+(?P<q>.+))?$")
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
            rich_heading(" No channel linked", level=3)
            + rich_note(
                "Set one first:\n"
                "<code>/channelplay @YourChannel</code>\n"
                "Bot + assistant must be able to join that channel's voice chat."
            ),
        )
        return

    try:
        target_chat = await bot.get_chat(channel_id)
        target_type_ok = target_chat.type in (ChatType.CHANNEL, ChatType.SUPERGROUP)
        bot_admin = await _bot_admin_status(channel_id) if target_type_ok else False
    except Exception as exc:
        LOGGER.warning("[cplay] linked target %s unavailable (%s)", channel_id, type(exc).__name__)
        bot_admin = None

    if bot_admin is not True:
        await rich_send(
            bot, group_id,
            rich_heading(" Linked channel unavailable", level=3)
            + rich_note("The bot must still be an admin in the linked channel. Nothing was queued; restore bot access or relink it with /channelplay."),
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
        document = getattr(reply, "document", None)
        document_video = False
        if document is not None:
            playable, document_video = _is_playable_document(document)
            if not playable:
                await rich_send(bot, group_id, rich_heading(" Unsupported file", level=3))
                return
        media = (
            getattr(reply, "video", None) or getattr(reply, "audio", None)
            or getattr(reply, "voice", None) or getattr(reply, "video_note", None)
            or document
        )
        if not media:
            # fall through to text query
            pass
        else:
            file_size = int(getattr(media, "file_size", 0) or 0)
            if file_size > _MAX_FILE_MB * 1024 * 1024:
                await rich_send(
                    bot, group_id,
                    rich_heading(" File too large", level=3)
                    + rich_note(f"Channel playback accepts media up to {_MAX_FILE_MB} MB."),
                )
                return
            pm = await rich_send(bot, group_id, rich_heading(" Channel play — downloading...", level=3))
            try:
                fresh = await bot.get_messages(reply.chat.id, reply.id)
                target = (
                    fresh.video or fresh.audio or fresh.voice
                    or fresh.video_note or fresh.document or media
                )
                fp = await bot.download_media(target)
            except Exception as e:
                LOGGER.exception("Could not download channel media for chat %s", group_id)
                await rich_edit(
                    pm,
                    rich_heading("⚠️ Couldn’t retrieve that media", level=3)
                    + rich_note(
                        "I couldn’t access the selected media from the linked channel. "
                        "Check that the bot can view the post, then try again."
                    ),
                )
                return

            if not fp:
                await rich_edit(pm, rich_heading(" Download failed", level=3))
                return
            is_video = force_video or bool(reply.video or reply.video_note) or document_video
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
            if pos is None:
                from videl.utils.helpers import delete_file
                delete_file(fp)
                await rich_send(bot, group_id, rich_heading(" Channel queue is full", level=3))
                return
            # Notify in group
            await rich_send(
                bot, group_id,
                rich_heading(" Playing in channel", level=3)
                + rich_kv_table([
                    ("Title", rich_esc(short(name))),
                    ("Channel", f"<code>{channel_id}</code>"),
                    ("Type", "Video" if is_video else "Audio"),
                ]),
                reply_markup=cplay_control_keyboard(group_id, channel_id),
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
    pm = await rich_send(bot, group_id, rich_heading(" Channel play — searching...", level=3))

    try:
        from videl.utils.assistant import is_assistant_in, try_join_assistant
        status = await is_assistant_in(channel_id)
        if status == "banned":
            await rich_edit(pm, rich_heading(" Assistant banned in channel", level=3))
            return
        if status == "not_started":
            await rich_edit(
                pm,
                rich_heading("⚠️ Voice assistant is offline", level=3)
                + rich_note("A session string must also connect successfully at startup. Check the deployment logs and confirm the current <code>STRING_SESSION</code> secret is set; never paste it into chat. Retry after the assistant starts."),
            )
            return
        if not status:
            ok = await try_join_assistant(channel_id, pm)
            if not ok:
                await rich_send(
                    bot, group_id,
                    rich_heading(" Assistant could not join channel", level=3)
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
                await rich_send(bot, group_id, rich_heading(" No results", level=3))
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
            if pos is None:
                await rich_send(bot, group_id, rich_heading(" Channel queue is full", level=3))
                return
            await rich_send(
                bot, group_id,
                rich_heading(" Queued in channel", level=3)
                + rich_kv_table([
                    ("Title", rich_esc(short(r["title"]))),
                    ("Channel", f"<code>{channel_id}</code>"),
                    ("Pos", str(pos)),
                ]),
                reply_markup=cplay_control_keyboard(group_id, channel_id),
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
        if pos is None:
            await rich_send(bot, group_id, rich_heading(" Channel queue is full", level=3))
            return
        await rich_send(
            bot, group_id,
            rich_heading(" Queued in channel", level=3)
            + rich_kv_table([
                ("Title", rich_esc(short(title))),
                ("Channel", f"<code>{channel_id}</code>"),
            ]),
            reply_markup=cplay_control_keyboard(group_id, channel_id),
        )
        if pos == 1:
            await play_song(channel_id, pm, song)
    except Exception as e:
        LOGGER.exception("Channel playback failed for group %s and channel %s", group_id, channel_id)
        await rich_edit(
            pm,
            rich_heading("⚠️ Channel playback failed", level=3)
            + rich_note(
                "I couldn’t start playback in the linked channel. Check the channel’s "
                "voice-chat and assistant permissions, then try again."
            ),
        )


@bot.on_callback_query(filters.regex(
    r"^cplayctl:(?P<action>pause|resume|skip|stop|show_queue|show_history|cycle_loop|volume_up|volume_down|replay):(?P<source>-?[0-9]{1,20}):(?P<target>-?[0-9]{1,20})$"
))
async def cplay_control_callback(_, query) -> None:
    """Route only cplay controls whose source-to-target link is still current."""
    match = query.matches[0] if query.matches else None
    if match is None:
        return
    try:
        source_chat_id = int(match.group("source"))
        target_chat_id = int(match.group("target"))
    except (TypeError, ValueError, OverflowError):
        await query.answer("Invalid channel control.", show_alert=True)
        return

    from videl.app.music_callbacks import handle_bound
    await handle_bound(
        bot, query, match.group("action"), source_chat_id, target_chat_id
    )
