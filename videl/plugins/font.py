"""Videl font command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['font']))
async def font_command(_, message):
    await run_plugin('font', message)

LOGGER.info("Videl command loaded: font")
