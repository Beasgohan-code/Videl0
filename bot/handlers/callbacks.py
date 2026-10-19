"""
Videl0 • Callbacks — all inline keyboards
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.utils.fonts import sc, sb
from bot.rich_ui import rich_heading, rich_kv_table, rich_note, rich_esc
from bot.utils.keyboards import music_controls_kb, help_kb, owner_panel_kb
from bot.config import is_sudo, OWNER_ID
from bot.database import db
import bot.database_ext

router = Router()

@router.callback_query(F.data == "close")
async def cb_close(cq: CallbackQuery):
    try: await cq.message.delete()
    except:
        try: await cq.answer("Closed", show_alert=False)
        except: pass

@router.callback_query(F.data.startswith("help:"))
async def cb_help(cq: CallbackQuery):
    cat=cq.data.split(":",1)[1]
    from bot.handlers.start import COMMANDS_HELP
    # map
    key={
        "general":"◍ ɢᴇɴᴇʀᴀʟ", "music":"⬪ ᴍᴜsɪᴄ", "ai":"⦿ ᴀɪ ᴄʜᴀᴛ",
        "utility":"◎ ᴜᴛɪʟɪᴛʏ", "admin":"⦿ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴ", "owner":"◍ ᴏᴡɴᴇʀ/Sudo", "fun":"𖦹 ғᴜɴ"
    }.get(cat, cat)
    await cq.answer()
    # build text
    cmds=[]
    for k,v in COMMANDS_HELP.items():
        if cat in k.lower() or k==key:
            cmds=v; break
    if not cmds and cat in COMMANDS_HELP: cmds=COMMANDS_HELP[cat]
    if not cmds: cmds=["No data"]
    text=rich_heading(key, level=3)+rich_note("<br>".join(f"<code>{c}</code>" for c in (cmds or [])))
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back", callback_data="help_back")]])
    try: await cq.message.edit_text(text, reply_markup=kb)
    except: await cq.message.answer(text)

@router.callback_query(F.data == "help_back")
async def cb_help_back(cq: CallbackQuery):
    await cq.answer()
    from bot.utils.keyboards import help_kb
    await cq.message.edit_text(rich_heading("📚 Help", level=2)+rich_note("Pick a category:"), reply_markup=help_kb())

@router.callback_query(F.data == "start_back")
async def cb_start_back(cq: CallbackQuery):
    await cq.answer()
    from bot.config import BOT_USERNAME, BOT_NAME
    from bot.utils.keyboards import start_kb
    await cq.message.edit_text(rich_heading(f"✨ Welcome to {BOT_NAME}", level=1)+rich_note("Use /help to explore."), reply_markup=start_kb(is_owner=is_sudo(cq.from_user.id)))

@router.callback_query(F.data == "owner_panel")
async def cb_owner_panel(cq: CallbackQuery):
    if not is_sudo(cq.from_user.id):
        return await cq.answer("Sudo only", show_alert=True)
    await cq.answer()
    await cq.message.edit_text(rich_heading("◍ ᴏᴡɴᴇʀ ᴘᴀɴᴇʟ", level=2)+rich_note("Manage bot:"), reply_markup=owner_panel_kb())

@router.callback_query(F.data.startswith("owner:"))
async def cb_owner(cq: CallbackQuery):
    if not is_sudo(cq.from_user.id): return await cq.answer("Sudo only", show_alert=True)
    action=cq.data.split(":",1)[1]
    await cq.answer()
    if action=="stats":
        s=await db.get_stats()
        await cq.message.edit_text(rich_heading(f"⬪ {sc('stats')} ⬪", level=3)+rich_kv_table([("Users",str(s["users"])),("Chats",str(s["chats"])),("Cmds",str(s["commands"]))]))
    elif action=="gbans":
        lst=await db.list_gbans()
        txt="<br>".join(f"<code>{g['user_id']}</code>" for g in lst[:20]) or "None"
        await cq.message.edit_text(rich_heading(f"⬪ {sc('gbans')} ⬪", level=3)+rich_note(txt))
    elif action=="sudolist":
        s=await db.get_chat_settings(0)
        await cq.message.edit_text(rich_heading(f"◍ {sc('sudo')} ◍", level=3)+rich_note(str(s.get("sudo_users","[]"))))
    elif action=="backup":
        await cq.message.edit_text("◍ ᴜsᴇ /backup command.")
    elif action=="restart":
        await cq.message.edit_text("🔄 Use /restart")
    elif action=="logs":
        await cq.message.edit_text("📜 Use /logs")
    elif action=="broadcast":
        await cq.message.edit_text("⬪ Use /broadcast <text>")

# ── Music callbacks ─────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("music:"))
async def cb_music(cq: CallbackQuery):
    action=cq.data.split(":",1)[1]
    chat_id=cq.message.chat.id if cq.message else cq.from_user.id
    if action=="pause":
        try:
            from bot.services.music_service import pause_call
            await pause_call(chat_id); await cq.answer("Paused")
        except Exception as e: await cq.answer(str(e)[:120])
    elif action=="resume":
        try:
            from bot.services.music_service import resume_call
            await resume_call(chat_id); await cq.answer("Resumed")
        except: await cq.answer("Resumed")
    elif action=="skip":
        q=await db.queue_list(chat_id)
        if not q: return await cq.answer("Empty")
        await db.queue_pop(chat_id)
        nxt=await db.queue_list(chat_id)
        if nxt: await cq.answer(f"Skipped → {nxt[0]['title'][:30]}")
        else: await cq.answer("Stopped")
        try: await cq.message.edit_text("⏭ Skipped. Use /queue for next.")
        except: pass
    elif action=="stop":
        await db.queue_clear(chat_id)
        try:
            from bot.services.music_service import stop_call
            await stop_call(chat_id)
        except: pass
        await cq.answer("Stopped")
        try: await cq.message.edit_text("⬩ sᴛᴏᴘᴘᴇᴅ & cleared.")
        except: pass
    elif action=="queue":
        q=await db.queue_list(chat_id)
        if not q: return await cq.answer("Empty", show_alert=True)
        txt=rich_heading("📜 Queue", level=3)+"<br>".join(f"{i}. {rich_esc(s['title'][:40])}" for i,s in enumerate(q[:8],1))
        await cq.answer()
        await cq.message.answer(txt)
    elif action=="shuffle":
        await db.queue_shuffle(chat_id); await cq.answer("Shuffled")
    elif action=="clear":
        await db.queue_clear(chat_id); await cq.answer("Cleared")

@router.callback_query(F.data == "noop")
async def cb_noop(cq: CallbackQuery):
    await cq.answer()

# ── Bio / Fun inline ─────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("fun:"))
async def cb_fun(cq: CallbackQuery):
    await cq.answer()
    action=cq.data.split(":",1)[1] if ":" in cq.data else ""
    if action=="dice":
        import random; await cq.message.reply(f"◍ {random.randint(1,6)} ◍")
