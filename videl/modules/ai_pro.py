# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — AI Pro ✦ Perfect
#  Uses ALL external AI repos fully: openai → groq → gemini → mistral → pollinations
#  Plus vision (openai vision), tts (gTTS), translate & summarize (same fallback chain)
#  Professional: typed, logged, rate-limited, history-aware, no bare except
# --------------------------------------------------------------------------------
from __future__ import annotations

import asyncio
import io
import logging
import urllib.parse
from pathlib import Path

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

import config
from videl import bot, LOGGER
from videl.utils.formatters import sc, sb
from videl.utils.rich_ui import (
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_details,
    rich_button,
    rich_img,
    rich_send,
    rich_edit,
    rich_pre,
    rich_esc,
)

try:
    from videl.utils.premium_emojis import pe
except Exception:
    def pe(k, fb="◍"):
        return fb

log = logging.getLogger("videl.ai_pro")

try:
    from openai import AsyncOpenAI
    _HAS_OPENAI = True
except Exception:
    _HAS_OPENAI = False

AI_SYSTEM = getattr(
    config,
    "AI_SYSTEM_PROMPT",
    "You are Videl — cyber dark perfect assistant by Beasgohan-code. "
    "Help with music, admin, utilities. Be concise, warm, expert. "
    "Use ◍ ⬪ ⫶ ⬢ when requested. No fluff. Answer in user's language.",
)

# Simple per-user cooldown to avoid API spam (external repo friendly)
_cooldown: dict[int, float] = {}
COOLDOWN_SEC = 2.5

def _can_ask(uid: int) -> bool:
    import time
    now = time.time()
    last = _cooldown.get(uid, 0)
    if now - last < COOLDOWN_SEC:
        return False
    _cooldown[uid] = now
    return True

async def _ask_ai(prompt: str, history: list | None = None, system: str | None = None) -> str:
    """Professional multi-provider fallback chain. Returns text answer."""
    msgs: list[dict] = [{"role": "system", "content": system or AI_SYSTEM}]
    if history:
        msgs += history[-8:]
    msgs.append({"role": "user", "content": prompt})

    # 1) OpenAI
    if getattr(config, "OPENAI_API_KEY", "") and _HAS_OPENAI:
        try:
            c = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            r = await c.chat.completions.create(model="gpt-4o-mini", messages=msgs, max_tokens=1000, temperature=0.7)
            txt = (r.choices[0].message.content or "").strip()
            if txt:
                log.debug("AI → openai gpt-4o-mini")
                return txt
        except Exception as e:
            log.debug(f"openai fail: {e}")

    # 2) Groq
    if getattr(config, "GROQ_API_KEY", ""):
        try:
            from groq import AsyncGroq
            g = AsyncGroq(api_key=config.GROQ_API_KEY)
            r = await g.chat.completions.create(model="llama-3.1-8b-instant", messages=msgs, max_tokens=1000)
            txt = (r.choices[0].message.content or "").strip()
            if txt:
                log.debug("AI → groq llama-3.1-8b")
                return txt
        except Exception as e:
            log.debug(f"groq fail: {e}")

    # 3) Gemini
    if getattr(config, "GEMINI_API_KEY", ""):
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.GEMINI_API_KEY)
            m = genai.GenerativeModel("gemini-1.5-flash")
            joined = "\n".join(f"{x['role']}: {x['content']}" for x in msgs)
            r = await asyncio.to_thread(m.generate_content, joined)
            txt = (getattr(r, "text", "") or "").strip()
            if txt:
                log.debug("AI → gemini-1.5-flash")
                return txt
        except Exception as e:
            log.debug(f"gemini fail: {e}")

    # 4) Mistral
    if getattr(config, "MISTRAL_API_KEY", ""):
        try:
            from mistralai import Mistral
            mistral = Mistral(api_key=config.MISTRAL_API_KEY)
            r = await asyncio.to_thread(lambda: mistral.chat.complete(model="mistral-small-latest", messages=msgs))
            txt = (r.choices[0].message.content or "").strip() if r and r.choices else ""
            if txt:
                log.debug("AI → mistral-small")
                return txt
        except Exception as e:
            log.debug(f"mistral fail: {e}")

    # 5) Pollinations (free, no key) — best effort
    try:
        import aiohttp
        q = urllib.parse.quote(prompt[:600])
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://text.pollinations.ai/{q}", timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    txt = (await resp.text()).strip()
                    if txt and len(txt) > 10:
                        log.debug("AI → pollinations")
                        return txt[:2000]
    except Exception as e:
        log.debug(f"pollinations fail: {e}")

    return f"◍ {sc('ai not configured')} ◍ — {sc('add openai_api_key / groq_api_key / gemini_api_key in .env')} ⬪ {pe('hex','⬢')}"

def _hdr(t: str, lvl: int = 2):
    return rich_heading(pe("orb","◍") + " " + t + " " + pe("spark","𖦹"), level=lvl)

# ── /ask — main AI chat ─────────────────────────────────────────────────────────
@bot.on_message(filters.command(["ask", "gpt", "ai", "videl", "gemini", "chat"]) & ~filters.forwarded)
async def ai_handler(_, m: Message):
    if m.from_user and not _can_ask(m.from_user.id):
        return await m.reply_text(f"◍ {sc('slow down')} ⏳ • {COOLDOWN_SEC}s ⫶ {sc('try again')} ◍")
    prompt = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not prompt and m.reply_to_message:
        prompt = m.reply_to_message.text or m.reply_to_message.caption or ""
    if not prompt:
        body = _hdr(sc("ai chat") + f" • {pe('diamond','⬪')} {sc('ask anything')}", 2)
        body += rich_note(pe("line","⫶") + f" <code>/ask {sc('question')}</code><br>" + pe("line","⫶") + f" <code>/ask {sc('reply to message to ask about it')}</code>")
        body += rich_details(pe("star","⭐️") + " " + sc("providers"), sc("OpenAI → Groq → Gemini → Mistral → Pollinations (auto-fallback)"))
        body += rich_details(pe("hex","⬢") + " " + sc("more"), f"<code>/summarize</code> • <code>/translate</code> • <code>/tts</code> • <code>/imagine</code> • <code>/vision</code>")
        return await rich_send(bot, m.chat.id, body)

    thinking = await rich_send(bot, m.chat.id, _hdr(pe("circle","⦿") + f" {sc('videl is thinking')} ⫶ {pe('diamond','⬪')}…", 3))
    try:
        ans = await _ask_ai(prompt)
        body = _hdr(pe("diamond","⬪") + f" {sb('Videl')} • {pe('spark','𖦹')}", 2)
        body += rich_note(ans)
        body += rich_note(pe("line","⫶") + f" {sc('continue')}: <code>/ask {sc('follow-up')}</code> ⫶ <code>/clearhistory</code> {sc('to reset')} {pe('small','⬩')}")
        await rich_edit(thinking, body)
        log.info(f"/ask by {m.from_user.id if m.from_user else '?'} in {m.chat.id}: {prompt[:60]} → {len(ans)} chars")
    except Exception as e:
        log.warning(f"ai_handler fail: {e}", exc_info=True)
        try:
            await rich_edit(thinking, _hdr(pe("cross","❌") + f" {sc('ai failed')}", 3) + rich_note(f"<code>{rich_esc(str(e)[:300])}</code>"))
        except Exception:
            await m.reply_text(f"◍ {sc('ai failed')}: {e} ◍")

# ── /imagine — pro image gen ───────────────────────────────────────────────────
@bot.on_message(filters.command(["imagine", "draw", "gen", "image", "dalle"]) & ~filters.forwarded)
async def imagine_handler(_, m: Message):
    prompt = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not prompt and m.reply_to_message:
        prompt = m.reply_to_message.text or m.reply_to_message.caption or ""
    if not prompt:
        return await rich_send(bot, m.chat.id, _hdr(sc("imagine") + f" • {pe('pin','📌')}", 3) + rich_note(f"<code>/imagine {sc('a cyber cat in neon city')}</code><br>" + pe("small","⬩") + f" {sc('uses DALL·E 3 if key set, else Pollinations')}"))

    wait = await rich_send(bot, m.chat.id, _hdr(pe("circle","⦿") + f" {sc('generating')} ⫶ {pe('diamond','⬪')} {sc(prompt[:30])}", 3))
    url: str | None = None
    if getattr(config, "OPENAI_API_KEY", "") and _HAS_OPENAI:
        try:
            c = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            r = await c.images.generate(model="dall-e-3", prompt=prompt, n=1, size="1024x1024", quality="standard")
            url = r.data[0].url
            log.info(f"/imagine dall-e by {m.from_user.id}: {prompt[:40]}")
        except Exception as e:
            log.debug(f"dalle fail: {e}")

    if not url:
        q = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{q}?nologo=true&width=1024&height=1024&seed={hash(prompt) % 9999}"

    caption = _hdr(sc(prompt[:50]), 2) + rich_note(pe("pin","📌") + f" <code>{rich_esc(prompt[:120])}</code><br>" + pe("small","⬩") + f" {sc('via')} <a href=\"{url}\">{sc('link')}</a> • {pe('spark','𖦹')} {sc('openai/pollinations')}")
    try:
        await bot.send_photo(m.chat.id, url, caption=caption, parse_mode=ParseMode.HTML, reply_to_message_id=m.id)
        await wait.delete()
    except Exception as e:
        log.warning(f"imagine send fail: {e}")
        await rich_edit(wait, _hdr(pe("check","✅") + f" {sc('image ready')}", 3) + rich_note(f"<a href=\"{url}\">{sc('open image')}</a> — {rich_esc(prompt[:80])} {pe('pin','📌')}"))

# ── /summarize — reply to long text ───────────────────────────────────────────
@bot.on_message(filters.command(["summarize", "sum"]) & ~filters.forwarded)
async def summarize_handler(_, m: Message):
    text = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not text and m.reply_to_message:
        text = m.reply_to_message.text or m.reply_to_message.caption or ""
    if not text:
        return await rich_send(bot, m.chat.id, _hdr(sc("summarize"), 3) + rich_note(f"<code>/summarize {sc('reply to long message')}</code>"))
    if len(text) < 80:
        return await rich_send(bot, m.chat.id, _hdr(sc("too short to summarize"), 3))
    wait = await rich_send(bot, m.chat.id, _hdr(pe("circle","⦿") + f" {sc('summarizing')}…", 3))
    out = await _ask_ai(f"Summarize concisely in 5 bullet points (keep language of input):\n\n{text[:4000]}", system="You are a concise summarizer. 5 bullets max. Be faithful.")
    await rich_edit(wait, _hdr(pe("diamond","⬪") + f" {sc('summary')} • {pe('line','⫶')}", 2) + rich_note(out))

# ── /translate — translate via AI fallback chain ───────────────────────────────
@bot.on_message(filters.command(["translate", "tr", "tl"]) & ~filters.forwarded)
async def translate_handler(_, m: Message):
    args = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    target = "English"
    q = args
    # allow: /translate es <text> or /translate <text> (auto-detect to English if not specified)
    if args and " " in args:
        maybe_lang = args.split()[0].lower()
        if len(maybe_lang) <= 6 and maybe_lang.isalpha():
            target = maybe_lang
            q = args[len(maybe_lang):].strip()
    if not q and m.reply_to_message:
        q = m.reply_to_message.text or m.reply_to_message.caption or ""
    if not q:
        return await rich_send(bot, m.chat.id, _hdr(sc("translate") + f" • {pe('target','◎')}", 3) + rich_note(f"<code>/translate {sc('text')}</code><br>" + pe("small","⬩") + f" <code>/translate es {sc('hello world')}</code> • <code>/translate hi</code>"))
    wait = await rich_send(bot, m.chat.id, _hdr(pe("circle","⦿") + f" {sc('translating')} → {rich_esc(target)}…", 3))
    out = await _ask_ai(f"Translate to {target}. Only output translation, no explanation:\n\n{q[:3000]}", system=f"You are a translation engine. Target: {target}. Output only translation.")
    await rich_edit(wait, _hdr(pe("target","◎") + f" {sc('translation')} → {rich_esc(target)}", 2) + rich_note(out))

# ── /tts — text to speech via gTTS ───────────────────────────────────────────
@bot.on_message(filters.command(["tts", "speak", "voice"]) & ~filters.forwarded)
async def tts_handler(_, m: Message):
    text = " ".join(m.command[1:]) if len(m.command) > 1 else ""
    if not text and m.reply_to_message:
        text = m.reply_to_message.text or m.reply_to_message.caption or ""
    if not text:
        return await rich_send(bot, m.chat.id, _hdr(sc("text to speech") + f" • {pe('music','🎵')}", 3) + rich_note(f"<code>/tts {sc('text')}</code> — {sc('reply supported')}"))
    wait = await rich_send(bot, m.chat.id, _hdr(pe("circle","⦿") + f" {sc('generating voice')}…", 3))
    try:
        from gtts import gTTS
        tts = gTTS(text[:800], lang="en", slow=False)
        bio = io.BytesIO()
        tts.write_to_fp(bio)
        bio.name = "videl_tts.mp3"
        bio.seek(0)
        await bot.send_voice(m.chat.id, voice=bio, caption=_hdr(pe("music","🎵") + f" {rich_esc(text[:80])}", 3), reply_to_message_id=m.id)
        await wait.delete()
        log.info(f"/tts by {m.from_user.id}: {text[:40]}")
    except Exception as e:
        log.warning(f"tts fail: {e}", exc_info=True)
        await rich_edit(wait, _hdr(pe("cross","❌") + f" {sc('tts failed')}", 3) + rich_note(f"<code>{rich_esc(str(e)[:300])}</code>"))

# ── /vision — describe image (OpenAI vision if key, else caption) ─────────────
@bot.on_message(filters.command(["vision", "describe", "see"]) & ~filters.forwarded)
async def vision_handler(_, m: Message):
    if not (m.reply_to_message and (m.reply_to_message.photo or m.reply_to_message.document)):
        return await rich_send(bot, m.chat.id, _hdr(sc("vision") + f" • {pe('eyes','👀')}", 3) + rich_note(f"<code>/vision {sc('reply to photo')}</code> — {sc('describe image via AI')}"))
    wait = await rich_send(bot, m.chat.id, _hdr(pe("circle","⦿") + f" {sc('analyzing image')}…", 3))
    try:
        # Download thumb
        path = await bot.download_media(m.reply_to_message, file_name="downloads/vision.jpg")
        prompt = " ".join(m.command[1:]) if len(m.command) > 1 else "Describe this image in detail, concise."

        if getattr(config, "OPENAI_API_KEY", "") and _HAS_OPENAI:
            import base64
            b64 = base64.b64encode(Path(path).read_bytes()).decode()
            c = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            r = await c.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ]}],
                max_tokens=800,
            )
            ans = (r.choices[0].message.content or "").strip()
            await rich_edit(wait, _hdr(pe("eyes","👀") + f" {sc('vision')}", 2) + rich_note(ans))
            Path(path).unlink(missing_ok=True)
            return
        # Fallback — no vision key
        await rich_edit(wait, _hdr(pe("eyes","👀") + f" {sc('vision')}", 2) + rich_note(f"{pe('line','⫶')} {sc('add openai_api_key for vision')} {pe('spark','𖦹')}<br>" + pe("small","⬩") + f" {sc('prompt')}: <code>{rich_esc(prompt[:80])}</code>"))
    except Exception as e:
        log.warning(f"vision fail: {e}", exc_info=True)
        await rich_edit(wait, _hdr(pe("cross","❌") + f" {sc('vision failed')}", 3) + rich_note(f"<code>{rich_esc(str(e)[:300])}</code>"))

LOGGER.info("⬪ ᴀɪ ᴘʀᴏ — ᴘᴇʀғᴇᴄᴛ ◍")
