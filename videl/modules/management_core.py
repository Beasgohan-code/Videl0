# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Videl → Videl Full Port — Pyrogram + Richgram + MongoDB
#  Videl Professional Management Suite — 9 core modules ported to Videl Professional Suite
#  Ported: All 9 modules fully integrated, credits changed to Videl, Richgram UI
#
#  Features ported:
#  • Admin: ban/tban/kick/mute/tmute/warn/unwarn/warnings/clearwarns/setwarnlimit/banlist/getadmins/promote/demote
#  • Locks: lock/unlock/locks (links/media/stickers/all/forward/polls) + content filter
#  • Blacklist: addblacklist/rmblacklist/blacklist + auto-delete + auto-warn
#  • Filters: filter/stop/filters + keyword auto-reply
#  • Notes: save/get/delnote/notes + #trigger (FallenRobot-style)
#  • Greetings: setwelcome/welcome/setcaptcha + welcome messages + captcha
#  • Pins: pin/unpin/unpinall/purge/cleanup/slowmode
#  • Rules: setrules/rules/clearrules
#  • Group utilities: polls and sticker metadata
#  • Misc: start/help/id/whois/stats
#  Uses Videl MongoDB only — no external deps, no Flask
# --------------------------------------------------------------------------------

import asyncio
import re
import random
import time
import logging
from collections import OrderedDict, deque
from datetime import datetime, timezone, timedelta
from typing import Optional

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import ChatAdminRequired, FloodWait, UserAdminInvalid

import config
from videl import LOGGER, bot
from videl.utils.db import get_db
from videl.utils.rich_ui import (
    rich_heading, rich_kv_table, rich_note, rich_esc, rich_send, rich_reply, rich_edit,
    rich_button, rich_details, rich_pre, rich_list
)

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

def set_chat_setting(chat_id: int, key: str, value):
    try:
        col = _chat_settings_col()
        if col is None:
            return
        col.update_one({"chat_id": chat_id}, {"$set": {key: value}}, upsert=True)
    except Exception as e:
        logger.debug(f"set_chat_setting fail: {e}")

def parse_time_arg(text: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*([smhd])", text.lower())
    if not m:
        return None
    amount = int(m.group(1))
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return amount * mult[m.group(2)]

async def is_admin(chat_id: int, user_id: int) -> bool:
    if user_id in getattr(config, "ADMIN_IDS", set()) or user_id == getattr(config, "OWNER_ID", 0):
        return True
    if user_id in getattr(config, "SUDO_USERS", []):
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
            # Try username lookup via admins
            try:
                admins = await bot.get_chat_members(message.chat.id, filter="administrators")
                for a in admins:
                    if a.user.username and a.user.username.lower() == arg.lower():
                        u = a.user
                        return u.id, u.first_name, f"@{u.username}"
            except Exception:
                pass
            return None, arg, arg
    return None, None, None

# ── Help Keyboard (Richgram) ──────────────────────────────────────────────────
def help_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡 Moderation", callback_data="mgmt_help_mod"),
         InlineKeyboardButton("⚙️ Settings", callback_data="mgmt_help_settings")],
        [InlineKeyboardButton("📝 Notes & filters", callback_data="mgmt_help_notes"),
         InlineKeyboardButton("🔧 Admin tools", callback_data="mgmt_help_admin")],
        [InlineKeyboardButton("🔗 Videl", url="https://t.me/VidelUpdates"),
         InlineKeyboardButton("💬 Support", url="https://t.me/VidelSupport")],
    ])

# ── Admin: Warn System ────────────────────────────────────────────────────────
@bot.on_message(filters.command(["warn", "dwarn"]))
async def warn_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, rich_note("❌ Reply to a user or use <code>/warn @user &lt;reason&gt;</code>"))
    if await is_admin(message.chat.id, target_id):
        return await rich_reply(message, rich_note("❌ Cannot warn an admin."))
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
            return await rich_reply(message, rich_note("❌ MongoDB not connected"))
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
                await rich_reply(message, rich_note(f"❌ Auto-ban failed: <code>{rich_esc(str(e))}</code>"))
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Error: <code>{rich_esc(str(e))}</code>"))

@bot.on_message(filters.command(["unwarn", "rmwarn"]))
async def unwarn_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, rich_note("❌ Reply to a user or use <code>/unwarn @user</code>"))
    col = _warnings_col()
    if col is None:
        return await rich_reply(message, rich_note("❌ DB not connected"))
    doc = col.find_one({"chat_id": message.chat.id, "user_id": target_id})
    if not doc or doc.get("count", 0) == 0:
        return await rich_reply(message, rich_note(f"✅ {rich_esc(target_name)} has no warnings."))
    reasons = doc.get("reasons", [])
    if reasons: reasons.pop()
    new_count = max(0, doc.get("count", 1) - 1)
    col.update_one({"chat_id": message.chat.id, "user_id": target_id}, {"$set": {"count": new_count, "reasons": reasons}})
    await rich_reply(message, rich_note(f"✅ Removed one warning from {rich_esc(target_name)}. Now <code>{new_count}</code> warnings."))

@bot.on_message(filters.command(["warnings", "warns"]))
async def warnings_cmd(_, message: Message):
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        target_id = message.from_user.id
        target_name = message.from_user.first_name
    col = _warnings_col()
    if col is None:
        return await rich_reply(message, rich_note("❌ DB not connected"))
    threshold = get_chat_setting(message.chat.id, "warn_threshold", 3)
    doc = col.find_one({"chat_id": message.chat.id, "user_id": target_id})
    if not doc or doc.get("count", 0) == 0:
        return await rich_reply(message, rich_note(f"✅ {rich_esc(target_name)} has no warnings."))
    count = doc.get("count", 0)
    reasons = doc.get("reasons", [])
    rows = [(f"{i+1}.", f"<code>{rich_esc(r.get('reason','—'))}</code> <i>{r.get('ts','')[:10]}</i>") for i, r in enumerate(reasons)]
    await rich_reply(message, rich_heading(f"⚠️ {rich_esc(target_name)}: {count}/{threshold} warnings", level=3) + rich_kv_table(rows))

@bot.on_message(filters.command(["clearwarns", "resetwarns"]))
async def clearwarns_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, rich_note("❌ Reply to a user"))
    col = _warnings_col()
    if col is not None:
        col.delete_one({"chat_id": message.chat.id, "user_id": target_id})
    await rich_reply(message, rich_note(f"✅ All warnings cleared for {rich_esc(target_name)}."))

@bot.on_message(filters.command("setwarnlimit"))
async def setwarnlimit_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await rich_reply(message, rich_note("❌ Usage: <code>/setwarnlimit &lt;number&gt;</code>"))
    limit = int(message.command[1])
    set_chat_setting(message.chat.id, "warn_threshold", limit)
    await rich_reply(message, rich_note(f"✅ Warn limit set to <code>{limit}</code>"))

# ── Admin: Ban/Kick/Mute ─────────────────────────────────────────────────────
@bot.on_message(filters.command(["ban", "tban", "dban"]))
async def ban_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, rich_note("❌ Reply to a user or use <code>/ban @user &lt;reason&gt;</code>"))
    if await is_admin(message.chat.id, target_id):
        return await rich_reply(message, rich_note("❌ Cannot ban an admin."))
    until = None
    if message.command[0].lower() == "tban":
        dur = parse_time_arg(message.text)
        if dur:
            until = datetime.now(timezone.utc) + timedelta(seconds=dur)
    reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason"
    try:
        await bot.ban_chat_member(message.chat.id, target_id, until_date=until)
        bcol = _banned_col()
        if bcol is not None:
            bcol.update_one({"chat_id": message.chat.id, "user_id": target_id}, {"$set": {"ts": datetime.now(timezone.utc).isoformat(), "reason": reason}}, upsert=True)
        await rich_reply(message, rich_kv_table([("🚫 Banned", f"{rich_esc(target_name)} (<code>{target_id}</code>)"), ("Reason", f"<code>{rich_esc(reason)}</code>")] + ([("Until", f"<code>{until}</code>")] if until else [])))
        if message.command[0].lower() == "dban" and message.reply_to_message:
            try: await message.reply_to_message.delete()
            except Exception: pass
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Ban failed: <code>{rich_esc(str(e))}</code>"))

@bot.on_message(filters.command("unban"))
async def unban_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, rich_note("❌ Reply to a user"))
    try:
        await bot.unban_chat_member(message.chat.id, target_id)
        await rich_reply(message, rich_note(f"✅ Unbanned {rich_esc(target_name)}"))
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Unban failed: <code>{rich_esc(str(e))}</code>"))

@bot.on_message(filters.command(["kick", "dkick"]))
async def kick_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, rich_note("❌ Reply to a user"))
    try:
        await bot.ban_chat_member(message.chat.id, target_id)
        await bot.unban_chat_member(message.chat.id, target_id)
        await rich_reply(message, rich_note(f"✅ Kicked {rich_esc(target_name)}"))
        if message.command[0].lower() == "dkick" and message.reply_to_message:
            try: await message.reply_to_message.delete()
            except Exception: pass
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Kick failed: <code>{rich_esc(str(e))}</code>"))

@bot.on_message(filters.command(["mute", "tmute"]))
async def mute_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, rich_note("❌ Reply to a user"))
    until = None
    if message.command[0].lower() == "tmute":
        dur = parse_time_arg(message.text)
        if dur:
            until = datetime.now(timezone.utc) + timedelta(seconds=dur)
    try:
        from pyrogram.types import ChatPermissions
        await bot.restrict_chat_member(message.chat.id, target_id, ChatPermissions(can_send_messages=False), until_date=until)
        await rich_reply(message, rich_kv_table([("🔇 Muted", f"{rich_esc(target_name)} (<code>{target_id}</code>)")] + ([("Until", f"<code>{until}</code>")] if until else [("Duration", "<code>forever</code>")])))
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Mute failed: <code>{rich_esc(str(e))}</code>"))

@bot.on_message(filters.command("unmute"))
async def unmute_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, rich_note("❌ Reply to a user"))
    try:
        from pyrogram.types import ChatPermissions
        await bot.restrict_chat_member(message.chat.id, target_id, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True))
        await rich_reply(message, rich_note(f"✅ Unmuted {rich_esc(target_name)}"))
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Unmute failed: <code>{rich_esc(str(e))}</code>"))

@bot.on_message(filters.command("promote"))
async def promote_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, rich_note("❌ Reply to a user"))
    try:
        await bot.promote_chat_member(message.chat.id, target_id, can_delete_messages=True, can_restrict_members=True, can_pin_messages=True, can_promote_members=False)
        await rich_reply(message, rich_note(f"✅ Promoted {rich_esc(target_name)}"))
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Promote failed: <code>{rich_esc(str(e))}</code>"))

@bot.on_message(filters.command("demote"))
async def demote_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    target_id, target_name, _ = await get_target(message)
    if not target_id:
        return await rich_reply(message, rich_note("❌ Reply to a user"))
    try:
        await bot.promote_chat_member(message.chat.id, target_id, can_delete_messages=False, can_restrict_members=False, can_pin_messages=False, can_promote_members=False, is_anonymous=False)
        await rich_reply(message, rich_note(f"✅ Demoted {rich_esc(target_name)}"))
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Demote failed: <code>{rich_esc(str(e))}</code>"))

@bot.on_message(filters.command("banlist"))
async def banlist_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    bcol = _banned_col()
    if bcol is None:
        return await rich_reply(message, rich_note("❌ DB not connected"))
    docs = list(bcol.find({"chat_id": message.chat.id}))
    if not docs:
        return await rich_reply(message, rich_note("✅ No banned users"))
    rows = [(f"<code>{d['user_id']}</code>", f"<code>{d.get('reason','—')[:30]}</code>") for d in docs[:20]]
    await rich_reply(message, rich_heading("🚫 Banned Users", level=3) + rich_kv_table(rows))

@bot.on_message(filters.command(["admins", "getadmins"]))
async def getadmins_cmd(_, message: Message):
    try:
        admins = await bot.get_chat_members(message.chat.id, filter="administrators")
        rows = [(f"{'👑' if a.status == ChatMemberStatus.OWNER else '⚡'} {rich_esc(a.user.first_name)}", f"<code>{a.user.id}</code> @{rich_esc(a.user.username or '—')}") for a in admins]
        await rich_reply(message, rich_heading("👑 Admins", level=3) + rich_kv_table(rows))
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Failed: <code>{rich_esc(str(e))}</code>"))

# ── Locks ─────────────────────────────────────────────────────────────────────
_LOCK_TYPES = ("links", "media", "stickers", "all", "forward", "polls")

@bot.on_message(filters.command("lock"))
async def lock_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2 or message.command[1].lower() not in _LOCK_TYPES:
        return await rich_reply(message, rich_note(f"❌ Usage: <code>/lock &lt;{' | '.join(_LOCK_TYPES)}&gt;</code>"))
    lock_type = message.command[1].lower()
    if lock_type == "all":
        for t in _LOCK_TYPES:
            if t != "all": set_chat_setting(message.chat.id, f"lock_{t}", True)
    else:
        set_chat_setting(message.chat.id, f"lock_{lock_type}", True)
    await rich_reply(message, rich_note(f"🔒 {lock_type.capitalize()} locked."))

@bot.on_message(filters.command("unlock"))
async def unlock_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2 or message.command[1].lower() not in _LOCK_TYPES:
        return await rich_reply(message, rich_note(f"❌ Usage: <code>/unlock &lt;{' | '.join(_LOCK_TYPES)}&gt;</code>"))
    lock_type = message.command[1].lower()
    if lock_type == "all":
        for t in _LOCK_TYPES:
            if t != "all": set_chat_setting(message.chat.id, f"lock_{t}", False)
    else:
        set_chat_setting(message.chat.id, f"lock_{lock_type}", False)
    await rich_reply(message, rich_note(f"🔓 {lock_type.capitalize()} unlocked."))

@bot.on_message(filters.command("locks"))
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
    if ((get_chat_setting(message.chat.id, "lock_forwards", False) or
         get_chat_setting(message.chat.id, "lock_forward", False)) and
            (message.forward_date or message.forward_from or message.forward_from_chat)):
        try: await message.delete()
        except Exception: logger.debug("Forward-lock deletion failed", exc_info=True)
        return
    if get_chat_setting(message.chat.id, "lock_polls", False) and message.poll:
        try: await message.delete()
        except Exception: logger.debug("Poll-lock deletion failed", exc_info=True)
        return
    text = message.text or message.caption or ""
    # Links lock
    if get_chat_setting(message.chat.id, "lock_links", False):
        if message.entities:
            for e in message.entities:
                if e.type in ("url", "text_link"):
                    try: await message.delete()
                    except Exception: pass
                    try: await bot.send_message(message.chat.id, "❌ Links are locked here.")
                    except Exception: pass
                    return
        if _URL_RE.search(text):
            try: await message.delete()
            except Exception: pass
            return
    # Media lock
    if get_chat_setting(message.chat.id, "lock_media", False):
        if message.photo or message.video or message.audio or message.document or message.animation or message.voice or message.video_note:
            try: await message.delete()
            except Exception: pass
            return
    # Stickers lock
    if get_chat_setting(message.chat.id, "lock_stickers", False):
        if message.sticker:
            try: await message.delete()
            except Exception: pass
            return

# ── Blacklist ─────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("addblacklist"))
async def addblacklist_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2:
        return await rich_reply(message, rich_note("❌ Usage: <code>/addblacklist &lt;word&gt;</code>"))
    word = " ".join(message.command[1:]).lower().strip()
    col = _blacklist_col()
    if col is None:
        return await rich_reply(message, rich_note("❌ DB not connected"))
    col.update_one({"chat_id": message.chat.id}, {"$addToSet": {"words": word}}, upsert=True)
    await rich_reply(message, rich_note(f"✅ <code>{rich_esc(word)}</code> added to blacklist."))

@bot.on_message(filters.command("rmblacklist"))
async def rmblacklist_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2:
        return await rich_reply(message, rich_note("❌ Usage: <code>/rmblacklist &lt;word&gt;</code>"))
    word = " ".join(message.command[1:]).lower().strip()
    col = _blacklist_col()
    if col is not None:
        col.update_one({"chat_id": message.chat.id}, {"$pull": {"words": word}})
    await rich_reply(message, rich_note(f"✅ <code>{rich_esc(word)}</code> removed."))

@bot.on_message(filters.command("blacklist"))
async def blacklist_list_cmd(_, message: Message):
    col = _blacklist_col()
    if col is None:
        return await rich_reply(message, rich_note("❌ DB not connected"))
    doc = col.find_one({"chat_id": message.chat.id})
    words = doc.get("words", []) if doc else []
    if not words:
        return await rich_reply(message, rich_note("✅ No blacklisted words"))
    rows = [(f"<code>{rich_esc(w)}</code>", "") for w in words]
    await rich_reply(message, rich_heading("🚫 Blacklisted Words", level=3) + rich_kv_table(rows))

@bot.on_message(filters.group, group=16)
async def mgmt_blacklist_checker(_, message: Message):
    if not message.chat or message.chat.type == "private": return
    if message.from_user and await is_admin(message.chat.id, message.from_user.id): return
    text = (message.text or message.caption or "").lower()
    if not text: return
    col = _blacklist_col()
    if col is None: return
    doc = col.find_one({"chat_id": message.chat.id})
    words = doc.get("words", []) if doc else []
    for word in words:
        if word in text:
            try: await message.delete()
            except Exception: pass
            threshold = get_chat_setting(message.chat.id, "warn_threshold", 3)
            wcol = _warnings_col()
            if wcol is not None:
                wcol.update_one({"chat_id": message.chat.id, "user_id": message.from_user.id}, {"$inc": {"count": 1}, "$push": {"reasons": {"reason": f"Blacklisted: {word}", "ts": datetime.now(timezone.utc).isoformat()}}}, upsert=True)
                doc2 = wcol.find_one({"chat_id": message.chat.id, "user_id": message.from_user.id})
                count = doc2.get("count", 1) if doc2 else 1
                await bot.send_message(message.chat.id, f"⚠️ {message.from_user.first_name} warned for blacklisted word. {count}/{threshold}")
                if count >= threshold:
                    try: await bot.ban_chat_member(message.chat.id, message.from_user.id)
                    except Exception: pass
            return

# ── Filters ───────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("filter"))
async def filter_add_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 3:
        return await rich_reply(message, rich_note("❌ Usage: <code>/filter &lt;keyword&gt; &lt;reply&gt;</code>"))
    keyword = message.command[1].lower().strip()
    reply = " ".join(message.command[2:])
    if message.reply_to_message:
        reply = message.reply_to_message.text or reply
    col = _filters_col()
    if col is None:
        return await rich_reply(message, rich_note("❌ DB not connected"))
    col.update_one({"chat_id": message.chat.id, "keyword": keyword}, {"$set": {"reply": reply}}, upsert=True)
    await rich_reply(message, rich_note(f"✅ Filter <code>{rich_esc(keyword)}</code> saved → <code>{rich_esc(reply[:50])}</code>"))

@bot.on_message(filters.command("stop"))
async def filter_stop_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2:
        return await rich_reply(message, rich_note("❌ Usage: <code>/stop &lt;keyword&gt;</code>"))
    keyword = message.command[1].lower().strip()
    col = _filters_col()
    if col is not None:
        r = col.delete_one({"chat_id": message.chat.id, "keyword": keyword})
        if r.deleted_count:
            return await rich_reply(message, rich_note(f"✅ Filter <code>{rich_esc(keyword)}</code> removed."))
    await rich_reply(message, rich_note(f"❌ No filter <code>{rich_esc(keyword)}</code> found."))

@bot.on_message(filters.command("filters"))
async def filters_list_cmd(_, message: Message):
    col = _filters_col()
    if col is None:
        return await rich_reply(message, rich_note("❌ DB not connected"))
    docs = list(col.find({"chat_id": message.chat.id}))
    if not docs:
        return await rich_reply(message, rich_note("✅ No filters in this chat"))
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
@bot.on_message(filters.command("save"))
async def save_note_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2:
        return await rich_reply(message, rich_note("❌ Usage: <code>/save &lt;name&gt; &lt;content&gt;</code> or reply with <code>/save &lt;name&gt;</code>"))
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
        return await rich_reply(message, rich_note("❌ Provide content"))
    col = _notes_col()
    if col is None:
        return await rich_reply(message, rich_note("❌ DB not connected"))
    doc = {"chat_id": message.chat.id, "name": name, "content": content, "type": note_type}
    if caption: doc["caption"] = caption
    col.update_one({"chat_id": message.chat.id, "name": name}, {"$set": doc}, upsert=True)
    await rich_reply(message, rich_note(f"✅ Note <code>{rich_esc(name)}</code> saved. Get with <code>#{rich_esc(name)}</code> or <code>/get {rich_esc(name)}</code>"))

@bot.on_message(filters.command("get"))
async def get_note_cmd(_, message: Message):
    if len(message.command) < 2:
        return await rich_reply(message, rich_note("❌ Usage: <code>/get &lt;name&gt;</code>"))
    name = message.command[1].lower().strip()
    await send_note(message.chat.id, name, reply_to=message.id)

async def send_note(chat_id: int, name: str, reply_to=None):
    col = _notes_col()
    if col is None: return
    doc = col.find_one({"chat_id": chat_id, "name": name.lower()})
    if not doc:
        await bot.send_message(chat_id, f"❌ No note `{name}` found.")
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

@bot.on_message(filters.command("delnote"))
async def delnote_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2:
        return await rich_reply(message, rich_note("❌ Usage: <code>/delnote &lt;name&gt;</code>"))
    name = message.command[1].lower().strip()
    col = _notes_col()
    if col is not None and col.delete_one({"chat_id": message.chat.id, "name": name}).deleted_count:
        await rich_reply(message, rich_note(f"✅ Note <code>{rich_esc(name)}</code> deleted."))
    else:
        await rich_reply(message, rich_note(f"❌ No note <code>{rich_esc(name)}</code> found."))

@bot.on_message(filters.command("notes"))
async def notes_list_cmd(_, message: Message):
    col = _notes_col()
    if col is None:
        return await rich_reply(message, rich_note("❌ DB not connected"))
    docs = list(col.find({"chat_id": message.chat.id}, {"name": 1}))
    if not docs:
        return await rich_reply(message, rich_note("✅ No notes in this chat"))
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
@bot.on_message(filters.command("setwelcome"))
async def setwelcome_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    content = " ".join(message.command[1:]) if len(message.command) > 1 else ""
    if not content:
        return await rich_reply(message, rich_note("❌ Usage: <code>/setwelcome &lt;message&gt;</code> — placeholders: <code>{name} {id} {title}</code>"))
    set_chat_setting(message.chat.id, "welcome_message", content)
    await rich_reply(message, rich_note("✅ Welcome message updated."))

@bot.on_message(filters.command("welcome"))
async def welcome_toggle_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2 or message.command[1].lower() not in ("on", "off"):
        return await rich_reply(message, rich_note("❌ Usage: <code>/welcome on|off</code>"))
    enabled = message.command[1].lower() == "on"
    set_chat_setting(message.chat.id, "welcome_enabled", enabled)
    await rich_reply(message, rich_note(f"✅ Welcome messages {'enabled' if enabled else 'disabled'}."))

@bot.on_message(filters.command("setcaptcha"))
async def setcaptcha_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2 or message.command[1].lower() not in ("on", "off"):
        return await rich_reply(message, rich_note("❌ Usage: <code>/setcaptcha on|off</code>"))
    enabled = message.command[1].lower() == "on"
    set_chat_setting(message.chat.id, "captcha_enabled", enabled)
    await rich_reply(message, rich_note(f"✅ Captcha {'enabled' if enabled else 'disabled'}."))

def _gen_captcha():
    a, b = random.randint(1, 10), random.randint(1, 10)
    op = random.choice(["+", "-", "×"])
    if op == "+": ans = a + b
    elif op == "-": ans = a - b
    else: ans = a * b
    return f"What is {a} {op} {b}?", str(ans)

async def _send_captcha(chat_id: int, user_id: int, user_name: str):
    q, ans = _gen_captcha()
    wrong1 = str(int(ans) + random.choice([-1, 1, 2, -2]))
    wrong2 = str(int(ans) + random.choice([3, -3, 4, -4]))
    opts = [ans, wrong1, wrong2]
    random.shuffle(opts)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(opt, callback_data=f"mgmt_cap_{user_id}_{opt}_{ans}") for opt in opts]])
    try:
        m = await bot.send_message(chat_id, f"👋 Welcome {user_name}!\n{q}\nVerify in 120s or you'll be kicked.", reply_markup=kb)
        # Save challenge
        ccol = _captcha_col()
        if ccol is not None:
            ccol.update_one({"chat_id": chat_id, "user_id": user_id}, {"$set": {"answer": ans, "msg_id": m.id, "ts": time.time()}}, upsert=True)
        # Auto-kick timer
        async def _kick_timeout():
            await asyncio.sleep(120)
            c = ccol.find_one({"chat_id": chat_id, "user_id": user_id}) if ccol is not None else None
            if c:
                try:
                    await bot.ban_chat_member(chat_id, user_id)
                    await bot.unban_chat_member(chat_id, user_id)
                    await bot.send_message(chat_id, f"⏰ {user_name} kicked for not verifying (captcha timeout)")
                    ccol.delete_one({"chat_id": chat_id, "user_id": user_id})
                except Exception: pass
        asyncio.create_task(_kick_timeout())
    except Exception as e:
        logger.debug(f"captcha send fail: {e}")

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
                txt = tmpl.format(name=member.first_name, id=member.id, title=message.chat.title or "group", mention=f"@{member.username}" if getattr(member, "username", None) else member.first_name)
            except Exception:
                txt = tmpl
            try:
                await bot.send_message(message.chat.id, txt)
            except Exception: pass
        # Captcha
        if get_chat_setting(message.chat.id, "captcha_enabled", False):
            # Restrict new user
            try:
                from pyrogram.types import ChatPermissions
                await bot.restrict_chat_member(message.chat.id, member.id, ChatPermissions(can_send_messages=False))
            except Exception: pass
            await _send_captcha(message.chat.id, member.id, member.first_name or "New user")

@bot.on_callback_query(filters.regex(r"^mgmt_cap_"))
async def mgmt_captcha_callback(_, cq: CallbackQuery):
    try:
        _, user_id, chosen, ans = cq.data.split("_", 3)
        user_id = int(user_id)
        if cq.from_user.id != user_id and not await is_admin(cq.message.chat.id, cq.from_user.id):
            return await cq.answer("This captcha is not for you!", show_alert=True)
        if chosen == ans:
            # Correct — unrestrict
            try:
                from pyrogram.types import ChatPermissions
                await bot.restrict_chat_member(cq.message.chat.id, user_id, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True))
            except Exception: pass
            ccol = _captcha_col()
            if ccol is not None:
                ccol.delete_one({"chat_id": cq.message.chat.id, "user_id": user_id})
            await cq.message.edit_text(f"✅ {cq.from_user.first_name} verified! Welcome 🎉")
            await cq.answer("Verified ✅")
        else:
            await cq.answer("❌ Wrong answer! Try again.", show_alert=True)
            # Kick on wrong
            try:
                await bot.ban_chat_member(cq.message.chat.id, user_id)
                await bot.unban_chat_member(cq.message.chat.id, user_id)
                await cq.message.edit_text(f"❌ {cq.from_user.first_name} failed captched and was kicked.")
            except Exception: pass
    except Exception as e:
        logger.debug(f"captcha callback fail: {e}")
        await cq.answer("Error", show_alert=False)

# ── Pins, Purge, Slowmode ────────────────────────────────────────────────────
@bot.on_message(filters.command(["pin", "unpin", "unpinall"]))
async def pin_cmds(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    cmd = message.command[0].lower()
    try:
        if cmd == "pin":
            if not message.reply_to_message:
                return await rich_reply(message, rich_note("❌ Reply to a message to pin."))
            await bot.pin_chat_message(message.chat.id, message.reply_to_message.id, disable_notification=False)
            await rich_reply(message, rich_note("📌 Message pinned."))
        elif cmd == "unpin":
            await bot.unpin_chat_message(message.chat.id)
            await rich_reply(message, rich_note("✅ Message unpinned."))
        elif cmd == "unpinall":
            await bot.unpin_all_chat_messages(message.chat.id)
            await rich_reply(message, rich_note("✅ All pins removed."))
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Failed: <code>{rich_esc(str(e))}</code>"))

@bot.on_message(filters.command(["purge", "cleanup"]))
async def purge_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if message.command[0].lower() == "purge":
        if not message.reply_to_message:
            return await rich_reply(message, rich_note("❌ Reply to the first message to purge from."))
        start, end = message.reply_to_message.id, message.id
        deleted = 0
        for mid in range(start, end):
            try: await bot.delete_messages(message.chat.id, mid); deleted += 1
            except Exception: pass
        await bot.send_message(message.chat.id, f"✅ Purged {deleted} messages.")
    else:
        count = int(message.command[1]) if len(message.command) > 1 and message.command[1].isdigit() else 0
        if not (1 <= count <= 100):
            return await rich_reply(message, rich_note("❌ Usage: <code>/cleanup &lt;1-100&gt;</code>"))
        deleted = 0
        for off in range(count):
            try: await bot.delete_messages(message.chat.id, message.id - off); deleted += 1
            except Exception: pass
        await bot.send_message(message.chat.id, f"✅ Deleted {deleted} messages.")

@bot.on_message(filters.command("slowmode"))
async def slowmode_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await rich_reply(message, rich_note("❌ Usage: <code>/slowmode &lt;seconds&gt;</code> (0 to disable)"))
    sec = int(message.command[1])
    try:
        await bot.set_chat_slow_mode(message.chat.id, sec)
        await rich_reply(message, rich_note(f"✅ Slowmode {'disabled' if sec==0 else f'set to {sec}s'}"))
    except Exception as e:
        await rich_reply(message, rich_note(f"❌ Failed: <code>{rich_esc(str(e))}</code>"))

# ── Rules ─────────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("setrules"))
async def setrules_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    content = " ".join(message.command[1:]) if len(message.command) > 1 else ""
    if not content:
        return await rich_reply(message, rich_note("❌ Usage: <code>/setrules &lt;rules&gt;</code>"))
    set_chat_setting(message.chat.id, "rules", content)
    await rich_reply(message, rich_note("✅ Rules updated."))

@bot.on_message(filters.command("rules"))
async def rules_cmd(_, message: Message):
    rules = get_chat_setting(message.chat.id, "rules", None)
    if not rules:
        return await rich_reply(message, rich_note("❌ No rules set"))
    await rich_reply(message, rich_heading("📜 Group Rules", level=3) + rich_note(rules))

@bot.on_message(filters.command("clearrules"))
async def clearrules_cmd(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("❌ Admins only", level=3))
    set_chat_setting(message.chat.id, "rules", None)
    await rich_reply(message, rich_note("✅ Rules cleared."))

# ── Group utilities ─────────────────────────────────────────────────────────
@bot.on_message(filters.command("poll"))
async def poll_cmd(_, message: Message):
    q = " ".join(message.command[1:]) if len(message.command) > 1 else ""
    if not q or "|" not in q:
        return await rich_reply(message, rich_note("❌ Usage: <code>/poll Question | Option1 | Option2 | ...</code>"))
    parts = [p.strip() for p in q.split("|")]
    await bot.send_poll(message.chat.id, parts[0], parts[1:])

@bot.on_message(filters.command("stickerid"))
async def stickerid_cmd(_, message: Message):
    if message.reply_to_message and message.reply_to_message.sticker:
        await rich_reply(message, rich_code(message.reply_to_message.sticker.file_id, lang=""))
    else:
        await rich_reply(message, rich_note("❌ Reply to a sticker"))

# ── Misc: help/id/whois/stats ────────────────────────────────────────────────
@bot.on_message(filters.command("help"))
async def help_cmd(_, message: Message):
    await rich_reply(message, rich_heading("📖 Videl Help — Videl Powered", level=2) + rich_note("Select a category:") , reply_markup=help_keyboard())

@bot.on_callback_query(filters.regex(r"^mgmt_help_"))
async def help_callback(_, cq: CallbackQuery):
    data = cq.data
    texts = {
        "mgmt_help_mod": "🛡 <b>Moderation</b>\n<code>/ban</code> • <code>/tban 1h</code> • <code>/unban</code> • <code>/kick</code> • <code>/mute</code> • <code>/tmute 10m</code> • <code>/unmute</code>\n<code>/warn</code> • <code>/unwarn</code> • <code>/warnings</code> • <code>/clearwarns</code> • <code>/setwarnlimit 3</code>\n<code>/promote</code> • <code>/demote</code> • <code>/banlist</code> • <code>/admins</code>",
        "mgmt_help_settings": "⚙️ <b>Settings</b>\n<code>/setwelcome</code> • <code>/welcome on|off</code> • <code>/setcaptcha on|off</code>\n<code>/setrules</code> • <code>/rules</code> • <code>/clearrules</code>\n<code>/lock links|media|stickers|all</code> • <code>/unlock</code> • <code>/locks</code>\n<code>/slowmode 10</code> • <code>/slowmode 0</code> to disable",
        "mgmt_help_notes": "📝 <b>Notes & Filters</b>\n<code>/save name content</code> • <code>/get name</code> • <code>#name</code> trigger • <code>/delnote name</code> • <code>/notes</code>\n<code>/filter keyword reply</code> • <code>/stop keyword</code> • <code>/filters</code>\n<code>/addblacklist word</code> • <code>/rmblacklist word</code> • <code>/blacklist</code>",
        "mgmt_help_admin": "🔧 <b>Admin Tools</b>\n<code>/pin</code> (reply) • <code>/unpin</code> • <code>/unpinall</code>\n<code>/purge</code> (reply) • <code>/cleanup 5</code>",
        "mgmt_help_misc": "ℹ️ <b>Misc</b>\n<code>/id</code> • <code>/whois @user</code> • <code>/stats</code>",
    }
    key = data.replace("mgmt_help_", "mgmt_help_" if data.startswith("mgmt_help_") else data)
    txt = texts.get(data, "Select a category")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="mgmt_help_back")]])
    await cq.message.edit_text(txt, reply_markup=kb)
    await cq.answer()

@bot.on_callback_query(filters.regex(r"^mgmt_help_back$"))
async def help_back(_, cq: CallbackQuery):
    await cq.message.edit_text(rich_heading("📖 Videl Help", level=2) + rich_note("Select a category"), reply_markup=help_keyboard())
    await cq.answer()

@bot.on_message(filters.command("id"))
async def id_cmd(_, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else "—"
    text = rich_heading("🆔 IDs", level=3) + rich_kv_table([("Chat", f"<code>{chat_id}</code>"), ("You", f"<code>{user_id}</code>")])
    if message.reply_to_message and message.reply_to_message.from_user:
        text += rich_kv_table([("Replied", f"<code>{message.reply_to_message.from_user.id}</code> — {rich_esc(message.reply_to_message.from_user.first_name)}")])
    await rich_reply(message, text)

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
        return await rich_reply(message, rich_note("❌ DB not connected"))
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

LOGGER.info(" Videl → Videl integrated ✅ — all 9 modules ported, Richgram UI, credits → Videl")
