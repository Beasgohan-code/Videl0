"""
Videl0 • YouTube Helpers — ported from ShizuMusic + enhanced
Handles search, resolve, download via Shruti API → yt-dlp fallback.
"""
import asyncio, os, re, logging
from typing import Optional
import aiohttp, aiofiles

from bot.config import YT_API_URL, YT_API_KEY, DOWNLOAD_DIR, YT_STREAM_TIMEOUT, MAX_DURATION_SECONDS

logger = logging.getLogger("videl.yt")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def extract_video_id(url: str) -> str:
    if not url: return ""
    if "v=" in url: return url.split("v=")[-1].split("&")[0].split("/")[0]
    if "youtu.be/" in url: return url.split("youtu.be/")[-1].split("?")[0].split("/")[0]
    if "youtube.com/shorts/" in url: return url.split("/shorts/")[-1].split("?")[0].split("/")[0]
    return url.strip()

def time_to_seconds(t) -> int:
    s=str(t)
    return sum(int(x)*60**i for i,x in enumerate(reversed(s.split(":"))))

async def search_yt(query: str, limit:int=1) -> list[dict]:
    """Search YouTube — tries py-yt then youtube_search fallback."""
    if not query: return []
    # try py_yt
    try:
        from py_yt import VideosSearch
        vs=VideosSearch(query, limit=limit)
        res=await vs.next()
        out=[]
        for r in res.get("result",[])[:limit]:
            out.append({
                "title": r.get("title",""),
                "link": r.get("link",""),
                "id": r.get("id",""),
                "duration": r.get("duration","0:00"),
                "channel": r.get("channel",{}).get("name",""),
                "thumbnails": r.get("thumbnails",[]),
                "views": r.get("viewCount",{}).get("short",""),
            })
        if out: return out
    except Exception as e:
        logger.debug(f"VideosSearch failed: {e}")

    # fallback youtubesearchpython
    try:
        from youtubesearchpython import VideosSearch as YTVS
        vs=YTVS(query, limit=limit)
        res=vs.result()
        out=[]
        for r in res.get("result",[])[:limit]:
            out.append({
                "title": r.get("title",""),
                "link": r.get("link",""),
                "id": r.get("id",""),
                "duration": r.get("duration","0:00"),
                "channel": r.get("channel",{}).get("name",""),
                "thumbnails": r.get("thumbnails",[]),
            })
        return out
    except Exception as e:
        logger.debug(f"YTVS fallback failed: {e}")
    return []

async def get_video_info(url_or_id: str) -> Optional[dict]:
    """Get video metadata via search + yt-dlp probe."""
    vid=extract_video_id(url_or_id)
    # try yt-dlp probe for accuracy
    try:
        import yt_dlp
        ydl_opts={"quiet":True,"no_warnings":True,"skip_download":True}
        loop=asyncio.get_event_loop()
        def _probe():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info=ydl.extract_info(f"https://www.youtube.com/watch?v={vid}" if len(vid)==11 else url_or_id, download=False)
                return info
        info=await loop.run_in_executor(None, _probe)
        return {
            "title": info.get("title",""),
            "id": info.get("id",vid),
            "link": info.get("webpage_url", f"https://www.youtube.com/watch?v={vid}"),
            "duration": info.get("duration",0),
            "duration_str": info.get("duration_string",""),
            "thumbnail": info.get("thumbnail",""),
            "uploader": info.get("uploader",""),
            "view_count": info.get("view_count",0),
        }
    except Exception:
        # fallback search
        lst=await search_yt(url_or_id, limit=1)
        return lst[0] if lst else None

async def download_song(link: str) -> Optional[str]:
    vid=extract_video_id(link)
    if not vid or len(vid)<3: return None
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    fp=os.path.join(DOWNLOAD_DIR, f"{vid}.mp3")
    if os.path.exists(fp) and os.path.getsize(fp)>0: return fp
    # Shruti API
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(f"{YT_API_URL}/download", params={"url":vid,"type":"audio","api_key":YT_API_KEY},
                                timeout=aiohttp.ClientTimeout(total=YT_STREAM_TIMEOUT)) as r:
                if r.status==200:
                    async with aiofiles.open(fp,"wb") as f:
                        async for ch in r.content.iter_chunked(131072): await f.write(ch)
                    if os.path.exists(fp) and os.path.getsize(fp)>0: return fp
    except Exception as e: logger.debug(f"shruti audio fail: {e}")
    # yt-dlp fallback
    try:
        import yt_dlp
        ydl_opts={"format":"bestaudio/best","outtmpl":fp.replace(".mp3",".%(ext)s"),"quiet":True,"no_warnings":True,
                  "postprocessors":[{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]}
        if os.path.exists("cookies.txt"): ydl_opts["cookiefile"]="cookies.txt"
        loop=asyncio.get_event_loop()
        def _dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={vid}" if len(vid)==11 else link])
        await loop.run_in_executor(None, _dl)
        # find file
        for ext in (".mp3",".m4a",".webm"):
            p=fp.replace(".mp3",ext)
            if os.path.exists(p): return p
        if os.path.exists(fp): return fp
    except Exception as e: logger.debug(f"yt-dlp audio fail: {e}")
    return None

async def resolve_stream(link: str) -> Optional[str]:
    """Return direct audio stream URL (for pytgcalls MediaStream). Uses yt-dlp extract."""
    vid=extract_video_id(link)
    try:
        import yt_dlp
        ydl_opts={"format":"bestaudio[ext=m4a]/bestaudio/best","quiet":True,"no_warnings":True,"skip_download":True}
        if os.path.exists("cookies.txt"): ydl_opts["cookiefile"]="cookies.txt"
        loop=asyncio.get_event_loop()
        def _ex():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info=ydl.extract_info(f"https://www.youtube.com/watch?v={vid}" if len(vid)==11 else link, download=False)
                return info.get("url") or info.get("requested_formats",[{}])[0].get("url")
        url=await loop.run_in_executor(None, _ex)
        return url
    except Exception as e:
        logger.debug(f"resolve_stream fail: {e}")
        return None

async def resolve_video_stream(link: str) -> Optional[str]:
    vid=extract_video_id(link)
    try:
        import yt_dlp
        ydl_opts={"format":"best[height<=720]/best","quiet":True,"no_warnings":True,"skip_download":True}
        if os.path.exists("cookies.txt"): ydl_opts["cookiefile"]="cookies.txt"
        loop=asyncio.get_event_loop()
        def _ex():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info=ydl.extract_info(f"https://www.youtube.com/watch?v={vid}" if len(vid)==11 else link, download=False)
                return info.get("url")
        return await loop.run_in_executor(None, _ex)
    except: return None
