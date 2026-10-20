"""Videl scheduler command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['schedule']))
async def scheduler_command(_, message):
    await run_plugin('scheduler', message)

LOGGER.info("Videl command loaded: scheduler")
