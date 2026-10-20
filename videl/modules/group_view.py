"""Observe new and edited updates without consuming or refetching Telegram history."""
from pyrogram import filters
from pyrogram.handlers import MessageHandler,EditedMessageHandler
from videl import bot
from videl.utils.group_view import capture

# Runs before moderation deletes a message. Recording still requires group opt-in.
bot.add_handler(MessageHandler(capture,filters.group | filters.private),group=-100)
bot.add_handler(EditedMessageHandler(capture,filters.group | filters.private),group=-100)
