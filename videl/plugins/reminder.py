"""Videl reminder command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['remind']))
async def reminder_command(_, message):
    await run_plugin('reminder', message)

LOGGER.info("Videl command loaded: reminder")
