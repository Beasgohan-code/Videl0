"""Player buttons share command authorization and domain logic, not a second engine.

Callback-query IDs suppress duplicate updates in-process, not across restarts.
Acknowledge each recognized update before slow voice actions; stale callback
answers are expected and must never retry or undo an already-run action.
"""
from collections import OrderedDict
import asyncio
import logging

from pyrogram.errors import QueryIdInvalid

from .router import Context, Parsed, CommandError, authorize
from . import music
from videl.utils.command_ui import rich_reply
from videl.utils.rich_ui import rich_heading, rich_note

log = logging.getLogger(__name__)
_ACTIONS = {
    "pause": "pause", "resume": "resume", "clear": "clear", "cycle_loop": "loop",
    "show_queue": "queue", "skip": "skip", "stop": "stop", "replay": "replay",
}
_inflight = set()
_completed = OrderedDict()


async def _answer(query, text="", *, show_alert=False) -> bool:
    """Answer once, quietly treating Telegram's expired callback ID as expected."""
    try:
        await query.answer(text, show_alert=show_alert)
        return True
    except QueryIdInvalid:
        log.debug("Player callback expired before Telegram accepted its answer")
        return False
    except Exception as error:
        # Do not turn callback-answer transport failures into a missed action.
        # This is not retried, and update deduplication still fences repeats.
        log.warning("Player callback acknowledgement failed (%s); continuing once", type(error).__name__)
        return False


async def _report_failure(client, query, text: str) -> None:
    """Show a result in chat when the callback was already acknowledged."""
    try:
        await rich_reply(
            query.message,
            rich_heading("⚠️ Player action not confirmed", level=3)
            + rich_note(text),
            client=client,
        )
    except Exception as error:
        log.debug("Could not show player callback result (%s)", type(error).__name__)


async def handle(client, query):
    name = _ACTIONS.get(query.data)
    if name is None:
        return False
    if not query.message or not query.from_user:
        await _answer(query, "Open the controls in a group chat.", show_alert=True)
        return True

    key = getattr(query, "id", None)
    if key is not None and (key in _inflight or key in _completed):
        return True
    if len(_inflight) >= 128:
        await _answer(query, "Player controls are busy. Please try again shortly.", show_alert=True)
        return True
    if key is not None:
        _inflight.add(key)
    try:
        from .routes import COMMANDS
        command = next(item for item in COMMANDS if item.name == name)
        ctx = Context(client, query.message, Parsed(name, ""), actor=query.from_user)
        if not await authorize(command, ctx):
            text = (
                "Current group admin permission is required; blocked chats/users cannot use these controls."
                if name != "queue" else "This queue is not available here."
            )
            await _answer(query, text, show_alert=True)
            return True

        # Voice start/leave, queue transitions, and Telegram membership checks
        # can take longer than Telegram's callback-answer window. Clear the
        # spinner now; the player card itself reflects successful changes.
        await _answer(query, "Opening queue…" if name == "queue" else "Updating playback…")
        screen = None
        try:
            if name == "queue":
                screen = await music.view_queue(ctx)
            else:
                await music.control(ctx, cycle=query.data == "cycle_loop")
        except CommandError as error:
            await _report_failure(client, query, str(error))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            log.warning("Player button %s unconfirmed (%s); no retry", name, type(error).__name__)
            await _report_failure(
                client, query,
                "The change could not be confirmed. Check the voice chat before trying again.",
            )
        if screen is not None:
            await rich_reply(query, screen.html, reply_markup=screen.keyboard, client=client)
        return True
    finally:
        if key is not None:
            _inflight.discard(key)
            _completed[key] = None
            while len(_completed) > 4096:
                _completed.popitem(last=False)
