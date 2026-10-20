"""Record command activity for real, privacy-minimal analytics."""
from datetime import datetime, timezone
import logging
from pyrogram import filters
from pyrogram.types import Message
from videl import bot, LOGGER
from videl.utils.db import get_db

log=logging.getLogger(__name__)

try:
    db=get_db()
    if db is not None:
        db["command_events"].create_index([("at",1)],expireAfterSeconds=90*86400)
        db["command_events"].create_index([("chat_id",1),("at",-1)])
except Exception:
    log.exception("analytics index initialization failed")

@bot.on_message(filters.incoming & filters.text, group=99)
async def record_command(_, message: Message):
    text=message.text or ""
    if not text.startswith("/") or not message.chat:
        return
    first=text.split(maxsplit=1)[0].split("@",1)[0]
    command=first[1:].lower()[:64]
    if not command:
        return
    db=get_db()
    if db is None:
        return
    try:
        db["command_events"].insert_one({
            "at":datetime.now(timezone.utc),
            "command":command,
            "chat_id":message.chat.id,
            "user_id":message.from_user.id if message.from_user else None,
            "chat_type":str(message.chat.type.value if hasattr(message.chat.type,"value") else message.chat.type),
        })
    except Exception:
        log.debug("command telemetry write failed",exc_info=True)

LOGGER.info("Command analytics enabled (90-day TTL; command name, chat and user IDs only)")
