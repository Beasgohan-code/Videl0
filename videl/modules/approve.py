# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Approvals
#  Inspired by AnonymousX1025/FallenRobot • approve.py — approve users to bypass
#  locks, blacklist, antiflood, captcha — better than Rose (adds web dashboard sync)
#  /approve /unapprove /approved /approval — clean cyber-dark
# --------------------------------------------------------------------------------

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message
from videl import bot
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note, rich_send
from videl.utils.db import approve_user, disapprove_user, is_approved, list_approved

async def _resolve_target(m: Message):
    if m.reply_to_message and m.reply_to_message.from_user:
        return m.reply_to_message.from_user.id, m.reply_to_message.from_user.first_name
    if len(m.command)>1:
        arg=m.command[1]
        if arg.isdigit(): return int(arg), arg
        try:
            u=await bot.get_users(arg)
            return u.id, u.first_name
        except: return None, None
    return None, None

@bot.on_message(filters.command(["approve","addapprove"]) & filters.group & group_allowed & user_allowed)
async def approve_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    uid, name = await _resolve_target(m)
    if not uid:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('usage')} ◍",3)+rich_note(f"<code>/approve</code> {sc('reply to user or id')}"))
    if is_approved(m.chat.id, uid):
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('already approved')} ◍",3))
    approve_user(m.chat.id, uid)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('approved')} ◍",3)+rich_kv_table([("ᴜsᴇʀ", f"<a href=\"tg://user?id={uid}\">{rich_esc(name)}</a>"),("ɪᴅ", f"<code>{uid}</code>")]))

@bot.on_message(filters.command(["unapprove","rmapprove","disapprove"]) & filters.group & group_allowed & user_allowed)
async def unapprove_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    uid, name = await _resolve_target(m)
    if not uid:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('usage')} ◍",3)+rich_note(f"<code>/unapprove</code> {sc('reply')}"))
    if not is_approved(m.chat.id, uid):
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('not approved')} ◍",3))
    disapprove_user(m.chat.id, uid)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('unapproved')} ◍",3)+rich_kv_table([("ᴜsᴇʀ", f"<code>{uid}</code>")]))

@bot.on_message(filters.command(["approved","approvelist","approval"]) & filters.group & group_allowed & user_allowed)
async def approved_list(_, m: Message):
    arr=list_approved(m.chat.id)
    if not arr:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no approved')} ◍",3))
    txt="<br>".join(f"• <code>{uid}</code> — <a href=\"tg://user?id={uid}\">{uid}</a>" for uid in arr[:80])
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('approved users')} ⫶ {len(arr)} ◍",3)+rich_note(txt))

@bot.on_message(filters.command(["approval"]) & filters.group & group_allowed & user_allowed)
async def approval_toggle(_, m: Message):
    # show status like GroupHelp — just info
    arr=list_approved(m.chat.id)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('approval')} ⫶ {len(arr)} ◍",3)+rich_note(f"{sc('approved bypass locks/blacklist/antiflood')}"))
