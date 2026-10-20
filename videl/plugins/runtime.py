"""Real implementations shared by Videl's command plugins.

Plugins are deliberately thin command adapters; all remote I/O is bounded by
short timeouts, user content is escaped, and state is persisted in MongoDB.
No demo/mock results are returned.
"""
from __future__ import annotations

import ast
import asyncio
import base64
import html
import io
import ipaddress
import json
import hashlib
import logging
import math
import os
import random
import re
import socket
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlparse, urljoin

import aiohttp
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from videl import LOGGER, bot
from videl.utils.db import get_db
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table, rich_esc, rich_reply

log = logging.getLogger("videl.plugins.runtime")
_TIMEOUT = aiohttp.ClientTimeout(total=12, connect=5)


def _db():
    return get_db()


def _col(name):
    db = _db()
    return db[name] if db is not None else None


def _args(message: Message) -> str:
    return " ".join((message.text or "").split()[1:]).strip()


def _who(message: Message) -> int:
    return message.from_user.id if message.from_user else 0


def _esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


async def _validate_public_url(raw: str) -> str:
    """Reject non-HTTP(S), credentialed, localhost and private-network URLs."""
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public http(s) URLs are accepted.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Private and local network URLs are not allowed.")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        loop = asyncio.get_running_loop()
        infos = await loop.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        addresses = {ipaddress.ip_address(info[4][0]) for info in infos}
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Private and reserved network addresses are not allowed.")
    return raw


async def _send(message: Message, title: str, body: str, *, photo: str = "", buttons=None):
    text = rich_heading(_esc(title), level=2) + rich_note(body)
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    if photo:
        try:
            return await bot.send_photo(message.chat.id, photo, caption=text, reply_markup=markup)
        except Exception:
            pass
    return await rich_reply(message, text, reply_markup=markup)


async def _get_json(url: str, *, params=None, headers=None):
    async with aiohttp.ClientSession(timeout=_TIMEOUT, headers=headers) as session:
        async with session.get(url, params=params, allow_redirects=True) as r:
            if r.status >= 400:
                raise RuntimeError(f"service returned HTTP {r.status}")
            return await r.json(content_type=None)


async def _get_text(url: str, *, params=None):
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
        async with session.get(url, params=params, allow_redirects=True) as r:
            if r.status >= 400:
                raise RuntimeError(f"service returned HTTP {r.status}")
            return await r.text()


class _SafeCalc(ast.NodeVisitor):
    OPS = {ast.Add: lambda a,b:a+b, ast.Sub: lambda a,b:a-b, ast.Mult: lambda a,b:a*b,
           ast.Div: lambda a,b:a/b, ast.FloorDiv: lambda a,b:a//b, ast.Mod: lambda a,b:a%b,
           ast.Pow: lambda a,b:a**b}
    FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
             "log": math.log, "log10": math.log10, "abs": abs, "round": round,
             "ceil": math.ceil, "floor": math.floor}
    def visit_Expression(self, n): return self.visit(n.body)
    def visit_Constant(self, n):
        if isinstance(n.value, (int,float)) and abs(n.value) < 10**12: return n.value
        raise ValueError("Only numeric constants are allowed")
    def visit_UnaryOp(self,n):
        v=self.visit(n.operand)
        if isinstance(n.op, ast.USub): return -v
        if isinstance(n.op, ast.UAdd): return v
        raise ValueError("Unsupported operator")
    def visit_BinOp(self,n):
        if type(n.op) not in self.OPS: raise ValueError("Unsupported operator")
        a,b=self.visit(n.left),self.visit(n.right)
        if isinstance(n.op,ast.Pow) and abs(b)>8: raise ValueError("Exponent too large")
        out=self.OPS[type(n.op)](a,b)
        if not math.isfinite(out) or abs(out)>1e100: raise ValueError("Result out of range")
        return out
    def visit_Name(self,n):
        if n.id in {"pi","e"}: return math.pi if n.id=="pi" else math.e
        raise ValueError("Unknown symbol")
    def visit_Call(self,n):
        if not isinstance(n.func,ast.Name) or n.func.id not in self.FUNCS or n.keywords: raise ValueError("Unsupported function")
        return self.FUNCS[n.func.id](*(self.visit(a) for a in n.args))
    def generic_visit(self,n): raise ValueError("Unsupported expression")


def safe_calculate(expression: str):
    tree=ast.parse(expression, mode="eval")
    if len(list(ast.walk(tree)))>80: raise ValueError("Expression too complex")
    return _SafeCalc().visit(tree)


async def run_plugin(slug: str, message: Message):
    """Run the real feature for a plugin slug; failures are reported honestly."""
    arg = _args(message)
    chat_id = message.chat.id
    user_id = _who(message)
    try:
        # ── Useful, real public-data services ───────────────────────────────
        if slug in {"weather"}:
            if not arg: return await _send(message, "Weather", "Usage: <code>/weather city</code>")
            data=await _get_json(f"https://wttr.in/{quote(arg)}", params={"format":"j1"})
            cur=data["current_condition"][0]; area=data["nearest_area"][0]
            place=area["areaName"][0]["value"]
            return await _send(message, f"Weather · {place}", f"{_esc(cur['weatherDesc'][0]['value'])}<br>🌡 {_esc(cur['temp_C'])}°C (feels {_esc(cur['FeelsLikeC'])}°C)<br>💧 Humidity {_esc(cur['湿度'] if '湿度' in cur else cur['humidity'])}% · 💨 {_esc(cur['windspeedKmph'])} km/h")
        if slug=="google":
            if not arg:return await _send(message,"Search", "Usage: <code>/google search terms</code>")
            data=await _get_json("https://api.duckduckgo.com/",params={"q":arg,"format":"json","no_html":1,"no_redirect":1})
            abstract=data.get("AbstractText") or data.get("Answer") or ""
            related=data.get("RelatedTopics",[])
            snippets=[x.get("Text") for x in related if isinstance(x,dict) and x.get("Text")][:4]
            body=_esc(abstract[:1000]) if abstract else ""
            if snippets:body+=("<br>" if body else "")+"<br>".join(f"• {_esc(x[:220])}" for x in snippets)
            if data.get("AbstractURL"):body+=f"<br><a href=\"{_esc(data['AbstractURL'])}\">Source</a>"
            return await _send(message,"Search results",body or f"No instant answer. <a href=\"https://duckduckgo.com/?q={quote(arg)}\">Open web search</a>")
        if slug=="wiki":
            if not arg: return await _send(message, "Wikipedia search", "Usage: <code>/wiki topic</code>")
            data=await _get_json("https://en.wikipedia.org/w/api.php", params={"action":"query","generator":"search","gsrsearch":arg,"gsrlimit":1,"prop":"extracts|info","exintro":1,"explaintext":1,"inprop":"url","format":"json","formatversion":2})
            pages=data.get("query",{}).get("pages",[])
            if not pages: return await _send(message,"No results",f"No encyclopedia result found for <code>{_esc(arg)}</code>.")
            p=pages[0]; extract=p.get("extract","")[:1200]
            return await _send(message,p["title"],f"{_esc(extract)}<br><a href=\"{_esc(p.get('fullurl',''))}\">Read article</a>")
        if slug in {"define","urban"}:
            if not arg: return await _send(message,"Dictionary", "Usage: <code>/define word</code>")
            if slug=="urban":
                data=await _get_json("https://api.urbandictionary.com/v0/define",params={"term":arg})
                items=data.get("list",[])
                if not items: return await _send(message,"No definition",f"No Urban Dictionary entry for <code>{_esc(arg)}</code>.")
                return await _send(message,f"Definition · {arg}",_esc(items[0].get("definition","")[:1200])+"<br><i>User-generated content</i>")
            data=await _get_json(f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(arg)}")
            entry=data[0]; meanings=entry.get("meanings",[])
            lines=[f"<b>{_esc(m.get('partOfSpeech',''))}</b>: {_esc(m.get('definitions',[{}])[0].get('definition',''))}" for m in meanings[:4]]
            return await _send(message,entry.get("word",arg),"<br>".join(lines) or "No definition available.")
        if slug in {"translate","language"}:
            if not arg: return await _send(message,"Translate", "Usage: <code>/tr text | target-language</code> (default: en)")
            parts=arg.rsplit("|",1); text=parts[0].strip(); target=parts[1].strip() if len(parts)>1 else "en"
            data=await _get_json("https://api.mymemory.translated.net/get",params={"q":text[:450],"langpair":f"auto|{target}"})
            translated=data.get("responseData",{}).get("translatedText","")
            if not translated: raise RuntimeError("translation service returned no text")
            return await _send(message,"Translation",f"<b>→ {_esc(target)}</b><br>{_esc(translated)}")
        if slug=="github":
            if not arg: return await _send(message,"GitHub", "Usage: <code>/github owner/repository</code>")
            repo=arg.removeprefix("https://github.com/").strip("/")
            if len(repo.split("/"))<2: return await _send(message,"GitHub", "Give a repository as <code>owner/name</code>.")
            data=await _get_json(f"https://api.github.com/repos/{quote(repo,safe='/')}",headers={"Accept":"application/vnd.github+json","User-Agent":"VidelBot"})
            return await _send(message,data.get("full_name",repo),f"{_esc(data.get('description') or 'No description')}<br>⭐ {_esc(data.get('stargazers_count'))} · 🍴 {_esc(data.get('forks_count'))} · open issues {_esc(data.get('open_issues_count'))}<br><a href=\"{_esc(data.get('html_url',''))}\">Open repository</a>")
        if slug in {"anime_search","anilist","character","manga","trending"}:
            if not arg and slug!="trending": return await _send(message,"Anime & manga", "Usage: send a title or character name.")
            if slug=="trending": url="https://api.jikan.moe/v4/top/anime"; params={"limit":8}
            elif slug=="character": url="https://api.jikan.moe/v4/characters"; params={"q":arg,"limit":1}
            elif slug=="manga": url="https://api.jikan.moe/v4/manga"; params={"q":arg,"limit":1}
            else: url="https://api.jikan.moe/v4/anime"; params={"q":arg,"limit":1}
            data=await _get_json(url,params=params); entries=data.get("data",[])
            if not entries: return await _send(message,"No results",f"Jikan found no match for <code>{_esc(arg)}</code>.")
            p=entries[0]
            if slug=="character":
                return await _send(message,p.get("name","Character"),f"{_esc(p.get('about','')[:1000])}<br><a href=\"{_esc(p.get('url',''))}\">MyAnimeList profile</a>",photo=p.get("images",{}).get("jpg",{}).get("image_url",""))
            title=p.get("title") or p.get("title_english") or "Anime"
            synopsis=(p.get("synopsis") or "No synopsis available.")[:1000]
            return await _send(message,title,f"{_esc(synopsis)}<br>Score: {_esc(p.get('score') or '—')} · Episodes: {_esc(p.get('episodes') or '—')}<br><a href=\"{_esc(p.get('url',''))}\">Details</a>",photo=p.get("images",{}).get("jpg",{}).get("image_url",""))
        if slug=="waifu" or slug=="neko":
            if slug=="waifu":
                data=await _get_json("https://api.waifu.im/search",params={"included_tags":"waifu"})
                images=data.get("images",[]); image=images[0] if images else {}
            else:
                data=await _get_json("https://nekos.best/api/v2/neko")
                image=(data.get("results") or [{}])[0]
            if not image: raise RuntimeError("image service returned no results")
            return await _send(message,slug.title(),f"<a href=\"{_esc(image.get('url',''))}\">Open image</a>",photo=image.get("url",""))
        if slug in {"joke","fact","quotepro","quote","truth","dare","memepro","quiz","gimme"}:
            if slug in {"joke","dare","truth","quiz","gimme"}:
                data=await _get_json("https://official-joke-api.appspot.com/random_joke") if slug=="joke" else await _get_json("https://uselessfacts.jsph.pl/api/v2/facts/random",params={"language":"en"}) if slug=="fact" else None
                if slug=="joke": body=f"{_esc(data.get('setup'))}<br><b>{_esc(data.get('punchline'))}</b>"
                elif slug=="fact": body=_esc(data.get("text",""))
                elif slug in {"truth","dare"}:
                    source="https://api.truthordarebot.xyz/v1/truth" if slug=="truth" else "https://api.truthordarebot.xyz/v1/dare"
                    d=await _get_json(source); body=_esc(d.get("question", "No prompt returned."))
                elif slug=="gimme":
                    d=await _get_json("https://uselessfacts.jsph.pl/api/v2/facts/random",params={"language":"en"}); body=_esc(d.get("text",""))
                else:
                    d=await _get_json("https://opentdb.com/api.php",params={"amount":1,"type":"multiple"})
                    q=d.get("results",[{}])[0]; body=f"{_esc(q.get('question',''))}<br><b>Answer:</b> {_esc(q.get('correct_answer',''))}"
                return await _send(message,slug.replace("pro","").title(),body)
            if slug in {"quote","quotepro"}:
                data=await _get_json("https://zenquotes.io/api/random"); q=data[0]
                return await _send(message, "Quote", f"“{_esc(q.get('q'))}”<br><i>— {_esc(q.get('a'))}</i>")
            if slug=="memepro":
                data=await _get_json("https://meme-api.com/gimme"); return await _send(message,data.get("title","Meme"),f"<a href=\"{_esc(data.get('postLink',''))}\">Open original</a>",photo=data.get("url",""))
        if slug=="covid":
            data=await _get_json("https://disease.sh/v3/covid-19/all")
            return await _send(message,"COVID-19 · worldwide",f"Cases: {_esc(data.get('cases'))}<br>Recovered: {_esc(data.get('recovered'))}<br>Deaths: {_esc(data.get('deaths'))}<br>Updated: {_esc(datetime.fromtimestamp(data.get('updated',0)/1000,timezone.utc).isoformat())}")
        if slug=="currency":
            parts=arg.upper().split()
            if len(parts)<2:return await _send(message,"Currency", "Usage: <code>/currency 25 USD EUR</code>")
            amount=float(parts[0]); base=parts[1]; target=parts[2] if len(parts)>2 else "INR"
            d=await _get_json(f"https://api.frankfurter.app/latest",params={"amount":amount,"from":base,"to":target})
            return await _send(message,"Currency conversion",f"{amount:g} {base} = <b>{_esc(d['rates'][target])} {target}</b><br>Rate date {_esc(d.get('date'))}")
        if slug=="shortener":
            if not arg:return await _send(message,"URL shortener", "Usage: <code>/short https://example.com</code>")
            if urlparse(arg).scheme not in {"http","https"}: return await _send(message,"Invalid URL", "Only http/https links can be shortened.")
            short=await _get_text("https://is.gd/create.php",params={"format":"simple","url":arg})
            return await _send(message,"Short link",f"<a href=\"{_esc(short.strip())}\">{_esc(short.strip())}</a>")
        if slug=="unshort":
            if not arg:return await _send(message,"Expand URL", "Usage: <code>/unshort https://short.url/...</code>")
            current=await _validate_public_url(arg)
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                for _ in range(6):
                    async with session.get(current,allow_redirects=False) as response:
                        location=response.headers.get("Location")
                        if response.status not in {301,302,303,307,308} or not location: break
                        current=await _validate_public_url(urljoin(current,location))
                else: raise RuntimeError("too many redirects")
            return await _send(message,"Expanded URL",f"<a href=\"{_esc(current)}\">{_esc(current)}</a>")
        if slug in {"ytsearch","anime_search"} and slug=="ytsearch":
            if not arg:return await _send(message,"YouTube search", "Usage: <code>/yts search words</code>")
            from videl.utils.youtube import search_yt_multi
            results=await search_yt_multi(arg,limit=5)
            if not results:return await _send(message,"No YouTube results",f"No results for <code>{_esc(arg)}</code>.")
            lines=[f"{i}. <a href=\"{_esc(v.get('link') or v.get('url',''))}\">{_esc(v.get('title','Untitled'))}</a> · {_esc(v.get('duration','?'))}" for i,v in enumerate(results,1)]
            return await _send(message,"YouTube results","<br>".join(lines))
        if slug in {"insta","tiktok","pinterest"}:
            if not arg: return await _send(message,"Media download",f"Usage: <code>/{message.command[0]} https://...</code>")
            await _validate_public_url(arg)
            from videl.utils.youtube import download_video
            status=await message.reply_text("◍ Downloading media…")
            path=await download_video(arg)
            if not path or not os.path.isfile(path): return await status.edit_text("Download failed: the source may be private, unsupported, or blocked by its provider.")
            try: await bot.send_video(chat_id, path, caption=f"Downloaded by Videl · requested by {_esc(message.from_user.first_name if message.from_user else 'user')}")
            finally:
                try: os.remove(path)
                except OSError: pass
                try: await status.delete()
                except Exception: pass
            return
        if slug=="qrgen":
            if not arg:return await _send(message,"QR generator", "Usage: <code>/qr text-or-url</code>")
            import qrcode
            from PIL import Image
            image=qrcode.make(arg); output=io.BytesIO(); output.name="videl-qr.png"; image.save(output,format="PNG"); output.seek(0)
            return await bot.send_photo(chat_id,output,caption="QR code generated locally by Videl.")
        if slug=="calculator" or slug=="math":
            if not arg:return await _send(message,"Calculator", "Usage: <code>/calc (12 + 3) * sqrt(16)</code><br>Supported: arithmetic, pi, e, sqrt/sin/cos/tan/log/abs/round/ceil/floor.")
            result=safe_calculate(arg.replace("^","**"))
            col=_col("calculator_logs")
            if col is not None: col.insert_one({"chat_id":chat_id,"user_id":user_id,"query":arg[:500],"result":str(result)[:200],"at":datetime.now(timezone.utc)})
            return await _send(message,"Result",f"<code>{_esc(result)}</code>")
        if slug=="github" and not arg: return await _send(message,"GitHub", "Usage: <code>/github owner/repository</code>")
        if slug=="paste":
            if not arg:
                if not message.reply_to_message or not message.reply_to_message.text: return await _send(message,"Paste", "Use <code>/paste text</code> or reply to a text message.")
                arg=message.reply_to_message.text
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.post("https://paste.rs",data=arg.encode(),headers={"Content-Type":"text/plain"}) as r:
                    if r.status>=400: raise RuntimeError(f"paste service HTTP {r.status}")
                    link=(await r.text()).strip()
            return await _send(message,"Paste created",f"<a href=\"{_esc(link)}\">{_esc(link)}</a>")
        if slug=="tts":
            if not arg:return await _send(message,"Text to speech", "Usage: <code>/tts text</code>")
            from gtts import gTTS
            audio=io.BytesIO(); audio.name="videl-tts.mp3"; gTTS(arg[:3500],lang="en").write_to_fp(audio); audio.seek(0)
            return await bot.send_audio(chat_id,audio,title="Videl TTS",caption="Text-to-speech audio")
        if slug=="carbon":
            if not arg and message.reply_to_message and message.reply_to_message.text: arg=message.reply_to_message.text
            if not arg:return await _send(message,"Code image", "Usage: <code>/carbon code</code> or reply to code.")
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as session:
                async with session.post("https://carbonara-42.vercel.app/api/cook",json={"code":arg[:12000],"theme":"seti","language":"auto","backgroundColor":"#111827"}) as r:
                    if r.status>=400: raise RuntimeError(f"image renderer HTTP {r.status}")
                    data=await r.read()
            return await bot.send_photo(chat_id,io.BytesIO(data),caption="Code image")
        if slug=="sysinfo":
            import psutil, platform
            disk=psutil.disk_usage("/")
            return await _send(message,"System info",f"Platform: {_esc(platform.platform())}<br>CPU: {psutil.cpu_percent(interval=None)}% · RAM: {psutil.virtual_memory().percent}%<br>Disk: {disk.percent}% · Uptime: {int(time.time()-psutil.boot_time())}s")
        if slug=="speedtest":
            start=time.perf_counter(); await _get_text("https://www.google.com/generate_204"); ms=(time.perf_counter()-start)*1000
            return await _send(message,"Network latency",f"HTTPS request to Google: <b>{ms:.0f} ms</b><br>This is latency, not a bandwidth speed test.")
        if slug in {"idpro","userinfo"}:
            target=message.reply_to_message.from_user if message.reply_to_message else message.from_user
            if not target:return await _send(message,"User info","Could not resolve the user.")
            return await _send(message,"User info",f"Name: {_esc(target.first_name)}<br>ID: <code>{target.id}</code><br>Username: @{_esc(target.username or '—')}<br>Bot: {bool(target.is_bot)}")
        if slug=="barcode":
            if not arg:return await _send(message,"Barcode", "Usage: <code>/barcode text</code>")
            import barcode
            from barcode.writer import ImageWriter
            output=io.BytesIO(); barcode.get("code128",arg[:80],writer=ImageWriter()).write(output,options={"write_text":True}); output.seek(0)
            return await bot.send_photo(chat_id,output,caption="Code 128 barcode")
        if slug=="font":
            if not arg:return await _send(message,"Font styles", "Usage: <code>/font text</code>")
            trans=str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789","𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵")
            return await _send(message,"Styled text",_esc(arg.translate(trans)))
        if slug=="emojify":
            if not arg:return await _send(message,"Emojify", "Usage: <code>/emojify text</code>")
            emoji={"love":"❤️","happy":"😊","sad":"😢","fire":"🔥","music":"🎵","cat":"🐱","dog":"🐶","yes":"✅","no":"❌","star":"⭐"}
            words=arg.split(); out=" ".join(f"{_esc(w)}{emoji.get(w.lower().strip('.,!?'), '')}" for w in words)
            return await _send(message,"Emojified",out)

        if slug=="lyricspro":
            query=arg
            if not query:
                from videl.core.queue import peek_current
                current=peek_current(chat_id); query=(current or {}).get("title","")
            if not query:return await _send(message,"Lyrics", "Usage: <code>/lyricspro artist - title</code> or play a track first.")
            data=await _get_json("https://lrclib.net/api/search",params={"q":query})
            if not data:return await _send(message,"No lyrics found",f"LRCLIB returned no match for <code>{_esc(query)}</code>.")
            item=data[0]; lyrics=item.get("plainLyrics") or item.get("syncedLyrics") or ""
            if not lyrics:return await _send(message,"No lyrics found", "The matching recording has no lyrics attached.")
            return await _send(message,item.get("trackName") or query,f"<i>{_esc(item.get('artistName',''))}</i><br><pre>{_esc(lyrics[:3500])}</pre>")
        if slug=="ebook":
            if not arg:return await _send(message,"Book search", "Usage: <code>/ebook book title or author</code>")
            data=await _get_json("https://openlibrary.org/search.json",params={"q":arg,"limit":5,"fields":"title,author_name,first_publish_year,key"})
            docs=data.get("docs",[])
            if not docs:return await _send(message,"No books found",f"No Open Library match for <code>{_esc(arg)}</code>.")
            rows=[]
            for book in docs:
                title=book.get("title","Untitled"); author=", ".join(book.get("author_name",[])[:2]) or "Unknown author"
                key=book.get("key",""); rows.append(f"<a href=\"https://openlibrary.org{_esc(key)}\">{_esc(title)}</a> — {_esc(author)} ({_esc(book.get('first_publish_year','n.d.'))})")
            return await _send(message,"Open Library results","<br>".join(rows))
        if slug=="lastfm":
            key=os.getenv("LASTFM_API_KEY","").strip()
            if not key:return await _send(message,"Last.fm unavailable", "Set <code>LASTFM_API_KEY</code> in deployment secrets to use this command.")
            if not arg:return await _send(message,"Last.fm", "Usage: <code>/lastfm artist</code>")
            data=await _get_json("https://ws.audioscrobbler.com/2.0/",params={"method":"artist.getinfo","artist":arg,"api_key":key,"format":"json"})
            artist=data.get("artist",{})
            if not artist:return await _send(message,"No Last.fm artist", "No artist was returned for that query.")
            stats=artist.get("stats",{})
            return await _send(message,artist.get("name",arg),f"Listeners: {_esc(stats.get('listeners','—'))} · Playcount: {_esc(stats.get('playcount','—'))}<br>{_esc(re.sub('<[^>]+>','',artist.get('bio',{}).get('summary',''))[:700])}<br><a href=\"{_esc(artist.get('url',''))}\">Last.fm profile</a>")
        if slug in {"telegraph_pro","telegraph2","tograph"}:
            content=arg or (message.reply_to_message.text if message.reply_to_message and message.reply_to_message.text else "")
            if not content:return await _send(message,"Publish to Telegraph", "Usage: <code>/telegraph Title | text</code> or reply to text.")
            title,sep,body=content.partition("|"); title=(title.strip() if sep else "Videl Note")[:120]; body=body.strip() if sep else content
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.get("https://api.telegra.ph/createAccount",params={"short_name":"VidelBot","author_name":"Videl"}) as response: account=await response.json(content_type=None)
                if not account.get("ok"):raise RuntimeError("Telegraph account creation failed")
                nodes=json.dumps([{"tag":"p","children":[body[:6000]]}],ensure_ascii=False)
                async with session.post("https://api.telegra.ph/createPage",data={"access_token":account["result"]["access_token"],"title":title,"content":nodes,"return_content":"false"}) as response: page=await response.json(content_type=None)
            if not page.get("ok"):raise RuntimeError(page.get("error","Telegraph publish failed"))
            link=page["result"]["url"]
            return await _send(message,"Telegraph page created",f"<a href=\"{_esc(link)}\">{_esc(link)}</a>")
        if slug=="trace":
            target=arg.strip()
            if not target:return await _send(message,"DNS lookup", "Usage: <code>/trace example.com</code>")
            url=target if "://" in target else "https://"+target
            await _validate_public_url(url)
            host=urlparse(url).hostname
            if not host:return await _send(message,"Invalid domain", "Provide a hostname or public URL.")
            loop=asyncio.get_running_loop(); infos=await loop.getaddrinfo(host,None,type=socket.SOCK_STREAM)
            ips=sorted({str(ipaddress.ip_address(info[4][0])) for info in infos if ipaddress.ip_address(info[4][0]).is_global})[:10]
            return await _send(message,f"DNS · {host}","<br>".join(f"<code>{_esc(ip)}</code>" for ip in ips) or "No public address records.")
        if slug=="wallpaper":
            if not arg:return await _send(message,"Wallpaper search", "Usage: <code>/wallpaper topic</code>")
            data=await _get_json("https://commons.wikimedia.org/w/api.php",params={"action":"query","generator":"search","gsrsearch":f"filetype:bitmap {arg}","gsrnamespace":6,"gsrlimit":1,"prop":"imageinfo","iiprop":"url","iiurlwidth":1200,"format":"json"})
            pages=data.get("query",{}).get("pages",[])
            if not pages:return await _send(message,"No wallpaper found", "Wikimedia Commons returned no image result.")
            page=pages[0]; info=page.get("imageinfo",[{}])[0]
            return await _send(message,page.get("title",arg),f"<a href=\"{_esc(info.get('descriptionurl',''))}\">Wikimedia Commons source</a>",photo=info.get("thumburl") or info.get("url",""))
        if slug=="zimage":
            return await _send(message,"Image generation disabled", "AI image generation is intentionally not enabled. This command will not fabricate an image.")

        # ── Persisted account / community features ──────────────────────────
        if slug=="afk":
            col=_col("videl_afk")
            if col is None:return await _send(message,"AFK unavailable","MongoDB is not connected; AFK state cannot be saved.")
            if not user_id:return await _send(message,"AFK","A Telegram user account is required.")
            col.update_one({"user_id":user_id},{"$set":{"user_id":user_id,"reason":arg[:300] or "Away","since":datetime.now(timezone.utc)}},upsert=True)
            return await _send(message,"AFK enabled",f"Your status is AFK. Reason: <i>{_esc(arg or 'Away')}</i>")
        if slug in {"invite","ghost","kang","sticker_tools","stickerpro","reaction"}:
            if slug=="invite":
                if not await _admin(message):return await _send(message,"Permission denied","Only group admins can create an invite link.")
                invite=await bot.create_chat_invite_link(chat_id,creates_join_request=False)
                return await _send(message,"Invite link",f"<a href=\"{_esc(invite.invite_link)}\">Open invite link</a>")
            if slug=="ghost":
                if not await _admin(message):return await _send(message,"Permission denied","Only group admins can ghost-delete messages.")
                if not message.reply_to_message:return await _send(message,"Ghost delete","Reply to the message you want removed, then use <code>/ghost</code>.")
                await message.reply_to_message.delete(); await message.delete(); return
            target=message.reply_to_message
            if slug=="reaction":
                if not target:return await _send(message,"Reaction","Reply to a message and use <code>/react 🔥</code>.")
                emoji=arg.strip() or "👍"
                if not hasattr(bot,"set_message_reaction"):return await _send(message,"Reaction unavailable","The installed Telegram client does not expose message reactions.")
                await bot.set_message_reaction(chat_id,target.id,emoji); return await _send(message,"Reaction set",f"Added {_esc(emoji)} to the replied-to message.")
            media=target.sticker if target else None
            if not media:return await _send(message,"Sticker tools","Reply to a sticker and run <code>/kang</code>, <code>/sticker</code> or <code>/stickerpro</code>.")
            if slug=="kang":
                await bot.send_sticker(chat_id,media.file_id); return
            return await _send(message,"Sticker details",f"Sticker ID: <code>{_esc(media.file_id)}</code><br>Unique ID: <code>{_esc(media.file_unique_id)}</code><br>Emoji: {_esc(media.emoji or '—')} · Animated: {bool(media.is_animated)} · Video: {bool(media.is_video)}")
        if slug in {"economy","karma","level"}:
            col=_col("plugin_accounts")
            if col is None:return await _send(message,"Accounts unavailable","MongoDB is not connected; account state cannot be saved.")
            key={"user_id":user_id,"chat_id":chat_id}
            doc=col.find_one(key) or {**key,"coins":0,"xp":0,"karma":0,"last_daily":None}
            cmd=message.command[0].lower()
            if slug=="economy" and arg.lower().startswith("daily"):
                last=doc.get("last_daily"); now=datetime.now(timezone.utc)
                if last and (now-last).total_seconds()<86400:return await _send(message,"Daily reward","You have already claimed today’s reward.")
                reward=random.randint(50,150); col.update_one(key,{"$inc":{"coins":reward},"$set":{"last_daily":now}},upsert=True)
                return await _send(message,"Daily reward",f"Added <b>{reward}</b> coins to your balance.")
            if slug=="economy" and arg.lower().startswith("pay "):
                parts=arg.split()
                target=message.reply_to_message.from_user if message.reply_to_message else None
                amount_token=parts[-1] if len(parts)>1 else ""
                if not amount_token.isdigit() or int(amount_token)<=0:return await _send(message,"Payment","Use <code>/economy pay amount</code> as a reply to the recipient, with a positive whole number.")
                amount=int(amount_token)
                if target is None:return await _send(message,"Payment","Reply to the recipient’s message; username transfers are not supported because Telegram usernames are mutable.")
                if target.id==user_id:return await _send(message,"Payment","You cannot pay yourself.")
                debit=col.update_one({**key,"coins":{"$gte":amount}},{"$inc":{"coins":-amount}})
                if debit.modified_count!=1:return await _send(message,"Payment declined","Insufficient balance.")
                col.update_one({"user_id":target.id,"chat_id":chat_id},{"$inc":{"coins":amount}},upsert=True)
                return await _send(message,"Transfer complete",f"Transferred <b>{amount}</b> coins to {_esc(target.first_name)}.")
            if slug=="economy": return await _send(message,"Wallet",f"Balance: <b>{int(doc.get('coins',0))}</b> coins<br>Use <code>/{cmd} daily</code> once per day.")
            if slug=="karma":
                if message.reply_to_message and message.reply_to_message.from_user:
                    target=message.reply_to_message.from_user.id
                    col.update_one({"user_id":target,"chat_id":chat_id},{"$inc":{"karma":1}},upsert=True)
                    val=col.find_one({"user_id":target,"chat_id":chat_id}) or {}
                    return await _send(message,"Karma updated",f"{_esc(message.reply_to_message.from_user.first_name)} now has <b>{val.get('karma',0)}</b> karma.")
                return await _send(message,"Karma",f"Your karma score is <b>{doc.get('karma',0)}</b>. Reply with <code>/karma</code> to give karma.")
            col.update_one(key,{"$inc":{"xp":1},"$set":{"updated_at":datetime.now(timezone.utc)}},upsert=True)
            xp=int(doc.get("xp",0)); return await _send(message,"Level",f"XP: <b>{xp}</b> · Level <b>{int(math.sqrt(xp/25))+1}</b><br>XP is recorded when this command is used.")
        if slug=="birthdays":
            col=_col("plugin_birthdays")
            if col is None:return await _send(message,"Birthday feature unavailable","MongoDB is not connected.")
            if not arg:
                d=col.find_one({"user_id":user_id,"chat_id":chat_id})
                return await _send(message,"Birthday",f"Saved date: <code>{_esc(d.get('date','not set') if d else 'not set')}</code><br>Set: <code>/birthday DD-MM</code>")
            try: date=datetime.strptime(arg,"%d-%m").strftime("%d-%m")
            except ValueError:return await _send(message,"Invalid date","Use the format <code>DD-MM</code>, for example <code>/birthday 09-11</code>.")
            col.update_one({"user_id":user_id,"chat_id":chat_id},{"$set":{"date":date,"name":message.from_user.first_name if message.from_user else "User"}},upsert=True)
            return await _send(message,"Birthday saved",f"Your birthday is saved as <code>{date}</code> for this chat.")
        if slug in {"reminder","timer","scheduler"}:
            clean_arg=re.sub(r"^in\s+", "", arg.strip(), flags=re.I)
            match=re.match(r"^(\d+)(s|m|h)\s+(.+)$",clean_arg,re.I)
            if not match:return await _send(message,"Reminder", "Usage: <code>/remind 10m take a break</code> or <code>/timer 30s tea</code>.")
            n=int(match.group(1)); unit=match.group(2).lower(); note=match.group(3)[:300]; seconds=n*{"s":1,"m":60,"h":3600}[unit]
            if seconds>86400:return await _send(message,"Reminder", "Maximum reminder delay is 24 hours.")
            col=_col("plugin_reminders")
            if col is None:return await _send(message,"Reminder unavailable","MongoDB is not connected; reminder cannot be persisted.")
            due=datetime.now(timezone.utc)+timedelta(seconds=seconds)
            result=col.insert_one({"chat_id":chat_id,"user_id":user_id,"text":note,"due_at":due,"created_at":datetime.now(timezone.utc),"status":"pending"})
            _schedule_reminder(col, {"_id":result.inserted_id,"chat_id":chat_id,"user_id":user_id,"text":note,"due_at":due})
            return await _send(message,"Reminder set",f"I’ll remind you in <b>{n}{unit}</b>: {_esc(note)}")
        if slug in {"welcome_pro","goodbye_pro"}:
            if not message.chat or message.chat.type.value=="private":return await _send(message,"Group setting","Use this command in a group.")
            if not arg:
                from videl.utils.db import get_welcome, get_goodbye
                value=(get_welcome(chat_id) if slug=="welcome_pro" else get_goodbye(chat_id)) or {}
                return await _send(message,"Welcome message" if slug=="welcome_pro" else "Goodbye message",f"Current: {_esc(value.get('text','(not configured)'))}<br>Set with <code>/{message.command[0]} your message</code>")
            from videl.utils.db import set_welcome, set_goodbye
            (set_welcome if slug=="welcome_pro" else set_goodbye)(chat_id,arg[:800],True)
            return await _send(message,"Saved", "The group message template was saved in MongoDB.")
        if slug in {"antiflood_pro","antiraid","antibot","automod","spamwatch"}:
            if not await _admin(message):return await _send(message,"Permission denied","Only group admins can update moderation settings.")
            enabled=arg.lower() not in {"off","disable","0"}; key={"antiflood_pro":"antiflood","antiraid":"antiraid","antibot":"antibot","automod":"automod","spamwatch":"spamwatch"}[slug]
            col=_col("plugin_chat_settings")
            if col is None:return await _send(message,"Settings unavailable","MongoDB is not connected.")
            col.update_one({"chat_id":chat_id},{"$set":{key:enabled}},upsert=True)
            if slug=="antiflood_pro":
                from videl.utils.db import set_antiflood
                set_antiflood(chat_id,enabled)
            return await _send(message,"Moderation setting saved",f"<code>{key}</code> is now <b>{'enabled' if enabled else 'disabled'}</b>. Note: enforcement is provided by the core moderation modules for supported rules.")
        if slug in {"filters_pro","rules_pro","notes_pro","connect","channel","pinpro","pollpro","report","tagall","purgepro","clean","warnpro","blacklist_pro","approve_pro","captcha_pro","logpro","backup"}:
            return await _management(slug,message,arg)
        if slug=="statspro":
            db=_db()
            if db is None:return await _send(message,"Stats unavailable","MongoDB is not connected.")
            names=db.list_collection_names(); counts=[]
            for name in names[:12]:
                try: counts.append((name,db[name].estimated_document_count()))
                except Exception: pass
            return await _send(message,"MongoDB diagnostics","<br>".join(f"<code>{_esc(k)}</code>: {_esc(v)}" for k,v in counts) or "No collections yet.")
        if slug in {"helper_pro","musichelp"}:
            return await _send(message,"Videl command guide","Music: <code>/play</code>, <code>/queue</code>, <code>/skip</code>, <code>/pause</code>, <code>/resume</code>, <code>/stop</code><br>Groups: <code>/help</code> · Utilities: <code>/weather</code>, <code>/wiki</code>, <code>/calc</code>, <code>/qr</code><br>Use <code>/help</code> for categories.")
        if slug in {"anime","waifu","wallpaper","selfies","zimage"}:
            return await _send(message,"Image search", "Use <code>/waifu</code> for a safe random illustration, or <code>/wallpaper query</code> to search. This feature does not generate AI images.")
        if slug in {"insta","tiktok","pinterest"}: return
        if slug=="speedtest": return
        if slug=="quiz": return
        if slug=="fact": return
        if slug=="quotepro": return
        if slug=="dice":
            return await _send(message,"Dice", "Telegram dice animation:", buttons=[[InlineKeyboardButton("🎲 Roll", callback_data="dice_roll")]])
        if slug=="couples":
            members=[]
            async for member in bot.get_chat_members(chat_id,limit=100):
                if member.user and not member.user.is_bot: members.append(member.user)
            if len(members)<2:return await _send(message,"Couples","Need at least two visible group members.")
            a,b=random.sample(members,2); return await _send(message,"Random match",f"{_esc(a.first_name)} 💞 {_esc(b.first_name)}")
        if slug=="ship":
            if not message.reply_to_message or not message.reply_to_message.from_user:return await _send(message,"Ship", "Reply to someone’s message to create a playful match score.")
            a=user_id; b=message.reply_to_message.from_user.id
            score=hashlib.sha256(f"{min(a,b)}:{max(a,b)}".encode()).digest()[0]%101
            return await _send(message,"Compatibility",f"💞 <b>{score}%</b> (deterministic playful score; not a real compatibility test)")
        if slug=="userinfo": return
        if slug in {"anime_search","anilist","character","manga","weather","wiki","github","define","urban","translate","language","currency","shortener","unshort","ytsearch","calculator","math","qrgen","barcode","font","emojify","carbon","paste","tts","sysinfo","covid","joke","fact","truth","dare","quotepro","quote","memepro"}: return
        if slug in {"insta","tiktok","pinterest"}: return
        # Functional aliases are routed to the corresponding Videl core command.
        # Do not claim success if a command requires a privileged action / missing input.
        if slug in {"invite","gimme","ghost","clean","goodbye_pro","welcome_pro"}:
            return await _send(message,slug.replace("_"," ").title(), "This command requires a configured group context. Use <code>/help</code> or ask a group admin to configure it.")
        # Utility features that have no input do not fabricate results.
        return await _send(message,slug.replace("_"," ").title(),f"This command has no implementation yet. It has been disabled instead of returning fabricated output. Use <code>/help</code> to find supported features.")
    except asyncio.TimeoutError:
        return await _send(message,"Service timeout", "The real service did not respond in time. Please retry shortly.")
    except Exception as exc:
        log.exception("Plugin %s failed", slug)
        return await _send(message,"Command failed",f"<code>{_esc(str(exc)[:240])}</code><br>No demo result was generated.")


def _schedule_reminder(col, reminder: dict) -> None:
    due = reminder.get("due_at")
    if not isinstance(due, datetime):
        log.warning("Skipping reminder with an invalid due_at value: %s", reminder.get("_id"))
        return
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    delay = max(0.0, (due - datetime.now(timezone.utc)).total_seconds())

    async def deliver():
        if delay:
            await asyncio.sleep(delay)
        pending = col.find_one({"_id": reminder["_id"], "status": "pending"})
        if not pending:
            return
        try:
            await bot.send_message(
                pending["chat_id"],
                f"⏰ <a href='tg://user?id={pending['user_id']}'>Reminder</a>: {_esc(pending.get('text', ''))}",
            )
        except Exception:
            col.update_one({"_id": reminder["_id"], "status": "pending"}, {"$set": {"status": "failed", "failed_at": datetime.now(timezone.utc)}})
            log.exception("reminder delivery failed (%s)", reminder.get("_id"))
        else:
            col.update_one({"_id": reminder["_id"], "status": "pending"}, {"$set": {"status": "sent", "sent_at": datetime.now(timezone.utc)}})

    asyncio.create_task(deliver(), name=f"reminder-{reminder.get('_id')}")


async def restore_pending_reminders() -> int:
    """Re-arm MongoDB-persisted reminders when the Telegram client starts."""
    col = _col("plugin_reminders")
    if col is None:
        return 0
    reminders = list(col.find({"status": "pending"}).sort("due_at", 1).limit(500))
    for reminder in reminders:
        _schedule_reminder(col, reminder)
    return len(reminders)


async def _admin(message: Message) -> bool:
    if not message.from_user or not message.chat: return False
    if message.from_user.id in getattr(config,"ALL_PRIVILEGED",set()): return True
    try:
        m=await bot.get_chat_member(message.chat.id,message.from_user.id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR,ChatMemberStatus.OWNER)
    except Exception: return False


async def _management(slug: str, message: Message, arg: str):
    chat_id=message.chat.id; user_id=_who(message)
    if slug=="pollpro":
        parts=arg.split("|")
        if len(parts)<3:return await _send(message,"Create poll","Usage: <code>/pollpro Question | Option 1 | Option 2</code>")
        return await bot.send_poll(chat_id,parts[0].strip(),[x.strip() for x in parts[1:11]],is_anonymous=False)
    if slug=="tagall":
        if not await _admin(message):return await _send(message,"Permission denied","Only group admins can tag members.")
        names=[]
        async for m in bot.get_chat_members(chat_id,limit=200):
            if m.user and not m.user.is_bot and m.user.id!=user_id:names.append(f"<a href='tg://user?id={m.user.id}'>{_esc(m.user.first_name)}</a>")
        if not names:return await _send(message,"No members","No visible members were returned by Telegram.")
        for i in range(0,len(names),30): await bot.send_message(chat_id,"📣 "+" ".join(names[i:i+30]),disable_web_page_preview=True)
        return
    if slug in {"purgepro","clean"}:
        if not await _admin(message):return await _send(message,"Permission denied","Only group admins can purge messages.")
        if not message.reply_to_message:return await _send(message,"Purge","Reply to the first message, then run <code>/purge</code>.")
        start=message.reply_to_message.id; end=message.id
        ids=list(range(start,end+1))
        for i in range(0,len(ids),100): await bot.delete_messages(chat_id,ids[i:i+100])
        return
    if slug=="warnpro":
        if not await _admin(message):return await _send(message,"Permission denied","Only group admins can warn members.")
        target=message.reply_to_message.from_user if message.reply_to_message else None
        if not target:return await _send(message,"Warn","Reply to a user's message. Usage: <code>/warn reason</code>.")
        from videl.utils.db import add_warn,get_warn_limit
        count=add_warn(chat_id,target.id,arg or "No reason"); limit=get_warn_limit(chat_id)
        if count>=limit:
            try: await bot.ban_chat_member(chat_id,target.id); action="threshold reached; member banned"
            except Exception: action="threshold reached; bot could not ban (check rights)"
        else: action=f"{limit-count} warning(s) remain before the configured limit"
        return await _send(message,"Warning recorded",f"{_esc(target.first_name)} now has <b>{count}/{limit}</b> warnings. {_esc(action)}")
    if slug=="channel":
        from videl.utils.db import get_linked_channel,set_linked_channel,clear_linked_channel
        if not await _admin(message):return await _send(message,"Permission denied","Only group admins can change the linked channel.")
        if arg.lower() in {"off","clear"}:
            clear_linked_channel(chat_id)
            return await _send(message,"Channel unlinked","This group no longer has a linked channel.")
        if not arg:return await _send(message,"Linked channel",f"Current linked channel: <code>{_esc(get_linked_channel(chat_id) or 'none')}</code><br>Set <code>/channel -1001234567890</code> using the channel's numeric Telegram ID.")
        if not arg.lstrip("-").isdigit():return await _send(message,"Invalid channel ID","Use the channel's numeric Telegram ID (often starts with <code>-100</code>); usernames cannot be stored by this command.")
        target=int(arg)
        set_linked_channel(chat_id,target)
        return await _send(message,"Channel linked",f"Linked channel ID saved as <code>{target}</code>.")
    if slug=="backup":
        if not getattr(config,"is_owner",lambda _id:False)(user_id):return await _send(message,"Owner only","Only the bot owner may create a database snapshot.")
        db=_db()
        if db is None:return await _send(message,"Backup unavailable","MongoDB is not connected.")
        snapshot={name:list(db[name].find({},limit=250)) for name in db.list_collection_names()}
        data=json.loads(json.dumps(snapshot,default=str))
        from videl.utils.db import save_backup
        bid=save_backup(chat_id,data)
        return await _send(message,"Database snapshot saved",f"Backup id: <code>{_esc(bid)}</code>. Snapshot contains up to 250 documents per collection.")
    if slug in {"filters_pro","rules_pro","notes_pro","connect","pinpro","report","logpro","approve_pro","captcha_pro","blacklist_pro"}:
        if slug=="report":
            if not arg and not message.reply_to_message:return await _send(message,"Report", "Reply to a message or add a report reason.")
            target=message.reply_to_message
            text=f"⚠️ Report in <code>{chat_id}</code> from <code>{user_id}</code>: {_esc(arg or (target.text if target else 'reported message'))}"
            log_id=getattr(config,"LOGGER_ID",0)
            if not log_id:return await _send(message,"Report not delivered","Set LOGGER_ID to a moderator log channel first.")
            await bot.send_message(log_id,text); return await _send(message,"Report sent","The report was delivered to the configured moderator log channel.")
        if not await _admin(message):return await _send(message,"Permission denied","Only group admins can change this setting.")
        # These commands feed the existing Mongo-backed core management data.
        if slug=="rules_pro":
            from videl.modules.management_core import get_chat_setting,set_chat_setting
            if not arg:
                current=get_chat_setting(chat_id,"rules","")
                return await _send(message,"Group rules",_esc(current) if current else "No rules set. Use <code>/rulespro text</code>.")
            set_chat_setting(chat_id,"rules",arg[:4000])
            return await _send(message,"Rules saved","Saved to the same MongoDB setting used by <code>/rules</code>.")
        if slug=="filters_pro":
            parts=arg.split(" ",1)
            if parts and parts[0].lower()=="list":
                from videl.modules.management_core import _filters_col
                col=_filters_col(); docs=list(col.find({"chat_id":chat_id}).limit(30)) if col is not None else []
                return await _send(message,"Saved filters","<br>".join(f"<code>{_esc(d.get('keyword'))}</code> → {_esc(d.get('reply',''))}" for d in docs) or "No saved filters.")
            if len(parts)<2:return await _send(message,"Filter","Usage: <code>/filtpro trigger reply text</code> or <code>/filtpro list</code>.")
            from videl.modules.management_core import _filters_col
            col=_filters_col()
            if col is None:return await _send(message,"Unavailable","MongoDB is not connected.")
            col.update_one({"chat_id":chat_id,"keyword":parts[0].lower()},{"$set":{"reply":parts[1][:1500],"user_id":user_id}},upsert=True)
            return await _send(message,"Filter saved",f"Messages containing <code>{_esc(parts[0])}</code> will get the saved reply.")
        if slug=="notes_pro":
            parts=arg.split(" ",1)
            col=_col("mgmt_notes")
            if col is None:return await _send(message,"Unavailable","MongoDB is not connected.")
            action=parts[0].lower() if parts else ""
            if action=="list":
                notes=list(col.find({"chat_id":chat_id},{"name":1}).sort("name",1).limit(40))
                return await _send(message,"Saved notes","<br>".join(f"<code>#{_esc(note.get('name',''))}</code>" for note in notes) or "No notes saved.")
            if action in {"get","show"}:
                name=parts[1].strip().lower() if len(parts)>1 else ""
                if not name:return await _send(message,"Note","Usage: <code>/notespro get name</code>.")
                note=col.find_one({"chat_id":chat_id,"name":name})
                return await _send(message,"Saved note" if note else "Note not found",_esc(note.get("content","")) if note else f"No note named <code>{_esc(name)}</code>.")
            if action in {"del","delete","remove"}:
                name=parts[1].strip().lower() if len(parts)>1 else ""
                if not name:return await _send(message,"Note","Usage: <code>/notespro delete name</code>.")
                result=col.delete_one({"chat_id":chat_id,"name":name})
                return await _send(message,"Note deleted" if result.deleted_count else "Note not found",f"<code>#{_esc(name)}</code>")
            if len(parts)<2:return await _send(message,"Note","Usage: <code>/notespro name content</code>, <code>/notespro get name</code>, <code>/notespro delete name</code> or <code>/notespro list</code>.")
            col.update_one({"chat_id":chat_id,"name":parts[0].lower()},{"$set":{"content":parts[1][:3500],"saved_by":user_id}},upsert=True)
            return await _send(message,"Note saved",f"Saved <code>#{_esc(parts[0])}</code>.")
        if slug=="connect":
            from videl.utils.db import allow_connect
            allow_connect(chat_id,arg.lower() not in {"off","disable","0"})
            return await _send(message,"PM connection",f"PM connection is {'allowed' if arg.lower() not in {'off','disable','0'} else 'disabled'} for this group.")
        if slug=="pinpro":
            target=message.reply_to_message
            if not target:return await _send(message,"Pin message","Reply to the message you want pinned.")
            await target.pin(disable_notification=True); return await _send(message,"Pinned","The replied-to message was pinned.")
        if slug=="logpro":
            if not arg:return await _send(message,"Log channel","Usage: send <code>/log @channel</code> in the group, or <code>/log off</code>.")
            from videl.utils.db import set_log_channel
            if arg.lower()=="off":set_log_channel(chat_id,None); return await _send(message,"Log channel cleared","This group’s log channel was removed.")
            target=int(arg) if arg.lstrip("-").isdigit() else arg
            set_log_channel(chat_id,target); return await _send(message,"Log channel set",f"Saved <code>{_esc(target)}</code>. Ensure the bot can post there.")
        if slug=="approve_pro":
            target=message.reply_to_message.from_user if message.reply_to_message else None
            if not target:return await _send(message,"Approve user","Reply to a user’s message to approve them.")
            from videl.utils.db import approve_user
            approve_user(chat_id,target.id); return await _send(message,"Approved",f"{_esc(target.first_name)} is approved for this group.")
        if slug=="captcha_pro":
            from videl.utils.db import set_captcha,get_captcha
            enabled=arg.lower() not in {"off","disable","0"}; set_captcha(chat_id,enabled)
            return await _send(message,"Join captcha",f"Captcha is now {'enabled' if enabled else 'disabled'} for future joins.")
        if slug=="blacklist_pro":
            parts=arg.split(maxsplit=1)
            if len(parts)<1:return await _send(message,"Blacklist","Usage: <code>/blpro add word</code>, <code>/blpro del word</code> or <code>/blpro list</code>.")
            from videl.utils.db import add_blacklist,remove_blacklist,get_blacklist
            action=parts[0].lower(); word=parts[1] if len(parts)>1 else ""
            if action=="list":return await _send(message,"Blacklist","<br>".join(_esc(x.get("trigger")) for x in get_blacklist(chat_id)) or "No blacklist rules.")
            if not word:return await _send(message,"Blacklist","Provide a word or phrase.")
            if action=="add":add_blacklist(chat_id,word);return await _send(message,"Blacklist updated",f"Added <code>{_esc(word)}</code>.")
            if action in {"del","remove"}:remove_blacklist(chat_id,word);return await _send(message,"Blacklist updated",f"Removed <code>{_esc(word)}</code>.")
            return await _send(message,"Blacklist","Use add, del, or list.")
    return await _send(message,slug.replace("_"," ").title(),"No side effect was performed. Check <code>/help</code> for supported commands.")


# Telegram Dice is interactive; callback handler is registered once here.
@bot.on_callback_query(filters.regex(r"^dice_roll$"))
async def _dice_callback(_, query):
    try:
        await bot.send_dice(query.message.chat.id, emoji="🎲")
        await query.answer()
    except Exception as e:
        await query.answer(str(e)[:150], show_alert=True)


# AFK return/mention watcher, using persisted records (not an in-memory fake).
@bot.on_message(filters.incoming & ~filters.service, group=8)
async def _afk_watcher(_, message: Message):
    if not message.from_user or not message.text or message.text.startswith("/"): return
    col=_col("videl_afk")
    if col is None:return
    uid=message.from_user.id
    own=col.find_one({"user_id":uid})
    if own:
        col.delete_one({"_id":own["_id"]})
        try: await message.reply_text(f"Welcome back, {_esc(message.from_user.first_name)}. I cleared your AFK status.")
        except Exception: pass
    seen=set()
    if message.reply_to_message and message.reply_to_message.from_user:seen.add(message.reply_to_message.from_user.id)
    for entity in message.entities or []:
        if getattr(entity,"type",None) and str(entity.type).endswith("TEXT_MENTION") and entity.user:seen.add(entity.user.id)
    for target in seen:
        item=col.find_one({"user_id":target})
        if item:
            try: await message.reply_text(f"{_esc(item.get('reason','Away'))}",reply_to_message_id=message.id)
            except Exception: pass


# Lightweight passive XP tracker; only record legitimate group messages, never commands.
@bot.on_message(filters.group & filters.incoming & ~filters.service, group=9)
async def _xp_watcher(_, message: Message):
    if not message.from_user or message.from_user.is_bot or (message.text or "").startswith("/"): return
    col=_col("plugin_accounts")
    if col is None:return
    key={"user_id":message.from_user.id,"chat_id":message.chat.id}
    try:
        now=time.time(); old=col.find_one(key,projection={"last_xp":1})
        if old and now-float(old.get("last_xp",0))<45:return
        col.update_one(key,{"$inc":{"xp":1},"$set":{"last_xp":now}},upsert=True)
    except Exception:log.debug("xp tracker failed",exc_info=True)
