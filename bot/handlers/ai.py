"""
Videl0 • AI Chat & Image — aiogram
/ask, /gpt, /ai, /imagine, /draw, /summarize, /translate, /tts, /vision
Uses multi-provider fallback via services/ai_provider.py
Stores history in Supabase.
"""
import asyncio, io, re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from bot.config import AI_MAX_HISTORY
from bot.database import db
import bot.database_ext
from bot.rich_ui import rich_heading, rich_kv_table, rich_note, rich_esc, rich_code, rich_pre, RichDraft
from bot.services.ai_provider import ask_ai, generate_image, summarize_text, translate_text
from bot.utils.helpers import split_text

router = Router()

# ── helpers ─────────────────────────────────────────────────────────────────
def _extract_prompt(message: Message) -> str:
    if len(message.text.split(maxsplit=1))>1:
        return message.text.split(maxsplit=1)[1]
    # reply context
    if message.reply_to_message and message.reply_to_message.text:
        return message.reply_to_message.text
    return ""

# ── /ask /gpt /ai ───────────────────────────────────────────────────────────
@router.message(Command("ask","gpt","ai","chat"))
async def ai_chat_cmd(message: Message):
    prompt=_extract_prompt(message)
    if not prompt:
        return await message.reply("Usage: /ask <question>\nOr reply to a message with /ask")
    uid=message.from_user.id; cid=message.chat.id
    hist=await db.ai_history(uid, limit=AI_MAX_HISTORY)
    # stream via RichDraft for cool effect
    draft=RichDraft(message.bot, cid, message_thread_id=getattr(message,"message_thread_id",None))
    await draft.update(rich_heading("🤖 Videl is thinking…", level=3)+rich_note(f"<code>{rich_esc(prompt[:80])}</code>"))
    try:
        history=[{"role":h["role"],"content":h["content"]} for h in hist]
        ans=await ask_ai(prompt, history=history)
        await db.ai_add(uid, cid, "user", prompt)
        await db.ai_add(uid, cid, "assistant", ans)
        # chunk long answers
        if len(ans)>3900:
            await draft.finish(rich_heading("🤖 Videl", level=3)+rich_note(rich_esc(ans[:3900])))
            for chunk in split_text(ans[3900:], 3800):
                await message.answer(rich_note(rich_esc(chunk)))
        else:
            await draft.finish(rich_heading("🤖 Videl", level=3)+rich_note(rich_esc(ans)) + rich_note(f'💬 <code>/ask</code> to continue • <code>/clearhistory</code> to reset'))
    except Exception as e:
        await draft.finish(rich_heading("⚠️ AI Error", level=3)+rich_note(rich_esc(str(e))))

@router.message(Command("clearhistory","clearchat"))
async def clear_history(message: Message):
    await db.ai_clear(message.from_user.id)
    await message.answer("🗑 History cleared.")

# ── /imagine /draw ───────────────────────────────────────────────────────────
@router.message(Command("imagine","draw","gen","generate"))
async def imagine_cmd(message: Message):
    prompt=_extract_prompt(message)
    if not prompt:
        return await message.reply("Usage: /imagine <prompt>\nEx: /imagine a cyberpunk cat in space")
    m=await message.answer("🎨 Generating…")
    url=await generate_image(prompt)
    if not url:
        return await m.edit_text("❌ Image gen failed (no API key).")
    try:
        await message.bot.send_photo(message.chat.id, photo=url, caption=f"🎨 <b>{prompt[:200]}</b>\n🔗 <a href=\"{url}\">Open</a>", parse_mode=ParseMode.HTML)
        await m.delete()
    except:
        await m.edit_text(f"🎨 <a href=\"{url}\">Image</a> for: {prompt[:100]}")

# ── /summarize ───────────────────────────────────────────────────────────────
@router.message(Command("summarize","sum"))
async def summarize_cmd(message: Message):
    text=_extract_prompt(message)
    if message.reply_to_message and message.reply_to_message.text:
        text=message.reply_to_message.text
    if not text: return await message.reply("Reply to text with /summarize")
    m=await message.answer("📝 Summarizing…")
    summ=await summarize_text(text[:6000])
    await m.edit_text(rich_heading("📝 Summary", level=3)+rich_note(rich_esc(summ)))

# ── /translate /tr ───────────────────────────────────────────────────────────
@router.message(Command("translate","tr"))
async def translate_cmd(message: Message):
    parts=message.text.split(maxsplit=2)
    target="en"; text=""
    if len(parts)==3: target=parts[1]; text=parts[2]
    elif len(parts)==2:
        if len(parts[1])<=5 and parts[1].isalpha(): # lang code alone?
            if message.reply_to_message: text=message.reply_to_message.text or ""; target=parts[1]
            else: text=""
        else: text=parts[1]
    elif message.reply_to_message: text=message.reply_to_message.text or ""
    if not text: return await message.reply("Usage: /translate [lang] <text> or reply: /tr es")
    if not target: target="en"
    m=await message.answer(f"🌐 Translating to {target}…")
    trn=await translate_text(text[:2000], target)
    await m.edit_text(rich_heading(f"🌐 Translation → {target}", level=3)+rich_note(rich_esc(trn)))

# ── /tts ───────────────────────────────────────────────────────────────────
@router.message(Command("tts","speak"))
async def tts_cmd(message: Message):
    text=_extract_prompt(message)
    if not text: return await message.reply("Usage: /tts <text>")
    try:
        from gtts import gTTS
        import tempfile, os
        tts=gTTS(text[:400], lang="en")
        fn=tempfile.mktemp(suffix=".mp3")
        tts.save(fn)
        await message.bot.send_voice(message.chat.id, voice=open(fn,"rb"), caption=f"🔊 {text[:80]}")
        try: os.remove(fn)
        except: pass
    except Exception as e: await message.reply(f"TTS fail: {e}")

# ── /vision (caption image) ────────────────────────────────────────────────
@router.message(Command("vision"))
async def vision_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("Reply to an image with /vision <question>")
    q=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "What do you see?")
    photo=message.reply_to_message.photo[-1]
    file=await message.bot.get_file(photo.file_id)
    file_url=f"https://api.telegram.org/file/bot{message.bot.token}/{file.file_path}" if file.file_path else None
    if not file_url:
        return await message.reply("Could not get image URL.")
    hist=await db.ai_history(message.from_user.id, limit=6)
    ans=await ask_ai(q, history=[{"role":h["role"],"content":h["content"]} for h in hist], image_url=file_url)
    await message.answer(rich_heading("👁️ Vision", level=3)+rich_note(rich_esc(ans)))

# ── Natural mention: @Videl or reply pinging bot ───────────────────────────
@router.message(F.text & ~F.text.startswith("/"))
async def natural_ai(message: Message):
    # if bot mentioned or in private, or user replies to bot
    bot_info=await message.bot.get_me()
    txt=(message.text or "").lower()
    mentioned = f"@{bot_info.username.lower()}" in txt
    reply_to_bot = message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id==bot_info.id
    is_private = message.chat.type=="private"
    if not (mentioned or reply_to_bot or is_private):
        return
    # avoid double handling if command
    if txt.startswith("/"): return
    prompt=message.text.replace(f"@{bot_info.username}","").strip()
    if not prompt: prompt="hello"
    # call ask
    hist=await db.ai_history(message.from_user.id, limit=6)
    ans=await ask_ai(prompt, history=[{"role":h["role"],"content":h["content"]} for h in hist])
    await db.ai_add(message.from_user.id, message.chat.id, "user", prompt)
    await db.ai_add(message.from_user.id, message.chat.id, "assistant", ans)
    await message.reply(rich_esc(ans))
