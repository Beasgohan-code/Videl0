"""Videl paste command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['paste']))
async def paste_command(_, message):
    await run_plugin('paste', message)

LOGGER.info("Videl command loaded: paste")
