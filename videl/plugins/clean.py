"""Videl clean command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['cleanpro']))
async def clean_command(_, message):
    await run_plugin('clean', message)

LOGGER.info("Videl command loaded: clean")
