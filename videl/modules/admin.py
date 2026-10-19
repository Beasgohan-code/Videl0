# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code
#  Group management inspired by open-source bots (AnnieXMusic, Nomade, FallenRobot patterns)
#  Fork & improve freely under MIT. Keep credits.
# --------------------------------------------------------------------------------

"""
Group management module — ban, mute, kick, promote, warn, welcome, purge, pin.
Requires the bot to be admin with appropriate rights.
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from pyrogram import enums, filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.errors import (
    ChatAdminRequired,
    FloodWait,
    PeerIdInvalid,
    RightForbidden,
    UserAdminInvalid,
    UserNotParticipant,
)
from pyrogram.types import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from videl import LOGGER, bot
from videl.modules.block import group_allowed, user_allowed
from videl.utils.db import (
    add_warn,
    get_warn_limit,
    get_warns,
    get_welcome,
    reset_warns,
    set_warn_limit,
    set_welcome,
    set_welcome_enabled,
    get_goodbye,
    set_goodbye,
)
from videl.utils.permissions import is_user_authorized
from videl.utils.rich_ui import (
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_send,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_target(message: Message) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Resolve target user from reply or command arg.
    Returns (user_id, mention_html, display_name) or (None, None, None).
    """
    user_id = None
    name = None

    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        user_id = u.id
        name = u.first_name or str(u.id)
    elif message.command and len(message.command) > 1:
        arg = message.command[1]
        if arg.isdigit() or (arg.startswith("-") and arg[1:].isdigit()):
            user_id = int(arg)
            name = str(user_id)
        else:
            # username
            try:
                u = await bot.get_users(arg)
                user_id = u.id
                name = u.first_name or str(u.id)
            except Exception:
                return None, None, None
    else:
        return None, None, None

    if user_id is None:
        return None, None, None

    mention = f'<a href="tg://user?id={user_id}">{rich_esc(name)}</a>'
    return user_id, mention, name


def _parse_time(text: str) -> Optional[timedelta]:
    """Parse 1m / 2h / 3d / 1w into timedelta. Returns None if permanent."""
    if not text:
        return None
    m = re.match(r"^(\d+)([smhdw])$", text.lower().strip())
    if not m:
        return None
    val, unit = int(m.group(1)), m.group(2)
    if unit == "s":
        return timedelta(seconds=val)
    if unit == "m":
        return timedelta(minutes=val)
    if unit == "h":
        return timedelta(hours=val)
    if unit == "d":
        return timedelta(days=val)
    if unit == "w":
        return timedelta(weeks=val)
    return None


async def _bot_can_restrict(chat_id: int) -> bool:
    try:
        me = await bot.get_chat_member(chat_id, "me")
        return bool(me.privileges and me.privileges.can_restrict_members)
    except Exception:
        return False


async def _bot_can_promote(chat_id: int) -> bool:
    try:
        me = await bot.get_chat_member(chat_id, "me")
        return bool(me.privileges and me.privileges.can_promote_members)
    except Exception:
        return False


async def _bot_can_delete(chat_id: int) -> bool:
    try:
        me = await bot.get_chat_member(chat_id, "me")
        return bool(me.privileges and me.privileges.can_delete_messages)
    except Exception:
        return False


async def _is_admin_or_owner(chat_id: int, user_id: int) -> bool:
    if user_id == config.OWNER_ID or user_id == 777000:
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


# ── /ban ───────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command(["ban", "dban"])
    & filters.group
    & group_allowed
    & user_allowed
)
async def ban_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    if not await _bot_can_restrict(chat_id):
        await rich_send(
            bot, chat_id,
            rich_heading("❌ Missing permission", level=3)
            + rich_note("I need <b>Restrict Members</b> right."),
        )
        return

    user_id, mention, name = await _get_target(message)
    if not user_id:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("<code>/ban</code> (reply) or <code>/ban @user [reason]</code>"),
        )
        return

    if user_id == config.OWNER_ID or user_id == (await bot.get_me()).id:
        await rich_send(bot, chat_id, rich_heading("❌ Can't ban this user", level=3))
        return

    if await _is_admin_or_owner(chat_id, user_id):
        await rich_send(bot, chat_id, rich_heading("❌ Can't ban an admin", level=3))
        return

    reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason"
    try:
        await bot.ban_chat_member(chat_id, user_id)
        await rich_send(
            bot, chat_id,
            rich_heading("🚫 User banned", level=3)
            + rich_kv_table([
                ("User", mention),
                ("By", message.from_user.mention if message.from_user else "?"),
                ("Reason", rich_esc(reason)),
            ]),
        )
        if message.command[0].lower() == "dban" and message.reply_to_message:
            try:
                await message.reply_to_message.delete()
            except Exception:
                pass
    except (ChatAdminRequired, RightForbidden, UserAdminInvalid) as e:
        await rich_send(bot, chat_id, rich_heading("❌ Ban failed", level=3) + rich_note(str(e)))
    except Exception as e:
        LOGGER.warning(f"ban error: {e}")
        await rich_send(bot, chat_id, rich_heading("❌ Ban failed", level=3) + rich_note(rich_esc(str(e))))


# ── /unban ─────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command("unban")
    & filters.group
    & group_allowed
    & user_allowed
)
async def unban_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    user_id, mention, _ = await _get_target(message)
    if not user_id:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("<code>/unban</code> (reply) or <code>/unban @user</code>"),
        )
        return

    try:
        await bot.unban_chat_member(chat_id, user_id)
        await rich_send(
            bot, chat_id,
            rich_heading("✅ User unbanned", level=3)
            + rich_kv_table([("User", mention)]),
        )
    except Exception as e:
        await rich_send(bot, chat_id, rich_heading("❌ Unban failed", level=3) + rich_note(rich_esc(str(e))))


# ── /kick ──────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command(["kick", "dkick"])
    & filters.group
    & group_allowed
    & user_allowed
)
async def kick_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    if not await _bot_can_restrict(chat_id):
        await rich_send(bot, chat_id, rich_heading("❌ Need Restrict Members right", level=3))
        return

    user_id, mention, _ = await _get_target(message)
    if not user_id:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("<code>/kick</code> (reply) or <code>/kick @user</code>"),
        )
        return

    if await _is_admin_or_owner(chat_id, user_id):
        await rich_send(bot, chat_id, rich_heading("❌ Can't kick an admin", level=3))
        return

    try:
        await bot.ban_chat_member(chat_id, user_id)
        await asyncio.sleep(0.5)
        await bot.unban_chat_member(chat_id, user_id)
        await rich_send(
            bot, chat_id,
            rich_heading("👢 User kicked", level=3)
            + rich_kv_table([("User", mention)]),
        )
        if message.command[0].lower() == "dkick" and message.reply_to_message:
            try:
                await message.reply_to_message.delete()
            except Exception:
                pass
    except Exception as e:
        await rich_send(bot, chat_id, rich_heading("❌ Kick failed", level=3) + rich_note(rich_esc(str(e))))


# ── /mute ──────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command(["mute", "tmute"])
    & filters.group
    & group_allowed
    & user_allowed
)
async def mute_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    if not await _bot_can_restrict(chat_id):
        await rich_send(bot, chat_id, rich_heading("❌ Need Restrict Members right", level=3))
        return

    user_id, mention, _ = await _get_target(message)
    if not user_id:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("<code>/mute</code> (reply) or <code>/mute @user [1h|2d|...]</code>"),
        )
        return

    if await _is_admin_or_owner(chat_id, user_id):
        await rich_send(bot, chat_id, rich_heading("❌ Can't mute an admin", level=3))
        return

    # optional duration
    duration = None
    if len(message.command) > 2:
        duration = _parse_time(message.command[2])
    elif len(message.command) > 1 and message.reply_to_message:
        duration = _parse_time(message.command[1])

    until = None
    if duration:
        until = datetime.utcnow() + duration

    try:
        await bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(),
            until_date=until,
        )
        extra = f" for {message.command[-1]}" if duration else " permanently"
        await rich_send(
            bot, chat_id,
            rich_heading(f"🔇 User muted{extra}", level=3)
            + rich_kv_table([("User", mention)]),
        )
    except Exception as e:
        await rich_send(bot, chat_id, rich_heading("❌ Mute failed", level=3) + rich_note(rich_esc(str(e))))


# ── /unmute ────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command("unmute")
    & filters.group
    & group_allowed
    & user_allowed
)
async def unmute_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    user_id, mention, _ = await _get_target(message)
    if not user_id:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("<code>/unmute</code> (reply) or <code>/unmute @user</code>"),
        )
        return

    try:
        await bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_send_polls=True,
            ),
        )
        await rich_send(
            bot, chat_id,
            rich_heading("🔊 User unmuted", level=3)
            + rich_kv_table([("User", mention)]),
        )
    except Exception as e:
        await rich_send(bot, chat_id, rich_heading("❌ Unmute failed", level=3) + rich_note(rich_esc(str(e))))


# ── /promote ───────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command("promote")
    & filters.group
    & group_allowed
    & user_allowed
)
async def promote_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    if not await _bot_can_promote(chat_id):
        await rich_send(bot, chat_id, rich_heading("❌ Need Promote Members right", level=3))
        return

    user_id, mention, _ = await _get_target(message)
    if not user_id:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("<code>/promote</code> (reply) or <code>/promote @user [title]</code>"),
        )
        return

    title = " ".join(message.command[2:]) if len(message.command) > 2 else "Admin"
    if not message.reply_to_message and len(message.command) > 2:
        title = " ".join(message.command[2:])
    elif message.reply_to_message and len(message.command) > 1:
        title = " ".join(message.command[1:])

    try:
        await bot.promote_chat_member(
            chat_id,
            user_id,
            privileges=enums.ChatPrivileges(
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=True,
                can_promote_members=False,
            ),
        )
        try:
            await bot.set_administrator_title(chat_id, user_id, title[:16])
        except Exception:
            pass
        await rich_send(
            bot, chat_id,
            rich_heading("⬆️ User promoted", level=3)
            + rich_kv_table([
                ("User", mention),
                ("Title", rich_esc(title[:16])),
            ]),
        )
    except Exception as e:
        await rich_send(bot, chat_id, rich_heading("❌ Promote failed", level=3) + rich_note(rich_esc(str(e))))


# ── /demote ────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command("demote")
    & filters.group
    & group_allowed
    & user_allowed
)
async def demote_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    if not await _bot_can_promote(chat_id):
        await rich_send(bot, chat_id, rich_heading("❌ Need Promote Members right", level=3))
        return

    user_id, mention, _ = await _get_target(message)
    if not user_id:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("<code>/demote</code> (reply) or <code>/demote @user</code>"),
        )
        return

    try:
        await bot.promote_chat_member(
            chat_id,
            user_id,
            privileges=enums.ChatPrivileges(
                can_manage_chat=False,
                can_delete_messages=False,
                can_manage_video_chats=False,
                can_restrict_members=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_promote_members=False,
            ),
        )
        await rich_send(
            bot, chat_id,
            rich_heading("⬇️ User demoted", level=3)
            + rich_kv_table([("User", mention)]),
        )
    except Exception as e:
        await rich_send(bot, chat_id, rich_heading("❌ Demote failed", level=3) + rich_note(rich_esc(str(e))))


# ── /warn ──────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command(["warn", "dwarn"])
    & filters.group
    & group_allowed
    & user_allowed
)
async def warn_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    user_id, mention, _ = await _get_target(message)
    if not user_id:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("<code>/warn</code> (reply) or <code>/warn @user [reason]</code>"),
        )
        return

    if await _is_admin_or_owner(chat_id, user_id):
        await rich_send(bot, chat_id, rich_heading("❌ Can't warn an admin", level=3))
        return

    reason = " ".join(message.command[2:]) if len(message.command) > 2 else (
        " ".join(message.command[1:]) if message.reply_to_message and len(message.command) > 1 else "No reason"
    )
    count = add_warn(chat_id, user_id, reason)
    limit = get_warn_limit(chat_id)

    await rich_send(
        bot, chat_id,
        rich_heading("⚠️ User warned", level=3)
        + rich_kv_table([
            ("User", mention),
            ("Warns", f"{count}/{limit}"),
            ("Reason", rich_esc(reason)),
        ]),
    )

    if message.command[0].lower() == "dwarn" and message.reply_to_message:
        try:
            await message.reply_to_message.delete()
        except Exception:
            pass

    if count >= limit:
        try:
            if await _bot_can_restrict(chat_id):
                await bot.ban_chat_member(chat_id, user_id)
                await rich_send(
                    bot, chat_id,
                    rich_heading("🚫 Auto-banned (warn limit reached)", level=3)
                    + rich_kv_table([("User", mention), ("Warns", f"{count}/{limit}")]),
                )
                reset_warns(chat_id, user_id)
        except Exception as e:
            LOGGER.warning(f"auto-ban on warn limit failed: {e}")


# ── /warns ─────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command("warns")
    & filters.group
    & group_allowed
    & user_allowed
)
async def warns_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    user_id, mention, _ = await _get_target(message)
    if not user_id and message.from_user:
        user_id = message.from_user.id
        mention = message.from_user.mention

    if not user_id:
        return

    data = get_warns(chat_id, user_id)
    limit = get_warn_limit(chat_id)
    reasons = data["reasons"][-5:]  # last 5
    reasons_txt = "\n".join(f"• {rich_esc(r)}" for r in reasons) if reasons else "None"

    await rich_send(
        bot, chat_id,
        rich_heading("📋 Warns", level=3)
        + rich_kv_table([
            ("User", mention),
            ("Count", f"{data['count']}/{limit}"),
        ])
        + rich_note(f"<b>Recent reasons:</b>\n{reasons_txt}"),
    )


# ── /resetwarns ────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command(["resetwarns", "rmwarns", "unwarn"])
    & filters.group
    & group_allowed
    & user_allowed
)
async def resetwarns_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    user_id, mention, _ = await _get_target(message)
    if not user_id:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("<code>/resetwarns</code> (reply) or <code>/resetwarns @user</code>"),
        )
        return

    reset_warns(chat_id, user_id)
    await rich_send(
        bot, chat_id,
        rich_heading("✅ Warns reset", level=3)
        + rich_kv_table([("User", mention)]),
    )


# ── /setwarnlimit ──────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command("setwarnlimit")
    & filters.group
    & group_allowed
    & user_allowed
)
async def setwarnlimit_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    if len(message.command) < 2 or not message.command[1].isdigit():
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("<code>/setwarnlimit 3</code> (1–20)"),
        )
        return

    limit = int(message.command[1])
    set_warn_limit(chat_id, limit)
    await rich_send(
        bot, chat_id,
        rich_heading("✅ Warn limit updated", level=3)
        + rich_kv_table([("Limit", str(get_warn_limit(chat_id)))]),
    )


# ── /purge ─────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command("purge")
    & filters.group
    & group_allowed
    & user_allowed
)
async def purge_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    if not await _bot_can_delete(chat_id):
        await rich_send(bot, chat_id, rich_heading("❌ Need Delete Messages right", level=3))
        return

    if not message.reply_to_message:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("Reply to a message with <code>/purge</code> to delete from that message to here."),
        )
        return

    start_id = message.reply_to_message.id
    end_id = message.id
    deleted = 0

    try:
        for msg_id in range(start_id, end_id + 1):
            try:
                await bot.delete_messages(chat_id, msg_id)
                deleted += 1
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass
            if deleted % 20 == 0:
                await asyncio.sleep(0.3)
    except Exception as e:
        LOGGER.warning(f"purge error: {e}")

    status = await rich_send(
        bot, chat_id,
        rich_heading("🗑️ Purge complete", level=3)
        + rich_kv_table([("Deleted", str(deleted))]),
    )
    await asyncio.sleep(3)
    try:
        await status.delete()
    except Exception:
        pass


# ── /pin /unpin ────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command("pin")
    & filters.group
    & group_allowed
    & user_allowed
)
async def pin_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return
    if not message.reply_to_message:
        await rich_send(bot, message.chat.id, rich_heading("Reply to a message to pin", level=3))
        return
    try:
        await message.reply_to_message.pin(disable_notification=False)
        await rich_send(bot, message.chat.id, rich_heading("📌 Message pinned", level=3))
    except Exception as e:
        await rich_send(bot, message.chat.id, rich_heading("❌ Pin failed", level=3) + rich_note(rich_esc(str(e))))


@bot.on_message(
    filters.command("unpin")
    & filters.group
    & group_allowed
    & user_allowed
)
async def unpin_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return
    try:
        if message.reply_to_message:
            await message.reply_to_message.unpin()
        else:
            await bot.unpin_chat_message(message.chat.id)
        await rich_send(bot, message.chat.id, rich_heading("📌 Unpinned", level=3))
    except Exception as e:
        await rich_send(bot, message.chat.id, rich_heading("❌ Unpin failed", level=3) + rich_note(rich_esc(str(e))))


# ── Welcome system ─────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command("setwelcome")
    & filters.group
    & group_allowed
    & user_allowed
)
async def setwelcome_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    text = message.text.split(None, 1)[1] if message.text and len(message.text.split(None, 1)) > 1 else ""
    if not text and message.reply_to_message and message.reply_to_message.text:
        text = message.reply_to_message.text

    if not text:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note(
                "Set a welcome message:\n"
                "<code>/setwelcome Hello {mention}! Welcome to {chat}</code>\n\n"
                "Placeholders: <code>{mention}</code> <code>{name}</code> <code>{id}</code> <code>{chat}</code>"
            ),
        )
        return

    set_welcome(chat_id, text, enabled=True)
    await rich_send(
        bot, chat_id,
        rich_heading("✅ Welcome message set", level=3)
        + rich_note(rich_esc(text[:200])),
    )


@bot.on_message(
    filters.command(["welcome", "welcomemode"])
    & filters.group
    & group_allowed
    & user_allowed
)
async def welcome_toggle_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    data = get_welcome(chat_id)
    arg = message.command[1].lower() if len(message.command) > 1 else ""

    if arg in ("on", "yes", "true", "enable"):
        set_welcome_enabled(chat_id, True)
        await rich_send(bot, chat_id, rich_heading("✅ Welcome enabled", level=3))
    elif arg in ("off", "no", "false", "disable"):
        set_welcome_enabled(chat_id, False)
        await rich_send(bot, chat_id, rich_heading("✅ Welcome disabled", level=3))
    else:
        status = "ON" if data["enabled"] else "OFF"
        await rich_send(
            bot, chat_id,
            rich_heading("👋 Welcome status", level=3)
            + rich_kv_table([
                ("Status", status),
                ("Message", rich_esc((data["text"] or "Not set")[:150])),
            ])
            + rich_note("Use <code>/welcome on|off</code> or <code>/setwelcome text</code>"),
        )


@bot.on_message(
    filters.command("setgoodbye")
    & filters.group
    & group_allowed
    & user_allowed
)
async def setgoodbye_cmd(_, message: Message) -> None:
    if not await is_user_authorized(message):
        return

    chat_id = message.chat.id
    text = message.text.split(None, 1)[1] if message.text and len(message.text.split(None, 1)) > 1 else ""
    if not text and message.reply_to_message and message.reply_to_message.text:
        text = message.reply_to_message.text

    if not text:
        await rich_send(
            bot, chat_id,
            rich_heading("Usage", level=3)
            + rich_note("<code>/setgoodbye Goodbye {name}!</code>"),
        )
        return

    set_goodbye(chat_id, text, enabled=True)
    await rich_send(bot, chat_id, rich_heading("✅ Goodbye message set", level=3))


# ── New member / left member handlers ──────────────────────────────────────────

@bot.on_message(filters.new_chat_members & group_allowed)
async def on_new_member(_, message: Message) -> None:
    chat_id = message.chat.id
    data = get_welcome(chat_id)
    if not data["enabled"] or not data["text"]:
        return

    for user in message.new_chat_members:
        if user.is_bot:
            continue
        text = (
            data["text"]
            .replace("{mention}", user.mention)
            .replace("{name}", user.first_name or "User")
            .replace("{id}", str(user.id))
            .replace("{chat}", message.chat.title or "this group")
        )
        try:
            await rich_send(bot, chat_id, text)
        except Exception as e:
            LOGGER.warning(f"welcome send failed: {e}")


@bot.on_message(filters.left_chat_member & group_allowed)
async def on_left_member(_, message: Message) -> None:
    chat_id = message.chat.id
    data = get_goodbye(chat_id)
    if not data["enabled"] or not data["text"]:
        return

    user = message.left_chat_member
    if not user or user.is_bot:
        return

    text = (
        data["text"]
        .replace("{mention}", user.mention)
        .replace("{name}", user.first_name or "User")
        .replace("{id}", str(user.id))
        .replace("{chat}", message.chat.title or "this group")
    )
    try:
        await rich_send(bot, chat_id, text)
    except Exception as e:
        LOGGER.warning(f"goodbye send failed: {e}")


# ── /admins ────────────────────────────────────────────────────────────────────

@bot.on_message(
    filters.command(["admins", "adminlist"])
    & filters.group
    & group_allowed
    & user_allowed
)
async def admins_cmd(_, message: Message) -> None:
    chat_id = message.chat.id
    try:
        members = []
        async for m in bot.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if m.user and not m.user.is_bot:
                title = m.custom_title or m.status.name.title()
                members.append(f"• {m.user.mention} — <i>{rich_esc(title)}</i>")
        if not members:
            await rich_send(bot, chat_id, rich_heading("No admins found", level=3))
            return
        await rich_send(
            bot, chat_id,
            rich_heading("👑 Admins", level=3)
            + rich_note("\n".join(members[:30])),
        )
    except Exception as e:
        await rich_send(bot, chat_id, rich_heading("❌ Failed", level=3) + rich_note(rich_esc(str(e))))
