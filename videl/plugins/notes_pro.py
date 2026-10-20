"""Videl notes_pro command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['notespro']))
async def notes_pro_command(_, message):
    await run_plugin('notes_pro', message)

LOGGER.info("Videl command loaded: notes_pro")
