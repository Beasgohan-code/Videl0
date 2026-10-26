"""Shared, acknowledged transitions for commands, buttons and stream completion."""
from dataclasses import dataclass
from videl import call_py
from videl.core import queue,player
from videl.core.playback_state import lock,sessions,forget
from pytgcalls.exceptions import NoActiveGroupCall
import asyncio
import logging

log=logging.getLogger(__name__)


@dataclass(frozen=True)
class Outcome:
    title:str
    body:str
    confirmed:bool=True


def cleanup(songs):
    """Only release local files no remaining queue references (including loop-all)."""
    from videl.utils.helpers import delete_file
    used={str(song.get(key)) for tracks in queue.chat_queues.values() for song in tracks
          for key in ('url','file_path') if song.get(key)}
    for song in songs:
        path=song.get('file_path')
        if path and str(path) not in used:delete_file(path)


async def stop(chat_id):
    async with lock(chat_id):
        from videl.core.playback_state import expect_voice_exit, cancel_expected_voice_exit
        expect_voice_exit(chat_id)
        try:
            response=await asyncio.wait_for(call_py.leave_call(chat_id),30)
            if response is False:raise RuntimeError('Leave not acknowledged')
        except NoActiveGroupCall:
            cancel_expected_voice_exit(chat_id)
        except Exception:
            cancel_expected_voice_exit(chat_id)
            raise
        # Any other exception propagates BEFORE irreversible local cleanup.
        from videl.core.autoplay import stop_autoplay
        stop_autoplay(chat_id)
        player.stop_progress(chat_id)
        forget(chat_id)
        try:
            from videl.modules.seek import clear_seek_state
            clear_seek_state(chat_id)
        except Exception:pass
        removed=queue.clear_queue(chat_id)
        cleanup(removed)
        return Outcome('Playback stopped','Voice chat exit confirmed. Queue, repeat and AutoPlay have been cleared.')


async def transition(chat_id,action,message=None,*,expected=None):
    async with lock(chat_id):
        current=queue.peek_current(chat_id)
        if expected is not None and current is not expected:
            return Outcome('Track already changed','The earlier request was not applied to a different track.',False)
        if action in {'stop','end','resetplayer'}:return await stop(chat_id)
        if current is None:return Outcome('No active track','Start a track with /play song name.',False)
        if action=='replay':
            if not await player.play_song(chat_id,message,current):
                return Outcome('Replay not confirmed','Queue preserved. Check the voice chat before retrying.',False)
            return Outcome('Track restarted','The voice engine acknowledged playback from the beginning.')
        if action!='skip':raise ValueError('Invalid playback transition')
        tracks=queue.get_queue(chat_id)
        if len(tracks)<2:
            outcome=await stop(chat_id)
            return Outcome('Last track skipped',outcome.body)
        if not await player.play_song(chat_id,message,tracks[1],advance=True):
            return Outcome('Skip not confirmed','The next stream was not confirmed. Queue preserved; check the voice chat before retrying.',False)
        cleanup([current])
        return Outcome('Track skipped','The next track was acknowledged by the voice engine.')


async def finished(chat_id,observed):
    """Fence queued end events against sessions replaced by manual transitions."""
    async with lock(chat_id):
        if observed is None or sessions.get(chat_id) is not observed or observed.ending:return
        current=queue.peek_current(chat_id)
        if current is not observed.song:return
        observed.ending=True
        mode=player.get_loop(chat_id)
        if mode=='one' or mode=='all' and queue.queue_size(chat_id)==1:
            await player.play_song(chat_id,None,current)
            return
        if queue.queue_size(chat_id)<2:
            from videl.core.autoplay import refill
            try:await asyncio.wait_for(refill(chat_id),20)
            except Exception as error:log.warning('AutoPlay refill unavailable (%s)',type(error).__name__)
        if queue.queue_size(chat_id)>1:
            next_song=queue.get_queue(chat_id)[1]
            if await player.play_song(chat_id,None,next_song,advance=True,rotate=mode=='all'):
                if mode!='all':cleanup([current])
            return
        await stop(chat_id)
