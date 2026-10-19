# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Production AI Module
#  Cyber Dark Perfected • Multi-provider fallback: OpenAI → Groq → Gemini → Mistral
# --------------------------------------------------------------------------------

import asyncio
from pyrogram import filters
from pyrogram.types import Message

import config
from videl import bot, LOGGER
from videl.utils.formatters import sc, sb

try:
    from openai import AsyncOpenAI
    _HAS_OPENAI = True
except: _HAS_OPENAI = False

AI_SYSTEM = getattr(config, "AI_SYSTEM_PROMPT", "You are Videl — cyber dark perfect assistant. Help with music, admin, utilities. Be concise warm. Use small caps aesthetic when requested.")

async def _ask_ai(prompt: str, history=None) -> str:
    model = getattr(config, "AI_DEFAULT_MODEL", "gpt-4o-mini")
    msgs = [{"role":"system","content": AI_SYSTEM}]
    if history:
        msgs += history[-8:]
    msgs.append({"role":"user","content": prompt})

    # OpenAI
    if getattr(config, "OPENAI_API_KEY", "") and _HAS_OPENAI:
        try:
            c = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            r = await c.chat.completions.create(model="gpt-4o-mini", messages=msgs, max_tokens=800, temperature=0.7)
            return r.choices[0].message.content
        except Exception as e: LOGGER.warning(f"openai fail {e}")
    # Groq
    if getattr(config, "GROQ_API_KEY", ""):
        try:
            from groq import AsyncGroq
            g = AsyncGroq(api_key=config.GROQ_API_KEY)
            r = await g.chat.completions.create(model="llama-3.1-8b-instant", messages=msgs, max_tokens=800)
            return r.choices[0].message.content
        except Exception as e: LOGGER.warning(f"groq fail {e}")
    # Gemini
    if getattr(config, "GEMINI_API_KEY", ""):
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.GEMINI_API_KEY)
            m = genai.GenerativeModel("gemini-1.5-flash")
            joined = "\n".join(f"{x['role']}: {x['content']}" for x in msgs)
            r = m.generate_content(joined)
            return r.text
        except Exception as e: LOGGER.warning(f"gemini fail {e}")
    return f"◍ {sc('ai not configured')} ◍ — {sc('add openai_api_key / groq_api_key in .env')} ⬪"

@bot.on_message(filters.command(["ask","gpt","ai"]) & ~filters.forwarded)
async def ai_handler(_, message: Message):
    prompt = " ".join(message.command[1:]) if len(message.command)>1 else ""
    if not prompt and message.reply_to_message and message.reply_to_message.text:
        prompt = message.reply_to_message.text
    if not prompt:
        return await message.reply_text(f"◍ {sc('usage')}: /ask <{sc('question')}> ◍")
    m = await message.reply_text(f"◍ {sc('videl is thinking')} ⫶")
    ans = await _ask_ai(prompt)
    try:
        await m.edit_text(f"⬪ {sc('videl')} ⬪\n\n{ans}\n\n◍ /ask — {sc('continue')} ⫶ /clearhistory — {sc('reset')} ◍")
    except: await message.reply_text(ans)

@bot.on_message(filters.command(["imagine","draw","gen"]) & ~filters.forwarded)
async def imagine_handler(_, message: Message):
    prompt = " ".join(message.command[1:]) if len(message.command)>1 else ""
    if not prompt: return await message.reply_text(f"◍ {sc('usage')}: /imagine <{sc('prompt')}> ◍")
    wait = await message.reply_text(f"◍ {sc('generating')} ⫶ ⬪⬩◍⬩⬪")
    url = None
    if getattr(config, "OPENAI_API_KEY",""):
        try:
            c = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            r = await c.images.generate(model="dall-e-3", prompt=prompt, n=1, size="1024x1024")
            url = r.data[0].url
        except: pass
    if not url:
        import urllib.parse
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?nologo=true"
    try:
        await message.reply_photo(url, caption=f"◍ {sc(prompt[:80].lower())} ◍")
        await wait.delete()
    except: await wait.edit_text(f"◍ <a href=\"{url}\">{sc('open image')}</a> ◍")

LOGGER.info("✅ AI module loaded — cyber dark perfected")
