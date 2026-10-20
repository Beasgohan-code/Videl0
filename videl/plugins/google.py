"""Videl google command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['google']))
async def google_command(_, message):
    await run_plugin('google', message)

LOGGER.info("Videl command loaded: google")
