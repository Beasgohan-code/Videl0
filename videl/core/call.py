# Videl © 2026 | Beasgohan-code | MIT — retain original attribution.
"""Voice updates use the same transition coordinator as commands and buttons."""
import logging
import time
from pytgcalls import filters as fl
from pytgcalls.types import StreamEnded,Device,ChatUpdate
from videl import bot,call_py
from videl.core import queue,player
from videl.core.playback_state import sessions,lock,forget,consume_expected_voice_exit
from videl.core.transitions import stop,finished,cleanup

log=logging.getLogger(__name__)


async def leave_vc(chat_id):
    """Compatibility entrypoint. Failures propagate; do not clear an active queue."""
    return await stop(chat_id)


@call_py.on_update(fl.stream_end())
async def on_stream_end(_,update):
    # An outgoing video stream also emits an end event; only audio owns queue
    # progression. Incoming microphone/speaker events must not advance it.
    if update.stream_type!=StreamEnded.Type.AUDIO or update.device!=Device.MICROPHONE:return
    observed=sessions.get(update.chat_id)
    if observed is None:return
    # PyTgCalls 2.x supplies no stream ID. Ignore teardown/duplicate events in the
    # first second after an acknowledged replacement; later ambiguous events
    # cannot be perfectly identified without upstream stream identities.
    if time.monotonic()-observed.started<1:return
    try:await finished(update.chat_id,observed)
    except Exception as error:log.warning('Stream completion unconfirmed (%s); no automatic retry',type(error).__name__)


@call_py.on_update(fl.chat_update(ChatUpdate.Status.LEFT_CALL))
async def on_call_left(_,update):
    """Clear ghost queue state when Telegram ends the voice chat externally."""
    chat_id=update.chat_id
    if consume_expected_voice_exit(chat_id):
        log.debug('Ignoring expected voice-chat leave update for %s',chat_id)
        return
    async with lock(chat_id):
        had_state=bool(queue.get_queue(chat_id) or sessions.get(chat_id))
        removed=queue.clear_queue(chat_id)
        player.stop_progress(chat_id)
        forget(chat_id)
        try:
            from videl.core.autoplay import stop_autoplay
            stop_autoplay(chat_id)
        except Exception:
            pass
        try:
            from videl.modules.seek import clear_seek_state
            clear_seek_state(chat_id)
        except Exception:
            pass
        cleanup(removed)
    if not had_state:
        return
    log.warning('Voice chat ended externally in %s (%s); cleared %d queued tracks',
                chat_id,getattr(update,'status','unknown'),len(removed))
    try:
        from videl.utils.command_ui import rich_send
        from videl.utils.rich_ui import rich_heading,rich_note
        await rich_send(
            bot,chat_id,
            rich_heading('🎙 Voice chat ended',level=3)
            + rich_note('Telegram ended the call or the assistant left. The stale queue was cleared. Start a new voice chat, then use /play again.'),
        )
    except Exception as error:
        log.debug('Voice-chat end notice could not be sent (%s)',type(error).__name__)
