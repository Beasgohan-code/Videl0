"""Videl ytsearch command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['yts']))
async def ytsearch_command(_, message):
    await run_plugin('ytsearch', message)

LOGGER.info("Videl command loaded: ytsearch")
