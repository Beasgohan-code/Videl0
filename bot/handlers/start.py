"""
Videl0 • Start / Help / Ping / Stats — Cyber Dark Perfected
◍ ⬪ ⫶  small caps + sans bold + cyber dark  ⫶ ⬪ ◍
"""
import time, psutil
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from aiogram.enums import ChatType

from bot.config import BOT_USERNAME, OWNER_ID, is_sudo, COMMANDS_HELP, BOT_NAME, SUPPORT_CHANNEL, SUPPORT_CHAT, WEBAPP_URL
from bot.database import db
import bot.database_ext
from bot.rich_ui import rich_heading, rich_kv_table, rich_note, rich_details, rich_send, rich_esc
from bot.utils.keyboards import start_kb, help_kb
from bot.utils.fonts import sc, sb, deco, header, PH, CYBER

router = Router()
start_time = time.time()

# ── /start ─ ◍ ᴡᴇʟᴄᴏᴍᴇ ────────────────────────────────────────────────────
@router.message(CommandStart())
async def start_cmd(message: Message):
    priv = is_sudo(message.from_user.id)
    rich_text = (
        rich_heading(f"◍ {sc('welcome to')} {sb(BOT_NAME)} ◍", level=1)
        + rich_kv_table([
            (sc("bot"), f"<code>@{BOT_USERNAME}</code>"),
            (sc("user"), rich_esc(message.from_user.full_name)),
            (sc("id"), f"<code>{message.from_user.id}</code>"),
            (sc("mode"), sb("Bot API 10.3") + f" ⫶ {sc('aiogram 3.31')} ⫶ {sc('richgram')}"),
        ])
        + rich_note(f"⬪ {sc('music')} ⫶ {sc('ai chat')} ⫶ {sc('utilities')} ⫶ {sc('group manager')} ─ {sc('all in one')}")
        + rich_details(f"◍ {sc('quick start')} ◍",
            rich_kv_table([
                (f"⫶ {sc('/play')}", sc("play music in vc / audio")),
                (f"⫶ {sc('/ask')}", sc("chat with ai")),
                (f"⫶ {sc('/help')}", sc("all commands")),
                (f"⫶ {sc('/ban')}", sc("admin tools")),
            ]), open=True)
        + rich_note(f'⬪ <a href="{SUPPORT_CHANNEL}">{sc("updates")}</a> ⫶ <a href="{SUPPORT_CHAT}">{sc("support")}</a> ⫶ <a href="{WEBAPP_URL}">{sc("dashboard")}</a> ⬪')
        + rich_note(f"◍ {sc('cyber dark • perfect • alive')} ◍")
    )
    kb = start_kb(is_owner=priv)
    try:
        await rich_send(message.bot, message.chat.id, rich_text, reply_markup=kb if not _has_rich else None)
    except:
        await message.answer(
            f"◍ <b>{sb(BOT_NAME)}</b> ◍\n"
            f"⫶ {sc(message.from_user.full_name.lower())} <code>{message.from_user.id}</code> ⫶\n\n"
            f"⬪ {sc('music')} ⫶ {sc('ai')} ⫶ {sc('utilities')} ⫶ {sc('group manager')} ⬪\n"
            f"{sc('use /help to explore')}",
            reply_markup=kb
        )
    await db.log_event("INFO", "/start", message.chat.id, message.from_user.id)

_has_rich=True
try:
    from aiogram.types import InputRichMessage
except: _has_rich=False

# ── /help — ◍ ʜᴇʟᴘ ─────────────────────────────────────────────────────────
@router.message(Command("help"))
async def help_cmd(message: Message):
    text = rich_heading(f"◍ {sc('videl help')} ◍", level=2)
    for cat, cmds in COMMANDS_HELP.items():
        # cat already has emoji, convert cmds to small caps style for display but keep code
        text += rich_details(f"⬪ {sc(cat.lower())} ⬪", "<code>" + " ⫶ ".join(cmds) + "</code>")
    text += rich_note(f"◍ {sc('tip: reply /help <module> e.g.')} <code>/help music</code> ◍")
    await message.answer(text, reply_markup=help_kb())

@router.message(F.text.regexp(r"^/help\s+(\w+)"))
async def help_module(message: Message):
    arg = message.text.split(maxsplit=1)[1].lower()
    mapping={
        "music": f"⬪ {sc('music')} ⫶ /play, /vplay, /queue, /skip, /stop, /pause, /resume, /seek, /shuffle, /lyrics",
        "ai": f"⬪ {sc('ai')} ⫶ /ask, /gpt, /imagine, /summarize, /translate, /tts, /vision",
        "admin": f"⬪ {sc('admin')} ⫶ /ban, /unban, /kick, /mute, /pin, /purge, /warn, /lock, /slowmode",
        "owner": f"◍ {sc('owner')} ◍ ⫶ /broadcast, /gban, /block, /addsudo, /backup, /eval, /logs",
        "utility":f"⫶ {sc('utility')} ⫶ /weather, /qr, /shorten, /calc, /wiki, /carbon, /git, /afk",
        "fun":f"◍ {sc('fun')} ◍ ⫶ /8ball, /dice, /flip, /ship, /joke, /meme, /quote",
        "general":f"◍ {sc('general')} ◍ ⫶ /start, /help, /ping, /stats, /id, /info",
    }
    txt=mapping.get(arg, f"◍ {sc('unknown module')} ◍ ⫶ {sc('try: music, ai, admin, owner, utility, fun, general')}")
    await message.answer(rich_heading(f"◍ {sc(arg)} ◍", level=3) + rich_note(rich_esc(txt)), reply_markup=help_kb())

# ── /ping — ⦿ ᴘᴏɴɢ ───────────────────────────────────────────────────────────
@router.message(Command("ping"))
async def ping_cmd(message: Message):
    t0=time.time()
    m=await message.answer(f"◍ {sc('pinging')} ⫶ ⬪⬩◍⬩⬪")
    t1=time.time()
    bot_ms=int((t1-t0)*1000)
    uptime=int(time.time()-start_time)
    h, rem=divmod(uptime,3600); mm, ss=divmod(rem,60)
    cpu=psutil.cpu_percent(interval=0.3); ram=psutil.virtual_memory().percent
    rich = (
        rich_heading(f"⦿ {sc('pong')} ⦿", level=3)
        + rich_kv_table([
            (sc("latency"), f"<code>{bot_ms} ms</code>"),
            (sc("uptime"), f"<code>{h}h {mm}m {ss}s</code>"),
            (sc("cpu"), f"<code>{cpu}%</code>"),
            (sc("ram"), f"<code>{ram}%</code>"),
            (sc("users"), f"<code>{(await db.get_stats())['users']}</code>"),
            (sc("chats"), f"<code>{(await db.get_stats())['chats']}</code>"),
        ])
        + rich_note(f"⬪ {sc('all systems operational')} ⫶ {sc('keep-alive & watchdog active')} ⬪")
    )
    await m.edit_text(rich, parse_mode="HTML")

# ── /stats — ⬪ sᴛᴀᴛs ─────────────────────────────────────────────────────────
@router.message(Command("stats"))
async def stats_cmd(message: Message):
    s=await db.get_stats()
    gbans=len(await db.list_gbans())
    uptime=int(time.time()-start_time)
    h, rem=divmod(uptime,3600); mm,_=divmod(rem,60)
    rich = (
        rich_heading(f"⬪ {sc('videl stats')} ⬪", level=2)
        + rich_kv_table([
            (sc("users"), f"<code>{s['users']}</code>"),
            (sc("chats"), f"<code>{s['chats']}</code>"),
            (sc("commands"), f"<code>{s['commands']}</code>"),
            (sc("gbans"), f"<code>{gbans}</code>"),
            (sc("uptime"), f"<code>{h}h {mm}m</code>"),
            (sc("sudo"), f"<code>{len(__import__('bot.config', fromlist=['ALL_PRIVILEGED']).ALL_PRIVILEGED)}</code>"),
        ])
        + rich_note(f"◍ <a href=\"{WEBAPP_URL}\">{sc('dashboard')}</a> ◍")
    )
    await message.answer(rich)

# ── /id — ◍ ɪᴅ ───────────────────────────────────────────────────────────────
@router.message(Command("id"))
async def id_cmd(message: Message):
    lines=[f"◍ {sc('you')}: <code>{message.from_user.id}</code>"]
    if message.reply_to_message and message.reply_to_message.from_user:
        lines.append(f"⫶ {sc('replied')}: <code>{message.reply_to_message.from_user.id}</code>")
    lines.append(f"⬪ {sc('chat')}: <code>{message.chat.id}</code> ({message.chat.type})")
    if message.chat.type != "private":
        lines.append(f"◎ {sc('title')}: {rich_esc(message.chat.title)}")
    await message.answer(rich_heading(f"◍ {sc('ids')} ◍", level=3)+rich_note("<br>".join(lines)))

@router.message(Command("info"))
async def info_cmd(message: Message):
    target=message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    rich = (
        rich_heading(f"◍ {sc('user info')} ◍", level=3)
        + rich_kv_table([
            (sc("name"), rich_esc(target.full_name)),
            (sc("id"), f"<code>{target.id}</code>"),
            (sc("username"), f"@{rich_esc(target.username)}" if target.username else "—"),
            (sc("is bot"), str(target.is_bot)),
            (sc("language"), target.language_code or "—"),
            (sc("is owner"), "⬪" if target.id==OWNER_ID else "◍"),
            (sc("is sudo"), "⬪" if is_sudo(target.id) else "◍"),
        ])
    )
    await message.answer(rich)

@router.message(Command("about"))
async def about_cmd(message: Message):
    rich = (
        rich_heading(f"⬪ {sc('about videl')} ⬪", level=2)
        + rich_kv_table([
            (sc("bot"), f"<code>@{BOT_USERNAME}</code>"),
            (sc("framework"), sb("aiogram 3.31") + f" ⫶ {sc('Bot API 10.3')}"),
            (sc("ui"), sc("richgram by badmunda05")),
            (sc("music"), sc("shizu core • yt-dlp • pytgcalls")),
            (sc("db"), sc("supabase + sqlite + dropbox")),
            (sc("hosting"), sc("vercel • fastapi keep-alive")),
        ])
        + rich_note(f"⫶ {sc('full-stack bot with admin, music, ai, utility, group manager')} ⫶\n"
                    f"◍ <a href=\"https://github.com/Beasgohan-code/Videl0\">{sc('github')}</a> ⫶ <a href=\"{SUPPORT_CHANNEL}\">{sc('channel')}</a> ◍")
    )
    await message.answer(rich)

@router.message(Command("repo"))
async def repo_cmd(message: Message):
    await message.answer(
        rich_heading(f"◍ {sc('videl repo')} ◍", level=3)
        + rich_note(f'◍ <a href="https://github.com/Beasgohan-code/Videl0">{sc("beasgohan-code/videl0")}</a> ◍<br>⫶ {sc("based on richgram & shizumusic by badmunda05")} ⫶')
        + rich_kv_table([(sc("stack"), sb("aiogram 3.31") + f" ⫶ {sc('fastapi • supabase • vercel')}")])
    )
