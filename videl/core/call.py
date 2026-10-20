# Videl © 2026 | Beasgohan-code | MIT — retain original attribution.
"""Voice updates use the same transition coordinator as commands and buttons."""
import logging
import time
from pytgcalls import filters as fl
from pytgcalls.types import StreamEnded,Device
from videl import call_py
from videl.core.playback_state import sessions
from videl.core.transitions import stop,finished

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
