"""Videl translate command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['tr']))
async def translate_command(_, message):
    await run_plugin('translate', message)

LOGGER.info("Videl command loaded: translate")
