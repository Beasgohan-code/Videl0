# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Perfected
#  Readable now-playing cards and semantic native playback controls
# --------------------------------------------------------------------------------
import asyncio, time
from pyrogram.errors import BadRequest
from pyrogram.types import InlineKeyboardMarkup, Message
from videl.utils.bot_ui import button as InlineKeyboardButton, visual_call
from pytgcalls.types import MediaStream, VideoQuality
import config
from videl import LOGGER, bot, call_py
from videl.utils.formatters import parse_dur, short
from videl.utils.rich_ui import RICH_AVAILABLE, rich_edit, rich_esc, rich_heading, rich_kv_table, rich_note, rich_send, rich_details
from videl.utils.youtube import MediaDownloadError, resolve_stream

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


_player_media_file_ids: dict[int, str] = {}
_rich_player_chats: set[int] = set()


def _clone_player_photo(source):
    if hasattr(source, "getvalue"):
        import io
        clone = io.BytesIO(source.getvalue())
        clone.name = getattr(source, "name", "videl-now-playing.jpg")
        return clone
    return source


def _player_photo_file_id(message) -> str | None:
    rich_message = getattr(message, "rich_message", None)
    for block in getattr(rich_message, "blocks", []) or []:
        photo = getattr(block, "photo", None)
        file_id = getattr(photo, "file_id", None)
        if file_id:
            return str(file_id)
    photos = getattr(message, "photo", None)
    if photos:
        photo = photos[-1] if isinstance(photos, (list, tuple)) else photos
        file_id = getattr(photo, "file_id", None)
        if file_id:
            return str(file_id)
    return None


def _rich_caption_text(caption):
    """Convert the known player-caption HTML subset to RichText caption entities."""
    from html.parser import HTMLParser
    from pyrogram.types import RichTextBold, RichTextCode, RichTextCustomEmoji

    def plain_text(items):
        return "".join(
            item if isinstance(item, str) else getattr(item, "alternative_text", "")
            for item in items
        )

    class Builder(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack = [(None, {}, [])]

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag in {"b", "strong", "code", "tg-emoji"}:
                self.stack.append((tag, attrs, []))
            elif tag in {"h1", "h2", "h3", "details", "blockquote", "p"}:
                if self.stack[-1][2] and not plain_text(self.stack[-1][2]).endswith("\n"):
                    self.stack[-1][2].append("\n\n")
            elif tag == "br":
                self.stack[-1][2].append("\n")

        def handle_endtag(self, tag):
            if tag in {"b", "strong", "code", "tg-emoji"}:
                index = next((i for i in range(len(self.stack) - 1, 0, -1)
                              if self.stack[i][0] == tag), None)
                if index is None:
                    return
                name, attrs, children = self.stack.pop(index)
                if name in {"b", "strong"}:
                    item = RichTextBold(children)
                elif name == "code":
                    item = RichTextCode(plain_text(children))
                else:
                    emoji_id = attrs.get("emoji-id")
                    alt = plain_text(children)
                    item = RichTextCustomEmoji(emoji_id, alt) if emoji_id else alt
                self.stack[-1][2].append(item)
            elif tag == "summary":
                self.stack[-1][2].append(" — ")
            elif tag in {"h1", "h2", "h3", "details", "blockquote", "p"}:
                self.stack[-1][2].append("\n\n")

        def handle_data(self, data):
            self.stack[-1][2].append(data)

    parser = Builder()
    parser.feed(caption)
    while len(parser.stack) > 1:
        tag = parser.stack[-1][0]
        parser.handle_endtag(tag)
    return parser.stack[0][2]


def _player_rich_message(photo, caption):
    """Keep the card in one RichMessage photo block with an entity-aware caption."""
    from pyrogram.types import (
        InputMediaPhoto, InputRichBlockPhoto, InputRichMessage, RichBlockCaption,
    )

    block = InputRichBlockPhoto(
        InputMediaPhoto(photo),
        caption=RichBlockCaption(text=_rich_caption_text(caption)),
    )
    return InputRichMessage(blocks=[block])


async def _send_player_card(chat_id, message, caption, keyboard, *, poster=None, thumbnail=None):
    """Send the existing one-message player card using RichMessage photo transport."""
    sources = []
    if poster is not None:
        sources.append(poster)
    if thumbnail and thumbnail != poster:
        sources.append(thumbnail)
    if RICH_AVAILABLE:
        for source in sources:
            try:
                result = await bot.send_rich_message(
                    chat_id=chat_id,
                    rich_message=_player_rich_message(_clone_player_photo(source), caption),
                    reply_markup=keyboard,
                )
                if result is None:
                    return None
                file_id = _player_photo_file_id(result)
                _rich_player_chats.add(chat_id)
                if file_id:
                    _player_media_file_ids[chat_id] = file_id
                return result
            except BadRequest:
                continue
    for source in sources:
        try:
            return await visual_call(
                bot.send_photo, chat_id, photo=_clone_player_photo(source), caption=caption,
                reply_markup=keyboard,
            )
        except BadRequest:
            continue
    if message is not None:
        return await rich_edit(message, caption, reply_markup=keyboard)
    return await rich_send(bot, chat_id, caption, reply_markup=keyboard)

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
        _player_media_file_ids.pop(chat_id, None)
        _rich_player_chats.discard(chat_id)


def start_progress(chat_id, message, total, song):
    stop_progress(chat_id, reset=False)
    _player_media_file_ids.pop(chat_id, None)
    _rich_player_chats.discard(chat_id)
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
    from videl.core.audio_quality import audio_quality_label
    from videl.utils.premium_emojis import pe
    metadata=[(pe("ios_symbols"),"Format",rich_esc(kind)),(pe("boseh_clock"),"Length",rich_esc(duration)),
              (pe("ios_controls"),"Voice quality",rich_esc(audio_quality_label()))]
    if artist and artist.casefold()!=title.casefold():
        metadata.append((pe("music2"),"Artist",rich_esc(short(artist,60))))
    metadata.append((pe("boseh_person"),"Requested by",f"<b>{rich_esc(requester)}</b>"))
    # Avoid HTML tables here: Telegram may flatten unsupported table markup in
    # captions. Explicit line breaks keep every Premium Emoji label readable.
    metadata_lines="\n".join(f"{icon} <b>{label}</b> · {value}" for icon,label,value in metadata)
    parts=[
        rich_heading(f"{pe('music')} {state}",level=2),
        f"<b>{rich_esc(title)}</b>",
        metadata_lines,
        f"<code>{_dot(elapsed,total)}</code>",
    ]
    if chat_id is not None:
        loop=get_loop(chat_id)
        upcoming=peek_next(chat_id)
        if upcoming:
            next_title=rich_esc(short(str(upcoming.get("title","Untitled track")),48))
            parts.append(rich_details(f"{pe('ios_play')} Up next",f"<b>{next_title}</b> · {rich_esc(str(upcoming.get('duration','Live'))[:12])}"))
        queued=max(queue_size(chat_id)-1,0)
        repeat={"off":"Off","one":"This track","all":"Queue"}.get(loop,"Off")
        parts.append(rich_note(f"{pe('ios_folder')} <b>{queued}</b> upcoming · {pe('ios_repeat')} Repeat: <b>{repeat}</b>"))
    return "\n\n".join(parts)


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
        if chat_id in _rich_player_chats:
            photo_file_id = _player_media_file_ids.get(chat_id)
            if not photo_file_id:
                return
            await visual_call(
                bot.edit_message_text,
                chat_id=chat_id,
                message_id=msg.id,
                rich_message=_player_rich_message(photo_file_id, cap),
                reply_markup=kb,
            )
        elif getattr(msg,"photo",None):
            await visual_call(bot.edit_message_caption,chat_id,msg.id,caption=cap,reply_markup=kb)
        else:
            await rich_edit(msg,cap,reply_markup=kb)
    except Exception as error:
        LOGGER.debug("Player progress edit unavailable (%s)", type(error).__name__)

async def _update_progress(chat_id:int, msg:Message, start_t:float, total:float, song:dict):
    while _np_msg.get(chat_id) is msg:
        if not is_paused(chat_id):
            await refresh_np_ui(chat_id)
            if total and current_position(chat_id) >= total:
                break
        await asyncio.sleep(12)


async def _delete_message(message) -> bool:
    if message is None:
        return False
    try:
        await message.delete()
        return True
    except Exception as error:
        LOGGER.debug("Player card cleanup failed (%s)", type(error).__name__)
        return False


def _same_message(first, second) -> bool:
    if first is second:
        return True
    first_id, second_id = getattr(first, "id", None), getattr(second, "id", None)
    return first_id is not None and second_id is not None and first_id == second_id

# ── Acknowledged playback transaction ──────────────────────────────────────────
async def play_song(chat_id:int, message:Message, song:dict, *, advance=False, rotate=False)->bool:
    """Resolve before changing streams; commit queue changes only after engine ack.

    False means playback was not confirmed. No uncertain voice request is retried.
    Card/log delivery is independent and can never undo acknowledged playback.
    """
    from videl.core.playback_state import lock,acknowledged
    from videl.core.queue import peek_current,get_queue,pop_current,add_to_queue
    async with lock(chat_id):
        previous_card = _np_msg.get(chat_id)
        expected=peek_current(chat_id)
        tracks=get_queue(chat_id)
        if (advance and (len(tracks)<2 or tracks[1] is not song)) or (not advance and expected is not song):
            return False
        url=song.get('url')
        if not url:return False
        stage = "media download"
        try:
            want_video=bool(song.get('video',False))
            media_path=await asyncio.wait_for(resolve_stream(url,video=want_video),45)
            if not want_video:
                stage = "optional audio effects"
                from videl.modules.effects import maybe_apply_effects
                # Effects are optional and internally bounded; a slow effect
                # lookup must not abort an otherwise playable track.
                media_path=await maybe_apply_effects(chat_id,media_path)
            # Other legacy producers may append while resolution awaits, but
            # cannot silently substitute a different queue head for this request.
            if peek_current(chat_id) is not expected:return False
            stage = "voice-chat playback"
            from videl.core.audio_quality import audio_quality
            stream=MediaStream(media_path,audio_parameters=audio_quality(),
                **({'video_parameters':VideoQuality.HD_720p} if want_video else {'video_flags':MediaStream.Flags.IGNORE}))
            from videl.core.voice_chat import play_with_auto_start
            response=await play_with_auto_start(call_py,chat_id,stream)
            if response is False:raise RuntimeError('Voice engine did not acknowledge playback')
        except asyncio.CancelledError:raise
        except Exception as error:
            LOGGER.warning('Playback unconfirmed during %s (%s); queue preserved, no retry',stage,type(error).__name__)
            from videl.core.voice_chat import VoiceChatStartError
            if isinstance(error, MediaDownloadError):
                title = 'Track unavailable'
                detail = str(error)
            elif isinstance(error, VoiceChatStartError):
                title = 'Voice chat unavailable'
                detail = str(error)
            elif isinstance(error, (asyncio.TimeoutError, TimeoutError)) and stage == "voice-chat playback":
                title = 'Voice chat timed out'
                detail = ('The audio downloaded, but PyTgCalls did not confirm the stream within 60 seconds. '
                          'Videl reset the playback session and retried once; the queue is preserved. '
                          'Check that the assistant session is online, the assistant is in this group and can join/speak, and a voice chat is active; '
                          'if nothing is playing, use Replay current track once.')
            elif isinstance(error, (asyncio.TimeoutError, TimeoutError)):
                title = 'Track preparation timed out'
                detail = 'The queue was preserved. Try again shortly; optional audio effects will be skipped if their settings are slow to load.'
            else:
                title = 'Playback not confirmed'
                detail = ('The queue was preserved, but Telegram did not confirm voice-chat start or join. '
                          'Videl tried the assistant and, when its rights allowed, the bot client; it changed no permissions. '
                          'Start a voice chat in Telegram and make sure the assistant can join and speak, then use /replay.')
            try:
                from videl.utils.command_ui import rich_send as command_rich_send
                retry_keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("Replay current track", callback_data="replay", style="primary", icon="ios_repeat")
                ]])
                await command_rich_send(
                    bot,
                    chat_id,
                    rich_heading(title, level=3) + rich_note(detail),
                    reply_markup=retry_keyboard,
                )
            except Exception:pass
            return False
        if advance:
            finished=pop_current(chat_id)
            if rotate and finished:add_to_queue(chat_id,finished)
        acknowledged(chat_id,song)
        try:
            from videl.utils.listening_recap import record as record_listening
            record_listening(chat_id, song)
        except Exception as error:
            LOGGER.debug('Listening recap update skipped (%s)', type(error).__name__)
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
            photo=None
            if poster:
                import io
                photo=io.BytesIO(poster)
                photo.name='videl-now-playing.jpg'
            pmsg=await _send_player_card(
                chat_id, message, caption, kb, poster=photo, thumbnail=thumb
            )
        except Exception as error:
            LOGGER.warning('Player card unconfirmed after playback ack (%s); no resend',type(error).__name__)
        if pmsg is not None:
            # Replace the previous card only after the new card was delivered;
            # this keeps the old controls available if Telegram rejects the new one.
            if previous_card is not None and not _same_message(previous_card, pmsg):
                await _delete_message(previous_card)
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
