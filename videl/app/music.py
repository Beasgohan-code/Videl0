"""Replacement queue controls backed by the real voice engine and queue.

No simulated state: pause/resume update progress only after engine acknowledgement.
Search, stream transitions and channel playback remain in their existing engine.
"""
import logging
import random
from videl import call_py
from videl.core import queue,player
from videl.utils.command_ui import result
from videl.utils.rich_ui import rich_button, rich_button_row
from videl.utils.premium_emojis import PREMIUM_IDS
from .router import Screen,CommandError

log=logging.getLogger(__name__)
from videl.core.playback_state import lock


async def view_queue(ctx):
    chat_id = ctx.message.chat.id
    tracks = list(queue.get_queue(chat_id))
    if not tracks:
        return Screen(
            result("Your queue", body="Nothing is playing yet. Send <code>/play song name</code> in a voice chat to get started.")
            + rich_button_row(
                rich_button("Music help", callback_data="help:music", style="primary",
                            icon_custom_emoji_id=PREMIUM_IDS["music"]),
                rich_button("Browse commands", callback_data="cmds:all:0",
                            icon_custom_emoji_id=PREMIUM_IDS["ios_search"]),
            )
        )

    # Keep the player card readable in Telegram while still showing a useful
    # preview of longer queues. result() escapes every title and duration.
    visible = tracks[:15]
    rows = []
    for index, track in enumerate(visible):
        title = str(track.get("title", "Untitled track"))[:80]
        duration = str(track.get("duration", "Live"))[:12]
        if index == 0:
            rows.append(("⏸ Paused" if player.is_paused(chat_id) else "▶ Now playing", f"{title} · {duration}"))
        else:
            rows.append((f"{index:02d} · 🎶 Up next", f"{title} · {duration}"))

    paused = player.is_paused(chat_id)
    loop = player.get_loop(chat_id)
    repeat_label = {"off": "Repeat: Off", "one": "Repeat: Track", "all": "Repeat: Queue"}.get(loop, "Repeat: Off")
    controls = "".join([
        rich_button_row(
            rich_button("Resume" if paused else "Pause", callback_data="resume" if paused else "pause",
                        style="success" if paused else "primary",
                        icon_custom_emoji_id=PREMIUM_IDS["ios_play" if paused else "rijif_pause"]),
            rich_button("Skip", callback_data="skip", icon_custom_emoji_id=PREMIUM_IDS["ios_play"]),
        ),
        rich_button_row(
            rich_button(repeat_label, callback_data="cycle_loop", style="success" if loop != "off" else None,
                        icon_custom_emoji_id=PREMIUM_IDS["ios_repeat"]),
            rich_button("Shuffle", callback_data="shuffle", icon_custom_emoji_id=PREMIUM_IDS["ios_arrows"]),
        ),
        rich_button_row(rich_button("Clear upcoming", callback_data="clear", style="danger",
                                    icon_custom_emoji_id=PREMIUM_IDS["ios_trash"])),
    ])
    upcoming = max(0, len(tracks) - 1)
    shown = min(len(tracks), len(visible))
    footer = f"{upcoming} upcoming · max 3 pending per requester · showing {shown} of {len(tracks)} tracks"
    return Screen(result("Music queue", rows, body=footer) + controls)


async def control(ctx, *, cycle=False):
    chat_id=ctx.message.chat.id
    name=ctx.command.name
    if name in {'skip','stop','end','resetplayer','replay'}:
        from videl.core.transitions import transition
        outcome=await transition(chat_id,name)
        if not outcome.confirmed:raise CommandError(outcome.body)
        # Stop has no live player; do not leave stale pause/replay controls.
        keyboard=player._now_playing_kb(chat_id) if queue.peek_current(chat_id) else None
        return Screen(result(outcome.title,body=outcome.body),keyboard)
    # Serialize new pause/resume and queue commands within this chat only.
    async with lock(chat_id):
        if not queue.peek_current(chat_id):raise CommandError('No active track. Start playback with /play song name.')
        if name in {'pause','resume'}:
            paused=name=='pause'
            if player.is_paused(chat_id)==paused:
                return Screen(result('Already paused' if paused else 'Already playing',body='No voice-engine change was requested.'),player._now_playing_kb(chat_id))
            acknowledged=await (call_py.pause(chat_id) if paused else call_py.resume(chat_id))
            if acknowledged is False:raise RuntimeError('Voice engine did not acknowledge action')
            player.set_paused(chat_id,paused)
            title='Playback paused' if paused else 'Playback resumed'
            body='Queue preserved. Playback state was acknowledged by the voice engine.'
        elif name=='loop':
            mode=ctx.command.arguments.casefold()
            if cycle:
                modes=('off','one','all')
                mode=modes[(modes.index(player.get_loop(chat_id))+1)%len(modes)]
            if mode not in {'off','one','all'}:raise CommandError('Use /loop off, /loop one or /loop all.')
            player.set_loop(chat_id,mode)
            title='Repeat updated';body=f'Repeat mode: {mode}.'
        elif name=='shuffle':
            tracks=queue.get_queue(chat_id)
            pending=tracks[1:];random.shuffle(pending);tracks[1:]=pending
            title='Upcoming tracks shuffled';body=f'{len(pending)} upcoming tracks shuffled. Current playback is unchanged.'
        elif name=='clear':
            from videl.core.autoplay import stop_autoplay
            stop_autoplay(chat_id)
            removed=queue.clear_pending(chat_id)
            # Preserve files: progress/stream-end handlers may still hold references.
            title='Upcoming queue cleared';body=f'{len(removed)} pending tracks removed. Current playback continues. AutoPlay is off.'
        else:raise CommandError('Unknown playback control.')
        try:await player.refresh_np_ui(chat_id)
        except Exception:log.warning('Player card refresh failed after confirmed %s; no action retry',name)
        return Screen(result(title,body=body),player._now_playing_kb(chat_id))
