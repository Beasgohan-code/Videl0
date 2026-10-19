# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Production AI • Cyber Dark
#  Multi-provider fallback: OpenAI → Groq → Gemini → Mistral → Pollinations
# --------------------------------------------------------------------------------
from __future__ import annotations
import asyncio, urllib.parse
from pyrogram import filters
from pyrogram.types import Message
import config
from videl import bot, LOGGER
from videl.utils.formatters import sc, sb

try: from openai import AsyncOpenAI; _HAS_OPENAI=True
except: _HAS_OPENAI=False

AI_SYSTEM = getattr(config, "AI_SYSTEM_PROMPT", "You are Videl — cyber dark perfect assistant. Help with music, admin, utilities. Be concise warm. Use ◍ ⬪ ⫶ when requested.")

async def _ask_ai(prompt: str, history=None) -> str:
    msgs=[{"role":"system","content":AI_SYSTEM}]
    if history: msgs+=history[-8:]
    msgs.append({"role":"user","content":prompt})
    # OpenAI
    if getattr(config,"OPENAI_API_KEY","") and _HAS_OPENAI:
        try:
            c=AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            r=await c.chat.completions.create(model="gpt-4o-mini", messages=msgs, max_tokens=900, temperature=0.7)
            if r.choices[0].message.content: return r.choices[0].message.content
        except Exception as e: LOGGER.debug(f"openai fail {e}")
    # Groq
    if getattr(config,"GROQ_API_KEY",""):
        try:
            from groq import AsyncGroq
            g=AsyncGroq(api_key=config.GROQ_API_KEY)
            r=await g.chat.completions.create(model="llama-3.1-8b-instant", messages=msgs, max_tokens=900)
            if r.choices[0].message.content: return r.choices[0].message.content
        except Exception as e: LOGGER.debug(f"groq fail {e}")
    # Gemini (sync API but small prompt)
    if getattr(config,"GEMINI_API_KEY",""):
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.GEMINI_API_KEY)
            m=genai.GenerativeModel("gemini-1.5-flash")
            joined="\n".join(f"{x['role']}: {x['content']}" for x in msgs)
            r= m.generate_content(joined)
            if r.text: return r.text
        except Exception as e: LOGGER.debug(f"gemini fail {e}")
    # Mistral
    if getattr(config,"MISTRAL_API_KEY",""):
        try:
            from mistralai import Mistral
            mistral=Mistral(api_key=config.MISTRAL_API_KEY)
            r= await asyncio.to_thread(lambda: mistral.chat.complete(model="mistral-small-latest", messages=msgs))
            if r and r.choices: return r.choices[0].message.content
        except Exception as e: LOGGER.debug(f"mistral fail {e}")
    return f"◍ {sc('ai not configured')} ◍ — {sc('add openai_api_key / groq_api_key in .env')} ⬪"

@bot.on_message(filters.command(["ask","gpt","ai","videl","gemini"]) & ~filters.forwarded)
async def ai_handler(_, message: Message):
    prompt=" ".join(message.command[1:]) if len(message.command)>1 else ""
    if not prompt and message.reply_to_message and message.reply_to_message.text: prompt=message.reply_to_message.text
    if not prompt: return await message.reply_text(f"◍ {sc('usage')}: /ask <{sc('question')}> ◍")
    thinking=await message.reply_text(f"◍ {sc('videl is thinking')} ⫶ ⬪⬩◍⬩⬪")
    ans=await _ask_ai(prompt)
    try: await thinking.edit_text(f"⬪ {sb('Videl')} ⬪\n\n{ans}\n\n◍ /ask — {sc('continue')} ⫶ /clearhistory — {sc('reset')} ◍")
    except: await message.reply_text(ans)

@bot.on_message(filters.command(["imagine","draw","gen","image"]) & ~filters.forwarded)
async def imagine_handler(_, message: Message):
    prompt=" ".join(message.command[1:]) if len(message.command)>1 else ""
    if not prompt: return await message.reply_text(f"◍ {sc('usage')}: /imagine <{sc('prompt')}> ◍")
    wait=await message.reply_text(f"◍ {sc('generating')} ⫶ ⬪⬩◍⬩⬪")
    url=None
    if getattr(config,"OPENAI_API_KEY","") and _HAS_OPENAI:
        try:
            c=AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            r=await c.images.generate(model="dall-e-3", prompt=prompt, n=1, size="1024x1024")
            url=r.data[0].url
        except: pass
    if not url: url=f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?nologo=true&width=1024&height=1024"
    try:
        await message.reply_photo(url, caption=f"◍ {sc(prompt[:80].lower())} ◍")
        await wait.delete()
    except Exception:
        try: await wait.edit_text(f"◍ <a href=\"{url}\">{sc('open image')}</a> ◍")
        except: await message.reply_text(url)

LOGGER.info("⬪ ᴀɪ ᴍᴏᴅᴜʟᴇ — ᴘᴇʀғᴇᴄᴛ ◍")
