import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock
from videl.plugins import settings
from videl.utils.interactive_settings import engine


class ConnectedApprovedMemberTests(unittest.IsolatedAsyncioTestCase):
    CHAT, OTHER, USER, BOT = -100811, -100812, 811, 999

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        for chat in (self.CHAT, self.OTHER):
            self.db["mgmt_chat_settings"].insert_one({"chat_id": chat, "revision": 0})
        self.db["approved"].insert_one({"chat": self.CHAT, "user": 101})
        self.db["approved"].insert_one({"chat": self.OTHER, "user": 202})
        self.serial = 50
        async def send(*args, **kwargs):
            self.serial += 1
            return SimpleNamespace(id=self.serial)
        self.client = SimpleNamespace(me=SimpleNamespace(id=self.BOT), send_message=AsyncMock(side_effect=send),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")))

    async def asyncTearDown(self):
        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        await engine.cancel_owner(chat_id=self.USER + 1, actor_id=self.USER + 1, target_chat_id=self.CHAT)

    def _query(self, action, user_id=None, chat_id=None):
        chat = self.CHAT if chat_id is None else chat_id
        tail = f"approved:{action}" + (f":{user_id}" if user_id is not None else "")
        return SimpleNamespace(data=f"settings:{chat}:{tail}:v0",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=12),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())

    async def _start(self, action, user_id=None):
        query = self._query(action, user_id)
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.settings_callback(self.client, query)
        return await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    async def _reply(self, session, text):
        message = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
            text=text, reply_to_message=SimpleNamespace(id=session.expected_message_id))
        with patch("videl.utils.db._db", self.db):
            await settings.connected_approved_action_reply(self.client, message)
        return await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    def _callback(self, action, session, user_id=None):
        actor = self.USER if user_id is None else user_id
        return SimpleNamespace(data=f"approved_action_{action}:{session.token}",
            message=SimpleNamespace(chat=SimpleNamespace(id=actor, type="private"), id=session.expected_message_id),
            from_user=SimpleNamespace(id=actor), answer=AsyncMock())

    async def _confirm(self, session, resolver=None, db=None):
        query = self._callback("save", session)
        with patch("videl.utils.db._db", db or self.db), patch("videl.app.connections.connected_target",
            new=resolver or AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.connected_approved_action_callback(self.client, query)
        return query

    async def test_list_uses_target_collection_and_keeps_remove_callbacks_group_scoped(self):
        query = self._query("list")
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(
                 SimpleNamespace(id=self.CHAT), None))), \
             patch("videl.plugins.settings.rich_edit", new=AsyncMock()) as edit:
            await settings.settings_callback(self.client, query)
        body_text = edit.await_args.args[1]
        self.assertIn("101", body_text)
        self.assertNotIn("202", body_text)
        callbacks = [button.callback_data for row in edit.await_args.kwargs["reply_markup"].inline_keyboard
                     for button in row if button.callback_data]
        self.assertIn(f"settings:{self.CHAT}:approved:remove:101:v0", callbacks)
        self.assertIn(f"settings:{self.CHAT}:approved:add:v0", callbacks)

    async def test_add_is_previewed_and_writes_only_target_group_after_fresh_auth(self):
        session = await self._start("add")
        self.assertIsNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 303}))
        session = await self._reply(session, "303")
        preview = self.client.send_message.await_args_list[-1].args[1]
        self.assertIn(f"Group: <code>{self.CHAT}</code>", preview)
        self.assertIn("User ID: <code>303</code>", preview)
        self.assertIn("No change has been made yet", preview)
        self.assertIsNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 303}))
        resolver = AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))
        query = await self._confirm(session, resolver)
        resolver.assert_awaited_once_with(self.client, self.USER, expected_chat_id=self.CHAT)
        self.assertIsNotNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 303}))
        self.assertIsNone(self.db["approved"].find_one({"chat": self.OTHER, "user": 303}))
        self.assertEqual(query.answer.call_args.args[0], "Approved-member change saved.")

    async def test_remove_preview_cancel_and_confirmation_are_group_scoped(self):
        session = await self._start("remove", 101)
        session = await self._reply(session, "PREVIEW")
        self.assertIsNotNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 101}))
        cancel = self._callback("cancel", session)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_approved_action_callback(self.client, cancel)
        self.assertIsNotNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 101}))

        session = await self._start("remove", 101)
        session = await self._reply(session, "PREVIEW")
        query = await self._confirm(session)
        self.assertIsNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 101}))
        self.assertIsNotNone(self.db["approved"].find_one({"chat": self.OTHER, "user": 202}))
        self.assertEqual(query.answer.call_args.args[0], "Approved-member change saved.")

    async def test_invalid_input_forgery_timeout_and_replay_do_not_mutate(self):
        session = await self._start("add")
        session = await self._reply(session, "not-a-user-id")
        # Invalid reply leaves the numeric prompt active; cancellation is explicit.
        self.assertIsNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 303}))
        forged = self._callback("save", session, user_id=self.USER + 1)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_approved_action_callback(self.client, forged)
        self.assertIsNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 303}))

        session = await self._start("add"); session = await self._reply(session, "303")
        clock = engine._clock
        try:
            engine._clock = lambda: 10**12
            expired = self._callback("save", session)
            with patch("videl.utils.db._db", self.db):
                await settings.connected_approved_action_callback(self.client, expired)
        finally:
            engine._clock = clock
        self.assertIsNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 303}))

    async def test_connection_revocation_stale_membership_and_db_failure_are_safe(self):
        session = await self._start("add"); session = await self._reply(session, "404")
        denied = await self._confirm(session, AsyncMock(return_value=(None, "connection revoked")))
        self.assertIn("connection", denied.answer.call_args.args[0].lower())
        self.assertIsNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 404}))

        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        session = await self._start("add"); session = await self._reply(session, "404")
        self.db["approved"].insert_one({"chat": self.CHAT, "user": 404})
        stale = await self._confirm(session)
        self.assertIn("changed", stale.answer.call_args.args[0].lower())
        self.assertIsNotNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 404}))

        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        session = await self._start("add"); session = await self._reply(session, "505")
        broken = mongomock.MongoClient().videl
        with patch("videl.utils.db.get_db", return_value=None), patch("videl.app.connections.connected_target",
            new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            failure = self._callback("save", session)
            await settings.connected_approved_action_callback(self.client, failure)
        self.assertIn("storage failed", failure.answer.call_args.args[0].lower())
        self.assertIsNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 505}))

        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        session = await self._start("remove", 101); session = await self._reply(session, "PREVIEW")
        with patch("videl.utils.db.get_db", return_value=None), patch("videl.app.connections.connected_target",
            new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            failure = self._callback("save", session)
            await settings.connected_approved_action_callback(self.client, failure)
        self.assertIn("storage failed", failure.answer.call_args.args[0].lower())
        self.assertIsNotNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 101}))

    async def test_concurrent_duplicate_confirmation_is_single_flight(self):
        session = await self._start("add"); session = await self._reply(session, "606")
        first, second = self._callback("save", session), self._callback("save", session)
        async def slow_resolver(*args, **kwargs):
            await asyncio.sleep(0.02)
            return SimpleNamespace(id=self.CHAT), None
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target", new=slow_resolver):
            await asyncio.gather(settings.connected_approved_action_callback(self.client, first),
                                 settings.connected_approved_action_callback(self.client, second))
        self.assertEqual(self.db["approved"].count_documents({"chat": self.CHAT, "user": 606}), 1)

        self.db["approved"].insert_one({"chat": self.CHAT, "user": 707})
        session = await self._start("remove", 707); session = await self._reply(session, "PREVIEW")
        first, second = self._callback("save", session), self._callback("save", session)
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target", new=slow_resolver):
            await asyncio.gather(settings.connected_approved_action_callback(self.client, first),
                                 settings.connected_approved_action_callback(self.client, second))
        self.assertIsNone(self.db["approved"].find_one({"chat": self.CHAT, "user": 707}))
        self.assertEqual(sum(q.answer.call_args.args[0] == "Approved-member change saved." for q in (first, second)), 1)


if __name__ == "__main__":
    unittest.main()
