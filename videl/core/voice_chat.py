"""Safe helpers for starting a Telegram group voice chat when playback needs one."""
from __future__ import annotations

import asyncio
import logging
import random

from pytgcalls.exceptions import NoActiveGroupCall
from pyrogram.enums import ChatMemberStatus
from pyrogram.raw.functions.phone import CreateGroupCall

from videl import assistant, bot

logger = logging.getLogger(__name__)
PLAY_ACK_TIMEOUT_SECONDS = 60
CALL_START_TIMEOUT_SECONDS = 45


class VoiceChatStartError(RuntimeError):
    """The assistant could not create or join a group voice chat."""


async def _create_group_call(client, chat_id: int, client_label: str) -> bool:
    """Ask one authorized Telegram client to create the call; never change rights."""
    try:
        chat = await client.get_chat(int(chat_id))
        peer = await client.resolve_peer(chat.id)
        await client.invoke(
            CreateGroupCall(
                peer=peer,
                random_id=random.randint(1, 2_147_483_647),
            )
        )
        await asyncio.sleep(1.5)
        logger.info("Started a Telegram voice chat in %s using %s client", chat_id, client_label)
        return True
    except Exception as exc:
        text = f"{type(exc).__name__} {exc}".casefold().replace(" ", "_")
        if any(marker in text for marker in (
            "groupcall_already_started",
            "groupcallalreadystarted",
            "group_call_already_started",
            "already_started",
        )):
            return True
        logger.warning("Could not start voice chat using %s client (%s)", client_label, type(exc).__name__)
        return False


async def _bot_can_manage_voice_chat(chat_id: int) -> bool:
    """Use the bot MTProto fallback only if Telegram reports the required right."""
    try:
        me = getattr(bot, "me", None) or await bot.get_me()
        member = await bot.get_chat_member(int(chat_id), int(me.id))
        status = getattr(member, "status", None)
        if status == ChatMemberStatus.OWNER:
            return True
        privileges = getattr(member, "privileges", None)
        return (
            status == ChatMemberStatus.ADMINISTRATOR
            and bool(getattr(privileges, "can_manage_video_chats", False))
        )
    except Exception as exc:
        logger.debug("Bot voice-chat right check unavailable (%s)", type(exc).__name__)
        return False


async def ensure_active_voice_chat(chat_id: int) -> bool:
    """Try the assistant session, then the authorized bot session; never promote.

    Telegram voice-chat creation is attempted only after playback explicitly
    reports that no call exists. Neither client is granted or changed any rights.
    """
    if await _create_group_call(assistant, chat_id, "assistant"):
        return True
    if await _bot_can_manage_voice_chat(chat_id):
        return await _create_group_call(bot, chat_id, "bot")
    return False


def is_missing_voice_chat(error: BaseException) -> bool:
    """Recognize only explicit 'no active call' failures safe to retry."""
    if isinstance(error, NoActiveGroupCall):
        return True
    text = f"{type(error).__name__} {error}".casefold().replace(" ", "_")
    return any(marker in text for marker in (
        "groupcallnotfound",
        "groupcall_not_found",
        "no_active_group_call",
        "noactivegroupcall",
    ))


async def play_with_auto_start(call_py, chat_id: int, stream):
    """Play once, creating a missing Telegram call and retrying only that case."""
    try:
        # Slow hosted assistants can take longer to negotiate/join the stream;
        # keep a firm bound, but avoid declaring failure during a normal join.
        return await asyncio.wait_for(
            call_py.play(chat_id, stream), PLAY_ACK_TIMEOUT_SECONDS
        )
    except Exception as play_error:
        if not is_missing_voice_chat(play_error):
            raise
        try:
            # Allow Telegram time to finish creating a call before the
            # playback retry; slow hosted/network RPCs need a longer bound.
            created = await asyncio.wait_for(ensure_active_voice_chat(chat_id), CALL_START_TIMEOUT_SECONDS)
        except asyncio.TimeoutError as startup_error:
            logger.warning("Voice-chat auto-start timed out in %s", chat_id)
            raise VoiceChatStartError(
                "Telegram did not finish creating the voice chat in time. Start one in the group manually and use /replay. For automatic creation, the assistant must already be a member with permission to manage video chats; Videl will not promote it or change group permissions."
            ) from startup_error
        if not created:
            raise VoiceChatStartError(
                "Telegram had no active voice chat, and no already-authorized client could create one. "
                "Start a voice chat manually, then use /replay. For automatic creation, the assistant or bot must already have Telegram’s Manage Video Chats permission; Videl never grants or changes permissions."
            ) from play_error
        try:
            return await asyncio.wait_for(
                call_py.play(chat_id, stream), PLAY_ACK_TIMEOUT_SECONDS
            )
        except Exception as retry_error:
            if is_missing_voice_chat(retry_error):
                raise VoiceChatStartError(
                    "Telegram reports that the voice chat started, but the assistant could not join it. "
                    "Check that the assistant is in the group and can join and speak in voice chats."
                ) from retry_error
            raise
