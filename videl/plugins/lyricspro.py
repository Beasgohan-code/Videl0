"""Videl lyricspro command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['lyricspro']))
async def lyricspro_command(_, message):
    await run_plugin('lyricspro', message)

LOGGER.info("Videl command loaded: lyricspro")
