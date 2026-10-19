# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import asyncio

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from videl import bot, call_py
from videl.core.player import play_song
from videl.core.queue import peek_current, pop_current, queue_size
from videl.modules.block import group_allowed, user_allowed
from videl.utils.formatters import short
from videl.utils.helpers import delete_file
from videl.utils.permissions import is_user_authorized
from videl.utils.rich_ui import (
    rich_edit,
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_send,
)


@bot.on_message(
    filters.group
    & filters.command("skip")
    & group_allowed
    & user_allowed
)
async def skip_cmd(_, message: Message) -> None:

    chat_id = message.chat.id

    if not await is_user_authorized(message):
        await rich_send(
            bot, chat_id,
            rich_heading("🔒 Admins only", level=3)
            + rich_note("This command is for group admins."),
        )
        return

    if not queue_size(chat_id):
        await rich_send(
            bot, chat_id,
            rich_heading("ℹ️ Queue is empty", level=3)
            + rich_note("Nothing to skip."),
        )
        return

    sm = await rich_send(bot, chat_id, rich_heading("⏭ Skipping...", level=3))

    skipped = pop_current(chat_id)

    try:
        await call_py.leave_call(chat_id)
    except Exception:
        pass

    await asyncio.sleep(2)

    try:
        delete_file(skipped.get("file_path", ""))
    except Exception:
        pass

    nxt = peek_current(chat_id)

    if nxt:
        await rich_edit(
            sm,
            rich_heading("⏭ ᴛʀᴀᴄᴋ Skipped", level=3)
            + rich_kv_table([
                ("Skipped", f"<code>{rich_esc(short(skipped['title']))}</code>"),
                ("ɴᴏᴡ ᴘʟᴀʏɪɴɢ", f"<code>{rich_esc(nxt['title'])}</code>"),
            ]),
        )
        dm = await rich_send(
            bot, chat_id,
            rich_heading("▶️ Next track", level=3)
            + rich_kv_table([("ᴛɪᴛʟᴇ", f"<code>{rich_esc(nxt['title'])}</code>")]),
        )
        await play_song(chat_id, dm, nxt)
    else:
        await rich_edit(
            sm,
            rich_heading("⏭ ᴛʀᴀᴄᴋ Skipped", level=3)
            + rich_kv_table([("Skipped", f"<code>{rich_esc(short(skipped['title']))}</code>")])
            + rich_note("Queue is now empty."),
        )

