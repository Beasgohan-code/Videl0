"""Replacement application entrypoint; remaining stateful domains migrate separately."""
from videl import bot
from videl.app.install import install
install(bot)
