"""Player buttons share command authorization and domain logic, not a second engine.

Callback-query IDs suppress duplicate updates in-process, not across restarts.
Acknowledge each recognized update before slow voice actions; stale callback
answers are expected and must never retry or undo an already-run action.
"""
from collections import OrderedDict
import asyncio
import logging

from pyrogram.errors import QueryIdInvalid

from .router import Context, Parsed, CommandError, authorize, chat_kind
from . import music
from videl.utils.command_ui import rich_reply
from videl.utils.rich_ui import rich_heading, rich_note

log = logging.getLogger(__name__)
_ACTIONS = {
    "pause": "pause", "resume": "resume", "clear": "clear", "cycle_loop": "loop",
    "show_queue": "queue", "show_history": "history",
    "volume_up": "volumeup", "volume_down": "volumedown",
    "skip": "skip", "stop": "stop", "replay": "replay",
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


async def _bot_is_target_admin(client, ctx) -> bool:
    from pyrogram.enums import ChatMemberStatus

    try:
        bot_user = getattr(client, "me", None) or await client.get_me()
        member = await client.get_chat_member(ctx.message.chat.id, bot_user.id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


async def _authorize_channel_music_control(client, command, ctx, *, check_bot=True) -> bool:
    """Channel player buttons require the bot and actor to retain target-admin status."""
    from pyrogram.enums import ChatMemberStatus
    from .router import blocked_reason

    if await blocked_reason(command, ctx):
        return False
    user = ctx.user
    if user is None:
        return False
    try:
        if check_bot and not await _bot_is_target_admin(client, ctx):
            return False
        member = await client.get_chat_member(ctx.message.chat.id, user.id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


async def handle(client, query):
    name = _ACTIONS.get(query.data)
    return await _handle(client, query, name, action_data=query.data)


async def handle_bound(client, query, action: str, source_chat_id: int, target_chat_id: int):
    """Dispatch a cplay control only while this source still maps to this target."""
    name = _ACTIONS.get(action)
    return await _handle(
        client, query, name, action_data=action,
        source_chat_id=source_chat_id, target_chat_id=target_chat_id,
    )


async def _handle(
    client, query, name, *, action_data: str,
    source_chat_id: int | None = None, target_chat_id: int | None = None,
):
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
        from types import SimpleNamespace
        from pyrogram.enums import ChatType
        from .routes import COMMANDS
        command = next(item for item in COMMANDS if item.name == name)
        bound = source_chat_id is not None and target_chat_id is not None
        if bound:
            location_id = int(query.message.chat.id)
            if (source_chat_id >= 0 or target_chat_id >= 0 or source_chat_id == target_chat_id
                    or location_id not in {source_chat_id, target_chat_id}):
                await _answer(query, "This channel control is not bound to this chat.", show_alert=True)
                return True
            from videl.utils.db import get_linked_channel
            if get_linked_channel(source_chat_id) != target_chat_id:
                await _answer(query, "This channel link changed. Use the current player controls.", show_alert=True)
                return True

            admin_command = next(item for item in COMMANDS if item.name == "skip")
            source_message = (
                query.message if location_id == source_chat_id
                else SimpleNamespace(chat=SimpleNamespace(id=source_chat_id, type=ChatType.SUPERGROUP))
            )
            target_message = (
                query.message if location_id == target_chat_id
                else SimpleNamespace(chat=SimpleNamespace(id=target_chat_id, type=ChatType.CHANNEL))
            )
            source_ctx = Context(client, source_message, Parsed("skip", ""), actor=query.from_user)
            target_ctx = Context(client, target_message, Parsed("skip", ""), actor=query.from_user)
            source_admin = await authorize(admin_command, source_ctx)
            from .router import blocked_reason
            target_blocked = await blocked_reason(admin_command, target_ctx)
            bot_admin = await _bot_is_target_admin(client, target_ctx)
            target_admin = await _authorize_channel_music_control(
                client, admin_command, target_ctx, check_bot=False
            )
            authorized = bool(bot_admin and not target_blocked and (source_admin or target_admin))
            ctx = Context(client, target_message, Parsed(name, ""), actor=query.from_user)
        else:
            ctx = Context(client, query.message, Parsed(name, ""), actor=query.from_user)
            if chat_kind(query.message) == "channel" and command.category == "music":
                authorized = await _authorize_channel_music_control(client, command, ctx)
            else:
                authorized = await authorize(command, ctx)
        if not authorized:
            if bound:
                text = "A current admin of the linked source group or target channel is required; the source-to-target mapping and bot access are rechecked."
            elif chat_kind(query.message) == "channel" and command.category == "music":
                text = "Current target-channel admin permission is required; blocked chats/users cannot use these controls."
            elif name != "queue":
                text = "Current group admin permission is required; blocked chats/users cannot use these controls."
            else:
                text = "This queue is not available here."
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
            elif name == "history":
                screen = await music.view_history(ctx)
            else:
                await music.control(ctx, cycle=action_data == "cycle_loop")
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
            keyboard = screen.keyboard
            if bound:
                from videl.modules.cplay import cplay_control_keyboard
                keyboard = cplay_control_keyboard(source_chat_id, target_chat_id)
            await rich_reply(query, screen.html, reply_markup=keyboard, client=client)
        return True
    finally:
        if key is not None:
            _inflight.discard(key)
            _completed[key] = None
            while len(_completed) > 4096:
                _completed.popitem(last=False)
