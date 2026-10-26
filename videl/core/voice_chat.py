"""Safe helpers for starting a Telegram group voice chat when playback needs one."""
from __future__ import annotations

import asyncio
import logging
import random

from pytgcalls.exceptions import NoActiveGroupCall
from pyrogram.raw.functions.phone import CreateGroupCall

from videl import assistant

logger = logging.getLogger(__name__)


class VoiceChatStartError(RuntimeError):
    """The assistant could not create or join a group voice chat."""


async def ensure_active_voice_chat(chat_id: int) -> bool:
    """Create a group call once; return success without exposing Telegram internals.

    The assistant account must be able to access the group and have permission
    to manage voice chats. If a call already exists, PyTgCalls can join it.
    """
    try:
        chat = await assistant.get_chat(int(chat_id))
        peer = await assistant.resolve_peer(chat.id)
        await assistant.invoke(
            CreateGroupCall(
                peer=peer,
                random_id=random.randint(1, 2_147_483_647),
            )
        )
        await asyncio.sleep(1.5)
        logger.info("Started a Telegram voice chat in %s", chat_id)
        return True
    except Exception as exc:
        text = f"{type(exc).__name__} {exc}".casefold()
        if "already" in text or "groupcall_already_started" in text:
            return True
        logger.warning("Could not start voice chat (%s)", type(exc).__name__)
        return False


def is_missing_voice_chat(error: BaseException) -> bool:
    """Recognize only explicit 'no active call' failures safe to retry."""
    if isinstance(error, NoActiveGroupCall):
        return True
    text = f"{type(error).__name__} {error}".casefold().replace(" ", "_")
    return any(marker in text for marker in (
        "groupcallnotfound",
        "groupcall_not_found",
        "not_in_group_call",
        "groupcall_forbidden",
        "no_active_group_call",
        "noactivegroupcall",
    ))


async def play_with_auto_start(call_py, chat_id: int, stream):
    """Play once, creating a missing Telegram call and retrying only that case."""
    try:
        return await asyncio.wait_for(call_py.play(chat_id, stream), 30)
    except Exception as play_error:
        if not is_missing_voice_chat(play_error):
            raise
        created = await asyncio.wait_for(ensure_active_voice_chat(chat_id), 20)
        if not created:
            raise VoiceChatStartError(
                "No active voice chat was found, and the assistant could not start one. "
                "Start a voice chat manually or grant the assistant Manage Video Chats permission."
            ) from play_error
        try:
            return await asyncio.wait_for(call_py.play(chat_id, stream), 30)
        except Exception as retry_error:
            if is_missing_voice_chat(retry_error):
                raise VoiceChatStartError(
                    "The voice chat was started, but Telegram did not let the assistant join it. "
                    "Check the assistant’s group access and voice-chat permissions."
                ) from retry_error
            raise
