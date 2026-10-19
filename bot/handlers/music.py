"""
Videl0 • Music — ShizuMusic core ported to aiogram
 Supports: /play, /vplay, /playforce, /queue, /skip, /stop, /pause, /resume, /seek, /shuffle, /lyrics, /song, /playlist, /thumbnail, /autoplay, /nowplaying
 Uses Shiruti API + yt-dlp, pytgcalls when assistant available, else file mode.
"""
import asyncio, time, re, logging, os, random
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType

from bot.config import is_sudo, COOLDOWN, QUEUE_LIMIT, MAX_DURATION_SECONDS, BOT_NAME
from bot.database import db
import bot.database_ext
from bot.rich_ui import rich_heading, rich_kv_table, rich_note, rich_img, rich_esc, rich_send, rich_reply
from bot.utils.keyboards import music_controls_kb, queue_kb
from bot.utils.helpers import format_duration, progress_bar
from bot.utils.youtube import search_yt, get_video_info, download_song, resolve_stream, extract_video_id

router = Router()
log=logging.getLogger("videl.music")

_last = {}
_pending={}

BLOCKED_WORDS=["porn","xxx","xnxx","xvideos","sex","lund","drug","cocaine","weed","charas"]

async def _db_track(cid:int, uid:int):
    try: await db.add_chat(cid, None, "group"); await db.add_user(uid, None, None)
    except: pass

# ── Helpers ─────────────────────────────────────────────────────────────────
async def _ensure_vc_possible(bot, chat_id:int) -> tuple[bool,str]:
    """Check if VC feasible — if assistant string session exists, else file mode only."""
    from bot.config import STRING_SESSION, API_ID
    if API_ID and STRING_SESSION:
        return True, "vc"
    return False, "file"

async def _play_song_internal(bot, chat_id:int, song:dict, status_msg: Message|None=None):
    """Actually stream via pytgcalls if possible, else send audio file."""
    from bot.config import STRING_SESSION, API_ID
    has_vc = bool(STRING_SESSION and API_ID)
    # try pytgcalls path
    if has_vc:
        try:
            from bot.services.music_service import call_py, play_via_call  # lazy
            ok=await play_via_call(chat_id, song)
            if ok: return True
        except Exception as e:
            log.warning(f"VC play fail {e}")
    # fallback: send audio file download
    try:
        fp=await download_song(song.get("url") or song.get("link",""))
        if fp and os.path.exists(fp):
            await bot.send_audio(chat_id, audio=open(fp,"rb"), title=song.get("title",""), performer=song.get("channel",""), caption=f"🎵 {song.get('title','')} • requested by {song.get('requester','')}")
            return True
        # if download fails, send stream link
        await bot.send_message(chat_id, f"🎵 <b>{song['title']}</b>\n🔗 <a href=\"{song.get('link','')}\">YouTube</a>\n👤 Requested by {song.get('requester','')}\n\n<i>Download unavailable — streaming link above</i>")
        return True
    except Exception as e:
        log.warning(f"file send fail {e}")
        return False

def _now_playing_rich(song: dict, elapsed=0, total=0, lang=None) -> str:
    # thumbnail via rich_img if enabled
    thumb=song.get("thumbnail") or ""
    thumb_html = rich_img(thumb) if thumb else ""
    bar = progress_bar(elapsed, total)
    return (
        rich_heading("🎶 Now Playing", level=3)
        + thumb_html
        + rich_kv_table([
            ("Title", rich_esc(song.get("title","")[:70])),
            ("Duration", f"<code>{song.get('duration','?')}</code>"),
            ("By", rich_esc(song.get("requester",""))),
            ("Progress", f"<code>{bar}</code> {format_duration(int(elapsed))}/{format_duration(int(total))}" if total else ""),
        ])
        + rich_note(f'🔗 <a href="{song.get("link","")}">{song.get("link","")}</a>')
    )

# ── /play ───────────────────────────────────────────────────────────────────
@router.message(F.text.regexp(r"^/(?:c?v?play)(?:@\w+)?(?:\s+(.+))?$", flags=re.I))
async def play_handler(message: Message):
    text=message.text or ""
    m=re.match(r"^/(?P<cmd>c?v?play)(?:@\w+)?(?:\s+(?P<q>.+))?$", text, re.I)
    if not m: return
    cmd=(m.group("cmd") or "play").lower()
    query=(m.group("q") or "").strip()
    # check reply audio/video
    user=message.from_user
    # determine target chat: /cplay → channel, else group
    chat_id=message.chat.id
    if cmd.startswith("c"):
        ch=await db.get_channel(message.chat.id)
        if ch: chat_id=int(ch)

    # delete command to keep clean
    try: await message.delete()
    except: pass

    # cooldown
    now=time.time()
    if chat_id in _last and now - _last[chat_id] < COOLDOWN:
        rem=int(COOLDOWN-(now-_last[chat_id]))
        if chat_id not in _pending:
            rep=await message.bot.send_message(chat_id, f"⏳ Cooldown {rem}s — queuing your request…")
            _pending[chat_id]=(message, rep, query, cmd)
            async def _later():
                await asyncio.sleep(rem)
                if chat_id in _pending:
                    _, rep2, q2, c2=_pending.pop(chat_id)
                    try: await rep2.delete()
                    except: pass
                    await _do_play(message, q2, c2.startswith("v"), chat_id)
            asyncio.create_task(_later())
        return
    _last[chat_id]=now

    # replied media handling
    if message.reply_to_message and (message.reply_to_message.audio or message.reply_to_message.video):
        orig=message.reply_to_message
        media=orig.audio or orig.video
        if media and getattr(media,"file_size",0) and media.file_size > 100*1024*1024:
            return await message.bot.send_message(chat_id, "❌ File too large (max 100MB).")
        title=getattr(media,"file_name","Audio")
        song={"title":title, "url": getattr(media,"file_id",""), "link": "", "duration":"0:00","duration_seconds": getattr(media,"duration",0) or 0,
              "thumbnail":None, "channel":"Telegram","requester": user.full_name, "requester_id": user.id}
        await db.queue_add(chat_id, title, song["url"], None, int(song["duration_seconds"]), user.id)
        q=await db.queue_list(chat_id)
        if len(q)==1:
            await _play_song_internal(message.bot, chat_id, song)
            await message.bot.send_message(chat_id, _now_playing_rich(song), reply_markup=music_controls_kb())
        else:
            await message.bot.send_message(chat_id, f"➕ Queued #{len(q)}: <b>{title}</b>")
        return

    if not query:
        return await message.bot.send_message(chat_id,
            rich_heading("Usage: /play", level=3)+
            rich_kv_table([("/play <song>", "Search & play audio"),("/vplay <song>","Play video in VC"),("/play + reply to audio","Play that file"),("/cplay <song>","Play in linked channel")])
        )
    # blocked words
    if any(w in query.lower() for w in BLOCKED_WORDS):
        return await message.bot.send_message(chat_id, "🚫 Blocked query.")
    await _do_play(message, query, cmd.endswith("vplay"), chat_id)

async def _do_play(message: Message, query: str, video: bool, chat_id:int):
    user=message.from_user
    # queue limit
    q=await db.queue_list(chat_id)
    if len(q) >= QUEUE_LIMIT:
        return await message.bot.send_message(chat_id, f"❌ Queue full ({QUEUE_LIMIT}). Skip or clear.")

    status=await message.bot.send_message(chat_id, rich_heading("🔍 Searching…", level=3)+rich_note(rich_esc(query)))

    # search
    results=await search_yt(query, limit=1)
    if not results:
        await status.edit_text("❌ No results.")
        return
    info=results[0]
    dur_sec = info.get("duration")
    # parse duration string to sec if needed
    if isinstance(dur_sec, str):
        try: dur_sec = sum(int(x)*60**i for i,x in enumerate(reversed(dur_sec.split(":"))))
        except: dur_sec=0
    dur_sec = int(dur_sec or 0)
    if dur_sec and dur_sec > MAX_DURATION_SECONDS:
        await status.edit_text(f"❌ Too long ({format_duration(dur_sec)} > {format_duration(MAX_DURATION_SECONDS)}).")
        return
    thumb = (info.get("thumbnails") or [{}])[0].get("url") if info.get("thumbnails") else info.get("thumbnail","")
    link = info.get("link") or f"https://www.youtube.com/watch?v={info.get('id','')}"
    song={
        "title": info.get("title","Unknown"),
        "link": link,
        "url": link,
        "duration": info.get("duration","0:00"),
        "duration_seconds": dur_sec,
        "thumbnail": thumb,
        "channel": info.get("channel","YouTube"),
        "requester": user.full_name,
        "requester_id": user.id,
    }
    pos=await db.queue_add(chat_id, song["title"], song["url"], thumb, dur_sec, user.id)
    q=await db.queue_list(chat_id)
    # if first -> play now
    if len(q)==1:
        await status.edit_text(_now_playing_rich(song), reply_markup=music_controls_kb())
        await _play_song_internal(message.bot, chat_id, song, status)
    else:
        await status.edit_text(
            rich_heading("➕ Queued", level=3)+
            rich_kv_table([("Title", rich_esc(song["title"])),("Position", f"#{pos+1}"),("Duration", str(song["duration"]))]),
            reply_markup=music_controls_kb()
        )

# ── /queue ─────────────────────────────────────────────────────────────────
@router.message(Command("queue"))
async def queue_cmd(message: Message):
    q=await db.queue_list(message.chat.id)
    if not q: return await message.answer("📭 Queue empty. Use /play <song>")
    txt=rich_heading("📜 Queue", level=3)
    for i, s in enumerate(q[:10], 1):
        emoji="▶️" if i==1 else f"{i}."
        txt+=rich_kv_table([ (f"{emoji} {rich_esc(s['title'][:40])}", f"<code>{format_duration(s.get('duration') or 0)}</code> • {rich_esc(str(s.get('requested_by','')))}") ])
    if len(q)>10: txt+=rich_note(f"+ {len(q)-10} more…")
    await message.answer(txt, reply_markup=queue_kb())

# ── /skip ──────────────────────────────────────────────────────────────────
@router.message(Command("skip"))
async def skip_cmd(message: Message):
    q=await db.queue_list(message.chat.id)
    if not q: return await message.answer("📭 Nothing to skip.")
    skipped=await db.queue_pop(message.chat.id)
    nxt=(await db.queue_list(message.chat.id))
    if nxt:
        ns=nxt[0]
        await message.answer(rich_heading("⏭ Skipped", level=3)+rich_note(f"Was: {rich_esc(skipped['title'])}<br>Now: {rich_esc(ns['title'])}"), reply_markup=music_controls_kb())
        # attempt play next
        await _play_song_internal(message.bot, message.chat.id, {"title":ns["title"],"url":ns["url"],"link":ns["url"],"duration":format_duration(ns.get("duration",0)),"duration_seconds":ns.get("duration",0),"requester":str(ns.get("requested_by",""))})
    else:
        await message.answer("⏹ Queue empty — stopped.")
        try:
            from bot.services.music_service import stop_call
            await stop_call(message.chat.id)
        except: pass

# ── /stop /end ──────────────────────────────────────────────────────────────
@router.message(Command("stop","end","clear"))
async def stop_cmd(message: Message):
    await db.queue_clear(message.chat.id)
    try:
        from bot.services.music_service import stop_call
        await stop_call(message.chat.id)
    except: pass
    await message.answer("⏹ Stopped & queue cleared.")

# ── /pause /resume ──────────────────────────────────────────────────────────
@router.message(Command("pause"))
async def pause_cmd(message: Message):
    try:
        from bot.services.music_service import pause_call
        await pause_call(message.chat.id); await message.answer("⏸ Paused.")
    except Exception as e: await message.answer(f"Pause: {e} • (file mode: no VC pause)")

@router.message(Command("resume"))
async def resume_cmd(message: Message):
    try:
        from bot.services.music_service import resume_call
        await resume_call(message.chat.id); await message.answer("▶️ Resumed.")
    except: await message.answer("▶️ Resumed (file mode).")

# ── /seek ──────────────────────────────────────────────────────────────────
@router.message(Command("seek"))
async def seek_cmd(message: Message):
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not arg: return await message.reply("Usage: /seek <seconds> e.g. /seek 30 /seek -10")
    try:
        secs=int(arg)
        from bot.services.music_service import seek_call
        await seek_call(message.chat.id, secs)
        await message.answer(f"⏩ Seek {secs}s")
    except Exception as e: await message.reply(f"Seek fail: {e}")

# ── /shuffle ────────────────────────────────────────────────────────────────
@router.message(Command("shuffle"))
async def shuffle_cmd(message: Message):
    await db.queue_shuffle(message.chat.id)
    await message.answer("🔀 Shuffled queue (kept current).")

# ── /nowplaying ────────────────────────────────────────────────────────────
@router.message(Command("nowplaying","np","current"))
async def np_cmd(message: Message):
    q=await db.queue_list(message.chat.id)
    if not q: return await message.answer("📭 Nothing playing.")
    s=q[0]
    song={"title":s["title"],"link":s["url"],"duration":format_duration(s.get("duration",0)),"requester":str(s.get("requested_by","")),"thumbnail":s.get("thumbnail")}
    await message.answer(_now_playing_rich(song), reply_markup=music_controls_kb())

# ── /lyrics /song ──────────────────────────────────────────────────────────
@router.message(Command("lyrics","song"))
async def lyrics_cmd(message: Message):
    query=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not query:
        q=await db.queue_list(message.chat.id)
        query=q[0]["title"] if q else ""
        if not query: return await message.reply("Usage: /lyrics <song name>")
    # Genius API if key else fallback search
    from bot.config import GENIUS_API_KEY
    lyrics=None
    if GENIUS_API_KEY:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as sess:
                async with sess.get("https://api.genius.com/search", headers={"Authorization": f"Bearer {GENIUS_API_KEY}"}, params={"q":query}) as r:
                    if r.status==200:
                        j=await r.json(); hits=j.get("response",{}).get("hits",[])
                        if hits: lyrics=f"Found on Genius: {hits[0]['result']['url']}"
        except: pass
    if not lyrics:
        # fallback poll via lyrics.ovh
        try:
            import aiohttp
            parts=query.split("-")
            artist=parts[0].strip() if len(parts)>1 else "Unknown"
            title=parts[1].strip() if len(parts)>1 else query
            async with aiohttp.ClientSession() as sess:
                async with sess.get(f"https://api.lyrics.ovh/v1/{artist}/{title}") as r:
                    if r.status==200:
                        j=await r.json(); lyrics=j.get("lyrics","")
        except: pass
    if lyrics:
        if len(lyrics)>3800: lyrics=lyrics[:3800]+"…"
        await message.answer(rich_heading(f"🎤 Lyrics — {query}", level=3)+rich_note(f"<pre>{rich_esc(lyrics)}</pre>"))
    else:
        await message.answer(rich_heading("🎤 Lyrics", level=3)+rich_note(f"No lyrics found for <code>{rich_esc(query)}</code>.<br>Try: <a href=\"https://genius.com/search?q={query.replace(' ','+')}\">Genius Search</a>"))

# ── /playlist ──────────────────────────────────────────────────────────────
@router.message(Command("playlist"))
async def playlist_cmd(message: Message):
    args=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip()
    uid=message.from_user.id
    if not args:
        return await message.answer(rich_heading("📂 Playlist", level=3)+rich_note("Usage:<br><code>/playlist create &lt;name&gt;</code><br><code>/playlist add &lt;name&gt; &lt;song&gt;</code><br><code>/playlist play &lt;name&gt;</code>"))
    parts=args.split(maxsplit=1)
    sub=parts[0].lower()
    rest=parts[1] if len(parts)>1 else ""
    if sub=="create":
        if not rest: return await message.reply("Give a name: /playlist create mylist")
        await db.add_playlist(uid, rest, [])
        await message.answer(f"✅ Created playlist <code>{rest}</code>")
    elif sub=="add":
        if not rest or " " not in rest: return await message.reply("Usage: /playlist add <name> <song>")
        name,song_q=rest.split(maxsplit=1)
        pl=await db.get_playlist(uid, name)
        if not pl: return await message.reply("Playlist not found. Create first.")
        tracks=pl.get("tracks") or []
        if len(tracks) >= 50: return await message.reply("Playlist full (50).")
        # search song
        res=await search_yt(song_q, limit=1)
        if not res: return await message.reply("Song not found.")
        tracks.append({"title":res[0]["title"], "link": res[0]["link"]})
        await db.add_playlist(uid, name, tracks)
        await message.answer(f"➕ Added to <code>{name}</code>: {res[0]['title']}")
    elif sub=="play":
        name=rest.strip()
        pl=await db.get_playlist(uid, name)
        if not pl or not pl.get("tracks"): return await message.reply("Playlist empty / not found.")
        for tr in pl["tracks"]:
            await db.queue_add(message.chat.id, tr["title"], tr["link"], None, 0, uid)
        await message.answer(f"▶️ Queued {len(pl['tracks'])} from <code>{name}</code>")
        # start first if queue was empty before
        q=await db.queue_list(message.chat.id)
        if len(q)==len(pl["tracks"]):
            first=q[0]; await _play_song_internal(message.bot, message.chat.id, {"title":first["title"],"url":first["url"],"link":first["url"],"requester":message.from_user.full_name})
    else:
        await message.reply("Unknown subcommand. Use create/add/play")

# ── /thumbnail /autoplay toggles ──────────────────────────────────────────
@router.message(Command("thumbnail"))
async def thumbnail_cmd(message: Message):
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").lower()
    if arg in ("on","enable","true"): await db.set_thumbnail(message.chat.id, True); await message.answer("🖼 Thumbnail ON")
    elif arg in ("off","disable","false"): await db.set_thumbnail(message.chat.id, False); await message.answer("🖼 Thumbnail OFF")
    else: on=await db.is_thumbnail_enabled(message.chat.id); await message.answer(f"🖼 Thumbnail is {'ON' if on else 'OFF'} — use /thumbnail on/off")

@router.message(Command("autoplay"))
async def autoplay_cmd(message: Message):
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").lower()
    if arg in ("on","enable","true"): await db.set_autoplay(message.chat.id, True); await message.answer("🍷 Autoplay ON")
    elif arg in ("off","disable","false"): await db.set_autoplay(message.chat.id, False); await message.answer("🍷 Autoplay OFF")
    else: on=await db.is_autoplay(message.chat.id); await message.answer(f"🍷 Autoplay is {'ON' if on else 'OFF'}")
