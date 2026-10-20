"""Videl unshort command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['unshort']))
async def unshort_command(_, message):
    await run_plugin('unshort', message)

LOGGER.info("Videl command loaded: unshort")
