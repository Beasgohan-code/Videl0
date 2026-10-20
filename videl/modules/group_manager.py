"""Permission-checked group workspace, reports and invite links."""
from collections import OrderedDict
import time
from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.types import InlineKeyboardMarkup
from videl import LOGGER, bot
from videl.plugins.base import is_admin, get_setting as get_chat_setting, set_settings as set_chat_settings, collection as _collection
from videl.utils.bot_ui import button
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table, rich_esc
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
        return rich_heading("Group settings unavailable", level=2) + rich_note("MongoDB could not be read. No protection state is being reported."), InlineKeyboardMarkup([[button("Refresh", callback_data=f"groupcfg:{chat_id}:refresh:0")]])
    states = {key: bool(saved.get(key, key == "welcome_enabled")) for key in RULES}
    rows = []
    items = list(RULES.items())
    for index in range(0, len(items), 2):
        rows.append([button(f"{'On' if states[key] else 'Off'} · {label}", callback_data=f"groupcfg:{chat_id}:{key}:{int(not states[key])}", style="success" if states[key] else "default", icon="shield") for key, label in items[index:index+2]])
    rows.append([button("Commands", callback_data="help:manage"), button("Refresh", callback_data=f"groupcfg:{chat_id}:refresh:0")])
    text = rich_heading("Group workspace", level=2) + rich_kv_table([("Group", rich_esc(title)), ("Chat ID", f"<code>{chat_id}</code>")]) + rich_note("Explicit On/Off actions are saved in MongoDB. Only current group admins can change them. The bot needs Delete messages and Restrict members permissions for protection and join verification.")
    return text, InlineKeyboardMarkup(rows)


@bot.on_message(filters.command(["group", "setup"]) & filters.group)
async def group_command(_, message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_note("Group admins only."))
    text, markup = panel(message.chat.id, message.chat.title or "Group")
    await rich_reply(message, text, reply_markup=markup)


@bot.on_callback_query(filters.regex(r"^groupcfg:"))
async def group_setting(_, query):
    try:
        _, chat, key, value = query.data.split(":")
        if not query.message or int(chat) != query.message.chat.id or value not in {"0", "1"}:
            raise ValueError()
    except (ValueError, AttributeError):
        return await query.answer("Invalid group control.", show_alert=True)
    if not await is_admin(query.message.chat.id, query.from_user.id):
        return await query.answer("Group admins only.", show_alert=True)
    if key != "refresh":
        if key not in RULES:
            return await query.answer("Unknown setting.", show_alert=True)
        updates = {key: value == "1"}
        if key == "lock_forwards":
            updates["lock_forward"] = value == "1"
        if not set_chat_settings(int(chat), updates):
            return await query.answer("MongoDB unavailable. Nothing was saved.", show_alert=True)
    await query.answer("Saved" if key != "refresh" else "Refreshed")
    text, markup = panel(int(chat), query.message.chat.title or "Group")
    await rich_edit(query.message, text, reply_markup=markup)


@bot.on_message(filters.command("report") & filters.group)
async def report_command(_, message):
    target = message.reply_to_message
    if not message.from_user or not target or not target.from_user:
        return await rich_reply(message, rich_note("Reply to the message you want admins to review with /report."))
    key = (message.chat.id, message.from_user.id)
    now = time.monotonic()
    if now - _REPORTS.get(key, -60) < 60:
        return await rich_reply(message, rich_note("Please wait a minute before submitting another report."))
    admins = [member async for member in bot.get_chat_members(message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS, limit=20)]
    mentions = " ".join(f'<a href="tg://user?id={member.user.id}">{rich_esc(member.user.first_name)}</a>' for member in admins if not member.user.is_bot)
    if not mentions:
        return await rich_reply(message, rich_note("No human admins could be resolved. Contact your group owner."))
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
    await rich_reply(message, rich_heading("Admin review requested", level=3) + rich_note(f"Reported message: <code>{target.id}</code>\n{mentions}\nReports do not automatically punish anyone."))


@bot.on_message(filters.command("permissions") & filters.group)
async def permission_command(_, message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_note("Group admins only."))
    from videl.utils.permission_diagnostics import permission_rows
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(message.chat.id, me.id)
        rows = permission_rows(member)
    except Exception:
        return await rich_reply(message, rich_note("Could not read current bot permissions. No rights are being reported; try again."))
    await rich_reply(message, rich_heading("Bot permission diagnostics", level=2)
        + rich_kv_table(rows)
        + rich_note("A group owner can change these in Telegram → Group → Administrators → Videl. Rights alone do not guarantee assistant access, media availability or playback."))

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
