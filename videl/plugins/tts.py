"""Videl tts command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['tts']))
async def tts_command(_, message):
    await run_plugin('tts', message)

LOGGER.info("Videl command loaded: tts")
