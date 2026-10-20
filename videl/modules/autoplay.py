# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from videl import bot
from videl.core.autoplay import (
    get_autoplay_query,
    is_autoplay,
    start_autoplay,
    stop_autoplay,
)
from videl.core.call import leave_vc
from videl.core.player import play_song
from videl.core.queue import peek_current, queue_size
from videl.modules.block import group_allowed, user_allowed
from videl.utils.formatters import short
from videl.utils.permissions import is_user_authorized
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note
from videl.utils.command_ui import rich_edit, rich_send


@bot.on_message(
    filters.group
    & filters.regex(r"^/autoplay(?:@\w+)?(?:\s+(?P<q>.+))?$")
    & group_allowed
    & user_allowed
)
async def autoplay_cmd(_, message: Message) -> None:

    chat_id = message.chat.id
    user    = message.from_user

    if not await is_user_authorized(message):
        await rich_send(
            bot, chat_id,
            rich_heading("⛔ admin only", level=3)
            + rich_note("only group admins can use /autoplay"),
        )
        return

    match = message.matches[0]
    query = (match.group("q") or "").strip()

    if not query:
        current_q = get_autoplay_query(chat_id)
        if is_autoplay(chat_id) and current_q:
            await rich_send(
                bot, chat_id,
                rich_heading("🔁 autoplay is already running", level=3)
                + rich_kv_table([("query", f"<code>{rich_esc(current_q)}</code>")])
                + rich_note("use /end to stop autoplay first"),
            )
        else:
            await rich_send(
                bot, chat_id,
                rich_heading("🔁 autoplay usage", level=3)
                + rich_kv_table([("usage", "<code>/autoplay sidhu moose wala</code>")])
                + rich_note("this will continuously play songs automatically"),
            )
        return

    pm = await rich_send(
        bot, chat_id,
        rich_heading("🔁 setting up autoplay...", level=3)
        + rich_kv_table([("query", f"<code>{rich_esc(query)}</code>")]),
    )

    req    = user.first_name if user else "AutoPlay"
    req_id = user.id         if user else 0

    was_playing = queue_size(chat_id) > 0
    count       = await start_autoplay(chat_id, query, req, req_id)

    if count == 0:
        stop_autoplay(chat_id)
        await rich_edit(
            pm,
            rich_heading("❍ autoplay failed", level=3)
            + rich_note("no songs were found, please try again"),
        )
        return

    first = peek_current(chat_id)

    await rich_edit(
        pm,
        rich_heading("🔁 autoplay started", level=3)
        + rich_kv_table([
            ("query", f"<code>{rich_esc(query)}</code>"),
            ("added", f"{count} songs to queue"),
        ])
        + rich_note("use /end to stop autoplay"),
    )

    if not was_playing and first:
        dm = await rich_send(
            bot, chat_id,
            rich_heading("❍ now playing", level=3)
            + rich_kv_table([("title", f"<code>{rich_esc(short(first['title']))}</code>")]),
        )
        await play_song(chat_id, dm, first)

    try:
        await message.delete()
    except Exception:
        pass

