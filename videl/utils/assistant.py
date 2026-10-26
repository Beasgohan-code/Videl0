# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

"""
Assistant utility functions.
Handles checking whether the assistant is in a group and auto-joining it.
Previously this logic was inline in play.py — now centralised here.
"""

import asyncio
import logging

from pyrogram.errors import RPCError, UserAlreadyParticipant
from pyrogram.types import Message

from videl import assistant, bot
from videl.utils.rich_ui import rich_edit, rich_heading, rich_note

log = logging.getLogger(__name__)
_ASSISTANT_START_COMPLETE: asyncio.Event | None = None
_ASSISTANT_READY = False


def assistant_starting() -> None:
    """Mark the user client as pending before Telegram begins delivering commands."""
    global _ASSISTANT_READY, _ASSISTANT_START_COMPLETE
    _ASSISTANT_READY = False
    # Bind the event to the actual app loop; tests and tools may use short-lived loops.
    _ASSISTANT_START_COMPLETE = asyncio.Event()


def assistant_startup_complete(ready: bool) -> None:
    """Publish only readiness, never the session string or its contents."""
    global _ASSISTANT_READY, _ASSISTANT_START_COMPLETE
    _ASSISTANT_READY = bool(ready)
    if _ASSISTANT_START_COMPLETE is None:
        _ASSISTANT_START_COMPLETE = asyncio.Event()
    _ASSISTANT_START_COMPLETE.set()


def assistant_ready() -> bool:
    return _ASSISTANT_READY and bool(getattr(assistant, "is_connected", False))


def assistant_status() -> dict:
    import config
    configured = bool(getattr(config, "STRING_SESSION", ""))
    ready = assistant_ready()
    event = _ASSISTANT_START_COMPLETE
    state = "ready" if ready else "not_configured" if not configured else "starting" if event is None or not event.is_set() else "failed"
    return {"configured": configured, "ready": ready, "state": state}


async def _wait_for_startup() -> bool:
    event = _ASSISTANT_START_COMPLETE
    if event is None:
        return False
    if not event.is_set():
        try:
            await asyncio.wait_for(event.wait(), timeout=15)
        except asyncio.TimeoutError:
            return False
    return assistant_ready()


async def is_assistant_in(chat_id: int):
    """
    Check whether the assistant is a member of the given group.

    Returns:
        True     — assistant is present
        False       — assistant is not present
        "banned"    — assistant was banned from the group
        "not_started" — user client has not connected successfully
    """
    if not await _wait_for_startup():
        return "not_started"

    try:
        me     = await assistant.get_me()
        member = await assistant.get_chat_member(chat_id, me.id)
        return member.status is not None

    except Exception as e:
        err = str(e)
        if "USER_BANNED" in err or "Banned" in err:
            return "banned"
        return False


async def try_join_assistant(chat_id: int, pm: Message) -> bool:
    """
    Attempt to make the assistant join the group via invite link.

    Args:
        chat_id: Target group chat ID.
        pm:      Status message to edit with progress / error text.

    Returns:
        True on success, False on failure.
    """
    if not await _wait_for_startup():
        log.warning("Assistant join skipped: the user client is not started")
        await rich_edit(
            pm,
            rich_heading("⚠️ Voice assistant is offline", level=3)
            + rich_note("The session string must be loaded and the assistant client must finish startup. Check the startup logs and deployment environment, then retry."),
        )
        return False

    try:
        invite_link = await bot.export_chat_invite_link(chat_id)

    except Exception:
        log.exception("Could not export an invite link for assistant join in chat %s", chat_id)
        await rich_edit(
            pm,
            rich_heading("🔗 Invite-link permission needed", level=3)
            + rich_note(
                "I couldn’t create an invite link. Ask a group admin to check my "
                "invite-link permissions, then try again."
            ),
        )
        return False

    try:
        # Normalise joinchat link format
        if invite_link.startswith("https://t.me/+"):
            invite_link = invite_link.replace(
                "https://t.me/+",
                "https://t.me/joinchat/",
            )

        # Must run on the same loop the assistant Client was started on
        try:
            await assistant.join_chat(invite_link)
        except RuntimeError as re:
            # Event loop mismatch — retry via invoke path is not available; re-raise clear msg
            if "event loop" in str(re).lower():
                raise RuntimeError(
                    "Assistant join_chat loop mismatch. "
                    "Ensure assistant is started before PyTgCalls on the same loop."
                ) from re
            raise
        await asyncio.sleep(2)
        return True

    except UserAlreadyParticipant:
        return True

    except RPCError:
        log.exception("Assistant could not join chat %s", chat_id)
        await rich_edit(
            pm,
            rich_heading("⚠️ Assistant couldn’t join", level=3)
            + rich_note(
                "Check that the assistant can access the group invite link and hasn’t "
                "been removed or banned. Then try again."
            ),
        )
        return False

    except Exception:
        log.exception("Unexpected assistant join failure for chat %s", chat_id)
        await rich_edit(
            pm,
            rich_heading("⚠️ Assistant join failed", level=3)
            + rich_note("Please try again. If the problem continues, ask a group admin to check the assistant’s access."),
        )
        return False
        
