# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Perfected
#  Readable now-playing cards and semantic native playback controls
# --------------------------------------------------------------------------------
import asyncio, random, time
from pyrogram.enums import ParseMode
from pyrogram.errors import BadRequest
from pyrogram.raw.functions.phone import CreateGroupCall
from pyrogram.types import InlineKeyboardMarkup, Message
from videl.utils.bot_ui import button as InlineKeyboardButton, visual_call
from pytgcalls import filters as fl
from ntgcalls import TelegramServerError
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import AudioQuality, MediaStream, VideoQuality, ChatUpdate, StreamEnded, GroupCallConfig, GroupCallParticipant, UpdatedGroupCallParticipant
import config
from videl import LOGGER, assistant, bot, call_py
from videl.core.queue import remove_from_queue
from videl.utils.formatters import parse_dur, short
from videl.utils.rich_ui import rich_edit, rich_esc, rich_heading, rich_img, rich_kv_table, rich_note, rich_send
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
def set_paused(c,v): _paused[c]=v

# ── Caption ───────────────────────────────────────────────────────────────────
def _dot(elapsed: float, total: float) -> str:
    from videl.utils.formatters import fmt_time
    total=max(0,total);elapsed=max(0,min(elapsed,total)) if total else 0
    filled=min(10,int(elapsed/total*10)) if total else 0
    return f"{fmt_time(elapsed)}  {'━'*filled}{'─'*(10-filled)}  {fmt_time(total)}"


def _now_playing_caption(song: dict, elapsed: float=0, total: float=0, chat_id: int|None=None) -> str:
    from videl.core.queue import peek_next, queue_size
    from videl.utils.premium_emojis import pe
    title=short(str(song.get("title","Untitled track")),60)
    requester=str(song.get("requester","Community"))
    duration=str(song.get("duration","Live"))
    if total<=0: total=parse_dur(duration) or float(song.get("duration_seconds") or 0)
    state="Paused" if chat_id is not None and is_paused(chat_id) else "Now playing"
    lines=[f"{pe('music', '🎵')} <b>{state}</b>",f"<b>{rich_esc(title)}</b>","",f"{'Video' if song.get('video') else 'Audio'} · {rich_esc(duration)}",f"Requested by <b>{rich_esc(requester)}</b>","",f"<code>{_dot(elapsed,total)}</code>"]
    if chat_id is not None:
        loop=get_loop(chat_id)
        if loop!="off": lines.append(f"Repeat: {'Current track' if loop=='one' else 'Entire queue'}")
        upcoming=peek_next(chat_id)
        if upcoming: lines.extend(["",f"Up next: <b>{rich_esc(short(str(upcoming.get('title','Untitled track')),48))}</b>"])
        lines.append(f"Queued tracks: <b>{max(queue_size(chat_id)-1,0)}</b>")
    return "\n".join(lines)


def _now_playing_kb(chat_id: int|None=None, votes: int=0, votes_needed: int=0) -> InlineKeyboardMarkup:
    paused=is_paused(chat_id) if chat_id is not None else False
    loop=get_loop(chat_id) if chat_id is not None else "off"
    rows=[[InlineKeyboardButton("Replay",callback_data="replay",icon="music"),InlineKeyboardButton("Resume" if paused else "Pause",callback_data="resume" if paused else "pause",style="success" if paused else "primary",icon="music"),InlineKeyboardButton("Skip",callback_data="skip",icon="right")],
          [InlineKeyboardButton({"off":"Repeat: Off","one":"Repeat: Track","all":"Repeat: Queue"}.get(loop,"Repeat: Off"),callback_data="cycle_loop",icon="music"),InlineKeyboardButton("Stop playback",callback_data="stop")]]
    if votes_needed>0: rows.append([InlineKeyboardButton(f"Vote to skip · {votes}/{votes_needed}",callback_data="vote_skip",icon="check")])
    return InlineKeyboardMarkup(rows)


async def refresh_np_ui(chat_id:int):
    msg=_np_msg.get(chat_id); song=_np_song.get(chat_id)
    if not msg or not song: return
    start_t=_np_start.get(chat_id,time.time()); total=_np_total.get(chat_id,0) or 0
    elapsed=min(time.time()-start_t,total) if total else 0
    cap=_now_playing_caption(song,elapsed,total,chat_id=chat_id); kb=_now_playing_kb(chat_id)
    try:
        if getattr(msg,"photo",None): await visual_call(bot.edit_message_caption,chat_id,msg.id,caption=cap,reply_markup=kb)
        else: await rich_edit(msg,cap,reply_markup=kb)
    except: pass

async def _update_progress(chat_id:int, msg:Message, start_t:float, total:float, song:dict):
    _np_msg[chat_id]=msg; _np_song[chat_id]=song; _np_start[chat_id]=start_t; _np_total[chat_id]=total; set_paused(chat_id,False)
    paused_accum=0.0; pause_began=None
    while True:
        if is_paused(chat_id):
            if pause_began is None: pause_began=time.time()
            await asyncio.sleep(2); continue
        if pause_began is not None:
            paused_accum+=time.time()-pause_began; pause_began=None; _np_start[chat_id]=start_t+paused_accum
        elapsed=min(time.time()-start_t-paused_accum,total) if total else 0
        cap=_now_playing_caption(song,elapsed,total,chat_id=chat_id); kb=_now_playing_kb(chat_id)
        try:
            if getattr(msg,"photo",None): await visual_call(bot.edit_message_caption,chat_id,msg.id,caption=cap,reply_markup=kb)
            else: await rich_edit(msg,cap,reply_markup=kb)
        except Exception as e:
            if "MESSAGE_NOT_MODIFIED" not in str(e): break
        if total and elapsed>=total: break
        await asyncio.sleep(12)

# ── VC ensure ─────────────────────────────────────────────────────────────────
async def _try_create_group_call(client, chat_id:int, who:str)->bool:
    try:
        peer=await client.resolve_peer(chat_id)
        await client.invoke(CreateGroupCall(peer=peer, random_id=random.randint(10000,999999)))
        LOGGER.info(f"[VC] Created by {who} in {chat_id}"); await asyncio.sleep(1.5); return True
    except Exception as e:
        err=str(e).lower()
        if "already" in err or "groupcall_already_started" in err or "group_call_already_started" in err:
            LOGGER.info(f"[VC] Already active ({who}) in {chat_id}"); return True
        LOGGER.warning(f"[VC] {who} CreateGroupCall failed: {e}"); return False

async def _try_promote_assistant(chat_id:int)->bool:
    try:
        from pyrogram.types import ChatPrivileges
        me_asst=await assistant.get_me()
        await bot.promote_chat_member(chat_id, me_asst.id, privileges=ChatPrivileges(can_manage_video_chats=True, can_invite_users=True))
        LOGGER.info(f"[VC] Promoted assistant in {chat_id}"); await asyncio.sleep(1); return True
    except Exception as e: LOGGER.warning(f"[VC] promote assistant failed: {e}"); return False

async def _ensure_vc(chat_id:int)->bool:
    chat_id=int(chat_id)
    if await _try_create_group_call(assistant,chat_id,"assistant"): return True
    if await _try_create_group_call(bot,chat_id,"bot"): return True
    if await _try_promote_assistant(chat_id):
        if await _try_create_group_call(assistant,chat_id,"assistant-after-promote"): return True
        if await _try_create_group_call(bot,chat_id,"bot-after-promote"): return True
    await rich_send(bot,chat_id,
        rich_heading(f"◍ {__import__('videl.utils.formatters',fromlist=['sc']).sc('need vc admin')}",level=3)
        + rich_note("ᴛᴇʟᴇɢʀᴀᴍ ɴᴇᴇᴅs <b>ᴍᴀɴᴀɢᴇ ᴠɪᴅᴇᴏ ᴄʜᴀᴛs</b> ᴛᴏ <b>sᴛᴀʀᴛ</b> ᴀ ᴄᴀʟʟ.<br>«ᴀᴅᴅ ᴍᴇᴍʙᴇʀs» ᴏɴʟʏ ɪɴᴠɪᴛᴇs ᴀssɪsᴛᴀɴᴛ — ɪᴛ ᴄᴀɴɴᴏᴛ sᴛᴀʀᴛ ᴠᴄ.<br><br>"
                    "<b>ғɪx:</b> ᴘʀᴏᴍᴏᴛᴇ <b>ʙᴏᴛ + ᴀssɪsᴛᴀɴᴛ</b> → ᴍᴀɴᴀɢᴇ ᴠɪᴅᴇᴏ ᴄʜᴀᴛs<br>ᴏʀ sᴛᴀʀᴛ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ᴍᴀɴᴜᴀʟʟʏ ᴏɴᴄᴇ, ᴛʜᴇɴ /play ᴀɢᴀɪɴ"))
    return False

# ── MAIN PLAY ─────────────────────────────────────────────────────────────────
async def play_song(chat_id:int, message:Message, song:dict)->None:
    chat_id=int(chat_id); url=song.get("url")
    if not url: return
    from videl.utils.formatters import sc
    loading_text=rich_heading(f"◍ {sc('loading')} ⫶",level=3)+rich_kv_table([(sc("song"), rich_esc(short(song['title'])))])
    try: await rich_edit(message, loading_text)
    except: message=await rich_send(bot,chat_id,loading_text)
    try:
        want_video=bool(song.get("video",False)); media_path=await resolve_stream(url, video=want_video)
    except Exception as e:
        try: remove_from_queue(chat_id,0)
        except: pass
        await rich_send(bot,chat_id, rich_heading(f"◍ {sc('download failed')}",level=3)+rich_note(f"<code>{rich_esc(str(e)[:400])}</code>")); return
    is_video=song.get("video",False)
    _vid_exts=(".mkv",".mp4",".webm",".avi",".mov",".m4v",".flv",".wmv",".mpeg",".mpg",".3gp")
    try:
        path_l=str(media_path or song.get("url") or "").lower()
        if any(path_l.endswith(ext) for ext in _vid_exts): is_video=True; song["video"]=True
    except: pass
    if not is_video:
        try:
            from videl.modules.effects import maybe_apply_effects
            media_path=await maybe_apply_effects(chat_id, media_path)
        except Exception as fx_err: LOGGER.warning(f"[Effects] Skipped: {fx_err}")
    played=False
    for attempt in range(2):
        try:
            if is_video: await call_py.play(chat_id, MediaStream(media_path, audio_parameters=AudioQuality.HIGH, video_parameters=VideoQuality.HD_720p))
            else: await call_py.play(chat_id, MediaStream(media_path, audio_parameters=AudioQuality.HIGH, video_flags=MediaStream.Flags.IGNORE))
            played=True; break
        except NoActiveGroupCall:
            if attempt==0:
                LOGGER.info(f"[VC] NoActiveGroupCall — Creating VC in {chat_id}")
                ok=await _ensure_vc(chat_id)
                if ok: continue
                try: remove_from_queue(chat_id,0)
                except: pass
                return
        except TelegramServerError as e:
            LOGGER.error(f"[PLAY] TelegramServerError: {e}")
            try: remove_from_queue(chat_id,0)
            except: pass
            await rich_send(bot,chat_id, rich_heading(f"◍ {sc('playback failed')} — ᴛɢ sᴇʀᴠᴇʀ",level=3)+rich_note(f"<code>{rich_esc(e)}</code>")); return
        except Exception as e:
            err=str(e).lower()
            vc_missing=any(x in err for x in ("groupcallnotfound","not_in_group_call","groupcall_forbidden","not in group call","no active group call"))
            if vc_missing and attempt==0:
                LOGGER.info(f"[VC] Creating VC in {chat_id}"); ok=await _ensure_vc(chat_id)
                if ok: continue
                try: remove_from_queue(chat_id,0)
                except: pass
                return
            if "chat_admin_required" in err or ("admin" in err and "user" not in err):
                LOGGER.error(f"[ADMIN ERROR] {e}"); ok=await _ensure_vc(chat_id)
                if ok: continue
                try: remove_from_queue(chat_id,0)
                except: pass
                return
            try: remove_from_queue(chat_id,0)
            except: pass
            await rich_send(bot,chat_id, rich_heading(f"◍ {sc('playback failed')}",level=3)+rich_note(f"<code>{rich_esc(e)}</code>")); LOGGER.error(f"[PLAY ERROR] {e}"); return
    if not played: return
    try:
        from videl.modules.seek import set_seek_state; set_seek_state(chat_id,0)
    except: pass
    try:
        from videl.database import add_served_chat, add_served_user, increment_play_count
        add_served_chat(chat_id); rid=song.get("requester_id")
        if rid: add_served_user(rid)
        increment_play_count(chat_id)
    except Exception as db_err: LOGGER.warning(f"[DB ERROR] {db_err}")
    total=parse_dur(str(song.get("duration","0:00")))
    if not total and song.get("duration_seconds"): total=float(song["duration_seconds"])
    set_paused(chat_id,False)
    caption=_now_playing_caption(song,0,total,chat_id=chat_id); kb=_now_playing_kb(chat_id); thumb=_thumb_url(song)
    pmsg=None
    photo_unconfirmed=False
    if thumb:
        try:
            pmsg=await visual_call(bot.send_photo,chat_id, photo=thumb, caption=caption, reply_markup=kb)
            try:
                if message and getattr(message,"id",None): await message.delete()
            except Exception: pass
        except BadRequest:
            LOGGER.info("[NP] Thumbnail rejected; using a text card")
        except Exception as exc:
            # Telegram might have accepted it: never duplicate an ambiguous send.
            LOGGER.warning("[NP] Photo delivery unconfirmed (%s); not resending", type(exc).__name__)
            photo_unconfirmed=True
    if pmsg is None and not photo_unconfirmed:
        if message is not None:
            pmsg=await rich_edit(message,caption,reply_markup=kb)
            if pmsg is None: pmsg=message
        else:
            pmsg=await rich_send(bot,chat_id,caption,reply_markup=kb)
    if pmsg is not None:
        asyncio.create_task(_update_progress(chat_id,pmsg,time.time(),total,song))
    if config.LOGGER_ID:
        asyncio.create_task(rich_send(bot,config.LOGGER_ID,
            rich_heading(f"◍ {sc('now playing')} — {rich_esc(short(song.get('title','?'),32))}",level=3)
            + rich_kv_table([("ᴛɪᴛʟᴇ",rich_esc(song.get("title","?"))),("ᴅᴜʀᴀᴛɪᴏɴ",rich_esc(song.get("duration","?"))),("ʙʏ",rich_esc(song.get("requester","?")))])))
