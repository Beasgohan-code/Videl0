# --------------------------------------------------------------------------------
#  Videl 👑 Group Protection & Automation Wizard — Real MongoDB Toggles
#  Reads and updates live group protection settings in mgmt_chat_settings
# --------------------------------------------------------------------------------
from __future__ import annotations
import logging
from datetime import datetime, timezone
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from videl.utils.bot_ui import button as InlineKeyboardButton

import config
from videl import bot
from videl.utils.db import get_db, set_antiflood
from videl.utils.rich_ui import rich_heading, rich_kv_table, rich_note, rich_reply, rich_edit

logger = logging.getLogger(__name__)

SETTING_ITEMS = [
    ("antispam", "⚡ Anti-Spam Shield", "Auto-detect & block spam bursts"),
    ("lock_links", "🔗 Link Blocker", "Block unauthorized URLs & invite links"),
    ("lock_forwards", "↩️ Forward Lock", "Block forwarded channel/user messages"),
    ("lock_media", "🖼️ Media Lock", "Restrict unapproved photos & videos"),
    ("lock_stickers", "🎭 Sticker Lock", "Restrict sticker spam in chat"),
    ("welcome_enabled", "👋 Welcome Gate", "Send automated welcome card to new members"),
]


def _webapp_url() -> str:
    return (getattr(config, "WEBAPP_URL", "https://videl0-control-panel.vercel.app") or "https://videl0-control-panel.vercel.app").rstrip("/")


def _read_settings(chat_id: int) -> dict[str, bool]:
    db = get_db()
    if db is None:
        return {k: False for k, _, _ in SETTING_ITEMS}
    doc = db["mgmt_chat_settings"].find_one({"chat_id": int(chat_id)}) or {}
    return {k: bool(doc.get(k, False)) for k, _, _ in SETTING_ITEMS}


async def _can_manage(client, chat_id: int, user_id: int, chat_type) -> bool:
    if config.is_sudo(user_id):
        return True
    if chat_type == ChatType.PRIVATE:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


def _wizard_panel(chat_id: int, chat_title: str) -> tuple[str, InlineKeyboardMarkup]:
    state = _read_settings(chat_id)
    active_count = sum(1 for v in state.values() if v)
    rows = [(label, f"<code>{'ENABLED ●' if state[key] else 'OFF ○'}</code> — {desc}") for key, label, desc in SETTING_ITEMS]
    text = (
        rich_heading(f"👑 Videl Studio · Group Manager ({chat_title})", level=1)
        + rich_kv_table([
            ("Protected Chat", f"<code>{chat_id}</code>"),
            ("Active Shields", f"<code>{active_count}/{len(SETTING_ITEMS)} enabled</code>"),
        ])
        + rich_kv_table(rows, headers=["Protection Rule", "Live State"])
        + rich_note("Tap any shield below to toggle it live in MongoDB, or open the Videl Web App Studio.")
    )

    buttons = []
    pair = []
    for key, label, _ in SETTING_ITEMS:
        icon = "✅" if state[key] else "⬜"
        short_label = label.split(" ", 1)[1] if " " in label else label
        pair.append(InlineKeyboardButton(f"{icon} {short_label}", callback_data=f"wiz2_toggle_{key}"))
        if len(pair) == 2:
            buttons.append(pair)
            pair = []
    if pair:
        buttons.append(pair)

    buttons.append([
        InlineKeyboardButton("🛡️ Enable All Shields", callback_data="wiz2_preset_strict"),
        InlineKeyboardButton("🔄 Reset All", callback_data="wiz2_preset_clear"),
    ])
    buttons.append([
        InlineKeyboardButton("👑 Open Videl Web App", url=f"{_webapp_url()}?tab=groups"),
        InlineKeyboardButton("✖ Close", callback_data="wiz2_close"),
    ])
    return text, InlineKeyboardMarkup(buttons)


@bot.on_message(filters.command(["setup", "configure", "wizard"]))
async def setup_cmd(client, message: Message):
    chat_id = message.chat.id
    title = message.chat.title or message.from_user.first_name if message.from_user else "Chat"
    text, kb = _wizard_panel(chat_id, title)
    await rich_reply(message, text, reply_markup=kb)


@bot.on_callback_query(filters.regex(r"^wiz2_"))
async def wiz2_cb(client, cq: CallbackQuery):
    data = cq.data
    chat = cq.message.chat if cq.message else None
    if not chat:
        return await cq.answer()
    if data == "wiz2_close":
        await cq.message.delete()
        return await cq.answer()

    uid = cq.from_user.id if cq.from_user else 0
    if not await _can_manage(client, chat.id, uid, chat.type):
        return await cq.answer("Only group admins or the bot owner can change protection settings.", show_alert=True)

    db = get_db()
    if data.startswith("wiz2_toggle_"):
        key = data.replace("wiz2_toggle_", "")
        valid_keys = {k for k, _, _ in SETTING_ITEMS}
        if key in valid_keys and db is not None:
            current = _read_settings(chat.id).get(key, False)
            new_val = not current
            db["served_chats"].update_one({"_id": int(chat.id)}, {"$set": {"_id": int(chat.id)}}, upsert=True)
            db["mgmt_chat_settings"].update_one(
                {"chat_id": int(chat.id)},
                {"$set": {key: new_val, "updated_by": uid, "updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
            if key == "antispam":
                try:
                    set_antiflood(chat.id, new_val)
                except Exception:
                    pass
            await cq.answer(f"{key}: {'Enabled ✅' if new_val else 'Disabled ○'}")
        elif db is None:
            return await cq.answer("MongoDB is not connected.", show_alert=True)
    elif data in ("wiz2_preset_strict", "wiz2_preset_clear"):
        if db is None:
            return await cq.answer("MongoDB is not connected.", show_alert=True)
        enable = data == "wiz2_preset_strict"
        updates = {k: enable for k, _, _ in SETTING_ITEMS}
        updates["updated_by"] = uid
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        db["served_chats"].update_one({"_id": int(chat.id)}, {"$set": {"_id": int(chat.id)}}, upsert=True)
        db["mgmt_chat_settings"].update_one({"chat_id": int(chat.id)}, {"$set": updates}, upsert=True)
        try:
            set_antiflood(chat.id, enable)
        except Exception:
            pass
        await cq.answer("All group shields enabled! 🛡️" if enable else "All group shields reset.")
    else:
        await cq.answer("Videl Studio Group Manager")

    title = chat.title or (cq.from_user.first_name if cq.from_user else "Chat")
    text, kb = _wizard_panel(chat.id, title)
    try:
        await rich_edit(cq.message, text, reply_markup=kb)
    except Exception:
        pass
