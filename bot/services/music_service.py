"""
Videl0 • Music Service — pytgcalls wrapper
If STRING_SESSION / API_ID not set, all ops are no-ops with graceful fallback.
Mirrors ShizuMusic core/player + core/call + core/queue.
"""
import logging, asyncio
from bot.config import API_ID, API_HASH, STRING_SESSION, BOT_TOKEN, LOGGER_ID, LOG_CHANNEL_ID
log=logging.getLogger("videl.music.svc")

# Attempt to init pytgcalls only if creds present
call_py = None
assistant = None
assistant_bot = None

if API_ID and API_HASH and STRING_SESSION and BOT_TOKEN:
    try:
        from pyrogram import Client
        from pyrogram.enums import ParseMode
        from pytgcalls import PyTgCalls
        # Bot client (not used for calls, just for logs)
        # Assistant (userbot) for VC
        assistant = Client("videl_assistant", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
        call_py = PyTgCalls(assistant)
        log.info("pytgcalls assistant ready")
    except Exception as e:
        log.warning(f"pytgcalls init fail: {e}")
        call_py = None
else:
    log.info("Music VC disabled — missing API_ID/STRING_SESSION. Running in file-mode.")

# queue is handled in DB; this just wraps call control
async def play_via_call(chat_id: int, song: dict) -> bool:
    if not call_py: return False
    try:
        from pytgcalls.types import MediaStream, AudioQuality
        from bot.utils.youtube import resolve_stream
        stream_url = await resolve_stream(song.get("url") or song.get("link",""))
        if not stream_url:
            return False
        # ensure call started
        await call_py.play(chat_id, MediaStream(stream_url, audio_parameters=AudioQuality.HIGH))
        log.info(f"Playing in {chat_id}: {song.get('title')}")
        return True
    except Exception as e:
        log.warning(f"play_via_call fail {chat_id}: {e}")
        return False

async def pause_call(chat_id: int):
    if call_py:
        try: await call_py.pause(chat_id)
        except Exception as e: log.debug(f"pause {e}")
    else: raise RuntimeError("VC not configured")

async def resume_call(chat_id: int):
    if call_py:
        try: await call_py.resume(chat_id)
        except Exception as e: log.debug(f"resume {e}")
    else: raise RuntimeError("VC not configured")

async def stop_call(chat_id: int):
    if call_py:
        try: await call_py.leave_call(chat_id)
        except: pass
    # also close panel tracking if any
    try: from bot.handlers.music import _last as _mlast; _mlast.pop(chat_id, None)
    except: pass

async def seek_call(chat_id: int, seconds: int):
    if call_py:
        try:
            # pytgcalls seek: re-play with seek arg? use call.seek if available
            await call_py.seek_stream(chat_id, seconds*1000)
        except Exception as e:
            raise RuntimeError(f"Seek not supported: {e}")
    else: raise RuntimeError("VC not configured")

def is_assistant_in(chat_id: int) -> bool:
    # stub
    return False
