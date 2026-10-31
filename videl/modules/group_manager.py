"""Permission-checked group workspace, reports and invite links."""
import asyncio
import html
import hashlib
import json
import config
from pyrogram import filters
from pyrogram.types import CopyTextButton, InlineKeyboardMarkup
from videl import LOGGER, bot
from videl.plugins.base import is_admin, chat_kind, set_settings as set_chat_settings, collection as _collection
from videl.utils.bot_ui import button
from videl.utils.rich_ui import rich_heading, rich_note, rich_kv_table, rich_esc
from videl.utils.premium_emojis import pe
from videl.utils.command_ui import rich_reply, rich_edit

RULES = {"antispam": "Flood protection", "lock_links": "Block links", "lock_forwards": "Block forwards", "lock_media": "Block media", "lock_stickers": "Block stickers", "lock_polls": "Block polls", "captcha_enabled": "Join verification", "welcome_enabled": "Welcome message"}


def panel(chat_id, title):
    try:
        col = _collection("mgmt_chat_settings")
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
    rows.append([button("Command presets", copy_text=CopyTextButton(text="/commandpreset")),
                 button("Refresh", callback_data=f"groupcfg:{chat_id}:refresh:0")])
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
        + rich_note("Command sets: use <code>/commandpreset</code> to preview a group-specific command profile. Add read-only helpers with <code>/reviewer add USER_ID</code>; summaries go to their DM only.")
    )
    return text, InlineKeyboardMarkup(rows)


async def _command_preset_plan(chat_id, preset):
    from videl.utils.command_presets import PRESETS, plan
    from videl.utils.command_catalog import commands
    from videl.utils.db import get_db, list_disabled
    if preset not in PRESETS:
        raise ValueError("Unknown command preset")
    if get_db() is None:
        raise RuntimeError("Command preset database unavailable")
    current = await asyncio.to_thread(list_disabled, chat_id)
    return plan(commands(), current, preset)


def _preset_signature(plan):
    raw = json.dumps(plan.get("result", []), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


@bot.on_message(filters.command("commandpreset", prefixes=config.COMMAND_PREFIX_LIST) & filters.group)
async def command_preset_command(_, message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("🔒 Group admins only", level=3))
    from videl.utils.command_presets import PRESETS
    requested = (message.text or "").split(maxsplit=1)
    preset = requested[1].strip().casefold() if len(requested) > 1 else None
    if preset and preset not in PRESETS:
        return await rich_reply(message, rich_heading("Choose a command profile", level=3)
                                 + rich_note("Available: <code>community</code>, <code>music</code>, <code>moderation</code>."))
    title = message.chat.title or "Group"
    choices = [[button(f"{item['label']} profile", callback_data=f"cmdpreset:{key}")]
               for key, item in PRESETS.items()]
    text = (rich_heading("🧩 Group command presets", level=2)
            + rich_kv_table([("Group", rich_esc(title)), ("Active profile", rich_esc(preset or "Custom / not detected"))])
            + rich_note("Choose a profile to preview exactly which group commands will be enabled or paused. The profile replaces current command switches only after confirmation."))
    if preset:
        try:
            plan = await _command_preset_plan(message.chat.id, preset)
        except Exception:
            return await rich_reply(message, rich_heading("⚠️ Preset preview unavailable", level=3)
                                     + rich_note("The registered command list or database could not be read. Nothing changed."))
        changes = [("Enable", ", ".join(plan["enable"][:12]) or "none"),
                   ("Pause", ", ".join(plan["disable"][:12]) or "none")]
        text += rich_kv_table(changes)
        if len(plan["enable"]) > 12 or len(plan["disable"]) > 12:
            text += rich_note(f"Additional changes: {max(0, len(plan['enable'])-12)} enable and {max(0, len(plan['disable'])-12)} pause.")
        choices = [[button(f"Confirm {PRESETS[preset]['label']}", callback_data=f"cmdpreset_apply:{preset}:{_preset_signature(plan)}", style="success")],
                   [button("Cancel", callback_data="cmdpreset_cancel")]]
    await rich_reply(message, text, reply_markup=InlineKeyboardMarkup(choices))


@bot.on_callback_query(filters.regex(r"^cmdpreset(?:_apply)?:|^cmdpreset_cancel$"))
async def command_preset_callback(_, query):
    message = getattr(query, "message", None)
    actor = getattr(query, "from_user", None)
    if message is None or chat_kind(message) not in {"group", "supergroup"}:
        return await query.answer("Open command presets in the group.", show_alert=True)
    if not actor or not await is_admin(message.chat.id, actor.id):
        return await query.answer("Current group admins only.", show_alert=True)
    data = query.data or ""
    if data == "cmdpreset_cancel":
        await query.answer("Cancelled")
        return await rich_edit(message, rich_heading("Command preset cancelled", level=3))
    parts = data.split(":")
    preset = parts[1] if len(parts) > 1 else ""
    from videl.utils.command_presets import PRESETS
    if preset not in PRESETS:
        return await query.answer("Unknown preset", show_alert=True)
    if data.startswith("cmdpreset:"):
        plan = await _command_preset_plan(message.chat.id, preset)
        rows = [("Enable", ", ".join(plan["enable"][:12]) or "none"),
                ("Pause", ", ".join(plan["disable"][:12]) or "none")]
        text = (rich_heading(f"Review {PRESETS[preset]['label']} profile", level=2)
                + rich_note(rich_esc(PRESETS[preset]["description"]))
                + rich_kv_table(rows)
                + rich_note("Confirm to replace the current command switches. This does not change Telegram rights."))
        markup = InlineKeyboardMarkup([[button("Confirm profile", callback_data=f"cmdpreset_apply:{preset}:{_preset_signature(plan)}", style="success")],
                                       [button("Cancel", callback_data="cmdpreset_cancel")]])
        await query.answer("Preview ready")
        return await rich_edit(message, text, reply_markup=markup)
    token = parts[2] if len(parts) == 3 else ""
    plan = await _command_preset_plan(message.chat.id, preset)
    if token != _preset_signature(plan):
        rows = [("Enable", ", ".join(plan["enable"][:12]) or "none"),
                ("Pause", ", ".join(plan["disable"][:12]) or "none")]
        text = (rich_heading("Command switches changed since preview", level=2)
                + rich_note("Review the updated list and confirm again; nothing has been applied yet.")
                + rich_kv_table(rows))
        markup = InlineKeyboardMarkup([[button("Confirm updated profile", callback_data=f"cmdpreset_apply:{preset}:{_preset_signature(plan)}", style="success")],
                                       [button("Cancel", callback_data="cmdpreset_cancel")]])
        await query.answer("Preview refreshed", show_alert=True)
        return await rich_edit(message, text, reply_markup=markup)
    from videl.utils.db import disable_cmd, enable_cmd, list_disabled
    plan = await _command_preset_plan(message.chat.id, preset)
    for name in plan["disable"]:
        await asyncio.to_thread(disable_cmd, message.chat.id, name)
    for name in plan["enable"]:
        await asyncio.to_thread(enable_cmd, message.chat.id, name)
    actual = set(await asyncio.to_thread(list_disabled, message.chat.id))
    if actual != set(plan["result"]):
        await query.answer("Some changes could not be saved; refresh before retrying.", show_alert=True)
        return await rich_edit(message, rich_heading("⚠️ Profile not fully applied", level=2)
                               + rich_note("The command switch database did not confirm every change. Review /commandpreset before retrying."))
    from videl.utils.audit import record_bot
    await asyncio.to_thread(record_bot, message.chat.id, "commands", action="command_preset",
                            detail=f"profile {preset}; enabled {len(plan['enable'])}; paused {len(plan['disable'])}", actor=actor.id)
    await query.answer("Profile applied")
    await rich_edit(message, rich_heading("✅ Command profile applied", level=2)
                    + rich_note(f"{PRESETS[preset]['label']} profile is now active for this group."))


async def _reviewers_collection():
    from videl.utils.db import get_db
    db = get_db()
    return db["mgmt_readonly_reviewers"] if db is not None else None


@bot.on_message(filters.command("reviewer", prefixes=config.COMMAND_PREFIX_LIST) & filters.group)
async def reviewer_command(_, message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("🔒 Group admins only", level=3))
    collection = await _reviewers_collection()
    if collection is None:
        return await rich_reply(message, rich_heading("⚠️ Reviewer role unavailable", level=3)
                                 + rich_note("The database is unavailable; no role changed."))
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) == 1:
        rows = list(collection.find({"chat_id": message.chat.id}).limit(50))
        listing = ", ".join(str(int(row["user_id"])) for row in rows) or "None"
        return await rich_reply(message, rich_heading("Read-only reviewers", level=3)
                                + rich_note(f"User IDs: <code>{listing}</code>")
                                + rich_note("Use <code>/reviewer add USER_ID</code> or <code>/reviewer remove USER_ID</code>."))
    action = parts[1].casefold()
    if action not in {"add", "remove"} or len(parts) != 3:
        return await rich_reply(message, rich_heading("Reviewer command", level=3)
                                + rich_note("Usage: <code>/reviewer add USER_ID</code> or <code>/reviewer remove USER_ID</code>."))
    token = parts[2].strip()
    try:
        identifier = token if token.startswith("@") else int(token)
        user = await bot.get_users(identifier)
        user_id = int(user.id)
        me = getattr(bot, "me", None) or await bot.get_me()
        if user_id <= 0 or user_id == int(me.id) or bool(getattr(user, "is_bot", False)):
            raise ValueError()
    except Exception:
        return await rich_reply(message, rich_heading("Choose a valid human user", level=3)
                                + rich_note("Pass a numeric Telegram user ID or @username."))
    if action == "add":
        try:
            member = await bot.get_chat_member(message.chat.id, user_id)
            status = str(getattr(member.status, "value", member.status)).casefold()
            if status in {"left", "kicked"}:
                raise ValueError()
        except Exception:
            return await rich_reply(message, rich_heading("Reviewer must be a current group member", level=3)
                                    + rich_note("I could not confirm this user is in the group. No role was added."))
        try:
            collection.update_one({"chat_id": message.chat.id, "user_id": user_id},
                                  {"$set": {"chat_id": message.chat.id, "user_id": user_id,
                                            "granted_by": message.from_user.id}}, upsert=True)
        except Exception:
            return await rich_reply(message, rich_heading("⚠️ Reviewer role not saved", level=3))
        verb = "added"
    else:
        try:
            result = collection.delete_one({"chat_id": message.chat.id, "user_id": user_id})
            if not result.deleted_count:
                return await rich_reply(message, rich_heading("No reviewer role found", level=3))
        except Exception:
            return await rich_reply(message, rich_heading("⚠️ Reviewer role not removed", level=3))
        verb = "removed"
    try:
        from videl.utils.audit import record_bot
        await asyncio.to_thread(record_bot, message.chat.id, "settings",
                                action=f"readonly_reviewer_{action}",
                                detail=f"read-only reviewer {user_id}", actor=message.from_user.id)
    except Exception:
        LOGGER.debug("reviewer role audit could not be recorded", exc_info=True)
    return await rich_reply(message, rich_heading(f"✅ Read-only reviewer {verb}", level=3)
                            + rich_note(f"User ID <code>{user_id}</code> can review the private queue summary with <code>/modqueue</code>, but cannot take moderation actions through this role."))


@bot.on_message(filters.command("adminsummary", prefixes=config.COMMAND_PREFIX_LIST) & filters.group)
async def admin_summary_command(_, message):
    actor = getattr(message, "from_user", None)
    if actor is None or not await is_admin(message.chat.id, actor.id):
        return await rich_reply(message, rich_heading("🔒 Current group admins only", level=3))
    parts = (message.text or "").split(maxsplit=1)
    value = parts[1].strip() if len(parts) > 1 else "status"
    from videl.utils.db import get_db
    from videl.utils.admin_digest import parse_time, subscribe, unsubscribe, COLLECTION
    db = get_db()
    if db is None:
        return await rich_reply(message, rich_heading("⚠️ Summary schedule unavailable", level=3))
    if value.casefold() == "off":
        unsubscribe(db, message.chat.id, actor.id)
        return await rich_reply(message, rich_heading("Daily admin summary paused", level=3))
    if value.casefold() == "status":
        row = db[COLLECTION].find_one({"chat_id": message.chat.id, "user_id": actor.id})
        if not row or not row.get("enabled"):
            return await rich_reply(message, rich_heading("No daily summary scheduled", level=3)
                                    + rich_note("Set one with <code>/adminsummary HH:MM</code> in UTC."))
        return await rich_reply(message, rich_heading("Daily admin summary", level=3)
                                + rich_note(f"Delivery is scheduled for {int(row['hour_utc']):02d}:{int(row['minute_utc']):02d} UTC. Last delivery: {html.escape(str(row.get('last_delivery') or 'not sent yet'))}."))
    parsed = parse_time(value)
    if parsed is None:
        return await rich_reply(message, rich_heading("Choose a UTC time", level=3)
                                + rich_note("Usage: <code>/adminsummary 09:30</code>, <code>/adminsummary status</code> or <code>/adminsummary off</code>."))
    if not subscribe(db, message.chat.id, actor.id, value):
        return await rich_reply(message, rich_heading("⚠️ Summary schedule not saved", level=3))
    try:
        await bot.send_message(actor.id, f"Videl daily admin summary is enabled for {html.escape(message.chat.title or 'your group')} at {value} UTC. Use /adminsummary off in the group to pause it.")
    except Exception:
        unsubscribe(db, message.chat.id, actor.id)
        return await rich_reply(message, rich_heading("📩 Start a private chat with Videl first", level=3)
                                + rich_note("The summary needs a working private chat. No schedule was saved."))
    from videl.utils.audit import record_bot
    await asyncio.to_thread(record_bot, message.chat.id, "settings", action="admin_summary_subscribe",
                            detail=f"admin {actor.id} opted into daily summary at {value} UTC", actor=actor.id)
    return await rich_reply(message, rich_heading("✅ Daily admin summary scheduled", level=3)
                            + rich_note(f"Your private digest will arrive at {value} UTC. Only you are subscribed. Disable with <code>/adminsummary off</code>."))


@bot.on_message(filters.command("modqueue", prefixes=config.COMMAND_PREFIX_LIST) & filters.group)
async def read_only_modqueue(_, message):
    user = getattr(message, "from_user", None)
    if user is None:
        return
    allowed = await is_admin(message.chat.id, user.id)
    if not allowed:
        collection = await _reviewers_collection()
        if collection is None or collection.find_one({"chat_id": message.chat.id, "user_id": user.id}) is None:
            return await rich_reply(message, rich_heading("🔒 Queue access unavailable", level=3)
                                    + rich_note("Only current group admins or an explicitly granted read-only reviewer can open this summary."))
        try:
            member = await bot.get_chat_member(message.chat.id, user.id)
            status = str(getattr(member.status, "value", member.status)).casefold()
            if status in {"left", "kicked"}:
                raise ValueError()
        except Exception:
            return await rich_reply(message, rich_heading("🔒 Current group membership could not be confirmed", level=3))
    try:
        from videl.utils.db import get_db
        db = get_db()
        if db is None:
            raise RuntimeError("database unavailable")
        reports = list(db["mgmt_reports"].find({"chat_id": message.chat.id, "status": "open"}).sort("ts", -1).limit(8))
        requests = list(db["mgmt_join_requests"].find({"chat_id": message.chat.id, "status": "pending"}).sort("ts", -1).limit(8))
        reviews = list(db["mgmt_escalations"].find({"chat_id": message.chat.id, "status": "open"}).sort("created_at", -1).limit(8))
    except Exception:
        return await rich_reply(message, rich_heading("⚠️ Queue summary unavailable", level=3))
    lines = [f"Open reports: {len(reports)}", f"Pending join requests: {len(requests)}", f"Pending action reviews: {len(reviews)}"]
    for row in reports:
        rid = str(row.get("_id", ""))[-8:]
        reason = html.escape(str(row.get("reason") or "No reason supplied").replace("\\n", " ")[:100])
        lines.append(f"Report …{rid}: {reason}")
    for row in requests:
        lines.append(f"Join request: {html.escape(str(row.get('name') or 'Member')[:60])}")
    for row in reviews:
        lines.append(f"Action review: {html.escape(str(row.get('action') or 'action'))} · member {int(row.get('user_id') or 0)}")
    try:
        await bot.send_message(user.id, "Read-only moderator queue summary\\n\\n" + "\\n".join(lines))
    except Exception:
        return await rich_reply(message, rich_heading("📩 Start a private chat with Videl first", level=3)
                                + rich_note("I could not send your queue summary privately. Start the bot in DM, then run /modqueue again here."))
    await rich_reply(message, rich_heading("📩 Queue summary sent privately", level=3)
                      + rich_note("This read-only role has no approve, resolve, warn, mute, ban or kick controls."))


@bot.on_message(filters.command("group", prefixes=config.COMMAND_PREFIX_LIST) & filters.group)
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
        return await query.answer("Invalid group control.", show_alert=True)
    if not await is_admin(query.message.chat.id, query.from_user.id):
        return await query.answer("Current group admins only.", show_alert=True)
    if key != "refresh":
        if key not in RULES:
            return await query.answer("Unknown setting.", show_alert=True)
        updates = {key: value == "1"}
        if key == "lock_forwards":
            updates["lock_forward"] = value == "1"
        if not set_chat_settings(int(chat), updates):
            return await query.answer("Settings could not be saved. Nothing changed.", show_alert=True)
    await query.answer("Saved" if key != "refresh" else "Refreshed")
    text, markup = panel(int(chat), query.message.chat.title or "Group")
    await rich_edit(query.message, text, reply_markup=markup)


@bot.on_message(filters.command("maintenance", prefixes=config.COMMAND_PREFIX_LIST) & filters.group)
async def maintenance_command(_, message):
    if not message.from_user or not await is_admin(message.chat.id, message.from_user.id):
        return await rich_reply(message, rich_heading("🔒 Current group admins only", level=3))
    from videl.utils.db import get_db
    from videl.utils.maintenance import FEATURES, normalize, save
    db = get_db()
    if db is None:
        return await rich_reply(message, rich_heading("⚠️ Maintenance settings unavailable", level=3))
    parts = (message.text or "").split(maxsplit=2)
    operation = parts[1].casefold() if len(parts) > 1 else "status"
    if operation == "status":
        row = db["mgmt_chat_settings"].find_one({"chat_id": message.chat.id}, {"maintenance": 1}) or {}
        current = normalize(row.get("maintenance"))
        state = ", ".join(current["features"]) if current["enabled"] else "off"
        return await rich_reply(message, rich_heading("Group maintenance mode", level=3)
                                + rich_note(f"Paused features: <code>{state}</code>")
                                + rich_note("Use <code>/maintenance on protection,onboarding</code> or <code>/maintenance off</code>."))
    if operation == "off":
        value = save(db, message.chat.id, enabled=False, features=())
    elif operation == "on" and len(parts) == 3:
        requested = {item.strip().casefold() for item in parts[2].split(",") if item.strip()}
        if not requested or requested - set(FEATURES):
            return await rich_reply(message, rich_heading("Choose maintenance areas", level=3)
                                    + rich_note("Available: <code>protection</code>, <code>onboarding</code>."))
        value = save(db, message.chat.id, enabled=True, features=requested)
    else:
        return await rich_reply(message, rich_heading("Maintenance mode", level=3)
                                + rich_note("Usage: <code>/maintenance on protection,onboarding</code>, <code>/maintenance off</code>, or <code>/maintenance status</code>."))
    if value is None:
        return await rich_reply(message, rich_heading("⚠️ Maintenance settings were not saved", level=3))
    try:
        from videl.utils.audit import record_bot
        detail = "maintenance " + (", ".join(value["features"]) if value["enabled"] else "off")
        await asyncio.to_thread(record_bot, message.chat.id, "settings", action="maintenance_mode",
                                detail=detail, actor=message.from_user.id)
    except Exception:
        LOGGER.debug("maintenance audit could not be recorded", exc_info=True)
    status = ", ".join(value["features"]) if value["enabled"] else "off"
    return await rich_reply(message, rich_heading("✅ Maintenance mode updated", level=3)
                            + rich_note(f"Paused features: <code>{status}</code>. Use <code>/maintenance off</code> to resume."))


@bot.on_message(filters.command("permissions", prefixes=config.COMMAND_PREFIX_LIST) & filters.group)
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
    """Queue Telegram's screening query and record the request for human review.

    This bot has no AI provider, so it never claims to make an AI decision.
    Telegram requires screening-query updates to be answered within 10 seconds;
    QUEUE preserves the request for the existing owner-panel review flow.
    """
    query_id = getattr(request, "query_id", None)
    if query_id:
        try:
            from pyrogram.enums import ChatJoinRequestQueryResult
            await bot.answer_chat_join_request_query(
                chat_join_request_query_id=str(query_id),
                result=ChatJoinRequestQueryResult.QUEUE,
            )
        except Exception:
            LOGGER.warning("Join-request screening query could not be queued", exc_info=True)
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
