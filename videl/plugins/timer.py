"""Videl timer command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['timer']))
async def timer_command(_, message):
    await run_plugin('timer', message)

LOGGER.info("Videl command loaded: timer")
