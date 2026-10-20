"""Videl barcode command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['barcode']))
async def barcode_command(_, message):
    await run_plugin('barcode', message)

LOGGER.info("Videl command loaded: barcode")
