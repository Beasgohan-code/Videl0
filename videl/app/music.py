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
    footer = f"{upcoming} upcoming · showing {shown} of {len(tracks)} tracks"
    return Screen(result("Music queue", rows, body=footer) + controls)


async def view_history(ctx):
    """Show the latest acknowledged tracks for this group in this process session."""
    from datetime import datetime, timezone
    from videl.utils.listening_recap import get

    records = get(ctx.message.chat.id)
    if not records:
        return Screen(result("Recent playback", body="No acknowledged tracks in this process session yet."))
    rows = []
    for index, item in enumerate(reversed(records[-15:]), start=1):
        played_at = item.get("at")
        if isinstance(played_at, datetime):
            if played_at.tzinfo is None:
                played_at = played_at.replace(tzinfo=timezone.utc)
            stamp = played_at.astimezone(timezone.utc).strftime("%d %b %H:%M UTC")
        else:
            stamp = "time unavailable"
        title = str(item.get("title") or "Untitled track")[:160]
        duration = str(item.get("duration") or "Live")[:20]
        rows.append((f"{index:02d} · {stamp}", f"{title} · {duration}"))
    return Screen(result("Recent playback", rows, body="Session-only history · titles only · clears when this process restarts."))


async def restore_queue(ctx):
    """Restore only safe upcoming metadata after a fresh track is playing."""
    chat_id = int(ctx.message.chat.id)
    if str(ctx.command.arguments or "").strip():
        raise CommandError("Use <code>/restorequeue</code> without arguments.")
    info = queue.recovery_info(chat_id)
    if not info:
        raise CommandError("There are no saved upcoming tracks for this group.")
    if not queue.peek_current(chat_id):
        raise CommandError(
            "Start a fresh track with /play first. The interrupted track will not be replayed; "
            "then run /restorequeue to append only the saved upcoming tracks."
        )
    async with lock(chat_id):
        count = queue.restore_upcoming(chat_id)
    if not count:
        raise CommandError("The saved queue changed or could not be restored. Nothing was replayed.")
    try:
        await player.refresh_np_ui(chat_id)
    except Exception as error:
        log.warning("Player card refresh failed after queue restore (%s)", type(error).__name__)
    return Screen(result("Upcoming tracks restored", body=f"Added {count} saved upcoming tracks. The current track was left unchanged."), player._now_playing_kb(chat_id))


async def manage_queue(ctx):
    """Admin-only, one-based edits for upcoming tracks; the current track is position zero."""
    from .router import Screen,CommandError

    chat_id=int(ctx.message.chat.id)
    name=ctx.command.name
    parts=str(ctx.command.arguments or "").split()
    required=2 if name=="move" else 1
    if len(parts)!=required or any(not part.isdecimal() for part in parts):
        usage={"remove":"/remove <upcoming position>","move":"/move <from position> <to position>","jump":"/jump <upcoming position>"}.get(name,"/queue")
        raise CommandError(f"Use <code>{usage}</code>. Positions start at 1 for the first upcoming track; the current track cannot be edited.")
    positions=[int(part) for part in parts]
    async with lock(chat_id):
        tracks=queue.get_queue(chat_id)
        if not tracks:
            raise CommandError("There is no active queue to edit.")
        if any(position<1 or position>=len(tracks) for position in positions):
            raise CommandError(f"Choose upcoming positions from 1 to {max(0,len(tracks)-1)}. The current track is protected.")
        if name=="remove":
            removed=queue.remove_upcoming(chat_id,positions[0])
            from videl.core.transitions import cleanup
            cleanup([removed])
            return Screen(result("Track removed",body=f"Removed upcoming track #{positions[0]}."))
        if name=="move":
            source,destination=positions
            if source==destination:
                raise CommandError("Choose two different upcoming positions.")
            if not queue.move_upcoming(chat_id,source,destination):
                raise CommandError("The queue changed before the move could be applied. Refresh /queue and try again.")
            return Screen(result("Queue reordered",body=f"Moved upcoming track #{source} to position #{destination}."))
        if name=="jump":
            position=positions[0]
            original=list(tracks)
            selected=queue.promote_upcoming(chat_id,position)
            if selected is None:
                raise CommandError("The selected track is no longer queued. Refresh /queue and try again.")
            from videl.core.transitions import transition
            try:
                outcome=await transition(chat_id,"skip",expected=original[0])
            except Exception as error:
                queue.restore_snapshot(chat_id,original)
                log.warning("Queue jump unconfirmed; order restored (%s)",type(error).__name__)
                raise CommandError("Playback was not confirmed; the original queue order was restored.") from error
            if not outcome.confirmed:
                queue.restore_snapshot(chat_id,original)
                raise CommandError(outcome.body)
            return Screen(result("Jumped to track",body=f"Started upcoming track #{position} after voice playback was confirmed."))
        raise CommandError("Unknown queue action.")


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
        if name in {'volumeup','volumedown'}:
            delta = 20 if name == 'volumeup' else -20
            target = max(20, min(200, player.volume_percent(chat_id) + delta))
            if target == player.volume_percent(chat_id):
                return Screen(result('Voice volume unchanged', body=f'Volume is already at the {target}% limit.'), player._now_playing_kb(chat_id))
            acknowledged = await call_py.change_volume_call(chat_id, target)
            if acknowledged is False:
                raise RuntimeError('Voice engine did not acknowledge volume change')
            player.set_volume_percent(chat_id, target)
            title = 'Voice volume updated'
            body = f'Voice-chat playback volume is now {target}%. Use the player card controls to adjust it in 20% steps.'
        elif name in {'pause','resume'}:
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
            queue.note_queue_mutation(chat_id)
            title='Upcoming tracks shuffled';body=f'{len(pending)} upcoming tracks shuffled. Current playback is unchanged.'
        elif name in {'clear','clearqueue'}:
            if str(ctx.command.arguments or "").strip():raise CommandError(f'Use <code>/{name}</code> without arguments.')
            from videl.core.autoplay import stop_autoplay
            stop_autoplay(chat_id)
            removed=queue.clear_pending(chat_id)
            # Preserve files: progress/stream-end handlers may still hold references.
            title='Upcoming queue cleared';body=f'{len(removed)} pending tracks removed. Current playback continues. AutoPlay is off.'
        else:raise CommandError('Unknown playback control.')
        try:await player.refresh_np_ui(chat_id)
        except Exception:log.warning('Player card refresh failed after confirmed %s; no action retry',name)
        return Screen(result(title,body=body),player._now_playing_kb(chat_id))
