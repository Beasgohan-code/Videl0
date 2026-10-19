# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

from pyrogram import filters
from pyrogram.types import Message

from videl import bot, call_py
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.rich_ui import rich_esc, rich_heading, rich_note, rich_send


@bot.on_message(
    filters.group
    & filters.command("resume")
    & group_allowed
    & user_allowed
)
async def resume_cmd(_, message: Message) -> None:

    chat_id = message.chat.id

    if not await is_user_authorized(message):
        await rich_send(
            bot, chat_id,
            rich_heading("🔒 Admins only", level=3)
            + rich_note("This command is for group admins."),
        )
        return

    try:
        await call_py.resume(chat_id)
        await rich_send(
            bot, chat_id,
            rich_heading("▶ sᴛʀᴇᴀᴍ ʀᴇsᴜᴍᴇᴅ", level=3)
            + rich_note("Playback continued."),
        )
    except Exception as e:
        await rich_send(
            bot, chat_id,
            rich_heading("❌ Resume failed", level=3)
            + rich_note(f"<code>{rich_esc(e)}</code>"),
        )

