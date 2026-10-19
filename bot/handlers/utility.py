"""
Videl0 • Utility — Cyber Dark Perfected
◍ weather ⬪ qr ⫶ shorten ⣂ calc ⫶ wiki ◎ git ◍ etc
"""
import re, html, asyncio, io, time, json
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
import aiohttp

from bot.rich_ui import rich_heading, rich_kv_table, rich_note, rich_esc, rich_img
from bot.database import db
import bot.database_ext
from bot.utils.helpers import escape_html
from bot.utils.fonts import sc, sb

router = Router()

# ── /weather — ◍ ᴡᴇᴀᴛʜᴇʀ ───────────────────────────────────────────────────
@router.message(Command("weather"))
async def weather_cmd(message: Message):
    q=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not q: return await message.reply(f"◍ {sc('usage')}: /weather <{sc('city')}> ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://wttr.in/{q}?format=j1", timeout=aiohttp.ClientTimeout(total=10)) as r:
                j=await r.json()
                cur=j.get("current_condition",[{}])[0]
                await message.answer(
                    rich_heading(f"◍ {sc('weather')} — {q} ◍", level=3)
                    + rich_kv_table([
                        (sc("temp"), f"<code>{cur.get('temp_C')}°C / {cur.get('temp_F')}°F</code>"),
                        (sc("feels"), f"<code>{cur.get('FeelsLikeC')}°C</code>"),
                        (sc("humidity"), f"<code>{cur.get('humidity')}%</code>"),
                        (sc("wind"), f"<code>{cur.get('windspeedKmph')} km/h {cur.get('winddir16Point')}</code>"),
                        (sc("desc"), cur.get("weatherDesc",[{}])[0].get("value","") if cur.get("weatherDesc") else ""),
                    ])
                    + rich_note(f"◍ {sc('source: wttr.in')} ◍")
                )
                return
    except Exception as e:
        await message.reply(f"◍ {sc('weather failed')}: {e} ◍")

# ── /qr — ⫶ ǫʀ ────────────────────────────────────────────────────────────────
@router.message(Command("qr","qrcode"))
async def qr_cmd(message: Message):
    q=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not q: return await message.reply(f"◍ {sc('usage')}: /qr <{sc('text or url')}> ◍")
    try:
        import qrcode
        img=qrcode.make(q)
        bio=io.BytesIO(); bio.name="qr.png"; img.save(bio, format="PNG"); bio.seek(0)
        await message.bot.send_photo(message.chat.id, photo=bio, caption=f"◍ {sc('qr for')}: <code>{escape_html(q)}</code> ◍")
    except Exception as e: await message.reply(f"◍ {sc('qr failed')}: {e} ◍")

# ── /shorten — ⬪ sʜᴏʀᴛᴇɴ ────────────────────────────────────────────────────
@router.message(Command("shorten","short","shorturl"))
async def shorten_cmd(message: Message):
    url=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip()
    if not url: return await message.reply(f"◍ {sc('usage')}: /shorten <{sc('url')}> ◍")
    if not url.startswith("http"): url="https://"+url
    try:
        import pyshorteners
        s=pyshorteners.Shortener()
        short=s.tinyurl.short(url)
        await message.answer(rich_heading(f"⬪ {sc('shortened')} ⬪", level=3)+rich_kv_table([(sc("original"),f"<a href=\"{url}\">{escape_html(url)}</a>"),(sc("short"),f"<a href=\"{short}\">{short}</a>")]))
    except:
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get("https://is.gd/create.php", params={"format":"simple","url":url}) as r:
                    t=await r.text()
                    await message.answer(f"◍ {sc('short')}: <a href=\"{t.strip()}\">{t.strip()}</a> ◍")
        except Exception as e: await message.reply(f"◍ {sc('shorten failed')}: {e} ◍")

# ── /calc — ⫶ ᴄᴀʟᴄ ──────────────────────────────────────────────────────────
@router.message(Command("calc","math"))
async def calc_cmd(message: Message):
    expr=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not expr: return await message.reply(f"◍ {sc('usage')}: /calc <{sc('expression')}> ◍ ⫶ /calc 2*(3+5)")
    try:
        result=eval(expr, {"__builtins__":None}, {})
        await message.answer(rich_heading(f"⫶ {sc('calc')} ⫶", level=3)+rich_kv_table([(sc("expr"),f"<code>{escape_html(expr)}</code>"),(sc("result"),f"<code>{result}</code>")]))
    except Exception as e: await message.reply(f"◍ {sc('calc error')}: {e} ◍")

# ── /define /ud /wiki — ◎ ────────────────────────────────────────────────────
@router.message(Command("define","meaning"))
async def define_cmd(message: Message):
    word=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip()
    if not word: return await message.reply(f"◍ {sc('usage')}: /define <{sc('word')}> ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}") as r:
                if r.status!=200: return await message.answer(f"◍ {sc('no definition found')} ◍")
                j=await r.json(); entry=j[0]
                meanings=entry.get("meanings",[])[0]
                defs=meanings.get("definitions",[])[:2]
                txt="<br>".join(f"⫶ {rich_esc(d.get('definition',''))}" for d in defs)
                await message.answer(rich_heading(f"◍ {sc(word)} ◍", level=3)+rich_kv_table([(sc("phonetic"), entry.get("phonetic","") ),(sc("pos"), meanings.get("partOfSpeech",""))])+rich_note(txt))
    except Exception as e: await message.reply(f"◍ {sc('define failed')}: {e} ◍")

@router.message(Command("ud"))
async def ud_cmd(message: Message):
    word=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip()
    if not word: return await message.reply(f"◍ {sc('usage')}: /ud <{sc('word')}> ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.urbandictionary.com/v0/define", params={"term":word}) as r:
                j=await r.json(); lst=j.get("list",[])
                if not lst: return await message.answer(f"◍ {sc('no ud entry')} ◍")
                top=lst[0]
                await message.answer(rich_heading(f"◍ {sc(f'ud: {word}')} ◍", level=3)+rich_note(rich_esc(top.get("definition","")[:1000]))+rich_note(f"⫶ {top.get('thumbs_up')} ⬪ {top.get('thumbs_down')}"))
    except Exception as e: await message.reply(f"◍ {sc('ud failed')}: {e} ◍")

@router.message(Command("wiki"))
async def wiki_cmd(message: Message):
    q=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip()
    if not q: return await message.reply(f"◍ {sc('usage')}: /wiki <{sc('query')}> ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://en.wikipedia.org/api/rest_v1/page/summary/"+q.replace(" ","_")) as r:
                if r.status!=200: return await message.answer(f"◍ {sc('no wiki page')} ◍")
                j=await r.json()
                await message.answer(rich_heading(f"◎ {sc(j.get('title','wiki'))} ◎", level=3)+rich_note(rich_esc(j.get("extract","")))+rich_note(f'◍ <a href="{j.get("content_urls",{}).get("desktop",{}).get("page","")}">{sc("read more")}</a> ◍'))
    except Exception as e: await message.reply(f"◍ {sc('wiki failed')}: {e} ◍")

# ── /carbon — ◍ ᴄᴀʀʙᴏɴ ────────────────────────────────────────────────────────
@router.message(Command("carbon"))
async def carbon_cmd(message: Message):
    code=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not code and message.reply_to_message and message.reply_to_message.text: code=message.reply_to_message.text
    if not code: return await message.reply(f"◍ {sc('usage')}: /carbon <{sc('code')}> {sc('or reply')} ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post("https://carbonara.solopov.dev/api/cook", json={"code":code[:2000]}) as r:
                if r.status==200:
                    data=await r.read()
                    bio=io.BytesIO(data); bio.name="carbon.png"
                    await message.bot.send_photo(message.chat.id, photo=bio, caption=f"◍ {sc('carbon')} ◍")
                    return
        await message.reply(f"◍ {sc('carbon failed')} ◍")
    except Exception as e: await message.reply(f"◍ {sc('carbon failed')}: {e} ◍")

# ── /paste — ⬪ ᴘᴀsᴛᴇ ───────────────────────────────────────────────────────────
@router.message(Command("paste"))
async def paste_cmd(message: Message):
    text=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not text and message.reply_to_message and message.reply_to_message.text: text=message.reply_to_message.text
    if not text: return await message.reply(f"◍ {sc('usage')}: /paste <{sc('text')}> ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post("https://spaceb.in/api/v1/documents/", data={"content":text}) as r:
                if r.status==201:
                    j=await r.json(); pid=j.get("payload",{}).get("id","")
                    await message.answer(f"◍ {sc('pasted')}: <a href=\"https://spaceb.in/{pid}\">https://spaceb.in/{pid}</a> ◍")
                    return
        await message.reply(f"◍ {sc('paste failed')} ◍")
    except Exception as e: await message.reply(f"◍ {sc('paste error')}: {e} ◍")

# ── /git — ◎ ɢɪᴛ ──────────────────────────────────────────────────────────────
@router.message(Command("git","github"))
async def git_cmd(message: Message):
    user=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip().lstrip("@")
    if not user: return await message.reply(f"◍ {sc('usage')}: /git <{sc('username')}> ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.github.com/users/{user}") as r:
                if r.status!=200: return await message.answer(f"◍ {sc('github user not found')} ◍")
                j=await r.json()
                rich=(
                    rich_heading(f"◎ {sc(j.get('login'))} ◎", level=3)
                    + rich_img(j.get("avatar_url",""))
                    + rich_kv_table([
                        (sc("name"), rich_esc(j.get("name") or "—")),
                        (sc("bio"), rich_esc((j.get("bio") or "")[:120])),
                        (sc("repos"), str(j.get("public_repos"))),
                        (sc("followers"), str(j.get("followers"))),
                        (sc("location"), rich_esc(j.get("location") or "—")),
                    ])
                    + rich_note(f'◍ <a href="{j.get("html_url")}">{sc("profile")}</a> ⫶ {j.get("created_at","")[:10]} ◍')
                )
                await message.answer(rich)
    except Exception as e: await message.reply(f"◍ {sc('git failed')}: {e} ◍")

@router.message(Command("pinterest","pinterestimg","pinimg"))
async def pinterest_cmd(message: Message):
    q=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "").strip()
    if not q: return await message.reply(f"◍ {sc('usage')}: /pinterest <{sc('query')}> ◍")
    await message.answer(f'◎ <a href="https://www.pinterest.com/search/pins/?q={q.replace(" ","%20")}">{sc("open pinterest")}</a> ◎')

@router.message(Command("sticker","steal","kang"))
async def sticker_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo: return await message.reply(f"◍ {sc('reply to image to steal')} ◍")
    try:
        file=await message.bot.get_file(message.reply_to_message.photo[-1].file_id)
        fpath=f"/tmp/{file.file_id}.jpg"
        await message.bot.download_file(file.file_path, fpath)
        await message.bot.send_sticker(message.chat.id, sticker=open(fpath,"rb"))
    except Exception as e: await message.reply(f"◍ {sc('sticker failed')}: {e} ◍")

@router.message(Command("afk"))
async def afk_cmd(message: Message):
    reason=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else sc("afk"))
    await db.set_afk(message.from_user.id, reason)
    await message.answer(f"◎ {sc(message.from_user.full_name.lower())} {sc('is now afk')}: {reason} ◎")

@router.message(Command("tagall"))
async def tagall_cmd(message: Message):
    if message.chat.type=="private": return
    text=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else sc("attention"))
    try:
        m=await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        from aiogram.enums import ChatMemberStatus
        from bot.config import is_sudo
        if m.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR) and not is_sudo(message.from_user.id):
            return await message.reply(f"⫶ {sc('admins only')} ⫶")
    except: pass
    await message.answer(f"◍ {sc('tagall by')} {message.from_user.full_name} ◍\n\n{escape_html(text)}")

@router.message(Command("speedtest"))
async def speedtest_cmd(message: Message):
    m=await message.answer(f"◍ {sc('running speedtest')} ⫶ ⬪⬩◍⬩⬪")
    try:
        import speedtest
        st=speedtest.Speedtest(); st.get_best_server()
        dl=st.download()/1_000_000; ul=st.upload()/1_000_000; ping=st.results.ping
        await m.edit_text(rich_heading(f"⬪ {sc('speedtest')} ⬪", level=3)+rich_kv_table([(sc("download"),f"<code>{dl:.2f} Mbps</code>"),(sc("upload"),f"<code>{ul:.2f} Mbps</code>"),(sc("ping"),f"<code>{ping:.0f} ms</code>")]))
    except Exception as e: await m.edit_text(f"◍ {sc('speedtest failed')}: {e} ◍")

@router.message(Command("news"))
async def news_cmd(message: Message):
    q=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "technology")
    from bot.config import NEWS_API_KEY
    if not NEWS_API_KEY: return await message.answer(f"◍ {sc('add news_api_key for real feed')} ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://newsapi.org/v2/everything", params={"q":q,"apiKey":NEWS_API_KEY,"pageSize":5}) as r:
                j=await r.json(); arts=j.get("articles",[])[:5]
                if not arts: return await message.answer(f"◍ {sc('no news')} ◍")
                txt=rich_heading(f"◎ {sc(f'news: {q}')} ◎", level=3)
                for a in arts: txt+=rich_note(f"<a href=\"{a['url']}\">{rich_esc(a['title'])}</a><br>{rich_esc((a.get('description') or '')[:120])}")
                await message.answer(txt)
    except Exception as e: await message.reply(f"◍ {sc('news failed')}: {e} ◍")

@router.message(Command("removebg"))
async def removebg_cmd(message: Message):
    await message.reply(f"◍ {sc('removebg')} ⫶ {sc('reply with image, needs api key')} ◍")
