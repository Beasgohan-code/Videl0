"""Videl lastfm command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['lastfm']))
async def lastfm_command(_, message):
    await run_plugin('lastfm', message)

LOGGER.info("Videl command loaded: lastfm")
