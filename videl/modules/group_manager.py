"""Permission-checked group workspace, reports and invite links."""
import config
from collections import OrderedDict
import time
from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.types import InlineKeyboardMarkup
from videl import LOGGER, bot
from videl.plugins.base import is_admin, get_setting as get_chat_setting, set_settings as set_chat_settings, collection as _collection
from videl.utils.bot_ui import button
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table, rich_esc
from videl.utils.premium_emojis import pe
from videl.utils.command_ui import rich_reply, rich_edit

RULES = {"antispam": "Flood protection", "lock_links": "Block links", "lock_forwards": "Block forwards", "lock_media": "Block media", "lock_stickers": "Block stickers", "lock_polls": "Block polls", "captcha_enabled": "Join verification", "welcome_enabled": "Welcome message"}
_REPORTS = OrderedDict()


def panel(chat_id, title):
    try:
        col = _collection()
        if col is None:
            raise RuntimeError("MongoDB unavailable")
        saved = col.find_one({"chat_id": chat_id}) or {}
    except Exception:
        return (
            rich_heading("⚠️ Group settings unavailable", level=2)
            + rich_note("I couldn’t read the saved settings, so I’m not showing guessed On/Off states. Refresh to try again.")
        ), InlineKeyboardMarkup([[button("Refresh settings", callback_data=f"groupcfg:{chat_id}:refresh:0", icon="ios_gear")]])
    states = {key: bool(saved.get(key, key == "welcome_enabled")) for key in RULES}
    rows = []
    items = list(RULES.items())
    for index in range(0, len(items), 2):
        rows.append([button(f"{'On' if states[key] else 'Off'} · {label}", callback_data=f"groupcfg:{chat_id}:{key}:{int(not states[key])}", style="success" if states[key] else "default", icon="lock" if states[key] else "unlock") for key, label in items[index:index+2]])
    rows.append([button("Commands", callback_data="help:manage"), button("Refresh", callback_data=f"groupcfg:{chat_id}:refresh:0")])
    state_rows = [
        ((pe("lock") if states[key] else pe("unlock")) + " " + label, "On" if states[key] else "Off")
        for key, label in items
    ]
    text = (
        rich_heading("🛡 Group safety dashboard", level=2)
        + rich_kv_table([("Group", rich_esc(title)), ("Chat ID", f"<code>{chat_id}</code>")])
        + rich_kv_table(state_rows)
        + rich_note("Use the controls below to change a setting. Changes save immediately; only current group admins can edit them.")
        + rich_note("For protection and join verification, Videl needs Delete messages and Restrict members rights.")
        + rich_note("Group branding: use <code>/settitle</code>, <code>/setdescription</code>, <code>/setphoto</code> or <code>/delphoto</code>. These actions require Telegram’s Change info right.")
    )
    return text, InlineKeyboardMarkup(rows)


@bot.on_message(filters.command("group", prefixes=config.COMMAND_PREFIXES) & filters.group)
async def group_command(_, message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("🔒 Group admins only", level=3) + rich_note("Ask a current group admin to open these controls."))
    text, markup = panel(message.chat.id, message.chat.title or "Group")
    await rich_reply(message, text, reply_markup=markup)


@bot.on_callback_query(filters.regex(r"^groupcfg:"))
async def group_setting(_, query):
    try:
        _, chat, key, value = query.data.split(":")
        if not query.message or int(chat) != query.message.chat.id or value not in {"0", "1"}:
            raise ValueError()
    except (ValueError, AttributeError):
        return await query.answer("❌ Invalid group control.", show_alert=True)
    if not await is_admin(query.message.chat.id, query.from_user.id):
        return await query.answer("🔒 Current group admins only.", show_alert=True)
    if key != "refresh":
        if key not in RULES:
            return await query.answer("❓ Unknown setting.", show_alert=True)
        updates = {key: value == "1"}
        if key == "lock_forwards":
            updates["lock_forward"] = value == "1"
        if not set_chat_settings(int(chat), updates):
            return await query.answer("⚠️ Settings could not be saved. Nothing changed.", show_alert=True)
    await query.answer("✅ Saved" if key != "refresh" else "🔄 Refreshed")
    text, markup = panel(int(chat), query.message.chat.title or "Group")
    await rich_edit(query.message, text, reply_markup=markup)


@bot.on_message(filters.command("report", prefixes=config.COMMAND_PREFIXES) & filters.group)
async def report_command(_, message):
    target = message.reply_to_message
    if not message.from_user or not target or not target.from_user:
        return await rich_reply(message, rich_heading("📣 Report a message", level=3) + rich_note("Reply to the message you want admins to review, then send <code>/report</code>. Reports notify human admins; they do not punish anyone automatically."))
    key = (message.chat.id, message.from_user.id)
    now = time.monotonic()
    if now - _REPORTS.get(key, -60) < 60:
        return await rich_reply(message, rich_heading("⏳ Please wait before reporting again", level=3) + rich_note("To prevent report spam, you can submit another report in about a minute."))
    admins = [member async for member in bot.get_chat_members(message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS, limit=20)]
    mentions = " ".join(f'<a href="tg://user?id={member.user.id}">{rich_esc(member.user.first_name)}</a>' for member in admins if not member.user.is_bot)
    if not mentions:
        return await rich_reply(message, rich_heading("⚠️ Admins could not be reached", level=3) + rich_note("Telegram did not return any human admins to notify. Contact your group owner directly."))
    _REPORTS[key] = now
    _REPORTS.move_to_end(key)
    while len(_REPORTS) > 4096:
        _REPORTS.popitem(last=False)
    # Persist the report so the owner panel can triage it later; the in-memory
    # map above only rate-limits repeat submissions.
    try:
        from datetime import datetime, timezone
        from videl.utils.db import get_db
        db = get_db()
        if db is not None:
            db["mgmt_reports"].insert_one({
                "chat_id": message.chat.id,
                "reporter": message.from_user.id,
                "target": getattr(target.from_user, "id", None),
                "message_id": target.id,
                "text": str(target.text or target.caption or "")[:280],
                "status": "open",
                "ts": datetime.now(timezone.utc),
            })
    except Exception:
        LOGGER.debug("report persistence failed", exc_info=True)
    quoted_text = str(target.text or target.caption or "").strip()
    preview = rich_esc(quoted_text[:320]) if quoted_text else "No text or caption — admins can review the replied message in the group."
    await rich_reply(
        message,
        rich_heading("📣 Report sent for review", level=3)
        + rich_kv_table([("Message", f"<code>#{target.id}</code>"), ("Preview", preview)])
        + rich_note(f"Group admins have been notified below.\n{mentions}")
        + rich_note("A report requests human review; it does not apply a punishment."),
    )


@bot.on_message(filters.command("permissions", prefixes=config.COMMAND_PREFIXES) & filters.group)
async def permission_command(_, message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("🔒 Group admins only", level=3) + rich_note("Ask a current group admin to open these controls."))
    from videl.utils.permission_diagnostics import permission_rows
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(message.chat.id, me.id)
        rows = permission_rows(member)
    except Exception:
        return await rich_reply(message, rich_heading("⚠️ Permission check unavailable", level=3) + rich_note("Telegram did not return the bot’s current admin rights. No permissions are being guessed; try again shortly."))
    rows = [
        (label, (pe("check") + " Granted") if state == "Granted" else (pe("rijif_warning") + " Missing"))
        for label, state in rows
    ]
    await rich_reply(
        message,
        rich_heading("🛡 Bot permission diagnostics", level=2)
        + rich_note("Current rights reported by Telegram for this group:")
        + rich_kv_table(rows)
        + rich_note("A group owner can update these in Telegram → Group → Administrators → Videl. Rights alone do not guarantee assistant access, media availability or playback."),
    )

@bot.on_chat_join_request()
async def join_request_seen(_, request):
    """Record a pending join request for the owner panel.

    Telegram keeps the request itself; this row only tells the panel that a
    person is waiting, so approving still happens through the Bot API.
    """
    try:
        from datetime import datetime, timezone
        from videl.utils.db import get_db
        chat = request.chat
        user = request.from_user
        db = get_db()
        if db is None or not chat or not user:
            return
        db["mgmt_join_requests"].update_one(
            {"chat_id": chat.id, "user": user.id},
            {"$set": {
                "chat_id": chat.id,
                "user": user.id,
                "name": str(user.first_name or "")[:80],
                "username": str(user.username or "")[:64],
                "status": "pending",
                "ts": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception:
        LOGGER.debug("join request could not be recorded", exc_info=True)
