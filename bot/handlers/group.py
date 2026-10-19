"""
Videl0 • Group — welcome, goodbye, filters, notes, rules, reports, language
"""
import re
from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import Command
from aiogram.enums import ChatType, ChatMemberStatus

from bot.config import is_sudo
from bot.database import db
import bot.database_ext
from bot.rich_ui import rich_heading, rich_kv_table, rich_note, rich_esc, rich_details

router = Router()

# ── Welcome/Goodbye triggers on join/left ───────────────────────────────────
@router.chat_member(F.new_chat_member.status == ChatMemberStatus.MEMBER)
async def welcome_new(event: ChatMemberUpdated):
    try:
        chat_id=event.chat.id
        welcome, media=await db.get_welcome(chat_id)
        if not welcome: return
        # replace placeholders
        user=event.new_chat_member.user
        txt=welcome.replace("{name}", user.full_name).replace("{username}", f"@{user.username or ''}").replace("{chat}", event.chat.title)
        if media:
            try: await event.bot.send_photo(chat_id, media, caption=txt)
            except: await event.bot.send_message(chat_id, txt)
        else:
            await event.bot.send_message(chat_id, txt)
    except: pass

@router.message(F.new_chat_members)
async def welcome_via_message(message: Message):
    try:
        welcome, media=await db.get_welcome(message.chat.id)
        if not welcome: return
        for u in message.new_chat_members:
            txt=welcome.replace("{name}", u.full_name).replace("{chat}", message.chat.title)
            if media: 
                try: await message.bot.send_photo(message.chat.id, media, caption=txt)
                except: await message.bot.send_message(message.chat.id, txt)
            else:
                await message.answer(txt)
    except: pass

# ── /setwelcome /welcome /delwelcome ───────────────────────────────────────
@router.message(Command("setwelcome"))
async def set_welcome(message: Message):
    if message.chat.type==ChatType.PRIVATE: return
    if not await _is_admin(message): return
    text=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not text and message.reply_to_message: text=message.reply_to_message.text or ""
    if not text: return await message.reply("Usage: /setwelcome <text with {name} {chat}>\nEx: /setwelcome Welcome {name} to {chat}!")
    media=None
    if message.reply_to_message and message.reply_to_message.photo:
        media=message.reply_to_message.photo[-1].file_id
    await db.set_welcome(message.chat.id, text, media)
    await message.answer(f"✅ Welcome set:\n<code>{rich_esc(text)}</code>")

@router.message(Command("welcome"))
async def get_welcome(message: Message):
    w,_=await db.get_welcome(message.chat.id)
    await message.answer(f"Welcome: <code>{rich_esc(w)}</code>" if w else "No welcome set. Use /setwelcome")

@router.message(Command("delwelcome","resetwelcome"))
async def del_welcome(message: Message):
    if not await _is_admin(message): return
    await db.set_welcome(message.chat.id, None, None)
    await message.answer("✅ Welcome deleted.")

# ── /goodbye ────────────────────────────────────────────────────────────────
@router.message(Command("setgoodbye","setleave"))
async def set_goodbye(message: Message):
    if not await _is_admin(message): return
    text=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not text: return await message.reply("Usage: /setgoodbye <text>")
    await db.set_goodbye(message.chat.id, text)
    await message.answer("✅ Goodbye set.")

@router.message(Command("goodbye","leave"))
async def get_goodbye(message: Message):
    w=await db.get_goodbye(message.chat.id)
    await message.answer(f"Goodbye: <code>{rich_esc(w)}</code>" if w else "No goodbye set.")

# ── /rules /setrules ───────────────────────────────────────────────────────
@router.message(Command("setrules"))
async def set_rules(message: Message):
    if not await _is_admin(message): return
    text=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not text and message.reply_to_message: text=message.reply_to_message.text or ""
    if not text: return await message.reply("Usage: /setrules <rules>")
    await db.set_rules(message.chat.id, text)
    await message.answer("✅ Rules set.")

@router.message(Command("rules"))
async def get_rules(message: Message):
    r=await db.get_rules(message.chat.id)
    if not r: return await message.answer("No rules. Admins: /setrules <text>")
    await message.answer(rich_heading("📜 Rules", level=3)+rich_note(rich_esc(r)))

# ── Filters ─────────────────────────────────────────────────────────────────
@router.message(Command("filter"))
async def add_filter(message: Message):
    if not await _is_admin(message): return
    parts=message.text.split(maxsplit=2)
    if len(parts)<3: return await message.reply("Usage: /filter <keyword> <reply text>\nEx: /filter hi Hello there!")
    kw=parts[1]; reply_text=parts[2]
    await db.add_filter(message.chat.id, kw, reply_text)
    await message.answer(f"✅ Filter <code>{kw}</code> added.")

@router.message(Command("stopfilter","delfilter","rmfilter"))
async def del_filter(message: Message):
    if not await _is_admin(message): return
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not arg: return await message.reply("Usage: /stopfilter <keyword>")
    await db.delete_filter(message.chat.id, arg)
    await message.answer(f"✅ Filter <code>{arg}</code> removed.")

@router.message(Command("filters"))
async def list_filters(message: Message):
    flts=await db.get_filters(message.chat.id)
    if not flts: return await message.answer("No filters.")
    txt="<br>".join(f"• <code>{rich_esc(f['keyword'])}</code> → {rich_esc(f['reply_text'][:50])}" for f in flts)
    await message.answer(rich_heading("🔍 Filters", level=3)+rich_note(txt))

# ── Notes ───────────────────────────────────────────────────────────────────
@router.message(Command("save","note"))
async def save_note(message: Message):
    if not await _is_admin(message): return
    parts=message.text.split(maxsplit=2)
    if len(parts)<2: return await message.reply("Usage: /save <name> [content] or reply to media")
    name=parts[1]
    content=parts[2] if len(parts)>2 else (message.reply_to_message.text if message.reply_to_message and message.reply_to_message.text else "")
    media=None
    if message.reply_to_message and (message.reply_to_message.photo or message.reply_to_message.document):
        media=(message.reply_to_message.photo[-1].file_id if message.reply_to_message.photo else message.reply_to_message.document.file_id)
        if not content: content=message.reply_to_message.caption or ""
    if not content and not media: return await message.reply("Give content or reply to media.")
    await db.add_note(message.chat.id, name, content, media)
    await message.answer(f"✅ Saved note <code>{name}</code>. Get with /get {name}")

@router.message(Command("get"))
async def get_note(message: Message):
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not arg: return await message.reply("Usage: /get <name>")
    note=await db.get_note(message.chat.id, arg)
    if not note: return await message.answer("Note not found.")
    if note.get("media_file_id"):
        try:
            await message.bot.send_photo(message.chat.id, note["media_file_id"], caption=note.get("content",""))
            return
        except: pass
    await message.answer(note.get("content",""))

@router.message(Command("clear","delnote"))
async def clear_note(message: Message):
    if not await _is_admin(message): return
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not arg: return await message.reply("Usage: /clear <name>")
    await db.delete_note(message.chat.id, arg)
    await message.answer(f"✅ Deleted note <code>{arg}</code>")

@router.message(Command("notes"))
async def list_notes(message: Message):
    # fetch via direct sql
    try:
        if db._sqlite:
            cur=db._sqlite.execute("SELECT name FROM videl_notes WHERE chat_id=?", (message.chat.id,))
            rows=[r[0] for r in cur.fetchall()]
            if not rows: return await message.answer("No notes.")
            await message.answer("📒 Notes: <code>"+" • ".join(rows)+"</code>")
        elif db.use_supabase:
            r=db.supabase.table("videl_notes").select("name").eq("chat_id", message.chat.id).execute()
            rows=[x["name"] for x in (r.data or [])]
            await message.answer("📒 Notes: "+" • ".join(rows) if rows else "No notes.")
    except: await message.answer("No notes.")

# ── #hashtag notes trigger ──────────────────────────────────────────────────
@router.message(F.text.regexp(r"^#(\w+)"))
async def hashtag_note(message: Message):
    m=re.match(r"^#(\w+)", message.text or "")
    if not m: return
    note=await db.get_note(message.chat.id, m.group(1))
    if not note: return
    if note.get("media_file_id"):
        try:
            await message.bot.send_photo(message.chat.id, note["media_file_id"], caption=note.get("content",""))
            return
        except: pass
    await message.reply(note.get("content",""))

# ── /report ─────────────────────────────────────────────────────────────────
@router.message(Command("report"))
async def report_cmd(message: Message):
    if not message.reply_to_message: return await message.reply("Reply to a message to report to admins.")
    reason=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "No reason")
    try:
        admins=await message.bot.get_chat_administrators(message.chat.id)
        mentions=" ".join(f"<a href=\"tg://user?id={a.user.id}\">{a.user.full_name}</a>" for a in admins if not a.user.is_bot)
        await message.answer(f"🚨 Report by {message.from_user.full_name}:\nReason: {reason}\nReported msg: <a href=\"https://t.me/c/{str(message.chat.id).replace('-100','')}/{message.reply_to_message.message_id}\">link</a>\n\nAdmins: {mentions}")
        await message.bot.send_message(message.reply_to_message.from_user.id, f"⚠️ You were reported in {message.chat.title}: {reason}", disable_notification=True)
    except: await message.reply("Could not notify admins (bot not admin?).")

# ── /staff /admins ───────────────────────────────────────────────────────────
@router.message(Command("staff","admins","adminlist"))
async def staff_cmd(message: Message):
    try:
        admins=await message.bot.get_chat_administrators(message.chat.id)
        txt=rich_heading("👮 Staff", level=3)
        for a in admins:
            role="👑 Creator" if a.status=="creator" else "🛡️ Admin"
            txt+=rich_note(f"{role}: {rich_esc(a.user.full_name)} — <code>{a.user.id}</code>")
        await message.answer(txt)
    except Exception as e: await message.reply(f"Fail: {e}")

# ── /setlang /language ─────────────────────────────────────────────────────
@router.message(Command("setlang","language","lang"))
async def setlang_cmd(message: Message):
    if not await _is_admin(message): return
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not arg: return await message.reply("Usage: /setlang <en|hi|pa>\nAvailable: en, hi, pa")
    arg=arg.lower()
    if arg not in ("en","hi","pa"): return await message.reply("Supported: en, hi, pa")
    await db.set_chat_lang(message.chat.id, arg)
    await message.answer(f"✅ Language set to <code>{arg}</code>")

async def _is_admin(message: Message) -> bool:
    if is_sudo(message.from_user.id): return True
    if message.chat.type==ChatType.PRIVATE: return False
    try:
        m=await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        if m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR): return True
    except: pass
    await message.reply("🔒 Admins only.")
    return False

# ── locks enforcement (url/bots/etc) ────────────────────────────────────────
@router.message(F.text)
async def locks_enforce(message: Message):
    if message.chat.type==ChatType.PRIVATE: return
    if is_sudo(message.from_user.id): return
    try:
        locks=await db.get_locks(message.chat.id)
        txt=(message.text or "")
        if locks.get("url") and re.search(r"https?://", txt):
            try: await message.delete(); return
            except: pass
        if locks.get("invite") and re.search(r"t\.me/(?:joinchat/|\+)", txt):
            try: await message.delete(); return
            except: pass
        if locks.get("spam") and len(txt)>1000:
            try: await message.delete()
            except: pass
    except: pass

# ── anti-flood on new member bots ───────────────────────────────────────────
@router.message(F.new_chat_members)
async def anti_bot_lock(message: Message):
    locks=await db.get_locks(message.chat.id)
    if not locks.get("bots"): return
    for u in message.new_chat_members:
        if u.is_bot:
            try:
                await message.bot.ban_chat_member(message.chat.id, u.id)
                await message.answer(f"🤖 Bot {u.full_name} auto-banned (bots locked).")
            except: pass
