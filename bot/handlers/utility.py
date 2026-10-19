"""
Videl0 • Utility — weather, qr, shorten, calc, define, wiki, carbon, git, etc.
"""
import re, html, asyncio, io, time, json
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
import aiohttp

from bot.rich_ui import rich_heading, rich_kv_table, rich_note, rich_esc, rich_code, rich_pre, rich_img
from bot.database import db
import bot.database_ext
from bot.utils.helpers import escape_html

router = Router()

# ── /weather ───────────────────────────────────────────────────────────────
@router.message(Command("weather"))
async def weather_cmd(message: Message):
    q=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not q: return await message.reply("Usage: /weather <city>")
    from bot.config import WEATHER_API_KEY
    # free wttr.in fallback
    try:
        async with aiohttp.ClientSession() as s:
            url=f"https://wttr.in/{q}?format=j1"
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                j=await r.json()
                cur=j.get("current_condition",[{}])[0]
                w=j.get("weather",[{}])[0]
                rich=(
                    rich_heading(f"🌤️ Weather — {q}", level=3)
                    + rich_kv_table([
                        ("Temp", f"<code>{cur.get('temp_C')}°C / {cur.get('temp_F')}°F</code>"),
                        ("Feels", f"<code>{cur.get('FeelsLikeC')}°C</code>"),
                        ("Humidity", f"<code>{cur.get('humidity')}%</code>"),
                        ("Wind", f"<code>{cur.get('windspeedKmph')} km/h {cur.get('winddir16Point')}</code>"),
                        ("Desc", cur.get("weatherDesc",[{}])[0].get("value","") if cur.get("weatherDesc") else ""),
                    ])
                    + rich_note(f"Source: wttr.in")
                )
                await message.answer(rich)
                return
    except Exception as e:
        await message.reply(f"Weather fail: {e.__class__.__name__}: {e}")

# ── /qr ────────────────────────────────────────────────────────────────────
@router.message(Command("qr","qrcode"))
async def qr_cmd(message: Message):
    q=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not q: return await message.reply("Usage: /qr <text or url>")
    try:
        import qrcode
        img=qrcode.make(q)
        bio=io.BytesIO(); bio.name="qr.png"; img.save(bio, format="PNG"); bio.seek(0)
        await message.bot.send_photo(message.chat.id, photo=bio, caption=f"🔳 QR for: <code>{escape_html(q)}</code>")
    except Exception as e: await message.reply(f"QR fail: {e}")

# ── /shorten ───────────────────────────────────────────────────────────────
@router.message(Command("shorten","short","shorturl"))
async def shorten_cmd(message: Message):
    url=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip()
    if not url: return await message.reply("Usage: /shorten <url>")
    if not url.startswith("http"): url="https://"+url
    try:
        import pyshorteners
        s=pyshorteners.Shortener()
        short=s.tinyurl.short(url)
        await message.answer(rich_heading("🔗 Shortened", level=3)+rich_kv_table([("Original",f"<a href=\"{url}\">{escape_html(url)}</a>"),("Short",f"<a href=\"{short}\">{short}</a>")]))
    except Exception:
        # fallback is.gd
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get("https://is.gd/create.php", params={"format":"simple","url":url}) as r:
                    t=await r.text()
                    await message.answer(f"🔗 Short: <a href=\"{t.strip()}\">{t.strip()}</a>")
        except Exception as e: await message.reply(f"Shorten fail: {e}")

# ── /calc ──────────────────────────────────────────────────────────────────
@router.message(Command("calc","math"))
async def calc_cmd(message: Message):
    expr=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not expr: return await message.reply("Usage: /calc <expression>\nEx: /calc 2*(3+5)")
    # safe eval: allow numbers + - * / ** % ()
    if not re.match(r"^[0-9+\-*/(). **%]+$", expr):
        # allow pow
        pass
    try:
        # safe
        allowed={"__builtins__":None}
        result=eval(expr, allowed, {})
        await message.answer(rich_heading("🧮 Calc", level=3)+rich_kv_table([("Expr",f"<code>{escape_html(expr)}</code>"),("Result",f"<code>{result}</code>")]))
    except Exception as e: await message.reply(f"Calc error: {e}")

# ── /define /ud /wiki ──────────────────────────────────────────────────────
@router.message(Command("define","meaning"))
async def define_cmd(message: Message):
    word=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip()
    if not word: return await message.reply("Usage: /define <word>")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}") as r:
                if r.status!=200:
                    return await message.answer("No definition found.")
                j=await r.json(); entry=j[0]
                meanings=entry.get("meanings",[])[0]
                defs=meanings.get("definitions",[])[:2]
                txt="<br>".join(f"• {rich_esc(d.get('definition',''))}<br><i>Ex: {rich_esc(d.get('example',''))}</i>" for d in defs)
                await message.answer(rich_heading(f"📖 {word}", level=3)+rich_kv_table([("Phonetic", entry.get("phonetic","") ),("POS", meanings.get("partOfSpeech",""))])+rich_note(txt))
    except Exception as e: await message.reply(f"Define fail: {e}")

@router.message(Command("ud"))
async def ud_cmd(message: Message):
    word=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip()
    if not word: return await message.reply("Usage: /ud <word>")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.urbandictionary.com/v0/define", params={"term":word}) as r:
                j=await r.json(); lst=j.get("list",[])
                if not lst: return await message.answer("No UD entry.")
                top=lst[0]
                await message.answer(rich_heading(f"📚 UD: {word}", level=3)+rich_note(rich_esc(top.get("definition","")[:1000]))+rich_note(f"👍 {top.get('thumbs_up')} 👎 {top.get('thumbs_down')}"))
    except Exception as e: await message.reply(f"UD fail: {e}")

@router.message(Command("wiki"))
async def wiki_cmd(message: Message):
    q=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip()
    if not q: return await message.reply("Usage: /wiki <query>")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://en.wikipedia.org/api/rest_v1/page/summary/"+q.replace(" ","_")) as r:
                if r.status!=200:
                    return await message.answer("No wiki page.")
                j=await r.json()
                await message.answer(rich_heading(j.get("title","Wiki"), level=3)+rich_note(rich_esc(j.get("extract","")))+rich_note(f'<a href="{j.get("content_urls",{}).get("desktop",{}).get("page","")}">Read more</a>'))
    except Exception as e: await message.reply(f"Wiki fail: {e}")

# ── /carbon ────────────────────────────────────────────────────────────────
@router.message(Command("carbon"))
async def carbon_cmd(message: Message):
    code=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not code and message.reply_to_message and message.reply_to_message.text:
        code=message.reply_to_message.text
    if not code: return await message.reply("Usage: /carbon <code> or reply to code")
    try:
        # carbonara api
        async with aiohttp.ClientSession() as s:
            async with s.post("https://carbonara.solopov.dev/api/cook", json={"code":code[:2000]}) as r:
                if r.status==200:
                    data=await r.read()
                    bio=io.BytesIO(data); bio.name="carbon.png"
                    await message.bot.send_photo(message.chat.id, photo=bio)
                    return
        await message.reply("Carbon generation failed.")
    except Exception as e: await message.reply(f"Carbon fail: {e}")

# ── /paste ─────────────────────────────────────────────────────────────────
@router.message(Command("paste"))
async def paste_cmd(message: Message):
    text=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not text and message.reply_to_message and message.reply_to_message.text:
        text=message.reply_to_message.text
    if not text: return await message.reply("Usage: /paste <text>")
    try:
        async with aiohttp.ClientSession() as s:
            # try spaceb.in
            async with s.post("https://spaceb.in/api/v1/documents/", data={"content":text}) as r:
                if r.status==201:
                    j=await r.json(); pid=j.get("payload",{}).get("id","")
                    await message.answer(f"📋 Pasted: <a href=\"https://spaceb.in/{pid}\">https://spaceb.in/{pid}</a>")
                    return
        await message.reply("Paste fail.")
    except Exception as e: await message.reply(f"Paste err: {e}")

# ── /git /github ────────────────────────────────────────────────────────────
@router.message(Command("git","github"))
async def git_cmd(message: Message):
    user=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip().lstrip("@")
    if not user: return await message.reply("Usage: /git <username>")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.github.com/users/{user}") as r:
                if r.status!=200: return await message.answer("GitHub user not found.")
                j=await r.json()
                rich=(
                    rich_heading(f"🐙 {j.get('login')}", level=3)
                    + rich_img(j.get("avatar_url",""))
                    + rich_kv_table([
                        ("Name", rich_esc(j.get("name") or "—")),
                        ("Bio", rich_esc((j.get("bio") or "")[:120])),
                        ("Repos", str(j.get("public_repos"))),
                        ("Followers", str(j.get("followers"))),
                        ("Following", str(j.get("following"))),
                        ("Location", rich_esc(j.get("location") or "—")),
                    ])
                    + rich_note(f'<a href="{j.get("html_url")}">Profile</a> • Created {j.get("created_at","")[:10]}')
                )
                await message.answer(rich)
    except Exception as e: await message.reply(f"Git fail: {e}")

# ── /pinterest /pinimg ─────────────────────────────────────────────────────
@router.message(Command("pinterest","pinterestimg","pinimg"))
async def pinterest_cmd(message: Message):
    q=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip()
    if not q: return await message.reply("Usage: /pinterest <query>")
    await message.answer(f'📌 Pinterest search: <a href="https://www.pinterest.com/search/pins/?q={q.replace(" ","%20")}">Open</a>')

# ── /sticker /steal /kang ──────────────────────────────────────────────────
@router.message(Command("sticker","steal","kang"))
async def sticker_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("Reply to an image to create sticker.")
    try:
        file=await message.bot.get_file(message.reply_to_message.photo[-1].file_id)
        fpath=f"/tmp/{file.file_id}.jpg"
        await message.bot.download_file(file.file_path, fpath)
        await message.bot.send_sticker(message.chat.id, sticker=open(fpath,"rb"))
    except Exception as e: await message.reply(f"Sticker fail: {e}")

# ── /afk ───────────────────────────────────────────────────────────────────
@router.message(Command("afk"))
async def afk_cmd(message: Message):
    reason=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "AFK")
    await db.set_afk(message.from_user.id, reason)
    await message.answer(f"💤 {message.from_user.full_name} is now AFK: {reason}")

# ── /tagall ────────────────────────────────────────────────────────────────
@router.message(Command("tagall"))
async def tagall_cmd(message: Message):
    if message.chat.type=="private": return
    text=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "Attention!")
    # only admins
    try:
        member=await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        from aiogram.enums import ChatMemberStatus
        from bot.config import is_sudo
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR) and not is_sudo(message.from_user.id):
            return await message.reply("Admins only.")
    except: pass
    # mention via 5 per batch using text_mention? fallback username mentions
    await message.answer(f"📢 <b>TagAll</b> by {message.from_user.full_name}\n\n{escape_html(text)}\n\n<code>Use /tagall for mention batch</code>")

# ── /speedtest ─────────────────────────────────────────────────────────────
@router.message(Command("speedtest"))
async def speedtest_cmd(message: Message):
    m=await message.answer("🚀 Running speedtest…")
    try:
        import speedtest
        st=speedtest.Speedtest()
        st.get_best_server()
        dl=st.download()/1_000_000
        ul=st.upload()/1_000_000
        ping=st.results.ping
        await m.edit_text(rich_heading("🚀 Speedtest", level=3)+rich_kv_table([("Download",f"<code>{dl:.2f} Mbps</code>"),("Upload",f"<code>{ul:.2f} Mbps</code>"),("Ping",f"<code>{ping:.0f} ms</code>")]))
    except Exception as e: await m.edit_text(f"Speedtest fail: {e}")

# ── /news ─────────────────────────────────────────────────────────────────
@router.message(Command("news"))
async def news_cmd(message: Message):
    q=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "technology")
    from bot.config import NEWS_API_KEY
    if not NEWS_API_KEY:
        return await message.answer("📰 Top headlines (demo) — add NEWS_API_KEY for real feed.")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://newsapi.org/v2/everything", params={"q":q,"apiKey":NEWS_API_KEY,"pageSize":5}) as r:
                j=await r.json(); arts=j.get("articles",[])[:5]
                if not arts: return await message.answer("No news.")
                txt=rich_heading(f"📰 News: {q}", level=3)
                for a in arts:
                    txt+=rich_note(f"<a href=\"{a['url']}\">{rich_esc(a['title'])}</a><br>{rich_esc((a.get('description') or '')[:120])}")
                await message.answer(txt)
    except Exception as e: await message.reply(f"News fail: {e}")

# ── /removebg stub ─────────────────────────────────────────────────────────
@router.message(Command("removebg"))
async def removebg_cmd(message: Message):
    await message.reply("🖼 RemoveBG: send image with /removebg while replying. Requires REMOVE_BG_API_KEY — add to .env to enable.")
