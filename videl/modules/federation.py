# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Federations
#  Inspired by PaulSonOfLars/tgbot (Marie) • global_bans / feds
#  and FallenRobot feds, AnnieXMusic federated bans — better than Rose
#  Rose closed-source fed system → re-implemented clean for Videl
#  Docs: /newfed /delfed /renamefed /chatfed /joinfed /leavefed /fban /unfban
#        /fedinfo /fedadmins /fpromote /fdemote /fedbanlist /myfeds /fedchats
# --------------------------------------------------------------------------------

import re
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import Message
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.permissions import is_user_authorized
from videl.utils.formatters import sc
from videl.utils.rich_ui import rich_esc, rich_heading, rich_kv_table, rich_note, rich_send
from videl.utils.db import (
    create_fed, delete_fed, get_fed, list_feds, join_fed_chat, leave_fed_chat,
    get_chat_fed, set_chat_fed, fban, unfban, get_fban, list_fbans,
    fed_add_admin, fed_remove_admin, fed_list_admins, is_fed_admin, get_fed_chats
)
import config

def _fed_id(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", name.lower().replace(" ", "_"))[:32]

@bot.on_message(filters.command("newfed") & filters.group & group_allowed & user_allowed)
async def newfed_cmd(_, m: Message):
    if not m.text or len(m.text.split(maxsplit=1))<2:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('usage')} ◍",3)+rich_note(f"<code>/newfed &lt;name&gt;</code>"))
    name=m.text.split(maxsplit=1)[1].strip()
    fid=_fed_id(name)
    if not fid: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('invalid name')} ◍",3))
    if get_fed(fid): return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('fed exists')} ◍",3))
    create_fed(fid, name, m.from_user.id)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('federation created')} ◍",3)+rich_kv_table([("ɴᴀᴍᴇ", rich_esc(name)),("ɪᴅ", f"<code>{fid}</code>")])+rich_note(f"⬪ {sc('add groups')}: /joinfed {fid} ⫶"))

@bot.on_message(filters.command("delfed") & group_allowed & user_allowed)
async def delfed_cmd(_, m: Message):
    if not m.text or len(m.text.split(maxsplit=1))<2:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('usage')} ◍",3)+rich_note("<code>/delfed &lt;fed_id&gt;</code>"))
    fid=m.text.split(maxsplit=1)[1].strip().lower()
    fed=get_fed(fid)
    if not fed: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('fed not found')} ◍",3))
    if fed["owner"]!=m.from_user.id and m.from_user.id!=config.OWNER_ID:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('owner only')} ◍",3))
    delete_fed(fid)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('federation deleted')} ◍",3))

@bot.on_message(filters.command(["joinfed","chatfed"]) & filters.group & group_allowed & user_allowed)
async def joinfed_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    if not m.text or len(m.text.split(maxsplit=1))<2:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('usage')} ◍",3)+rich_note("<code>/joinfed &lt;fed_id&gt;</code>"))
    fid=m.text.split(maxsplit=1)[1].strip().lower()
    if not get_fed(fid): return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('fed not found')} ◍",3))
    set_chat_fed(m.chat.id, fid)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('joined federation')} ◍",3)+rich_kv_table([("ғᴇᴅ", f"<code>{fid}</code>")]))

@bot.on_message(filters.command("leavefed") & filters.group & group_allowed & user_allowed)
async def leavefed_cmd(_, m: Message):
    if not await is_user_authorized(m): return
    cur=get_chat_fed(m.chat.id)
    if not cur: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('not in fed')} ◍",3))
    set_chat_fed(m.chat.id, None)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('left federation')} ◍",3)+rich_note(f"<code>{cur}</code>"))

@bot.on_message(filters.command("fban") & group_allowed & user_allowed)
async def fban_cmd(_, m: Message):
    # resolve target
    uid=None; reason="No reason"
    if m.reply_to_message and m.reply_to_message.from_user:
        uid=m.reply_to_message.from_user.id
        if len(m.text.split(maxsplit=1))>1: reason=m.text.split(maxsplit=1)[1]
    elif len(m.command)>1:
        arg=m.command[1]
        if arg.isdigit(): uid=int(arg); reason=" ".join(m.command[2:]) if len(m.command)>2 else "No reason"
        else:
            try: u=await bot.get_users(arg); uid=u.id; reason=" ".join(m.command[2:]) if len(m.command)>2 else "No reason"
            except: pass
    if not uid: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('reply or id')} ◍",3))
    # find fed from chat or from owner's feds
    fid=get_chat_fed(m.chat.id)
    if not fid:
        # pick first fed owned by sender
        for fed in list_feds():
            if fed["owner"]==m.from_user.id or is_fed_admin(fed["_id"], m.from_user.id):
                fid=fed["_id"]; break
    if not fid: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no fed')} — /newfed &lt;name&gt; ◍",3))
    if not is_fed_admin(fid, m.from_user.id) and get_fed(fid)["owner"]!=m.from_user.id and m.from_user.id!=config.OWNER_ID:
        return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('fed admin only')} ◍",3))
    fban(fid, uid, reason, m.from_user.id)
    # enforce in all fed chats (best-effort)
    chats=get_fed_chats(fid)
    count=0
    for cid in chats:
        try: await bot.ban_chat_member(cid, uid); count+=1
        except: pass
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('fbanned')} ◍",3)+rich_kv_table([("ᴜsᴇʀ", f"<code>{uid}</code>"),("ғᴇᴅ", f"<code>{fid}</code>"),("ʀᴇᴀsᴏɴ", rich_esc(reason)),("ᴄʜᴀᴛs", str(count))]))

@bot.on_message(filters.command("unfban") & group_allowed & user_allowed)
async def unfban_cmd(_, m: Message):
    uid=None
    if m.reply_to_message and m.reply_to_message.from_user: uid=m.reply_to_message.from_user.id
    elif len(m.command)>1 and m.command[1].isdigit(): uid=int(m.command[1])
    else:
        if len(m.command)>1:
            try: u=await bot.get_users(m.command[1]); uid=u.id
            except: pass
    if not uid: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('reply or id')} ◍",3))
    # find fed
    fid=get_chat_fed(m.chat.id)
    if not fid:
        for fed in list_feds():
            if fed["owner"]==m.from_user.id or is_fed_admin(fed["_id"], m.from_user.id):
                fid=fed["_id"]; break
    if not fid: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no fed')} ◍",3))
    unfban(fid, uid)
    for cid in get_fed_chats(fid):
        try: await bot.unban_chat_member(cid, uid)
        except: pass
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('unfbanned')} ◍",3)+rich_kv_table([("ᴜsᴇʀ", f"<code>{uid}</code>")]))

@bot.on_message(filters.command(["fedinfo","fedstat"]) & group_allowed & user_allowed)
async def fedinfo_cmd(_, m: Message):
    fid=None
    if len(m.text.split(maxsplit=1))>1: fid=m.text.split(maxsplit=1)[1].strip().lower()
    else: fid=get_chat_fed(m.chat.id)
    if not fid: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no fed')} ◍",3))
    fed=get_fed(fid)
    if not fed: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('fed not found')} ◍",3))
    chats=len(get_fed_chats(fid)); bans=len(list_fbans(fid)); admins=len(fed_list_admins(fid))
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('federation')} ⬪ {rich_esc(fed['name'])} ◍",3)+rich_kv_table([("ɪᴅ", f"<code>{fid}</code>"),("ᴏᴡɴᴇʀ", f"<code>{fed['owner']}</code>"),("ᴄʜᴀᴛs", str(chats)),("ʙᴀɴs", str(bans)),("ᴀᴅᴍɪɴs", str(admins))]))

@bot.on_message(filters.command("myfeds") & group_allowed)
async def myfeds_cmd(_, m: Message):
    feds=[f for f in list_feds() if f["owner"]==m.from_user.id or is_fed_admin(f["_id"], m.from_user.id)]
    if not feds: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no feds')} ◍",3))
    txt="<br>".join(f"• {rich_esc(f['name'])} — <code>{f['_id']}</code>" for f in feds)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('your feds')} ◍",3)+rich_note(txt))

@bot.on_message(filters.command("fedchats") & group_allowed & user_allowed)
async def fedchats_cmd(_, m: Message):
    fid=get_chat_fed(m.chat.id)
    if len(m.text.split(maxsplit=1))>1: fid=m.text.split(maxsplit=1)[1].strip().lower()
    if not fid: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no fed')} ◍",3))
    chats=get_fed_chats(fid)
    if not chats: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no chats')} ◍",3))
    txt="<br>".join(f"<code>{c}</code>" for c in chats[:50])
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('fed chats')} ◍",3)+rich_note(txt))

@bot.on_message(filters.command("fedbanlist") & group_allowed & user_allowed)
async def fedbanlist_cmd(_, m: Message):
    fid=get_chat_fed(m.chat.id)
    if len(m.text.split(maxsplit=1))>1: fid=m.text.split(maxsplit=1)[1].strip().lower()
    if not fid: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no fed')} ◍",3))
    bans=list_fbans(fid)
    if not bans: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no fbans')} ◍",3))
    txt="<br>".join(f"<code>{b['user']}</code> — {rich_esc(b.get('reason',''))}" for b in bans[:30])
    await rich_send(bot, m.chat.id, rich_heading(f"◎ {sc('fed bans')} ◎",3)+rich_note(txt))

@bot.on_message(filters.command(["fpromote","faddadmin"]) & group_allowed & user_allowed)
async def fpromote_cmd(_, m: Message):
    if not m.reply_to_message or not m.reply_to_message.from_user: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('reply to user')} ◍",3))
    fid=get_chat_fed(m.chat.id) or (m.text.split(maxsplit=1)[1].strip().lower() if len(m.text.split())>1 else None)
    if not fid: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no fed')} ◍",3))
    fed=get_fed(fid)
    if not fed or fed["owner"]!=m.from_user.id: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('owner only')} ◍",3))
    fed_add_admin(fid, m.reply_to_message.from_user.id)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('fed admin added')} ◍",3))

@bot.on_message(filters.command(["fdemote","fremadmin"]) & group_allowed & user_allowed)
async def fdemote_cmd(_, m: Message):
    if not m.reply_to_message or not m.reply_to_message.from_user: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('reply to user')} ◍",3))
    fid=get_chat_fed(m.chat.id)
    if not fid: return await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('no fed')} ◍",3))
    fed_remove_admin(fid, m.reply_to_message.from_user.id)
    await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('fed admin removed')} ◍",3))

# auto-enforce fban on join
@bot.on_message(filters.new_chat_members & group_allowed, group=5)
async def fed_enforce(_, m: Message):
    fed=get_chat_fed(m.chat.id)
    if not fed: return
    for u in m.new_chat_members:
        if get_fban(fed, u.id):
            try: await bot.ban_chat_member(m.chat.id, u.id); await rich_send(bot, m.chat.id, rich_heading(f"◍ {sc('fbanned user joined')} ◍",3)+rich_note(f"<code>{u.id}</code>"))
            except: pass
