"""Videl afk command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['afk']))
async def afk_command(_, message):
    await run_plugin('afk', message)

LOGGER.info("Videl command loaded: afk")
