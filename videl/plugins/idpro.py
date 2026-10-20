"""Videl idpro command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['idpro']))
async def idpro_command(_, message):
    await run_plugin('idpro', message)

LOGGER.info("Videl command loaded: idpro")
