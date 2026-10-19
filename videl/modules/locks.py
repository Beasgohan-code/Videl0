# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Content locks panel + simple anti-flood
#  Inspired by open-source group management bots
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

import time
from collections import defaultdict, deque

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from videl import bot, LOGGER
from videl.modules.block import group_allowed, user_allowed
from videl.utils.db import (
    get_antiflood,
    get_mod_settings,
    set_antiflood,
    set_mod_setting,
)
from videl.utils.permissions import is_user_authorized
from videl.utils.rich_ui import (
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_send,
)

# chat_id -> user_id -> deque of timestamps
_flood_bucket: dict[int, dict[int, deque]] = defaultdict(lambda: defaultdict(deque))


LOCK_KEYS = {
    "nsfw": "NSFW / adult media",
    "badword": "Bad words",
    "link": "Links / URLs",
    "document": "Documents / files",
}


def _locks_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    settings = get_mod_settings(chat_id)
    rows = []
    for key, label in LOCK_KEYS.items():
        on = settings.get(key, True)
        emoji = "🔒" if on else "🔓"
        rows.append([
            InlineKeyboardButton(
                f"{emoji} {label}: {'ON' if on else 'OFF'}",
                callback_data=f"locktoggle:{key}",
            )
        ])
    af = get_antiflood(chat_id)
    af_label = f"🌊 Anti-flood: {'ON' if af.get('enabled') else 'OFF'} ({af.get('limit', 6)}/{af.get('window', 8)}s)"
    rows.append([InlineKeyboardButton(af_label, callback_data="locktoggle:antiflood")])
    rows.append([InlineKeyboardButton("✕ Close", callback_data="lockclose")])
    return InlineKeyboardMarkup(rows)


@bot.on_message(
    filters.command(["locks", "lockpanel", "contentlocks"])
    & filters.group
    & group_allowed
    & user_allowed
)
async def locks_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    await rich_send(
        bot, chat_id,
        rich_heading("🔐 Content locks", level=3)
        + rich_note("Toggle filters below. Locked = bot will try to delete matching content."),
        reply_markup=_locks_keyboard(chat_id),
    )


@bot.on_message(
    filters.command(["antiflood", "setflood"])
    & filters.group
    & group_allowed
    & user_allowed
)
async def antiflood_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    args = message.command[1:]

    if not args:
        af = get_antiflood(chat_id)
        await rich_send(
            bot, chat_id,
            rich_heading("🌊 Anti-flood", level=3)
            + rich_kv_table([
                ("Enabled", "Yes" if af.get("enabled") else "No"),
                ("Limit", str(af.get("limit", 6))),
                ("Window", f"{af.get('window', 8)}s"),
            ])
            + rich_note(
                "<code>/antiflood on</code>\n"
                "<code>/antiflood off</code>\n"
                "<code>/antiflood 5 10</code> — max 5 messages per 10 seconds"
            ),
        )
        return

    if args[0].lower() in ("on", "yes", "true", "enable"):
        set_antiflood(chat_id, True)
        await rich_send(bot, chat_id, rich_heading("✅ Anti-flood enabled", level=3))
        return
    if args[0].lower() in ("off", "no", "false", "disable"):
        set_antiflood(chat_id, False)
        await rich_send(bot, chat_id, rich_heading("✅ Anti-flood disabled", level=3))
        return

    if len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
        set_antiflood(chat_id, True, int(args[0]), int(args[1]))
        af = get_antiflood(chat_id)
        await rich_send(
            bot, chat_id,
            rich_heading("✅ Anti-flood updated", level=3)
            + rich_kv_table([
                ("Limit", str(af["limit"])),
                ("Window", f"{af['window']}s"),
            ]),
        )
        return

    await rich_send(bot, chat_id, rich_heading("Invalid usage", level=3) + rich_note("See /antiflood"))


# ── Anti-flood middleware (lightweight) ────────────────────────────────────────

@bot.on_message(filters.group & group_allowed, group=8)
async def antiflood_watcher(_, message: Message) -> None:
    if not message.from_user or message.from_user.is_bot:
        return
    if message.service:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Skip admins / owner
    if user_id == config.OWNER_ID:
        return
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return
    except Exception:
        pass

    af = get_antiflood(chat_id)
    if not af.get("enabled"):
        return

    now = time.time()
    window = float(af.get("window", 8))
    limit = int(af.get("limit", 6))
    bucket = _flood_bucket[chat_id][user_id]

    # drop old timestamps
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    bucket.append(now)

    if len(bucket) > limit:
        try:
            await message.delete()
        except Exception:
            pass
        # mild mute 60s
        try:
            from pyrogram.types import ChatPermissions
            from datetime import datetime, timedelta
            await bot.restrict_chat_member(
                chat_id,
                user_id,
                permissions=ChatPermissions(),
                until_date=datetime.utcnow() + timedelta(seconds=60),
            )
            await rich_send(
                bot, chat_id,
                rich_heading("🌊 Flood detected", level=3)
                + rich_note(f"{message.from_user.mention} muted for 60s (too many messages)."),
            )
        except Exception as e:
            LOGGER.debug(f"antiflood action failed: {e}")
        bucket.clear()


# Callback toggles are handled in callbacks.py (we register a small handler here too)

from pyrogram import enums


@bot.on_callback_query(filters.regex(r"^locktoggle:") | filters.regex(r"^lockclose$"))
async def locks_callback(_, cq) -> None:
    data = cq.data or ""
    if not cq.message or not cq.message.chat:
        return
    chat_id = cq.message.chat.id

    if not await is_user_authorized(cq):
        await cq.answer("Admins only", show_alert=True)
        return

    if data == "lockclose":
        try:
            await cq.message.delete()
        except Exception:
            pass
        await cq.answer()
        return

    key = data.split(":", 1)[-1]
    if key == "antiflood":
        af = get_antiflood(chat_id)
        set_antiflood(chat_id, not af.get("enabled"), af.get("limit", 6), af.get("window", 8))
        await cq.answer("Anti-flood toggled")
    elif key in LOCK_KEYS:
        settings = get_mod_settings(chat_id)
        new_val = not settings.get(key, True)
        set_mod_setting(chat_id, key, new_val)
        await cq.answer(f"{LOCK_KEYS[key]} → {'ON' if new_val else 'OFF'}")
    else:
        await cq.answer()
        return

    try:
        await cq.message.edit_reply_markup(reply_markup=_locks_keyboard(chat_id))
    except Exception:
        pass
