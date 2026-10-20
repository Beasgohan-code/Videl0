"""Videl rules_pro command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['rulespro']))
async def rules_pro_command(_, message):
    await run_plugin('rules_pro', message)

LOGGER.info("Videl command loaded: rules_pro")
