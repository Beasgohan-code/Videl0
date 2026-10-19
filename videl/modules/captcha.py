# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Captcha / Verification
#  Inspired by Rose captcha + FallenRobot welcome captcha
#  Math captcha (no external API) + button captcha fallback
#  /captcha on/off/math/button — better than Rose (adds TOTP-like timeout mute)
# --------------------------------------------------------------------------------

import asyncio, random, time
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from pyrogram.enums import ChatMemberStatus
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note, rich_send
from videl.utils.db import get_captcha, set_captcha

# pending: (chat_id, user_id) -> {answer, msg_id, expire}
_PENDING: dict[tuple[int,int], dict] = {}

def _gen_math() -> tuple[str, int]:
    a=random.randint(1, 25); b=random.randint(1, 25)
    op=random.choice(["+","-","×"])
    if op=="+": ans=a+b; expr=f"{a} + {b}"
    elif op=="-":
        if a<b: a,b=b,a
        ans=a-b; expr=f"{a} − {b}"
    else:
        # keep small
        a=random.randint(2, 9); b=random.randint(2, 9)
        ans=a*b; expr=f"{a} × {b}"
    return expr, ans

async def _kick_pending(chat_id: int, user_id: int, msg_id: int | None, reason: str):
    # delete captcha message, mute/kick
    _PENDING.pop((chat_id,user_id), None)
    try:
        if msg_id: await bot.delete_messages(chat_id, msg_id)
    except: pass
    try:
        from datetime import datetime, timedelta
        from pyrogram.types import ChatPermissions
        # soft action: mute until captcha solved, then kick if timeout
        # But we don't have perms pre — try kick
        await bot.ban_chat_member(chat_id, user_id)
        # if mode is kick → stay banned; if mute → unban after but keep mute?
        # For now kick (auto-remove) — admins can add verification later
    except Exception as e: LOGGER.debug(f"[captcha] kick fail: {e}")

@bot.on_message(filters.command(["captcha","welcome_captcha","verification"]) & filters.group & group_allowed & user_allowed)
async def captcha_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    args=m.text.split()
    if len(args)==1:
        cur=get_captcha(m.chat.id)
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('captcha')} ◍",3)+rich_kv_table([("sᴛᴀᴛᴜs", "ON" if cur["enabled"] else "OFF"),("ᴍᴏᴅᴇ", f"<code>{cur['mode']}</code>"),("ᴛɪᴍᴇᴏᴜᴛ", f"<code>{cur['timeout']}s</code>")])+rich_note(f"<code>/captcha on</code> — {sc('enable')}<br><code>/captcha off</code><br><code>/captcha math</code> — {sc('math')}<br><code>/captcha button</code> — {sc('button click')}"))
    arg=args[1].lower()
    cur=get_captcha(m.chat.id)
    if arg in ("on","yes","enable","true"):
        set_captcha(m.chat.id, True, cur["mode"], cur["timeout"])
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('captcha enabled')} ◍",3))
    if arg in ("off","no","disable","false"):
        set_captcha(m.chat.id, False, cur["mode"], cur["timeout"])
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('captcha disabled')} ◍",3))
    if arg in ("math","button"):
        set_captcha(m.chat.id, cur["enabled"], arg, cur["timeout"])
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('captcha mode')} ◍",3)+rich_kv_table([("ᴍᴏᴅᴇ", f"<code>{arg}</code>")]))
    if arg.isdigit():
        t=int(arg)
        set_captcha(m.chat.id, cur["enabled"], cur["mode"], max(30, min(t, 600)))
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('timeout updated')} ◍",3))
    return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('usage')} ◍",3)+rich_note("<code>/captcha on/off/math/button/120</code>"))


@bot.on_message(filters.new_chat_members & group_allowed, group=2)
async def captcha_on_join(_, m: Message):
    chat_id=m.chat.id
    cap=get_captcha(chat_id)
    if not cap.get("enabled"): return
    mode=cap.get("mode","math")
    timeout=int(cap.get("timeout",120))
    for user in m.new_chat_members:
        if user.is_bot: continue
        # need restrict perm to mute first — best effort
        try:
            from pyrogram.types import ChatPermissions
            await bot.restrict_chat_member(chat_id, user.id, ChatPermissions(can_send_messages=False))
        except: pass
        if mode=="math":
            expr, ans=_gen_math()
            # generate 4 options (1 correct + 3 fake)
            opts={ans}
            while len(opts)<4:
                opts.add(ans+random.randint(-8,8))
                if 0 in opts: opts.remove(0)
            opts=list(opts); random.shuffle(opts)
            rows=[]
            for o in opts:
                cb="captcha_ok" if o==ans else f"captcha_fail:{ans}"
                rows.append(InlineKeyboardButton(f"{o}", callback_data=cb))
            # 2x2 grid
            kb=InlineKeyboardMarkup([rows[i:i+2] for i in range(0, len(rows), 2)])
            try:
                sent=await bot.send_message(chat_id, f"◍ {sc('welcome')} <a href=\"tg://user?id={user.id}\">{rich_esc(user.first_name)}</a> ◍\n⬪ {sc('verify you are human')} ⫶\n<b>{expr} = ?</b> ◍ {sc('you have')} {timeout}s ⫶", reply_markup=kb)
                _PENDING[(chat_id,user.id)]={"answer": ans, "msg": sent.id, "expire": time.time()+timeout}
                # schedule timeout check
                async def _timeout():
                    await asyncio.sleep(timeout)
                    pending=_PENDING.get((chat_id,user.id))
                    if not pending: return
                    # still pending → kick
                    await _kick_pending(chat_id, user.id, pending["msg"], "timeout")
                    try: await bot.send_message(chat_id, f"◍ <code>{user.id}</code> {sc('kicked — captcha timeout')} ◍")
                    except: pass
                asyncio.create_task(_timeout())
            except Exception as e: LOGGER.warning(f"[captcha] send fail: {e}")
        else: # button mode
            kb=InlineKeyboardMarkup([[InlineKeyboardButton(f"◍ {sc('i am human')} ◍", callback_data="captcha_ok")]])
            try:
                sent=await bot.send_message(chat_id, f"◍ {sc('welcome')} <a href=\"tg://user?id={user.id}\">{rich_esc(user.first_name)}</a> ◍\n⬪ {sc('click to verify')} ⫶ {timeout}s ◍", reply_markup=kb)
                _PENDING[(chat_id,user.id)]={"answer": 0, "msg": sent.id, "expire": time.time()+timeout}
                async def _timeout2():
                    await asyncio.sleep(timeout)
                    pending=_PENDING.get((chat_id,user.id))
                    if not pending: return
                    await _kick_pending(chat_id, user.id, pending["msg"], "timeout")
                asyncio.create_task(_timeout2())
            except Exception as e: LOGGER.warning(f"[captcha] button fail: {e}")


@bot.on_callback_query(filters.regex(r"^captcha_"))
async def captcha_cb(_, q: CallbackQuery):
    if not q.message or not q.message.chat: return
    chat_id=q.message.chat.id
    user_id=q.from_user.id
    pend=_PENDING.get((chat_id,user_id))
    if not pend:
        # maybe someone else clicking? check any pending for this chat where callback user matches?
        # For group join, only new user should solve — but allow anyone? we restrict to user only
        return await q.answer(f"◍ {sc('not for you')} ◍", show_alert=True)
    data=q.data or ""
    if data=="captcha_ok":
        # correct
        _PENDING.pop((chat_id,user_id), None)
        try:
            await q.message.delete()
        except: pass
        try:
            from pyrogram.types import ChatPermissions
            await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True))
        except: pass
        await q.answer(f"◍ {sc('verified')} ◍")
        try: await bot.send_message(chat_id, f"◍ <a href=\"tg://user?id={user_id}\">{rich_esc(q.from_user.first_name)}</a> {sc('verified — welcome')} ◍")
        except: pass
        return
    if data.startswith("captcha_fail"):
        _PENDING.pop((chat_id,user_id), None)
        try: await q.message.delete()
        except: pass
        try: await bot.ban_chat_member(chat_id, user_id)
        except: pass
        await q.answer(f"◍ {sc('wrong — kicked')} ◍", show_alert=True)
        return
    await q.answer()
