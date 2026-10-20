"""Videl userinfo command adapter — real implementation in runtime.py."""
from pyrogram import filters
from videl import LOGGER, bot
from videl.plugins.runtime import run_plugin

@bot.on_message(filters.command(['userinfo']))
async def userinfo_command(_, message):
    await run_plugin('userinfo', message)

LOGGER.info("Videl command loaded: userinfo")
