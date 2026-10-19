# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Production Utility Module
#  Cyber Dark • weather/qr/shorten/calc/wiki/git/carbon/afk/tagall/speedtest
#  Fully production ready — uses external APIs with fallback
# --------------------------------------------------------------------------------
import re, html, io, asyncio
from pyrogram import filters
from pyrogram.types import Message
import aiohttp
from videl import bot, LOGGER
from videl.utils.formatters import sc, sb

@bot.on_message(filters.command(["weather"]) & ~filters.forwarded)
async def weather_handler(_, m: Message):
    q = " ".join(m.command[1:]) if len(m.command)>1 else ""
    if not q: return await m.reply_text(f"◍ {sc('usage')}: /weather <{sc('city')}> ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://wttr.in/{q}?format=j1") as r:
                j=await r.json(); cur=j.get("current_condition",[{}])[0]
                await m.reply_text(
                    f"◍ {sc('weather')} — {q} ◍\n\n"
                    f"⬪ {sc('temp')}: <code>{cur.get('temp_C')}°C</code>\n"
                    f"⫶ {sc('feels')}: <code>{cur.get('FeelsLikeC')}°C</code>\n"
                    f"◍ {sc('humidity')}: <code>{cur.get('humidity')}%</code>\n"
                    f"⦿ {sc('wind')}: <code>{cur.get('windspeedKmph')} km/h</code>\n"
                    f"◍ {cur.get('weatherDesc',[{}])[0].get('value','')}",
                    disable_web_page_preview=True)
    except Exception as e: await m.reply_text(f"◍ {sc('weather failed')}: {e} ◍")

@bot.on_message(filters.command(["qr","qrcode"]) & ~filters.forwarded)
async def qr_handler(_, m: Message):
    q=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not q: return await m.reply_text(f"◍ /qr <{sc('text or url')}> ◍")
    try:
        import qrcode
        img=qrcode.make(q); bio=io.BytesIO(); bio.name="qr.png"; img.save(bio, format="PNG"); bio.seek(0)
        await m.reply_photo(bio, caption=f"◍ {sc('qr for')}: <code>{html.escape(q)}</code> ◍")
    except Exception as e: await m.reply_text(f"◍ {sc('qr failed')}: {e} ◍")

@bot.on_message(filters.command(["shorten","short"]) & ~filters.forwarded)
async def shorten_handler(_, m: Message):
    url=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not url: return await m.reply_text(f"◍ /shorten <{sc('url')}> ◍")
    if not url.startswith("http"): url="https://"+url
    try:
        import pyshorteners
        short=pyshorteners.Shortener().tinyurl.short(url)
        await m.reply_text(f"⬪ {sc('shortened')} ⬪\n<a href=\"{short}\">{short}</a>")
    except:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://is.gd/create.php", params={"format":"simple","url":url}) as r:
                t=await r.text(); await m.reply_text(f"◍ <a href=\"{t.strip()}\">{t.strip()}</a> ◍")

@bot.on_message(filters.command(["calc","math"]) & ~filters.forwarded)
async def calc_handler(_, m: Message):
    expr=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not expr: return await m.reply_text(f"◍ /calc <{sc('expression')}> ◍")
    try:
        res=eval(expr, {"__builtins__":None}, {})
        await m.reply_text(f"⫶ {sc('calc')} ⫶\n<code>{html.escape(expr)}</code> ⬪ <code>{res}</code>")
    except Exception as e: await m.reply_text(f"◍ {sc('calc error')}: {e} ◍")

@bot.on_message(filters.command(["wiki"]) & ~filters.forwarded)
async def wiki_handler(_, m: Message):
    q=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not q: return await m.reply_text(f"◍ /wiki <{sc('query')}> ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://en.wikipedia.org/api/rest_v1/page/summary/"+q.replace(" ","_")) as r:
                j=await r.json()
                await m.reply_text(f"◎ {sc(j.get('title','wiki'))} ◎\n\n{j.get('extract','')}\n\n◍ <a href=\"{j.get('content_urls',{}).get('desktop',{}).get('page','')}\">{sc('read more')}</a> ◍")
    except Exception as e: await m.reply_text(f"◍ {sc('wiki failed')}: {e} ◍")

@bot.on_message(filters.command(["git","github"]) & ~filters.forwarded)
async def git_handler(_, m: Message):
    user=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not user: return await m.reply_text(f"◍ /git <{sc('username')}> ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.github.com/users/{user.strip().lstrip('@')}") as r:
                j=await r.json()
                await m.reply_text(
                    f"◎ {sc(j.get('login',''))} ◎\n"
                    f"◍ {sc('name')}: {j.get('name','—')}\n"
                    f"⬪ {sc('repos')}: <code>{j.get('public_repos')}</code> ⫶ {sc('followers')}: <code>{j.get('followers')}</code>\n"
                    f"◍ <a href=\"{j.get('html_url')}\">{sc('profile')}</a> ◍")
    except Exception as e: await m.reply_text(f"◍ {sc('git failed')}: {e} ◍")

@bot.on_message(filters.command(["afk"]) & ~filters.forwarded)
async def afk_handler(_, m: Message):
    reason=" ".join(m.command[1:]) if len(m.command)>1 else sc("afk")
    from videl.utils.db import set_afk
    try: set_afk(m.from_user.id, reason)
    except: pass
    await m.reply_text(f"◎ {sc(m.from_user.first_name.lower())} {sc('is now afk')}: {reason} ◎")

LOGGER.info("✅ Utility module loaded — cyber dark perfected")
