# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

from pyrogram import filters
from pyrogram.types import Message

from videl import bot
from videl.core.call import leave_vc
from videl.core.queue import clear_queue, queue_size
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.rich_ui import rich_heading, rich_note, rich_send


# ── /stop & /end ──────────────────────────────────────────────────────────────

@bot.on_message(
    filters.group
    & filters.command(["stop", "end"])
    & group_allowed
    & user_allowed
)
async def stop_cmd(_, message: Message) -> None:

    chat_id = message.chat.id

    if not await is_user_authorized(message):
        await rich_send(bot, chat_id, rich_heading("🔒 Admins only", level=3))
        return

    await leave_vc(chat_id)

    await rich_send(
        bot, chat_id,
        rich_heading("⏹ Playback stopped", level=3)
        + rich_note("Queue cleared · left voice chat"),
    )


# ── /clear ─────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.group
    & filters.command("clear")
    & group_allowed
    & user_allowed
)
async def clear_cmd(_, message: Message) -> None:

    chat_id = message.chat.id

    if not await is_user_authorized(message):
        await rich_send(bot, chat_id, rich_heading("🔒 Admins only", level=3))
        return

    try:
        from videl.core.autoplay import stop_autoplay
        stop_autoplay(chat_id)
    except Exception:
        pass

    if not queue_size(chat_id):
        await rich_send(bot, chat_id, rich_heading("ℹ️ Queue is empty", level=3))
        return

    clear_queue(chat_id)
    await rich_send(
        bot, chat_id,
        rich_heading("🧹 Queue cleared", level=3)
        + rich_note("All songs removed."),
    )


# ── /reboot ────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command("reboot")
    & group_allowed
    & user_allowed
)
async def reboot_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    await leave_vc(chat_id)
    await rich_send(
        bot, chat_id,
        rich_heading("🔄 Chat reset", level=3)
        + rich_note("All states reset."),
    )

