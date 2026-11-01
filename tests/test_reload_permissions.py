import asyncio
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock

from videl.app.router import parse
from videl.plugins import group
from videl.utils import chat_admins

CHAT = -1001234001
ACTOR = 501
BOT = 900
REMOVED = 502
PROMOTED = 503


def telegram_member(user_id, status="administrator", **rights):
    return {"user": {"id": user_id, "is_bot": user_id == BOT, "first_name": f"User {user_id}"},
            "status": status, **rights}


class ReloadPermissionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["served_chats"].insert_one({"_id": CHAT})
        self.actor = SimpleNamespace(id=ACTOR)
        self.client = SimpleNamespace()
        self.ctx = SimpleNamespace(
            client=self.client,
            message=SimpleNamespace(chat=SimpleNamespace(id=CHAT, type="supergroup"), id=10),
            user=self.actor,
        )
        group._RELOAD_LOCKS.pop(CHAT, None)
        self.db_patch = patch.object(group.base, "db", return_value=self.db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def response(self, *, actor_status="administrator", bot_status="administrator",
                 send_messages=True, admins=None):
        roster = admins if admins is not None else [
            telegram_member(ACTOR, "administrator", can_delete_messages=True),
            telegram_member(BOT, "administrator", can_delete_messages=True, can_send_messages=True),
        ]
        async def call(method, payload):
            if method == "getChatMember" and payload["user_id"] == ACTOR:
                return {"user": {"id": ACTOR}, "status": actor_status}
            if method == "getChatMember" and payload["user_id"] == BOT:
                return {"user": {"id": BOT, "is_bot": True}, "status": bot_status,
                        "can_delete_messages": bot_status == "administrator",
                        "can_restrict_members": False,
                        "can_send_messages": send_messages}
            if method == "getMe":
                return {"id": BOT, "is_bot": True, "username": "Videlapp"}
            if method == "getChat":
                return {"id": CHAT, "type": "supergroup", "permissions": {"can_send_messages": send_messages}}
            if method == "getChatAdministrators":
                return roster
            raise AssertionError((method, payload))
        return call

    async def test_reload_fetches_fresh_admin_roster_bot_identity_and_rights_atomically(self):
        api = self.response(admins=[
            telegram_member(ACTOR, "administrator", can_delete_messages=True),
            telegram_member(REMOVED, "administrator", can_invite_users=True),
            telegram_member(BOT, "administrator", can_delete_messages=True, can_send_messages=True),
        ])
        with patch("videl.plugins.group._telegram_bot_api", side_effect=api) as telegram:
            result = await group.reload_group_permissions(self.ctx)
        methods = [call.args[0] for call in telegram.await_args_list]
        self.assertEqual(methods, ["getChatMember", "getMe", "getChatMember", "getChat", "getChatAdministrators"])
        self.assertIn("Group permission refresh complete", group.base.plain(result.html))
        self.assertIn("Atomic group snapshot synchronized", result.html)
        snapshot = self.db["chat_admins"].find_one({"_id": f"group:{CHAT}"})
        self.assertEqual({row["user"] for row in snapshot["admins"]}, {ACTOR, REMOVED, BOT})
        self.assertEqual(snapshot["bot"]["status"], "administrator")
        self.assertTrue(snapshot["bot"]["rights"]["can_delete_messages"])
        self.assertTrue(snapshot["chat_permissions"]["can_send_messages"])
        displayed = chat_admins.bot_statuses(self.db, [CHAT])[CHAT]
        self.assertTrue(displayed["admin"])
        self.assertTrue(displayed["rights"]["can_delete_messages"])
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": CHAT}))
        self.assertFalse(any(method in {"promoteChatMember", "setChatPermissions"} for method in methods))

    async def test_removed_and_newly_promoted_admins_are_reflected_after_refresh(self):
        first = self.response(admins=[telegram_member(ACTOR), telegram_member(REMOVED)])
        second = self.response(admins=[telegram_member(ACTOR), telegram_member(PROMOTED)])
        with patch("videl.plugins.group._telegram_bot_api", side_effect=first):
            await group.reload_group_permissions(self.ctx)
        with patch("videl.plugins.group._telegram_bot_api", side_effect=second):
            await group.reload_group_permissions(self.ctx)
        never = lambda *_args: (_ for _ in ()).throw(AssertionError("fresh cache expected"))
        self.assertFalse(chat_admins.check(self.db, never, CHAT, REMOVED)["admin"])
        self.assertTrue(chat_admins.check(self.db, never, CHAT, PROMOTED)["admin"])

    async def test_bot_permission_change_is_reflected_and_missing_right_is_named(self):
        api = self.response(bot_status="member", send_messages=False,
                            admins=[telegram_member(ACTOR)])
        with patch("videl.plugins.group._telegram_bot_api", side_effect=api):
            result = await group.reload_group_permissions(self.ctx)
        self.assertIn("Bot admin status", result.html)
        self.assertIn("Administrator status", result.html)
        self.assertIn("Send Messages", result.html)
        snapshot = self.db["chat_admins"].find_one({"_id": f"group:{CHAT}"})
        self.assertEqual(snapshot["bot"]["status"], "member")
        self.assertFalse(snapshot["bot"]["rights"]["can_send_messages"])

    async def test_unauthorized_caller_is_checked_fresh_and_cannot_change_cache(self):
        chat_admins._store(self.db, CHAT, ACTOR, "administrator", {"can_delete_messages": True})
        api = self.response(actor_status="member")
        with patch("videl.plugins.group._telegram_bot_api", side_effect=api) as telegram:
            with self.assertRaisesRegex(ValueError, "Only a current group administrator"):
                await group.reload_group_permissions(self.ctx)
        self.assertEqual([call.args[0] for call in telegram.await_args_list], ["getChatMember"])
        self.assertIsNone(self.db["chat_admins"].find_one({"_id": f"group:{CHAT}"}))

    async def test_telegram_failure_keeps_previous_snapshot_unchanged(self):
        previous = chat_admins.replace_group_snapshot(
            self.db, CHAT, [telegram_member(ACTOR), telegram_member(REMOVED)],
            telegram_member(BOT, can_delete_messages=True),
        )
        before = self.db["chat_admins"].find_one({"_id": f"group:{CHAT}"})
        async def fail(method, payload):
            if method == "getChatMember" and payload["user_id"] == ACTOR:
                return {"status": "administrator"}
            if method == "getMe":
                return {"id": BOT}
            if method == "getChatMember":
                return {"status": "administrator"}
            if method == "getChat":
                return {"permissions": {"can_send_messages": True}}
            if method == "getChatAdministrators":
                raise RuntimeError("Telegram unavailable")
            raise AssertionError(method)
        with patch("videl.plugins.group._telegram_bot_api", side_effect=fail):
            with self.assertRaisesRegex(ValueError, "previous permission cache was retained"):
                await group.reload_group_permissions(self.ctx)
        after = self.db["chat_admins"].find_one({"_id": f"group:{CHAT}"})
        self.assertEqual(after, before)
        self.assertEqual(previous["admins"], before["admins"])

    async def test_simultaneous_refresh_for_same_group_is_rejected(self):
        entered, release = asyncio.Event(), asyncio.Event()
        normal = self.response()
        async def delayed(method, payload):
            if method == "getChatMember" and payload["user_id"] == ACTOR:
                entered.set()
                await release.wait()
            return await normal(method, payload)
        with patch("videl.plugins.group._telegram_bot_api", side_effect=delayed):
            first = asyncio.create_task(group.reload_group_permissions(self.ctx))
            await entered.wait()
            with self.assertRaisesRegex(ValueError, "already running"):
                await group.reload_group_permissions(self.ctx)
            release.set()
            await first

    async def test_tagall_rechecks_fresh_bot_status_after_reload(self):
        with patch("videl.plugins.group._telegram_bot_api", side_effect=self.response()):
            await group.reload_group_permissions(self.ctx)
        client = SimpleNamespace(send_message=AsyncMock())
        tag_ctx = SimpleNamespace(client=client, message=self.ctx.message,
                                  command=SimpleNamespace(arguments=""))
        async def demoted(method, payload):
            if method == "getMe":
                return {"id": BOT}
            if method == "getChatMember":
                return {"status": "member"}
            raise AssertionError("tagall must stop before reading/sending")
        with patch("videl.plugins.group._telegram_bot_api", side_effect=demoted):
            with self.assertRaisesRegex(ValueError, "missing permission: Administrator"):
                await group.tagall(tag_ctx)
        client.send_message.assert_not_awaited()

    async def test_reload_respects_a_lease_owned_by_another_instance(self):
        self.assertTrue(chat_admins.acquire_refresh_lock(self.db, CHAT, "other-instance"))
        api = self.response()
        with patch("videl.plugins.group._telegram_bot_api", side_effect=api) as telegram:
            with self.assertRaisesRegex(ValueError, "Another Videl instance"):
                await group.reload_group_permissions(self.ctx)
        self.assertEqual([call.args[0] for call in telegram.await_args_list], ["getChatMember"])
        self.assertTrue(chat_admins.release_refresh_lock(self.db, CHAT, "other-instance"))

    async def test_shared_refresh_lease_rejects_a_second_process_and_expires(self):
        self.assertTrue(chat_admins.acquire_refresh_lock(self.db, CHAT, "instance-a"))
        self.assertFalse(chat_admins.acquire_refresh_lock(self.db, CHAT, "instance-b"))
        self.assertFalse(chat_admins.release_refresh_lock(self.db, CHAT, "instance-b"))
        now = chat_admins._now()
        with patch("videl.utils.chat_admins._now", return_value=now + timedelta(seconds=121)):
            self.assertTrue(chat_admins.acquire_refresh_lock(self.db, CHAT, "instance-b"))
        self.assertFalse(chat_admins.release_refresh_lock(self.db, CHAT, "instance-a"))
        self.assertTrue(chat_admins.release_refresh_lock(self.db, CHAT, "instance-b"))

    async def test_reload_command_is_registered_for_groups_and_not_a_restart(self):
        command = next(entry for entry in group.COMMANDS if entry.name == "reload")
        self.assertEqual(command.policy, "group")
        self.assertIn("does not restart Videl", command.summary)
        self.assertEqual(parse("/reload@Videlapp", "videlapp").name, "reload")

    async def test_configured_owner_can_recover_without_current_group_admin_status(self):
        api = self.response(actor_status="member")
        with patch.object(group.config, "OWNER_ID", ACTOR), \
             patch("videl.plugins.group._telegram_bot_api", side_effect=api):
            result = await group.reload_group_permissions(self.ctx)
        self.assertIn("Configured Videl owner/admin", result.html)
        self.assertIsNotNone(self.db["chat_admins"].find_one({"_id": f"group:{CHAT}"}))


if __name__ == "__main__":
    unittest.main()
