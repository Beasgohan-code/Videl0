"""
Videl0 • Decorators & Checks — aiogram
"""
import functools
from aiogram.types import Message
from aiogram.enums import ChatType
from bot.config import is_owner, is_sudo

def owner_only(func):
    @functools.wraps(func)
    async def wrap(message: Message, *args, **kwargs):
        if not is_owner(message.from_user.id):
            return await message.reply("◍ ᴏᴡɴᴇʀ ᴏɴʟʏ ◍")
        return await func(message, *args, **kwargs)
    return wrap

def sudo_only(func):
    @functools.wraps(func)
    async def wrap(message: Message, *args, **kwargs):
        if not is_sudo(message.from_user.id):
            return await message.reply("⛔ Sudo only.")
        return await func(message, *args, **kwargs)
    return wrap

def admin_only(func):
    """Checks Telegram admin OR sudo."""
    @functools.wraps(func)
    async def wrap(message: Message, *args, **kwargs):
        if is_sudo(message.from_user.id):
            return await func(message, *args, **kwargs)
        if message.chat.type == ChatType.PRIVATE:
            return await message.reply("Use this in groups.")
        try:
            member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
            if member.status in ("administrator","creator"):
                return await func(message, *args, **kwargs)
        except: pass
        return await message.reply("🔒 Admins only.")
    return wrap

def group_only(func):
    @functools.wraps(func)
    async def wrap(message: Message, *args, **kwargs):
        if message.chat.type == ChatType.PRIVATE:
            return await message.reply("⫶ ɢʀᴏᴜᴘs ᴏɴʟʏ ⫶")
        return await func(message, *args, **kwargs)
    return wrap

async def is_bot_admin(message: Message) -> bool:
    try:
        me=await message.bot.get_me()
        m=await message.bot.get_chat_member(message.chat.id, me.id)
        return m.status in ("administrator","creator")
    except: return False

def cooldown(rate: int=3, per: int=10):
    """simple per-user cooldown via dict"""
    _buckets={}
    def deco(func):
        @functools.wraps(func)
        async def wrap(message: Message, *args, **kwargs):
            import time
            uid=message.from_user.id
            now=time.time()
            bucket=_buckets.get(uid, [])
            bucket=[t for t in bucket if now-t < per]
            if len(bucket) >= rate:
                return await message.reply(f"◍ sʟᴏᴡ ᴅᴏᴡɴ — {per}s ⫶")
            bucket.append(now); _buckets[uid]=bucket
            return await func(message, *args, **kwargs)
        return wrap
    return deco
