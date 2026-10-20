"""Bounded, throttled activity telemetry. Non-music groups count as active too."""
import asyncio
import time
from collections import OrderedDict
from pyrogram import filters
from videl import bot
from videl.utils.db import touch_chat_activity, touch_user_activity

_seen = OrderedDict()


def _due(kind, identifier):
    key, now = (kind, identifier), time.monotonic()
    if now-_seen.get(key, -61) < 60:
        return False
    _seen[key] = now
    _seen.move_to_end(key)
    while len(_seen) > 20000:
        _seen.popitem(last=False)
    return True


@bot.on_message(filters.all, group=-1000)
async def observe_activity(_, message):
    if getattr(message, "outgoing", False):
        return
    jobs = []
    chat, user = getattr(message, "chat", None), getattr(message, "from_user", None)
    if chat and _due("chat", chat.id):
        jobs.append(asyncio.to_thread(touch_chat_activity, chat.id))
    if user and not user.is_bot and _due("user", user.id):
        jobs.append(asyncio.to_thread(touch_user_activity, user.id))
    if jobs:
        await asyncio.gather(*jobs)
