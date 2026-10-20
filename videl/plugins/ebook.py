"""Videl ebook command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['ebook']))
async def ebook_command(_, message):
    await run_plugin('ebook', message)

LOGGER.info("Videl command loaded: ebook")
