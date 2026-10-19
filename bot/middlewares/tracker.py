"""Track users/chats, gban check, afk, flood."""
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from aiogram.enums import ChatType
from typing import Any, Callable, Dict
import time, asyncio
from bot.config import is_sudo
from bot.database import db
import bot.database_ext  # patch
from collections import defaultdict, deque

_flood = defaultdict(lambda: deque(maxlen=10))

class TrackerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: Dict[str,Any]) -> Any:
        if isinstance(event, Message) and event.from_user and event.chat:
            uid=event.from_user.id
            cid=event.chat.id
            # track
            try:
                await db.add_user(uid, event.from_user.username, event.from_user.full_name)
                if event.chat.type != ChatType.PRIVATE:
                    await db.add_chat(cid, event.chat.title, event.chat.type)
                await db.inc_stat((event.text or "").split()[0] if event.text else "message", cid, uid)
            except: pass

            # gban auto kick
            try:
                if not is_sudo(uid):
                    gb=await db.is_gbanned(uid)
                    if gb:
                        if event.chat.type != ChatType.PRIVATE:
                            try:
                                await event.bot.ban_chat_member(cid, uid)
                                await event.reply(f"🚫 Gbanned user {uid} auto-banned.\nReason: {gb.get('reason','')}")
                            except: pass
                        return
            except: pass

            # flood
            try:
                settings=await db.get_chat_settings(cid) if event.chat.type!=ChatType.PRIVATE else {}
                flood_limit=settings.get("flood_limit",5)
                flood_window=settings.get("flood_window",6)
                now=time.time()
                dq=_flood[cid]
                dq.append((uid, now))
                # count recent from same user
                recent=[t for u,t in dq if u==uid and now-t < flood_window]
                if len(recent) > flood_limit and len(recent)==flood_limit+1:
                    try:
                        await event.bot.restrict_chat_member(cid, uid, permissions=None, until_date=int(now+60))
                        await event.reply(f"🚷 Flood detected — muted {event.from_user.full_name} for 60s")
                    except: pass
            except: pass

            # afk check — if reply mentions afk user
            if event.reply_to_message and event.reply_to_message.from_user:
                try:
                    afk=await db.get_afk(event.reply_to_message.from_user.id)
                    if afk:
                        await event.reply(f"💤 {event.reply_to_message.from_user.full_name} is AFK: {afk.get('reason','')}", disable_notification=True)
                except: pass
            # remove afk on activity
            try:
                afk=await db.get_afk(uid)
                if afk and event.text and not event.text.startswith("/afk"):
                    await db.rm_afk(uid)
                    await event.reply(f"✅ Welcome back {event.from_user.full_name}, you are no longer AFK.")
            except: pass

            # filter trigger
            if event.text and event.chat.type != ChatType.PRIVATE:
                try:
                    filters=await db.get_filters(cid)
                    txt=event.text.lower()
                    for f in filters:
                        if f["keyword"].lower() in txt:
                            await event.reply(f["reply_text"])
                            break
                except: pass

        return await handler(event, data)
