"""Videl currency command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['currency']))
async def currency_command(_, message):
    await run_plugin('currency', message)

LOGGER.info("Videl command loaded: currency")
