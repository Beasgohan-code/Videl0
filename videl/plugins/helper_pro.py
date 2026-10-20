"""Videl helper_pro command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['helperpro']))
async def helper_pro_command(_, message):
    await run_plugin('helper_pro', message)

LOGGER.info("Videl command loaded: helper_pro")
