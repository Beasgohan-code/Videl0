"""Videl musichelp command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['musichelp']))
async def musichelp_command(_, message):
    await run_plugin('musichelp', message)

LOGGER.info("Videl command loaded: musichelp")
