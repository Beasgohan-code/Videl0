"""
Videl0 • Owner / Sudo — broadcast, gban, sudo manage, eval, shell, backup
"""
import asyncio, os, sys, traceback, subprocess, io, contextlib, time, json, html
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from bot.config import is_owner, is_sudo, OWNER_ID, LOG_CHANNEL_ID
from bot.database import db
import bot.database_ext
from bot.utils.fonts import sc, sb
from bot.rich_ui import rich_heading, rich_kv_table, rich_note, rich_esc, rich_code, rich_pre
from bot.utils.decorators import owner_only, sudo_only

router = Router()

async def _resolve_user(message: Message, arg: str) -> int|None:
    if message.reply_to_message and message.reply_to_message.from_user:
        # if no arg, use reply
        if not arg: return message.reply_to_message.from_user.id
    if not arg: return None
    arg=arg.strip().lstrip("@")
    if arg.lstrip("-").isdigit(): return int(arg)
    for ent in (message.entities or []):
        if ent.user: return ent.user.id
    # try username fetch via chat? not resolvable offline -> fail
    return None

# ── /addsudo /rmsudo /sudolist ────────────────────────────────────────────
@router.message(Command("addsudo"))
async def addsudo_cmd(message: Message):
    if not is_owner(message.from_user.id): return await message.reply("◍ ᴏᴡɴᴇʀ ᴏɴʟʏ.")
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    uid=await _resolve_user(message, arg)
    if not uid: return await message.reply("Usage: /addsudo <reply|id>")
    # persist in chat settings? we use chat settings of 0 as global
    # store in DB videl_chats id 0 settings sudo list? simpler: update .env note + DB
    # we store as setting in chat 0
    try:
        s=await db.get_chat_settings(0)
        lst=set(s.get("sudo_users", []))
        lst.add(uid)
        s["sudo_users"]=list(lst)
        await db.set_chat_settings(0,s)
        await message.answer(rich_heading(f"◍ {sc('sudo added')} ◍", level=3)+rich_note(f"User <code>{uid}</code> added. Restart may be needed for config reload."))
        if LOG_CHANNEL_ID:
            try: await message.bot.send_message(LOG_CHANNEL_ID, f"➕ Sudo added: {uid} by {message.from_user.id}")
            except: pass
    except Exception as e: await message.reply(f"Fail: {e}")

@router.message(Command("rmsudo"))
async def rmsudo_cmd(message: Message):
    if not is_owner(message.from_user.id): return await message.reply("◍ ᴏᴡɴᴇʀ ᴏɴʟʏ.")
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    uid=await _resolve_user(message, arg)
    if not uid: return await message.reply("Usage: /rmsudo <reply|id>")
    try:
        s=await db.get_chat_settings(0); lst=set(s.get("sudo_users",[])); lst.discard(uid)
        s["sudo_users"]=list(lst); await db.set_chat_settings(0,s)
        await message.answer(f"➖ Removed sudo <code>{uid}</code>")
    except Exception as e: await message.reply(f"Fail: {e}")

@router.message(Command("sudolist"))
async def sudolist_cmd(message: Message):
    s=await db.get_chat_settings(0)
    lst=s.get("sudo_users",[])
    # also include from config
    from bot.config import SUDO_USERS, OWNER_ID
    all_ids=set(lst) | set(SUDO_USERS) | ({OWNER_ID} if OWNER_ID else set())
    txt="<br>".join(f"<code>{i}</code>" for i in all_ids) or "None"
    await message.answer(rich_heading("◍ sᴜᴅᴏ ʟɪsᴛ", level=3)+rich_note(txt))

# ── /gban /ungban /gbans /block /unblock ──────────────────────────────────
@router.message(Command("gban"))
async def gban_cmd(message: Message):
    if not is_sudo(message.from_user.id): return await message.reply("Sudo only.")
    parts=message.text.split(maxsplit=2)
    arg=parts[1] if len(parts)>1 else ""
    reason=parts[2] if len(parts)>2 else "No reason"
    uid=await _resolve_user(message, arg)
    if not uid: return await message.reply("Usage: /gban <reply|id> [reason]")
    if is_sudo(uid): return await message.reply("Can't gban privileged.")
    await db.gban(uid, reason, message.from_user.id)
    await message.answer(rich_heading(f"⬪ {sc('gbanned')} ⬪", level=3)+rich_kv_table([("User",f"<code>{uid}</code>"),("Reason",rich_esc(reason))])+rich_note("Enforced in all chats on next message."))
    # try to kick from all known chats
    try:
        chats=[]
        if db.use_supabase:
            r=db.supabase.table("videl_chats").select("id").limit(100).execute()
            chats=[c["id"] for c in (r.data or []) if str(c["id"]).startswith("-100")]
        for cid in chats[:20]:
            try: await message.bot.ban_chat_member(cid, uid); await asyncio.sleep(0.2)
            except: pass
    except: pass

@router.message(Command("ungban"))
async def ungban_cmd(message: Message):
    if not is_sudo(message.from_user.id): return
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    uid=await _resolve_user(message, arg)
    if not uid: return await message.reply("Usage: /ungban <reply|id>")
    await db.ungban(uid)
    await message.answer(f"◍ Ungbanned <code>{uid}</code>")

@router.message(Command("gbans"))
async def gbans_cmd(message: Message):
    lst=await db.list_gbans()
    if not lst: return await message.answer("No gbans.")
    txt="<br>".join(f"<code>{g['user_id']}</code> — {rich_esc(g.get('reason',''))}" for g in lst[:30])
    await message.answer(rich_heading(f"⬪ {sc('gbans')} ⬪", level=3)+rich_note(txt)+(rich_note(f"+ {len(lst)-30} more…") if len(lst)>30 else ""))

@router.message(Command("block"))
async def block_cmd(message: Message):
    if not is_sudo(message.from_user.id): return
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    uid=await _resolve_user(message, arg)
    target=uid or (int(arg) if arg.lstrip("-").isdigit() else None)
    if not target: return await message.reply("Usage: /block <user|chat>")
    # decide chat or user by range: chats are negative or big, users positive
    if str(target).startswith("-"):
        await db.block_chat(target); await message.answer(f"◍ Blocked chat <code>{target}</code>")
    else:
        await db.block_user(target, "blocked", message.from_user.id); await message.answer(f"◍ Blocked user <code>{target}</code>")

@router.message(Command("unblock"))
async def unblock_cmd(message: Message):
    if not is_sudo(message.from_user.id): return
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    uid=await _resolve_user(message, arg)
    target=uid or (int(arg) if arg.lstrip("-").isdigit() else None)
    if not target: return await message.reply("Usage: /unblock <user|chat>")
    if str(target).startswith("-"):
        await db.unblock_chat(target); await message.answer(f"◍ Unblocked chat <code>{target}</code>")
    else:
        await db.unblock_user(target); await message.answer(f"◍ Unblocked user <code>{target}</code>")

# ── /broadcast ─────────────────────────────────────────────────────────────
@router.message(Command("broadcast","gcast"))
async def broadcast_cmd(message: Message):
    if not is_sudo(message.from_user.id): return
    text=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if message.reply_to_message: text=message.reply_to_message.text or text
    if not text: return await message.reply("Usage: /broadcast <text> or reply to message")
    # gather chats
    chats=[]
    try:
        if db.use_supabase:
            r=db.supabase.table("videl_chats").select("id").execute()
            chats=[c["id"] for c in (r.data or [])]
        elif db._sqlite:
            cur=db._sqlite.execute("SELECT id FROM videl_chats")
            chats=[row[0] for row in cur.fetchall()]
    except: chats=[]
    if not chats: return await message.reply("No chats to broadcast.")
    sent=0; failed=0
    prog=await message.answer(f"⬪ ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ to {len(chats)} chats…")
    for cid in chats:
        try:
            await message.bot.send_message(cid, f"⬪ <b>Broadcast</b>\n\n{text}")
            sent+=1
        except: failed+=1
        await asyncio.sleep(0.04)
        if sent%20==0:
            try: await prog.edit_text(f"⬪ {sent}/{len(chats)}…")
            except: pass
    await prog.edit_text(rich_heading("⬪ ʙʀᴏᴀᴅᴄᴀsᴛ Done", level=3)+rich_kv_table([("Sent",str(sent)),("Failed",str(failed))]))

# ── /eval /exec /shell ─────────────────────────────────────────────────────
@router.message(Command("eval"))
async def eval_cmd(message: Message):
    if not is_owner(message.from_user.id): return
    code=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not code and message.reply_to_message: code=message.reply_to_message.text or ""
    if not code: return await message.reply("Usage: /eval <code>")
    # strip code blocks
    if code.startswith("```"):
        code="\n".join(code.split("\n")[1:-1]) if "```" in code else code[3:-3]
    old_stdout=sys.stdout; buf=io.StringIO()
    try:
        sys.stdout=buf
        # provide context
        ctx={"bot":message.bot,"message":message,"db":db,"m":message,"chat":message.chat,"user":message.from_user}
        # try eval then exec
        try:
            result=eval(code, ctx)
            if asyncio.iscoroutine(result): result=await result
            out=str(result)
        except SyntaxError:
            exec(code, ctx)
            out=""
        stdout=buf.getvalue()
        text=(stdout+"\n"+out).strip() or "◍ Done (no output)"
        if len(text)>3800: text=text[:3800]+"…"
        await message.reply(rich_pre(text, "python"))
    except Exception:
        await message.reply(rich_pre(traceback.format_exc(), "python"))
    finally:
        sys.stdout=old_stdout

@router.message(Command("exec","shell","sh"))
async def shell_cmd(message: Message):
    if not is_owner(message.from_user.id): return
    cmd=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    if not cmd: return await message.reply("Usage: /shell <cmd>")
    try:
        proc=await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err=await asyncio.wait_for(proc.communicate(), timeout=15)
        text=(out.decode()+("\n"+err.decode() if err else "")).strip() or "(no output)"
        if len(text)>3800: text=text[:3800]+"…"
        await message.reply(rich_pre(f"$ {cmd}\n{text}","bash"))
    except Exception as e: await message.reply(f"Shell error: {e}")

# ── /logs /restart /backup /activevc /leave ─────────────────────────────────
@router.message(Command("logs"))
async def logs_cmd(message: Message):
    if not is_sudo(message.from_user.id): return
    try:
        with open("log.txt","r") as f:
            lines=f.readlines()[-60:]
        await message.reply(rich_pre("".join(lines)[-3500:], "log"))
    except Exception as e: await message.reply(f"No logs: {e}")

@router.message(Command("restart"))
async def restart_cmd(message: Message):
    if not is_owner(message.from_user.id): return
    await message.answer("🔄 Restarting…")
    os._exit(0)

@router.message(Command("backup"))
async def backup_cmd(message: Message):
    if not is_sudo(message.from_user.id): return
    await message.answer("◍ ʙᴀᴄᴋɪɴɢ ᴜᴘ…")
    # dump stats to file then upload to Dropbox if configured
    try:
        s=await db.get_stats()
        dump=json.dumps(s, indent=2)
        fname=f"/tmp/videl_backup_{int(time.time())}.json"
        with open(fname,"w") as f: f.write(dump)
        # Dropbox upload
        from bot.config import DROPBOX_ACCESS_TOKEN, DROPBOX_BACKUP_FOLDER
        if DROPBOX_ACCESS_TOKEN:
            import dropbox
            dbx=dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
            with open(fname,"rb") as f: dbx.files_upload(f.read(), f"{DROPBOX_BACKUP_FOLDER}/{os.path.basename(fname)}", mode=dropbox.files.WriteMode.overwrite)
            await message.answer("◍ Backup uploaded to Dropbox.")
        else:
            await message.answer(f"◍ Local backup at {fname}\n<code>{html.escape(dump)}</code>")
        # also log channel
        if LOG_CHANNEL_ID:
            try: await message.bot.send_document(LOG_CHANNEL_ID, document=open(fname,"rb"), caption="◍ ʙᴀᴄᴋᴜᴘ")
            except: pass
    except Exception as e: await message.answer(f"Backup fail: {e}")

@router.message(Command("activevc"))
async def activevc_cmd(message: Message):
    if not is_sudo(message.from_user.id): return
    # check queue entries as proxy for active
    try:
        if db._sqlite:
            cur=db._sqlite.execute("SELECT DISTINCT chat_id FROM videl_music_queue")
            chats=[r[0] for r in cur.fetchall()]
            await message.answer(rich_heading("⬪ Active Queues", level=3)+rich_note("<br>".join(f"<code>{c}</code>" for c in chats) or "None"))
        else:
            r=db.supabase.table("videl_music_queue").select("chat_id").execute()
            chats=list({x["chat_id"] for x in (r.data or [])})
            await message.answer(f"Active: {chats}")
    except Exception as e: await message.reply(f"Err: {e}")

@router.message(Command("leave"))
async def leave_cmd(message: Message):
    if not is_sudo(message.from_user.id): return
    arg=(message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1))>1 else "")
    cid=int(arg) if arg.lstrip("-").isdigit() else message.chat.id
    try:
        await message.bot.leave_chat(cid)
        await message.answer(f"Left {cid}")
    except Exception as e: await message.reply(f"Leave fail: {e}")
