"""Videl language command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['langpro']))
async def language_command(_, message):
    await run_plugin('language', message)

LOGGER.info("Videl command loaded: language")
