"""Telegram guest-bot support and shared Bot API capability detection."""
import logging

from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent

from videl import bot

log = logging.getLogger(__name__)


@bot.on_guest_message()
async def guest_message(_, message):
    """Respond to a guest mention without assuming access to chat history."""
    query_id = getattr(message, "guest_query_id", None)
    if not query_id:
        return

    content = (
        "Videl is a Telegram utility and group-management bot. I can only see "
        "this mention and replies to it, not the rest of the chat.\n\n"
        "Add me to a group to use its configured moderation, welcome messages, "
        "and member verification. In a private chat, use /help to browse available commands."
    )
    try:
        await bot.answer_guest_query(
            guest_query_id=str(query_id),
            result=InlineQueryResultArticle(
                id="videl-guest-info",
                title="About Videl",
                description="Telegram utilities and group management",
                input_message_content=InputTextMessageContent(message_text=content),
            ),
        )
    except Exception as exc:
        # Do not log guest message contents or query identifiers.
        log.info("Guest response could not be delivered (%s)", type(exc).__name__)
