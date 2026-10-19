"""
Videl0 • Start / Help / Ping / Stats — aiogram + Richgram
Uses Bot API 10.3 Rich Messages for pretty tables.
"""
import time, psutil
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from aiogram.enums import ChatType
from aiogram.utils.markdown import hcode

from bot.config import BOT_USERNAME, OWNER_ID, is_owner, is_sudo, COMMANDS_HELP, BOT_NAME, SUPPORT_CHANNEL, SUPPORT_CHAT, WEBAPP_URL
from bot.database import db
import bot.database_ext
from bot.rich_ui import rich_heading, rich_kv_table, rich_note, rich_details, rich_send, rich_esc, rich_reply, RichDraft
from bot.utils.keyboards import start_kb, help_kb

router = Router()
start_time = time.time()

# ── /start ─────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def start_cmd(message: Message):
    priv = is_sudo(message.from_user.id)
    # Rich start card
    rich_text = (
        rich_heading(f"✨ Welcome to {BOT_NAME}", level=1)
        + rich_kv_table([
            ("Bot", f"<code>@{BOT_USERNAME}</code>"),
            ("User", rich_esc(message.from_user.full_name)),
            ("ID", f"<code>{message.from_user.id}</code>"),
            ("Mode", "🔥 Bot API 10.3 • aiogram 3.31 • Richgram"),
        ])
        + rich_note("🎶 Music • 🤖 AI Chat • 🧰 Utilities • 🛡️ Group Manager — all-in-one.")
        + rich_details("Quick Start", 
            rich_kv_table([
                ("/play", "Play music in VC / as audio"),
                ("/ask", "Chat with AI"),
                ("/help", "All commands"),
                ("/ban", "Admin tools (group)"),
            ]), open=True)
        + rich_note(f'🔗 <a href="{SUPPORT_CHANNEL}">Updates</a> • <a href="{SUPPORT_CHAT}">Support</a> • <a href="{WEBAPP_URL}">Dashboard</a>')
    )
    # Also add inline keyboard fallback for clients without rich
    kb = start_kb(is_owner=priv)
    try:
        await rich_send(message.bot, message.chat.id, rich_text, reply_markup=kb if not _has_rich else None)
        # fallback keyboard if rich succeeded (rich buttons already inside text, but also send kb)
        if _has_rich:
            # send plain keyboard under rich message via edit? aiogram rich_message can't carry InlineKeyboardMarkup? we add extra
            pass
        else:
            await message.answer("👋 Welcome! Use /help to see all features.", reply_markup=kb)
    except:
        await message.answer(
            f"✨ <b>Welcome to {BOT_NAME}</b>\n"
            f"👤 {message.from_user.full_name} (<code>{message.from_user.id}</code>)\n\n"
            f"🎶 Music • 🤖 AI • 🧰 Utilities • 🛡️ Group Manager\n"
            f"Use /help to explore.",
            reply_markup=kb
        )
    await db.log_event("INFO", "/start", message.chat.id, message.from_user.id)

# helper for rich availability in this module
_has_rich=True
try:
    from aiogram.types import InputRichMessage
except: _has_rich=False

# ── /help ──────────────────────────────────────────────────────────────────
@router.message(Command("help"))
async def help_cmd(message: Message):
    text = rich_heading("📚 Videl0 Help", level=2)
    for cat, cmds in COMMANDS_HELP.items():
        text += rich_details(cat, "<code>" + " • ".join(cmds) + "</code>")
    text += rich_note("💡 Tip: Reply /help <module> e.g. <code>/help music</code> for details.")
    await message.answer(text, reply_markup=help_kb())

@router.message(F.text.regexp(r"^/help\s+(\w+)"))
async def help_module(message: Message):
    arg = message.text.split(maxsplit=1)[1].lower()
    mapping={
        "music": "🎵 Music — /play, /vplay, /queue, /skip, /stop, /pause, /resume, /seek, /shuffle, /lyrics, /song, /playlist, /thumbnail, /autoplay",
        "ai": "🤖 AI — /ask, /gpt, /imagine, /summarize, /translate, /tts, /vision, /clearhistory",
        "admin": "🛡️ Admin — /ban, /unban, /kick, /mute, /unmute, /pin, /purge, /warn, /lock, /slowmode, /setwelcome",
        "owner": "👑 Owner — /broadcast, /gban, /block, /addsudo, /backup, /eval, /exec, /logs, /restart",
        "utility":"🧰 Utility — /weather, /qr, /shorten, /calc, /wiki, /carbon, /git, /afk, /tagall",
        "fun":"🎲 Fun — /8ball, /dice, /flip, /ship, /joke, /meme, /quote",
        "general":"🚀 General — /start, /help, /ping, /stats, /id, /info",
    }
    txt=mapping.get(arg, "❓ Unknown module. Try: music, ai, admin, owner, utility, fun, general")
    await message.answer(rich_heading(arg.title(), level=3) + rich_note(rich_esc(txt)), reply_markup=help_kb())

# ── /ping ──────────────────────────────────────────────────────────────────
@router.message(Command("ping"))
async def ping_cmd(message: Message):
    t0=time.time()
    m=await message.answer("🏓 Pinging…")
    t1=time.time()
    bot_ms=int((t1-t0)*1000)
    uptime=int(time.time()-start_time)
    h, rem=divmod(uptime,3600); mm, ss=divmod(rem,60)
    cpu=psutil.cpu_percent(interval=0.3); ram=psutil.virtual_memory().percent
    rich = (
        rich_heading("🏓 Pong!", level=3)
        + rich_kv_table([
            ("Bot Latency", f"<code>{bot_ms} ms</code>"),
            ("Uptime", f"<code>{h}h {mm}m {ss}s</code>"),
            ("CPU", f"<code>{cpu}%</code>"),
            ("RAM", f"<code>{ram}%</code>"),
            ("Users", f"<code>{(await db.get_stats())['users']}</code>"),
            ("Chats", f"<code>{(await db.get_stats())['chats']}</code>"),
        ])
        + rich_note("✅ All systems operational — keep-alive & watchdog active.")
    )
    await m.edit_text(rich, parse_mode="HTML")

# ── /stats ─────────────────────────────────────────────────────────────────
@router.message(Command("stats"))
async def stats_cmd(message: Message):
    s=await db.get_stats()
    gbans=len(await db.list_gbans())
    uptime=int(time.time()-start_time)
    h, rem=divmod(uptime,3600); mm,_=divmod(rem,60)
    rich = (
        rich_heading("📊 Videl0 Stats", level=2)
        + rich_kv_table([
            ("Users", f"<code>{s['users']}</code>"),
            ("Chats", f"<code>{s['chats']}</code>"),
            ("Commands", f"<code>{s['commands']}</code>"),
            ("Gbans", f"<code>{gbans}</code>"),
            ("Uptime", f"<code>{h}h {mm}m</code>"),
            ("Sudo", f"<code>{len(__import__('bot.config', fromlist=['ALL_PRIVILEGED']).ALL_PRIVILEGED)}</code>"),
        ])
        + rich_note(f"Dashboard: <a href=\"{WEBAPP_URL}\">{WEBAPP_URL}</a>")
    )
    await message.answer(rich)

# ── /id /info ───────────────────────────────────────────────────────────────
@router.message(Command("id"))
async def id_cmd(message: Message):
    lines=[f"👤 You: <code>{message.from_user.id}</code>"]
    if message.reply_to_message and message.reply_to_message.from_user:
        lines.append(f"👤 Replied user: <code>{message.reply_to_message.from_user.id}</code>")
    lines.append(f"💬 Chat: <code>{message.chat.id}</code> ({message.chat.type})")
    if message.chat.type != ChatType.PRIVATE:
        lines.append(f"🏷 Title: {rich_esc(message.chat.title)}")
    await message.answer(rich_heading("🆔 IDs", level=3)+rich_note("<br>".join(lines)))

@router.message(Command("info"))
async def info_cmd(message: Message):
    target=message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    rich = (
        rich_heading("👤 User Info", level=3)
        + rich_kv_table([
            ("Name", rich_esc(target.full_name)),
            ("ID", f"<code>{target.id}</code>"),
            ("Username", f"@{rich_esc(target.username)}" if target.username else "—"),
            ("Is Bot", str(target.is_bot)),
            ("Language", target.language_code or "—"),
            ("Is Owner", "✅" if target.id==OWNER_ID else "❌"),
            ("Is Sudo", "✅" if is_sudo(target.id) else "❌"),
        ])
    )
    await message.answer(rich)

@router.message(Command("about"))
async def about_cmd(message: Message):
    rich = (
        rich_heading("ℹ️ About Videl0", level=2)
        + rich_kv_table([
            ("Bot", f"<code>@{BOT_USERNAME}</code>"),
            ("Framework", "aiogram 3.31 • Bot API 10.3"),
            ("UI", "Richgram by Badmunda05"),
            ("Music", "ShizuMusic core • yt-dlp • pytgcalls"),
            ("DB", "Supabase + SQLite + Dropbox backup"),
            ("Hosting", "Vercel • FastAPI keep-alive"),
        ])
        + rich_note("Full-stack Telegram bot with Admin, Music, AI, Utility, Group Manager.\n"
                    f"Source: <a href=\"https://github.com/Beasgohan-code/Videl0\">GitHub</a> • Updates: <a href=\"{SUPPORT_CHANNEL}\">Channel</a>")
    )
    await message.answer(rich)

@router.message(Command("repo"))
async def repo_cmd(message: Message):
    await message.answer(
        rich_heading("💻 Videl0 Repo", level=3)
        + rich_note('GitHub: <a href="https://github.com/Beasgohan-code/Videl0">Beasgohan-code/Videl0</a><br>Based on Richgram & ShizuMusic by Badmunda05')
        + rich_kv_table([("Stack","aiogram 3.31 + FastAPI + Supabase + Vercel")])
    )
