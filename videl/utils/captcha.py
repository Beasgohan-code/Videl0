"""MongoDB-backed join verification with opaque callbacks and restart recovery."""
from __future__ import annotations
import asyncio
import html
import inspect
import logging
import random
import secrets
from datetime import datetime, timedelta, timezone
from pymongo import ReturnDocument
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatPermissions, InlineKeyboardMarkup
from videl import bot
from videl.utils.db import get_db
from videl.utils.bot_ui import button, visual_call

log = logging.getLogger(__name__)
_WORKER = None


def _collection():
    db = get_db()
    return db["mgmt_captcha"] if db is not None else None


def make_challenge():
    a, b = random.randint(1, 10), random.randint(1, 10)
    correct = a + b
    choices = [correct, correct + random.choice([1, 2, 3]), correct - random.choice([1, 2, 3])]
    random.shuffle(choices)
    return f"What is {a} + {b}?", choices, choices.index(correct)


def permission_values(permissions):
    return {field: getattr(permissions, field) for field in inspect.signature(ChatPermissions).parameters if isinstance(getattr(permissions, field, None), bool)}


async def issue_challenge(chat_id, user_id, name):
    col = _collection()
    if col is None:
        log.warning("Join verification skipped: MongoDB unavailable")
        return False
    key = {"chat_id": chat_id, "user_id": user_id}
    nonce = secrets.token_hex(8)
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return False
        chat = await bot.get_chat(chat_id)
        previous = getattr(member, "permissions", None) or chat.permissions
        if previous is None:
            raise RuntimeError("Default permissions unavailable")
        values = permission_values(previous)
        question, choices, correct_index = make_challenge()
        doc = {**key, "nonce": nonce, "permissions": values, "correct_index": correct_index, "attempts": 0, "status": "preparing", "expires_at": datetime.now(timezone.utc) + timedelta(seconds=120)}
        await asyncio.to_thread(col.update_one, key, {"$set": doc, "$unset": {"lease_until": "", "expiry_action": ""}}, upsert=True)
        await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
        markup = InlineKeyboardMarkup([[button(str(choice), callback_data=f"verify:{user_id}:{nonce}:{index}") for index, choice in enumerate(choices)]])
        message = await visual_call(bot.send_message, chat_id, text=f"<b>Welcome, {html.escape(str(name))}</b>\n{question}\nChoose the answer within 2 minutes to stay in this group.", reply_markup=markup)
        await asyncio.to_thread(col.update_one, {**key, "nonce": nonce}, {"$set": {"status": "pending", "msg_id": message.id}})
        return True
    except Exception as exc:
        log.warning("Join challenge not established (%s)", type(exc).__name__)
        # If sending fails, do not leave someone muted without a usable challenge.
        try:
            doc = await asyncio.to_thread(col.find_one, {**key, "nonce": nonce})
            if doc:
                await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(**doc["permissions"]))
                await asyncio.to_thread(col.delete_one, {**key, "nonce": nonce})
        except Exception:
            log.warning("Challenge rollback deferred to expiry recovery")
        return False


async def answer_challenge(query):
    col = _collection()
    try:
        prefix, uid, nonce, choice = query.data.split(":")
        uid, choice = int(uid), int(choice)
        if prefix != "verify" or not 0 <= choice < 3 or not query.message or query.from_user.id != uid:
            return await query.answer("This verification belongs to another user.", show_alert=True)
    except (ValueError, AttributeError):
        return await query.answer("Invalid verification button.", show_alert=True)
    if col is None:
        return await query.answer("Verification is temporarily unavailable. Ask an admin.", show_alert=True)
    key = {"chat_id": query.message.chat.id, "user_id": uid, "nonce": nonce, "msg_id": query.message.id, "status": "pending"}
    doc = await asyncio.to_thread(col.find_one, key)
    if not doc or doc["expires_at"].replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        return await query.answer("This challenge has expired. Ask an admin to help.", show_alert=True)
    if choice != doc["correct_index"]:
        update = {"$inc": {"attempts": 1}}
        if doc.get("attempts", 0) >= 1:
            update["$set"] = {"expires_at": datetime.now(timezone.utc)}
        await asyncio.to_thread(col.update_one, key, update)
        return await query.answer("Incorrect answer. Only two attempts are allowed.", show_alert=True)
    claimed = await asyncio.to_thread(col.find_one_and_update, key, {"$set": {"status": "verifying"}}, return_document=ReturnDocument.AFTER)
    if not claimed:
        return await query.answer("Verification is already being processed.")
    try:
        await bot.restrict_chat_member(key["chat_id"], uid, ChatPermissions(**claimed["permissions"]))
    except Exception:
        await asyncio.to_thread(col.update_one, {**key, "status": "verifying"}, {"$set": {"status": "pending"}})
        return await query.answer("Permissions could not be restored. Retry or contact an admin.", show_alert=True)
    await asyncio.to_thread(col.delete_one, {**key, "status": "verifying"})
    from videl.utils.onboarding import record as record_onboarding
    record_onboarding(key["chat_id"], "verified")
    await query.answer("Verified. Welcome!")
    try:
        await visual_call(query.message.edit_text, text="<b>Verification complete</b>\nWelcome to the group.", reply_markup=None)
    except Exception:
        pass  # Membership was already restored; never undo it for a UI failure.


async def expire_challenges():
    col = _collection()
    if col is None:
        return
    now = datetime.now(timezone.utc)
    selector = {"expires_at": {"$lte": now}, "status": {"$in": ["pending", "preparing", "verifying", "expiring"]}, "$or": [{"lease_until": {"$exists": False}}, {"lease_until": {"$lte": now}}]}
    docs = await asyncio.to_thread(lambda: list(col.find(selector).limit(100)))
    from videl.utils.db import get_db
    from videl.utils.maintenance import is_paused
    database = get_db()
    for doc in docs:
        key = {"chat_id": doc["chat_id"], "user_id": doc["user_id"], "nonce": doc["nonce"]}
        if is_paused(database, doc.get("chat_id"), "protection"):
            # Defer, rather than repeatedly rescanning, an expiry while incident
            # protections are paused. Verification deadlines resume afterwards.
            await asyncio.to_thread(col.update_one, key,
                {"$set":{"expires_at":now+timedelta(seconds=30)}})
            continue
        action = doc.get("expiry_action", "kick" if doc["status"] == "pending" else "restore")
        claimed = await asyncio.to_thread(col.find_one_and_update, {**key, **selector, "status": doc["status"]}, {"$set": {"status": "expiring", "expiry_action": action, "lease_until": now + timedelta(seconds=30)}}, return_document=ReturnDocument.AFTER)
        if not claimed:
            continue
        try:
            member = await bot.get_chat_member(doc["chat_id"], doc["user_id"])
            if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER, ChatMemberStatus.BANNED, ChatMemberStatus.LEFT):
                if action == "kick":
                    # Temporary ban bounds the damage if the process dies before unban.
                    await bot.ban_chat_member(doc["chat_id"], doc["user_id"], until_date=now + timedelta(seconds=60))
                    await bot.unban_chat_member(doc["chat_id"], doc["user_id"])
                else:
                    await bot.restrict_chat_member(doc["chat_id"], doc["user_id"], ChatPermissions(**claimed["permissions"]))
            await asyncio.to_thread(col.delete_one, key)
            if action == "kick":
                from videl.utils.onboarding import record as record_onboarding
                record_onboarding(doc["chat_id"], "timed_out")
        except Exception as exc:
            log.warning("Challenge expiry deferred (%s)", type(exc).__name__)


def start_captcha_worker():
    global _WORKER
    if _WORKER is not None and not _WORKER.done():
        return _WORKER
    async def run():
        while True:
            try:
                await expire_challenges()
            except Exception as exc:
                log.warning("Challenge recovery unavailable (%s)", type(exc).__name__)
            await asyncio.sleep(15)
    _WORKER = asyncio.create_task(run(), name="join-verification-recovery")
    return _WORKER


async def stop_captcha_worker():
    global _WORKER
    if _WORKER is not None:
        _WORKER.cancel()
        await asyncio.gather(_WORKER, return_exceptions=True)
        _WORKER = None
