# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  MongoDB-backed group management with vendored Badmunda05 Richgram UI.
#  Telegram permissions and handler checks remain authoritative.
# --------------------------------------------------------------------------------

import html
import asyncio
import re
import random
import time
import logging
from collections import OrderedDict, deque
from datetime import datetime, timezone, timedelta
from typing import Optional

from videl.utils.command_ui import notice as command_notice
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, CallbackQuery, ChatAdministratorRights
from videl.utils.bot_ui import button as InlineKeyboardButton, visual_call
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter
from pyrogram.errors import ChatAdminRequired, FloodWait, UserAdminInvalid

import config
from videl import LOGGER, bot
from videl.utils.db import get_db, is_approved
from videl.utils.moderation import LOCK_TYPES, locked_message_reason
from videl.utils.rich_ui import rich_heading, rich_kv_table, rich_note, rich_esc, rich_button, rich_details, rich_pre, rich_list
from videl.utils.command_ui import rich_send, rich_reply, rich_edit

logger = logging.getLogger(__name__)

# ── DB helpers (Videl MongoDB) ────────────────────────────────────────────────
def _db():
    return get_db()

def _chat_settings_col():
    db = _db()
    return db["mgmt_chat_settings"] if db is not None else None

def _warnings_col():
    db = _db()
    return db["mgmt_warnings"] if db is not None else None

def _banned_col():
    db = _db()
    return db["mgmt_banned_users"] if db is not None else None

def _notes_col():
    db = _db()
    return db["mgmt_notes"] if db is not None else None

def _blacklist_col():
    db = _db()
    return db["mgmt_blacklist"] if db is not None else None

def _filters_col():
    db = _db()
    return db["mgmt_filters"] if db is not None else None

def _captcha_col():
    db = _db()
    return db["mgmt_captcha"] if db is not None else None

def get_chat_setting(chat_id: int, key: str, default=None):
    try:
        col = _chat_settings_col()
        if col is None:
            return default
        doc = col.find_one({"chat_id": chat_id})
        return doc.get(key, default) if doc else default
    except Exception:
        return default

def set_chat_settings(chat_id: int, values: dict) -> bool:
    try:
        col = _chat_settings_col()
        if col is None:
            return False
        col.update_one({"chat_id": chat_id}, {"$set": values}, upsert=True)
        return True
    except Exception:
        logger.warning("Group settings were not saved", exc_info=True)
        return False


def set_chat_setting(chat_id: int, key: str, value) -> bool:
    return set_chat_settings(chat_id, {key: value})


def parse_time_arg(text: str) -> Optional[int]:
    match = re.search(r"(?:^|\s)([1-9][0-9]{0,6})([smhd])(?:\s|$)", text.lower())
    if not match:
        return None
    seconds = int(match[1]) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[match[2]]
    return seconds if 60 <= seconds <= 365 * 86400 else None

async def is_admin(chat_id: int, user_id: int) -> bool:
    if user_id in getattr(config, "ADMIN_IDS", set()) or user_id == getattr(config, "OWNER_ID", 0):
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False

async def get_target(message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, u.first_name, f"@{u.username}" if u.username else u.first_name
    if len(message.command) > 1:
        arg = message.command[1]
        if arg.startswith("@"):
            arg = arg[1:]
        try:
            uid = int(arg)
            try:
                u = await bot.get_users(uid)
                return u.id, u.first_name, f"@{u.username}" if getattr(u, "username", None) else u.first_name
            except Exception:
                return uid, str(uid), str(uid)
        except ValueError:
            try:
                user = await bot.get_users(arg)
                return user.id, user.first_name, f"@{user.username}" if user.username else user.first_name
            except Exception:
                return None, arg, arg
    return None, None, None

# ── Help Keyboard (Richgram) ──────────────────────────────────────────────────
def help_keyboard():
    from videl.utils.help_catalog import guide
    return guide()[1]

# ── Admin: Warn System ────────────────────────────────────────────────────────
@bot.on_message(filters.command(["warn", "dwarn"]) & filters.group)
async def warn_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, command_notice('Reply to a user or use <code>/warn @user &lt;reason&gt;</code>', status='error'))
    if await is_admin(message.chat.id, target_id):
        return await rich_reply(message, command_notice('Cannot warn an admin.', status='error'))
    reason = " ".join(message.command[2:]) if len(message.command) > 2 else (" ".join(message.command[1:]) if message.reply_to_message and len(message.command) > 1 else "No reason")
    if message.command[0].lower() == "warn" and len(message.command) > 1 and not message.reply_to_message:
        # Try to extract reason after username
        m = re.search(r"/warn(?:@\w+)?(?:\s+@?\w+)?\s*(.*)", message.text, re.DOTALL)
        if m and m.group(1).strip():
            reason = m.group(1).strip()
    threshold = get_chat_setting(message.chat.id, "warn_threshold", 3)
    try:
        col = _warnings_col()
        if col is None:
            return await rich_reply(message, command_notice('MongoDB not connected', status='error'))
        doc = col.find_one({"chat_id": message.chat.id, "user_id": target_id})
        count = (doc.get("count", 0) + 1) if doc else 1
        col.update_one(
            {"chat_id": message.chat.id, "user_id": target_id},
            {"$push": {"reasons": {"reason": reason, "ts": datetime.now(timezone.utc).isoformat()}}, "$set": {"count": count}},
            upsert=True
        )
        await rich_reply(message, rich_kv_table([("⚠️ Warned", f"{rich_esc(target_name)} (<code>{target_id}</code>)"), ("Reason", f"<code>{rich_esc(reason)}</code>"), ("Count", f"<code>{count}/{threshold}</code>")]))
        if message.command[0].lower() == "dwarn" and message.reply_to_message:
            try: await message.reply_to_message.delete()
            except Exception: pass
        if count >= threshold:
            try:
                await bot.ban_chat_member(message.chat.id, target_id)
                bcol = _banned_col()
                if bcol is not None:
                    bcol.update_one({"chat_id": message.chat.id, "user_id": target_id}, {"$set": {"ts": datetime.now(timezone.utc).isoformat()}}, upsert=True)
                await rich_send(bot, message.chat.id, rich_heading(f"🚫 {rich_esc(target_name)} banned for {threshold} warnings", level=3))
            except Exception as e:
                await rich_reply(message, command_notice(f'Auto-ban failed: <code>{rich_esc(str(e))}</code>', status='error'))
    except Exception as e:
        await rich_reply(message, command_notice(f'Error: <code>{rich_esc(str(e))}</code>', status='error'))

@bot.on_message(filters.command(["unwarn", "rmwarn"]) & filters.group)
async def unwarn_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, command_notice('Reply to a user or use <code>/unwarn @user</code>', status='error'))
    col = _warnings_col()
    if col is None:
        return await rich_reply(message, command_notice('DB not connected', status='error'))
    doc = col.find_one({"chat_id": message.chat.id, "user_id": target_id})
    if not doc or doc.get("count", 0) == 0:
        return await rich_reply(message, command_notice(f'{rich_esc(target_name)} has no warnings.', status='success'))
    reasons = doc.get("reasons", [])
    if reasons: reasons.pop()
    new_count = max(0, doc.get("count", 1) - 1)
    col.update_one({"chat_id": message.chat.id, "user_id": target_id}, {"$set": {"count": new_count, "reasons": reasons}})
    await rich_reply(message, command_notice(f'Removed one warning from {rich_esc(target_name)}. Now <code>{new_count}</code> warnings.', status='success'))

@bot.on_message(filters.command(["warnings", "warns"]) & filters.group)
async def warnings_cmd(_, message: Message):
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        target_id = message.from_user.id
        target_name = message.from_user.first_name
    col = _warnings_col()
    if col is None:
        return await rich_reply(message, command_notice('DB not connected', status='error'))
    threshold = get_chat_setting(message.chat.id, "warn_threshold", 3)
    doc = col.find_one({"chat_id": message.chat.id, "user_id": target_id})
    if not doc or doc.get("count", 0) == 0:
        return await rich_reply(message, command_notice(f'{rich_esc(target_name)} has no warnings.', status='success'))
    count = doc.get("count", 0)
    reasons = doc.get("reasons", [])
    rows = [(f"{i+1}.", f"<code>{rich_esc(r.get('reason','—'))}</code> <i>{r.get('ts','')[:10]}</i>") for i, r in enumerate(reasons)]
    await rich_reply(message, rich_heading(f"⚠️ {rich_esc(target_name)}: {count}/{threshold} warnings", level=3) + rich_kv_table(rows))

@bot.on_message(filters.command(["clearwarns", "resetwarns"]) & filters.group)
async def clearwarns_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, command_notice('Reply to a user', status='error'))
    col = _warnings_col()
    if col is not None:
        col.delete_one({"chat_id": message.chat.id, "user_id": target_id})
    await rich_reply(message, command_notice(f'All warnings cleared for {rich_esc(target_name)}.', status='success'))

@bot.on_message(filters.command("setwarnlimit") & filters.group)
async def setwarnlimit_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await rich_reply(message, command_notice('Usage: <code>/setwarnlimit &lt;number&gt;</code>', status='error', title='How to use this command'))
    limit = int(message.command[1])
    if not set_chat_setting(message.chat.id, "warn_threshold", limit):
        return await rich_reply(message, rich_note("MongoDB is unavailable. Nothing was saved."))
    await rich_reply(message, command_notice(f'Warn limit set to <code>{limit}</code>', status='success'))

# ── Admin: Ban/Kick/Mute ─────────────────────────────────────────────────────





@bot.on_message(filters.command("promote") & filters.group)
async def promote_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, command_notice('Reply to a user', status='error'))
    try:
        await bot.promote_chat_member(message.chat.id, target_id, privileges=ChatAdministratorRights(can_delete_messages=True, can_restrict_members=True, can_pin_messages=True))
        await rich_reply(message, command_notice(f'Promoted {rich_esc(target_name)}', status='success'))
    except Exception as e:
        await rich_reply(message, command_notice(f'Promote failed: <code>{rich_esc(str(e))}</code>', status='error'))

@bot.on_message(filters.command("demote") & filters.group)
async def demote_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, command_notice('Reply to a user', status='error'))
    try:
        await bot.promote_chat_member(message.chat.id, target_id, privileges=ChatAdministratorRights(can_manage_chat=False))
        await rich_reply(message, command_notice(f'Demoted {rich_esc(target_name)}', status='success'))
    except Exception as e:
        await rich_reply(message, command_notice(f'Demote failed: <code>{rich_esc(str(e))}</code>', status='error'))

@bot.on_message(filters.command("banlist") & filters.group)
async def banlist_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    bcol = _banned_col()
    if bcol is None:
        return await rich_reply(message, command_notice('DB not connected', status='error'))
    docs = list(bcol.find({"chat_id": message.chat.id}))
    if not docs:
        return await rich_reply(message, command_notice('No banned users', status='success'))
    rows = [(f"<code>{d['user_id']}</code>", f"<code>{d.get('reason','—')[:30]}</code>") for d in docs[:20]]
    await rich_reply(message, rich_heading("🚫 Banned Users", level=3) + rich_kv_table(rows))

@bot.on_message(filters.command(["admins", "getadmins"]) & filters.group)
async def getadmins_cmd(_, message: Message):
    try:
        admins = [member async for member in bot.get_chat_members(message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS, limit=50)]
        rows = [(f"{'👑' if a.status == ChatMemberStatus.OWNER else '⚡'} {rich_esc(a.user.first_name)}", f"<code>{a.user.id}</code> @{rich_esc(a.user.username or '—')}") for a in admins]
        await rich_reply(message, rich_heading("👑 Admins", level=3) + rich_kv_table(rows))
    except Exception as e:
        await rich_reply(message, command_notice(f'Failed: <code>{rich_esc(str(e))}</code>', status='error'))

# ── Locks ─────────────────────────────────────────────────────────────────────
_LOCK_TYPES = LOCK_TYPES + ("all",)


async def change_lock(message, enabled):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_note("Group admins only."))
    selected = (message.command[1].lower() if len(message.command) > 1 else "")
    if selected not in _LOCK_TYPES:
        return await rich_reply(message, rich_note("Choose: <code>" + " | ".join(_LOCK_TYPES) + "</code>"))
    types = LOCK_TYPES if selected == "all" else (selected,)
    updates = {f"lock_{kind}": enabled for kind in types}
    if "forward" in types:
        updates["lock_forwards"] = enabled
    if not set_chat_settings(message.chat.id, updates):
        return await rich_reply(message, rich_note("MongoDB is unavailable. Nothing was saved."))
    await rich_reply(message, rich_note(f"{selected.capitalize()}: {'blocked' if enabled else 'allowed'}. Admins and approved users are exempt."))


@bot.on_message(filters.command("lock") & filters.group)
async def lock_cmd(_, message: Message):
    await change_lock(message, True)


@bot.on_message(filters.command("unlock") & filters.group)
async def unlock_cmd(_, message: Message):
    await change_lock(message, False)

@bot.on_message(filters.command("locks") & filters.group)
async def locks_cmd(_, message: Message):
    rows = []
    for t in _LOCK_TYPES:
        if t == "all": continue
        state = "🔒 Locked" if get_chat_setting(message.chat.id, f"lock_{t}", False) else "🔓 Open"
        rows.append((t.capitalize(), f"<code>{state}</code>"))
    await rich_reply(message, rich_heading("🔒 Lock Status", level=3) + rich_kv_table(rows))

_FLOOD_WINDOWS = OrderedDict()

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

@bot.on_message(filters.group, group=15)
async def mgmt_content_checker(_, message: Message):
    if not message.chat or message.chat.type == "private":
        return
    # Admin bypass
    if message.from_user and await is_admin(message.chat.id, message.from_user.id):
        return
    if message.from_user and is_approved(message.chat.id, message.from_user.id):
        return
    # Both the wizard and web manager persist these exact keys.
    if get_chat_setting(message.chat.id, "antispam", False) and message.from_user:
        key = (message.chat.id, message.from_user.id)
        now = time.monotonic()
        window = _FLOOD_WINDOWS.setdefault(key, deque(maxlen=32))
        _FLOOD_WINDOWS.move_to_end(key)
        while window and now - window[0] > 8:
            window.popleft()
        window.append(now)
        while len(_FLOOD_WINDOWS) > 10000:
            _FLOOD_WINDOWS.popitem(last=False)
        if len(window) > 6:
            try: await message.delete()
            except Exception: logger.debug("Anti-spam deletion failed", exc_info=True)
            return
    reason = locked_message_reason(message, lambda kind: get_chat_setting(message.chat.id, "lock_" + kind, False) or (kind == "forward" and get_chat_setting(message.chat.id, "lock_forwards", False)))
    if reason:
        try:
            await message.delete()
        except Exception:
            logger.debug("Lock deletion failed", exc_info=True)

# ── Filters ───────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("filter") & filters.group)
async def filter_add_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 3:
        return await rich_reply(message, command_notice('Usage: <code>/filter &lt;keyword&gt; &lt;reply&gt;</code>', status='error', title='How to use this command'))
    keyword = message.command[1].lower().strip()
    reply = " ".join(message.command[2:])
    if message.reply_to_message:
        reply = message.reply_to_message.text or reply
    col = _filters_col()
    if col is None:
        return await rich_reply(message, command_notice('DB not connected', status='error'))
    col.update_one({"chat_id": message.chat.id, "keyword": keyword}, {"$set": {"reply": reply}}, upsert=True)
    await rich_reply(message, command_notice(f'Filter <code>{rich_esc(keyword)}</code> saved → <code>{rich_esc(reply[:50])}</code>', status='success'))

@bot.on_message(filters.command("stopfilter") & filters.group)
async def filter_stop_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2:
        return await rich_reply(message, command_notice('Usage: <code>/stop &lt;keyword&gt;</code>', status='error', title='How to use this command'))
    keyword = message.command[1].lower().strip()
    col = _filters_col()
    if col is not None:
        r = col.delete_one({"chat_id": message.chat.id, "keyword": keyword})
        if r.deleted_count:
            return await rich_reply(message, command_notice(f'Filter <code>{rich_esc(keyword)}</code> removed.', status='success'))
    await rich_reply(message, command_notice(f'No filter <code>{rich_esc(keyword)}</code> found.', status='error'))

@bot.on_message(filters.command("filters") & filters.group)
async def filters_list_cmd(_, message: Message):
    col = _filters_col()
    if col is None:
        return await rich_reply(message, command_notice('DB not connected', status='error'))
    docs = list(col.find({"chat_id": message.chat.id}))
    if not docs:
        return await rich_reply(message, command_notice('No filters in this chat', status='success'))
    rows = [(f"<code>{rich_esc(d['keyword'])}</code>", f"<code>{rich_esc(d['reply'][:30])}</code>") for d in docs]
    await rich_reply(message, rich_heading("🔤 Filters", level=3) + rich_kv_table(rows))

@bot.on_message(filters.group, group=17)
async def mgmt_filter_checker(_, message: Message):
    if not message.chat or message.chat.type == "private": return
    text = (message.text or "").lower()
    if not text: return
    col = _filters_col()
    if col is None: return
    docs = list(col.find({"chat_id": message.chat.id}))
    for d in docs:
        if d["keyword"] in text:
            try: await message.reply_text(d["reply"])
            except Exception: pass
            break

# ── Notes ─────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("save") & filters.group)
async def save_note_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2:
        return await rich_reply(message, command_notice('Usage: <code>/save &lt;name&gt; &lt;content&gt;</code> or reply with <code>/save &lt;name&gt;</code>', status='error', title='How to use this command'))
    name = message.command[1].lower().strip()
    content = " ".join(message.command[2:]) if len(message.command) > 2 else ""
    note_type = "text"
    caption = ""
    if message.reply_to_message:
        r = message.reply_to_message
        if r.text: content = r.text
        elif r.photo: content, note_type, caption = r.photo.file_id, "photo", r.caption or ""
        elif r.document: content, note_type, caption = r.document.file_id, "document", r.caption or ""
        elif r.video: content, note_type, caption = r.video.file_id, "video", r.caption or ""
        elif r.audio: content, note_type, caption = r.audio.file_id, "audio", r.caption or ""
        elif r.sticker: content, note_type = r.sticker.file_id, "sticker"
    if not content:
        return await rich_reply(message, command_notice('Provide content', status='error'))
    col = _notes_col()
    if col is None:
        return await rich_reply(message, command_notice('DB not connected', status='error'))
    doc = {"chat_id": message.chat.id, "name": name, "content": content, "type": note_type}
    if caption: doc["caption"] = caption
    col.update_one({"chat_id": message.chat.id, "name": name}, {"$set": doc}, upsert=True)
    await rich_reply(message, command_notice(f'Note <code>{rich_esc(name)}</code> saved. Get with <code>#{rich_esc(name)}</code> or <code>/get {rich_esc(name)}</code>', status='success'))

@bot.on_message(filters.command("get") & filters.group)
async def get_note_cmd(_, message: Message):
    if len(message.command) < 2:
        return await rich_reply(message, command_notice('Usage: <code>/get &lt;name&gt;</code>', status='error', title='How to use this command'))
    name = message.command[1].lower().strip()
    await send_note(message.chat.id, name, reply_to=message.id)

async def send_note(chat_id: int, name: str, reply_to=None):
    col = _notes_col()
    if col is None: return
    doc = col.find_one({"chat_id": chat_id, "name": name.lower()})
    if not doc:
        await rich_send(bot, chat_id, rich_heading("Note not found", level=3) + rich_note(f"No saved note named <code>{rich_esc(name)}</code>."), reply_to_message_id=reply_to)
        return
    t, content, caption = doc.get("type", "text"), doc["content"], doc.get("caption", "")
    try:
        if t == "text": await bot.send_message(chat_id, content, reply_to_message_id=reply_to)
        elif t == "photo": await bot.send_photo(chat_id, content, caption=caption, reply_to_message_id=reply_to)
        elif t == "document": await bot.send_document(chat_id, content, caption=caption, reply_to_message_id=reply_to)
        elif t == "video": await bot.send_video(chat_id, content, caption=caption, reply_to_message_id=reply_to)
        elif t == "audio": await bot.send_audio(chat_id, content, caption=caption, reply_to_message_id=reply_to)
        elif t == "sticker": await bot.send_sticker(chat_id, content, reply_to_message_id=reply_to)
    except Exception as e:
        logger.debug(f"send_note fail: {e}")

@bot.on_message(filters.command("delnote") & filters.group)
async def delnote_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2:
        return await rich_reply(message, command_notice('Usage: <code>/delnote &lt;name&gt;</code>', status='error', title='How to use this command'))
    name = message.command[1].lower().strip()
    col = _notes_col()
    if col is not None and col.delete_one({"chat_id": message.chat.id, "name": name}).deleted_count:
        await rich_reply(message, command_notice(f'Note <code>{rich_esc(name)}</code> deleted.', status='success'))
    else:
        await rich_reply(message, command_notice(f'No note <code>{rich_esc(name)}</code> found.', status='error'))

@bot.on_message(filters.command("notes") & filters.group)
async def notes_list_cmd(_, message: Message):
    col = _notes_col()
    if col is None:
        return await rich_reply(message, command_notice('DB not connected', status='error'))
    docs = list(col.find({"chat_id": message.chat.id}, {"name": 1}))
    if not docs:
        return await rich_reply(message, command_notice('No notes in this chat', status='success'))
    rows = [(f"<code>#{rich_esc(d['name'])}</code>", "") for d in docs]
    await rich_reply(message, rich_heading("📝 Saved Notes", level=3) + rich_kv_table(rows))

@bot.on_message(filters.group, group=18)
async def mgmt_notes_trigger(_, message: Message):
    text = message.text or ""
    if not text.startswith("#"): return
    m = re.match(r"#(\w+)", text)
    if m:
        await send_note(message.chat.id, m.group(1), reply_to=message.id)

# ── Greetings & Captcha ───────────────────────────────────────────────────────
@bot.on_message(filters.command("setwelcome") & filters.group)
async def setwelcome_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    content = " ".join(message.command[1:]) if len(message.command) > 1 else ""
    if not content:
        return await rich_reply(message, command_notice('Usage: <code>/setwelcome &lt;message&gt;</code> — placeholders: <code>{name} {id} {title}</code>', status='error', title='How to use this command'))
    if not set_chat_setting(message.chat.id, "welcome_message", content):
        return await rich_reply(message, rich_note("MongoDB is unavailable. Nothing was saved."))
    await rich_reply(message, command_notice('Welcome message updated.', status='success'))

@bot.on_message(filters.command("welcome") & filters.group)
async def welcome_toggle_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2 or message.command[1].lower() not in ("on", "off"):
        return await rich_reply(message, command_notice('Usage: <code>/welcome on|off</code>', status='error', title='How to use this command'))
    enabled = message.command[1].lower() == "on"
    if not set_chat_setting(message.chat.id, "welcome_enabled", enabled):
        return await rich_reply(message, rich_note("MongoDB is unavailable. Nothing was saved."))
    await rich_reply(message, command_notice(f"Welcome messages {('enabled' if enabled else 'disabled')}.", status='success'))

@bot.on_message(filters.command("setcaptcha") & filters.group)
async def setcaptcha_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2 or message.command[1].lower() not in ("on", "off"):
        return await rich_reply(message, command_notice('Usage: <code>/setcaptcha on|off</code>', status='error', title='How to use this command'))
    enabled = message.command[1].lower() == "on"
    if not set_chat_setting(message.chat.id, "captcha_enabled", enabled):
        return await rich_reply(message, rich_note("MongoDB is unavailable. Nothing was saved."))
    await rich_reply(message, command_notice(f"Captcha {('enabled' if enabled else 'disabled')}.", status='success'))

from videl.utils.captcha import issue_challenge as _send_captcha, answer_challenge

@bot.on_message(filters.new_chat_members, group=5)
async def mgmt_welcome_handler(_, message: Message):
    for member in message.new_chat_members:
        # Skip bot itself
        me = await bot.get_me()
        if member.id == me.id:
            continue
        # Welcome
        if get_chat_setting(message.chat.id, "welcome_enabled", True):
            tmpl = get_chat_setting(message.chat.id, "welcome_message", "Welcome {name} to {title}! 👋")
            try:
                txt = tmpl.format(name=rich_esc(member.first_name), id=member.id, title=rich_esc(message.chat.title or "group"), mention=rich_esc(f"@{member.username}" if getattr(member, "username", None) else member.first_name))
            except Exception:
                txt = tmpl
            try:
                await bot.send_message(message.chat.id, txt)
            except Exception: pass
        # Stateful CAPTCHA handles restrictions, saved challenges and safe rollback.
        if not member.is_bot and get_chat_setting(message.chat.id, "captcha_enabled", False) and not is_approved(message.chat.id, member.id):
            await _send_captcha(message.chat.id, member.id, member.first_name or "New user")

@bot.on_callback_query(filters.regex(r"^verify:"))
async def mgmt_captcha_callback(_, cq: CallbackQuery):
    await answer_challenge(cq)

# ── Pins, Purge, Slowmode ────────────────────────────────────────────────────
@bot.on_message(filters.command(["pin", "unpin", "unpinall"]) & filters.group)
async def pin_cmds(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    cmd = message.command[0].lower()
    try:
        if cmd == "pin":
            if not message.reply_to_message:
                return await rich_reply(message, command_notice('Reply to a message to pin.', status='error'))
            await bot.pin_chat_message(message.chat.id, message.reply_to_message.id, disable_notification=False)
            await rich_reply(message, rich_note("📌 Message pinned."))
        elif cmd == "unpin":
            await bot.unpin_chat_message(message.chat.id)
            await rich_reply(message, command_notice('Message unpinned.', status='success'))
        elif cmd == "unpinall":
            await bot.unpin_all_chat_messages(message.chat.id)
            await rich_reply(message, command_notice('All pins removed.', status='success'))
    except Exception as e:
        await rich_reply(message, command_notice(f'Failed: <code>{rich_esc(str(e))}</code>', status='error'))

@bot.on_message(filters.command(["purge", "cleanup"]) & filters.group)
async def purge_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if message.command[0].lower() == "purge":
        if not message.reply_to_message:
            return await rich_reply(message, command_notice('Reply to the first message to purge from.', status='error'))
        start, end = message.reply_to_message.id, message.id
        deleted = 0
        for mid in range(start, end):
            try: await bot.delete_messages(message.chat.id, mid); deleted += 1
            except Exception: pass
        await rich_send(bot, message.chat.id, rich_heading("Purge results", level=3) + rich_note(f"Telegram confirmed deletion of {deleted} messages."))
    else:
        count = int(message.command[1]) if len(message.command) > 1 and message.command[1].isdigit() else 0
        if not (1 <= count <= 100):
            return await rich_reply(message, command_notice('Usage: <code>/cleanup &lt;1-100&gt;</code>', status='error', title='How to use this command'))
        deleted = 0
        for off in range(count):
            try: await bot.delete_messages(message.chat.id, message.id - off); deleted += 1
            except Exception: pass
        await rich_send(bot, message.chat.id, rich_heading("Cleanup results", level=3) + rich_note(f"Telegram confirmed deletion of {deleted} messages."))

@bot.on_message(filters.command("slowmode") & filters.group)
async def slowmode_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await rich_reply(message, command_notice('Usage: <code>/slowmode &lt;seconds&gt;</code> (0 to disable)', status='error', title='How to use this command'))
    sec = int(message.command[1])
    try:
        await bot.set_chat_slow_mode(message.chat.id, sec)
        await rich_reply(message, command_notice(f"Slowmode {('disabled' if sec == 0 else f'set to {sec}s')}", status='success'))
    except Exception as e:
        await rich_reply(message, command_notice(f'Failed: <code>{rich_esc(str(e))}</code>', status='error'))

# ── Rules ─────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("setrules") & filters.group)
async def setrules_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    content = " ".join(message.command[1:]) if len(message.command) > 1 else ""
    if not content:
        return await rich_reply(message, command_notice('Usage: <code>/setrules &lt;rules&gt;</code>', status='error', title='How to use this command'))
    if not set_chat_setting(message.chat.id, "rules", content):
        return await rich_reply(message, rich_note("MongoDB is unavailable. Nothing was saved."))
    await rich_reply(message, command_notice('Rules updated.', status='success'))

@bot.on_message(filters.command("rules") & filters.group)
async def rules_cmd(_, message: Message):
    rules = get_chat_setting(message.chat.id, "rules", None)
    if not rules:
        return await rich_reply(message, command_notice('No rules set', status='error'))
    await rich_reply(message, rich_heading("📜 Group Rules", level=3) + rich_note(rules))

@bot.on_message(filters.command("clearrules") & filters.group)
async def clearrules_cmd(_, message: Message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if not set_chat_setting(message.chat.id, "rules", None):
        return await rich_reply(message, rich_note("MongoDB is unavailable. Nothing was saved."))
    await rich_reply(message, command_notice('Rules cleared.', status='success'))

# ── Group utilities ─────────────────────────────────────────────────────────
@bot.on_message(filters.command(["poll", "quiz"]))
async def poll_cmd(_, message: Message):
    from videl.utils.poll_options import build_poll
    from videl.utils.bot_api import bot_api
    try:
        payload = build_poll(" ".join((message.command or [])[1:]), quiz=message.command[0].split("@", 1)[0].lower() == "quiz")
    except ValueError as exc:
        return await rich_reply(message, rich_heading("Poll setup", level=3) + rich_note(html.escape(str(exc))))
    payload["chat_id"] = message.chat.id
    if getattr(message, "message_thread_id", None):
        payload["message_thread_id"] = message.message_thread_id
    status, result = await bot_api("sendPoll", payload)
    if not status or not result.get("ok"):
        await rich_reply(message, rich_heading("Poll not confirmed", level=3) + rich_note(html.escape(str(result.get("description", "Telegram rejected this poll")))))

@bot.on_message(filters.command("stickerid"))
async def stickerid_cmd(_, message: Message):
    if message.reply_to_message and message.reply_to_message.sticker:
        await rich_reply(message, rich_code(message.reply_to_message.sticker.file_id, lang=""))
    else:
        await rich_reply(message, command_notice('Reply to a sticker', status='error'))

# ── Misc: help/id/whois/stats ────────────────────────────────────────────────

@bot.on_message(filters.command("whois"))
async def whois_cmd(_, message: Message):
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        target_id = message.from_user.id
        target_name = message.from_user.first_name
        u = message.from_user
    else:
        try: u = await bot.get_users(target_id)
        except Exception: u = None
    if u:
        rows = [("Name", f"{rich_esc(u.first_name)} {rich_esc(getattr(u, 'last_name', '') or '')}".strip()), ("ID", f"<code>{u.id}</code>"), ("Username", f"@{rich_esc(u.username)}" if getattr(u, "username", None) else "—"), ("Mention", f"<a href=\"tg://user?id={u.id}\">{rich_esc(u.first_name)}</a>")]
        try:
            m = await bot.get_chat_member(message.chat.id, u.id)
            rows.append(("Status", f"<code>{m.status}</code>"))
        except Exception: pass
        await rich_reply(message, rich_heading(f"👤 {rich_esc(target_name)}", level=3) + rich_kv_table(rows))
    else:
        await rich_reply(message, rich_note(f"👤 <code>{target_id}</code> — {rich_esc(target_name)}"))

@bot.on_message(filters.command("stats"))
async def stats_cmd(_, message: Message):
    db = _db()
    if db is None:
        return await rich_reply(message, command_notice('DB not connected', status='error'))
    try:
        chat_count = db["mgmt_chat_settings"].count_documents({}) if "mgmt_chat_settings" in db.list_collection_names() else 0
        warn_count = db["mgmt_warnings"].count_documents({}) if "mgmt_warnings" in db.list_collection_names() else 0
        note_count = db["mgmt_notes"].count_documents({}) if "mgmt_notes" in db.list_collection_names() else 0
    except Exception:
        chat_count = warn_count = note_count = "—"
    from videl import bot_start_time
    import time
    uptime = time.time() - bot_start_time
    h, r = divmod(int(uptime), 3600)
    m, s = divmod(r, 60)
    await rich_reply(message, rich_heading("📊 Videl Stats", level=3) + rich_kv_table([("Uptime", f"<code>{h}h {m}m {s}s</code>"), ("Chats", f"<code>{chat_count}</code>"), ("Warnings", f"<code>{warn_count}</code>"), ("Notes", f"<code>{note_count}</code>"), ("Bot", f"@{getattr(config, 'BOT_USERNAME', 'Videl0Bot')}")]))

LOGGER.info("Group management handlers loaded with Richgram command UI")
