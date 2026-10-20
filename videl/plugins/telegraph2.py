"""Videl telegraph2 command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['tgraph']))
async def telegraph2_command(_, message):
    await run_plugin('telegraph2', message)

LOGGER.info("Videl command loaded: telegraph2")
