"""Videl pollpro command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['pollpro']))
async def pollpro_command(_, message):
    await run_plugin('pollpro', message)

LOGGER.info("Videl command loaded: pollpro")
