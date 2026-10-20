# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Utility • Cyber Dark
#  weather / qr / shorten / calc / wiki / git / afk / carbon — all ◍ ⬪ ⫶
# --------------------------------------------------------------------------------
from __future__ import annotations
import html, io, re
import aiohttp
from pyrogram import filters
from pyrogram.types import Message
from videl import bot, LOGGER
from videl.utils.formatters import sc, sb

@bot.on_message(filters.command(["weather"]) & ~filters.forwarded)
async def weather_handler(_, m: Message):
    q=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not q: return await m.reply_text(f"◍ {sc('usage')}: /weather <{sc('city')}> ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://wttr.in/{q}?format=j1", timeout=aiohttp.ClientTimeout(total=12)) as r:
                j=await r.json(); cur=j.get("current_condition",[{}])[0]
                now=j.get("weather",[{}])[0] if j.get("weather") else {}
                await m.reply_text(
                    f"◍ {sc(q.lower())} ◍\n\n"
                    f"⬪ {sc('temp')}: <code>{cur.get('temp_C','—')}°C</code> ⫶ {sc('feels')}: <code>{cur.get('FeelsLikeC','—')}°C</code>\n"
                    f"⫶ {sc('humidity')}: <code>{cur.get('humidity','—')}%</code> ⫶ {sc('wind')}: <code>{cur.get('windspeedKmph','—')} ᴋᴍ/ʜ</code>\n"
                    f"◍ {cur.get('weatherDesc',[{}])[0].get('value','')}\n"
                    f"⬪ {sc('max')}: <code>{now.get('maxtempC','—')}°C</code> ⫶ {sc('min')}: <code>{now.get('mintempC','—')}°C</code> ◍",
                    disable_web_page_preview=True)
    except Exception as e: await m.reply_text(f"◍ {sc('weather failed')}: {e} ◍")

@bot.on_message(filters.command(["qr","qrcode"]) & ~filters.forwarded)
async def qr_handler(_, m: Message):
    q=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not q and m.reply_to_message and m.reply_to_message.text: q=m.reply_to_message.text
    if not q: return await m.reply_text(f"◍ /qr <{sc('text or url')}> ◍")
    try:
        import qrcode
        img=qrcode.make(q); bio=io.BytesIO(); bio.name="qr.png"; img.save(bio,format="PNG"); bio.seek(0)
        await m.reply_photo(bio, caption=f"◍ {sc('qr for')}: <code>{html.escape(q[:200])}</code> ◍")
    except Exception as e: await m.reply_text(f"◍ {sc('qr failed')}: {e} ◍")

@bot.on_message(filters.command(["shorten","short","tinyurl"]) & ~filters.forwarded)
async def shorten_handler(_, m: Message):
    url=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not url and m.reply_to_message: url=m.reply_to_message.text or ""
    if not url: return await m.reply_text(f"◍ /shorten <{sc('url')}> ◍")
    if not url.startswith("http"): url="https://"+url.strip()
    try:
        import pyshorteners; short=pyshorteners.Shortener().tinyurl.short(url)
        await m.reply_text(f"⬪ {sc('shortened')} ⬪\n◍ <a href=\"{short}\">{short}</a> ◍")
    except:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://is.gd/create.php", params={"format":"simple","url":url}) as r:
                    t=(await r.text()).strip()
                    await m.reply_text(f"◍ <a href=\"{t}\">{t}</a> ◍")
        except Exception as e: await m.reply_text(f"◍ {sc('shorten failed')}: {e} ◍")

@bot.on_message(filters.command(["calc","math","evaluate"]) & ~filters.forwarded)
async def calc_handler(_, m: Message):
    expr=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not expr: return await m.reply_text(f"◍ /calc <{sc('expression')}> ◍  — {sc('e.g.')} <code>2*(3+5)</code>")
    try:
        from videl.plugins.runtime import safe_calculate
        res=safe_calculate(expr.replace("^","**"))
        await m.reply_text(f"⫶ {sc('calc')} ⫶\n<code>{html.escape(expr)}</code> ⬪ <code>{res}</code> ◍")
    except Exception as e: await m.reply_text(f"◍ {sc('calc error')}: {html.escape(str(e))} ◍")

@bot.on_message(filters.command(["wiki","wikipedia"]) & ~filters.forwarded)
async def wiki_handler(_, m: Message):
    q=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not q: return await m.reply_text(f"◍ /wiki <{sc('query')}> ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://en.wikipedia.org/api/rest_v1/page/summary/"+q.replace(" ","_"),
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status!=200: raise RuntimeError(f"wiki {r.status}")
                j=await r.json()
                title=j.get("title","Wiki"); extract=j.get("extract","")[:900]
                url=j.get("content_urls",{}).get("desktop",{}).get("page","")
                await m.reply_text(f"◎ {sc(title.lower())} ◎\n\n{html.escape(extract)}\n\n◍ <a href=\"{url}\">{sc('read more')}</a> ◍", disable_web_page_preview=True)
    except Exception as e: await m.reply_text(f"◍ {sc('wiki failed')}: {e} ◍")

@bot.on_message(filters.command(["git","github","gh"]) & ~filters.forwarded)
async def git_handler(_, m: Message):
    user=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not user: return await m.reply_text(f"◍ /git <{sc('username')}> ◍")
    user=user.strip().lstrip("@").split()[0]
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.github.com/users/{user}", timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status!=200: raise RuntimeError(f"github {r.status}")
                j=await r.json()
                await m.reply_text(
                    f"◎ {sc(j.get('login','') or user)} ◎\n"
                    f"◍ {sc('name')}: <b>{html.escape(j.get('name') or '—')}</b> ⫶ {sc('bio')}: {html.escape((j.get('bio') or '—')[:120])}\n"
                    f"⬪ {sc('repos')}: <code>{j.get('public_repos','—')}</code> ⫶ {sc('followers')}: <code>{j.get('followers','—')}</code> ⫶ {sc('following')}: <code>{j.get('following','—')}</code>\n"
                    f"◍ <a href=\"{j.get('html_url','')}\">{sc('profile')}</a> ⫶ <a href=\"{j.get('html_url','')}/?tab=repositories\">{sc('repos')}</a> ◍",
                    disable_web_page_preview=True)
    except Exception as e: await m.reply_text(f"◍ {sc('git failed')}: {e} ◍")

@bot.on_message(filters.command(["carbon"]) & ~filters.forwarded)
async def carbon_handler(_, m: Message):
    code=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if m.reply_to_message and m.reply_to_message.text: code=m.reply_to_message.text
    if not code: return await m.reply_text(f"◍ /carbon <{sc('code')} — {sc('reply to code too')} ◍")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://carbonara.solopov.dev/api/cook", params={"code":code[:1500]}, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status==200:
                    data=await r.read()
                    bio=io.BytesIO(data); bio.name="carbon.png"
                    await m.reply_photo(bio, caption=f"◍ {sc('carbon')} ◍")
                    return
        raise RuntimeError("carbonara fail")
    except Exception as e: await m.reply_text(f"◍ {sc('carbon failed')}: {e} ◍")

LOGGER.info("⬪ ᴜᴛɪʟs — ᴘᴇʀғᴇᴄᴛ ◍")
