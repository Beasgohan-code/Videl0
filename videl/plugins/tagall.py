"""Videl tagall command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['tagall']))
async def tagall_command(_, message):
    await run_plugin('tagall', message)

LOGGER.info("Videl command loaded: tagall")
