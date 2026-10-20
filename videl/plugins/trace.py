"""Videl trace command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['trace']))
async def trace_command(_, message):
    await run_plugin('trace', message)

LOGGER.info("Videl command loaded: trace")
