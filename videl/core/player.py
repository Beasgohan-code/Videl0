# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Perfected
#  Readable now-playing cards and semantic native playback controls
# --------------------------------------------------------------------------------
import asyncio, time
from pyrogram.errors import BadRequest
from pyrogram.types import InlineKeyboardMarkup, Message
from videl.utils.bot_ui import button as InlineKeyboardButton, visual_call
from pytgcalls.types import AudioQuality, MediaStream, VideoQuality
import config
from videl import LOGGER, bot, call_py
from videl.utils.formatters import parse_dur, short
from videl.utils.rich_ui import rich_edit, rich_esc, rich_heading, rich_img, rich_kv_table, rich_note, rich_send, rich_details
from videl.utils.youtube import resolve_stream

_nf_pills = lambda: (
    "<p>"
    f'<tg-button type="url" style="primary" url="{config.SUPPORT_GROUP}">⫶ sᴜᴘᴘᴏʀᴛ</tg-button> '
    f'<tg-button type="url" style="success" url="{config.UPDATES_CHANNEL}">◎ ᴜᴘᴅᴀᴛᴇs</tg-button>'
    "</p>"
)

def _thumb_url(song: dict) -> str:
    thumb=(song.get("thumbnail") or "").strip(); vid=(song.get("video_id") or "").strip()
    if not vid and song.get("url"):
        u=str(song["url"])
        if "v=" in u: vid=u.split("v=")[-1].split("&")[0]
        elif "youtu.be/" in u: vid=u.split("youtu.be/")[-1].split("?")[0]
    if vid and ("ytimg" not in thumb or not thumb): return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    if thumb.startswith("http"): return thumb.split("?")[0]
    if vid: return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return ""

_paused: dict[int,bool]={}
_loop_mode: dict[int,str]={}
_np_msg: dict[int,Message]={}
_np_song: dict[int,dict]={}
_np_start: dict[int,float]={}
_np_total: dict[int,float]={}

def get_loop(c): return _loop_mode.get(c,"off")
def set_loop(c,m):
    if m not in ("off","one","all"): m="off"
    _loop_mode[c]=m; return m
def cycle_loop(c):
    order=("off","one","all"); cur=get_loop(c); nxt=order[(order.index(cur)+1)%len(order)]; return set_loop(c,nxt)
def is_paused(c): return bool(_paused.get(c,False))
_pause_started = {}
_progress_tasks = {}


def set_paused(c, value):
    if value and not _paused.get(c, False):
        _pause_started[c] = time.time()
    elif not value and c in _pause_started:
        duration = time.time() - _pause_started.pop(c)
        if c in _np_start:
            _np_start[c] += duration
    _paused[c] = value


def current_position(chat_id):
    now = _pause_started.get(chat_id, time.time())
    return max(0, now - _np_start.get(chat_id, now))


def stop_progress(chat_id, reset=True):
    old = _progress_tasks.pop(chat_id, None)
    if old and not old.done():
        old.cancel()
    if reset:
        for state in (_paused, _pause_started, _np_msg, _np_song, _np_start, _np_total, _loop_mode):
            state.pop(chat_id, None)


def start_progress(chat_id, message, total, song):
    stop_progress(chat_id, reset=False)
    _pause_started.pop(chat_id, None)
    _paused[chat_id] = False
    if message is not None:_np_msg[chat_id] = message
    else:_np_msg.pop(chat_id,None)
    _np_song[chat_id] = song
    _np_start[chat_id] = time.time()
    _np_total[chat_id] = total
    if message is not None:
        _progress_tasks[chat_id] = asyncio.create_task(_update_progress(chat_id, message, time.time(), total, song))


# ── Caption ───────────────────────────────────────────────────────────────────
def _dot(elapsed: float, total: float) -> str:
    from videl.utils.formatters import fmt_time
    total=max(0,total);elapsed=max(0,min(elapsed,total)) if total else 0
    filled=min(10,int(elapsed/total*10)) if total else 0
    return f"{fmt_time(elapsed)}  {'━'*filled}{'─'*(10-filled)}  {fmt_time(total)}"


def _now_playing_caption(song: dict, elapsed: float=0, total: float=0, chat_id: int|None=None) -> str:
    from videl.core.queue import peek_next, queue_size
    title=short(str(song.get("title","Untitled track")),60)
    requester=str(song.get("requester","Community"))
    duration=str(song.get("duration","Live"))
    if total<=0: total=parse_dur(duration) or float(song.get("duration_seconds") or 0)
    state="Paused" if chat_id is not None and is_paused(chat_id) else "Now playing"
    kind="Video" if song.get("video") else "Audio"
    artist=str(song.get("artist") or song.get("uploader") or song.get("channel") or "").strip()
    metadata=[("Format",kind),("Length",rich_esc(duration))]
    if artist and artist.casefold()!=title.casefold():
        metadata.append(("Artist",rich_esc(short(artist,60))))
    metadata.append(("Requested by",f"<b>{rich_esc(requester)}</b>"))
    parts=[
        rich_heading(f"🎵 {state}",level=2),
        rich_note(f"<b>{rich_esc(title)}</b>"),
        rich_kv_table(metadata),
        rich_note(f"<code>{_dot(elapsed,total)}</code>"),
    ]
    if chat_id is not None:
        loop=get_loop(chat_id)
        upcoming=peek_next(chat_id)
        if upcoming:
            next_title=rich_esc(short(str(upcoming.get("title","Untitled track")),48))
            parts.append(rich_details("⏭ Up next",f"<b>{next_title}</b> · {rich_esc(str(upcoming.get('duration','Live'))[:12])}"))
        queued=max(queue_size(chat_id)-1,0)
        repeat={"off":"Off","one":"This track","all":"Queue"}.get(loop,"Off")
        parts.append(rich_note(f"<b>{queued}</b> upcoming · Repeat: <b>{repeat}</b>"))
    return "".join(parts)


def _now_playing_kb(chat_id: int|None=None, votes: int=0, votes_needed: int=0) -> InlineKeyboardMarkup:
    paused=is_paused(chat_id) if chat_id is not None else False
    loop=get_loop(chat_id) if chat_id is not None else "off"
    rows=[
        [InlineKeyboardButton("Resume" if paused else "Pause",callback_data="resume" if paused else "pause",style="success" if paused else "primary",icon="ios_play" if paused else "rijif_pause"),
         InlineKeyboardButton("Skip",callback_data="skip",style="primary",icon="ios_play")],
        [InlineKeyboardButton("Queue",callback_data="show_queue",icon="stats"),
         InlineKeyboardButton({"off":"Repeat: Off","one":"Repeat: Track","all":"Repeat: Queue"}.get(loop,"Repeat: Off"),callback_data="cycle_loop",icon="ios_repeat")],
        [InlineKeyboardButton("Replay",callback_data="replay",icon="ios_repeat"),
         InlineKeyboardButton("Stop",callback_data="stop",style="danger",icon="ios_close")],
    ]
    if votes_needed>0: rows.append([InlineKeyboardButton(f"Vote to skip · {votes}/{votes_needed}",callback_data="vote_skip",icon="rijif_thumbs_up")])
    rows.append([
        InlineKeyboardButton("Help center",callback_data="help:home",icon="info"),
        InlineKeyboardButton("Browse commands",callback_data="cmds:all:0",icon="search"),
    ])
    return InlineKeyboardMarkup(rows)


async def refresh_np_ui(chat_id:int):
    msg=_np_msg.get(chat_id); song=_np_song.get(chat_id)
    if not msg or not song: return
    start_t=_np_start.get(chat_id,time.time()); total=_np_total.get(chat_id,0) or 0
    elapsed=min(current_position(chat_id),total) if total else current_position(chat_id)
    cap=_now_playing_caption(song,elapsed,total,chat_id=chat_id); kb=_now_playing_kb(chat_id)
    try:
        if getattr(msg,"photo",None): await visual_call(bot.edit_message_caption,chat_id,msg.id,caption=cap,reply_markup=kb)
        else: await rich_edit(msg,cap,reply_markup=kb)
    except: pass

async def _update_progress(chat_id:int, msg:Message, start_t:float, total:float, song:dict):
    while _np_msg.get(chat_id) is msg:
        if not is_paused(chat_id):
            await refresh_np_ui(chat_id)
            if total and current_position(chat_id) >= total:
                break
        await asyncio.sleep(12)

# ── Acknowledged playback transaction ──────────────────────────────────────────
async def play_song(chat_id:int, message:Message, song:dict, *, advance=False, rotate=False)->bool:
    """Resolve before changing streams; commit queue changes only after engine ack.

    False means playback was not confirmed. No uncertain voice request is retried.
    Card/log delivery is independent and can never undo acknowledged playback.
    """
    from videl.core.playback_state import lock,acknowledged
    from videl.core.queue import peek_current,get_queue,pop_current,add_to_queue
    async with lock(chat_id):
        expected=peek_current(chat_id)
        tracks=get_queue(chat_id)
        if (advance and (len(tracks)<2 or tracks[1] is not song)) or (not advance and expected is not song):
            return False
        url=song.get('url')
        if not url:return False
        try:
            want_video=bool(song.get('video',False))
            media_path=await asyncio.wait_for(resolve_stream(url,video=want_video),45)
            if not want_video:
                from videl.modules.effects import maybe_apply_effects
                media_path=await asyncio.wait_for(maybe_apply_effects(chat_id,media_path),20)
            # Other legacy producers may append while resolution awaits, but
            # cannot silently substitute a different queue head for this request.
            if peek_current(chat_id) is not expected:return False
            stream=MediaStream(media_path,audio_parameters=AudioQuality.HIGH,
                **({'video_parameters':VideoQuality.HD_720p} if want_video else {'video_flags':MediaStream.Flags.IGNORE}))
            response=await asyncio.wait_for(call_py.play(chat_id,stream),30)
            if response is False:raise RuntimeError('Voice engine did not acknowledge playback')
        except asyncio.CancelledError:raise
        except Exception as error:
            LOGGER.warning('Playback unconfirmed (%s); queue preserved, no retry',type(error).__name__)
            try:
                await rich_send(bot,chat_id,rich_heading('Playback not confirmed',level=3)+rich_note(
                    'The queue was preserved. Check that a voice chat is active and the assistant can join. Use /replay to retry the current track or /skip to try the next. No permissions were changed.'))
            except Exception:pass
            return False
        if advance:
            finished=pop_current(chat_id)
            if rotate and finished:add_to_queue(chat_id,finished)
        acknowledged(chat_id,song)
        try:
            total=parse_dur(str(song.get('duration','0:00'))) or float(song.get('duration_seconds') or 0)
        except (ValueError,TypeError):total=0
        # Establish the playback clock even when every UI delivery fails.
        start_progress(chat_id,None,total,song)
        try:
            from videl.modules.seek import set_seek_state
            set_seek_state(chat_id,0)
        except Exception:pass
        pmsg=None
        try:
            caption=_now_playing_caption(song,0,total,chat_id=chat_id)
            kb=_now_playing_kb(chat_id)
            thumb=_thumb_url(song)
            poster=None
            try:
                from videl.utils.player_poster import build as build_player_poster
                poster_song=dict(song)
                poster_song['thumbnail']=thumb or str(song.get('thumbnail') or '')
                poster=await asyncio.wait_for(build_player_poster(poster_song),timeout=5.5)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                LOGGER.debug('Generated player poster skipped (%s)',type(error).__name__)
            if poster:
                import io
                photo=io.BytesIO(poster)
                photo.name='videl-now-playing.jpg'
            else:
                photo=thumb
            if photo:
                try:
                    pmsg=await visual_call(bot.send_photo,chat_id,photo=photo,caption=caption,reply_markup=kb)
                except BadRequest:
                    # A definite rejection is safe to fall back to the original
                    # provider thumbnail, then the classic rich text player.
                    if poster and thumb:
                        try:pmsg=await visual_call(bot.send_photo,chat_id,photo=thumb,caption=caption,reply_markup=kb)
                        except BadRequest:pmsg=await rich_edit(message,caption,reply_markup=kb) if message is not None else await rich_send(bot,chat_id,caption,reply_markup=kb)
                    else:
                        pmsg=await rich_edit(message,caption,reply_markup=kb) if message is not None else await rich_send(bot,chat_id,caption,reply_markup=kb)
            elif message is not None:pmsg=await rich_edit(message,caption,reply_markup=kb)
            else:pmsg=await rich_send(bot,chat_id,caption,reply_markup=kb)
        except Exception as error:
            LOGGER.warning('Player card unconfirmed after playback ack (%s); no resend',type(error).__name__)
        if pmsg is not None:
            # Preserve the acknowledgement-time clock (UI delivery can be slow).
            _np_msg[chat_id]=pmsg
            _progress_tasks[chat_id]=asyncio.create_task(_update_progress(chat_id,pmsg,_np_start[chat_id],total,song))
        try:
            from videl.database import add_served_chat,add_served_user,increment_play_count
            def record():
                add_served_chat(chat_id)
                if song.get('requester_id'):add_served_user(song['requester_id'])
                increment_play_count(chat_id)
            await asyncio.to_thread(record)
        except Exception as error:LOGGER.warning('Play statistics unavailable (%s)',type(error).__name__)
        if config.LOGGER_ID:
            async def log_play():
                try:
                    await rich_send(bot,config.LOGGER_ID,rich_heading('Now playing',level=3)+rich_kv_table([
                        ('Track',rich_esc(str(song.get('title','Unknown'))[:160])),
                        ('Chat',str(chat_id)),('Requester',rich_esc(str(song.get('requester','Unknown'))[:100]))]))
                except Exception as error:LOGGER.warning('Play log unavailable (%s)',type(error).__name__)
            asyncio.create_task(log_play())
        return True
