import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock
from pyrogram.enums import ChatType

from videl.plugins import notes, settings
from videl.utils.interactive_settings import InteractionEngine


class ConnectedFilterEditorTests(unittest.IsolatedAsyncioTestCase):
    CHAT, USER = -100991, 991

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["mgmt_chat_settings"].insert_one({"chat_id": self.CHAT, "revision": 0})
        self.engine = InteractionEngine()
        self.patches = [patch("videl.utils.db._db", self.db),
                        patch.object(notes, "engine", self.engine),
                        patch.object(settings, "engine", self.engine),
                        patch("videl.plugins.notes.rich_edit", new=AsyncMock()),
                        patch("videl.plugins.settings.rich_edit", new=AsyncMock())]
        for item in self.patches: item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(self.patches)])
        self.serial = 100
        async def send(*args, **kwargs):
            self.serial += 1
            return SimpleNamespace(id=self.serial)
        self.client = SimpleNamespace(send_message=AsyncMock(side_effect=send),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")))
        self.group = SimpleNamespace(id=self.CHAT, type=ChatType.SUPERGROUP, title="Connected filters")
        self.user = SimpleNamespace(id=self.USER)
        self.resolver = AsyncMock(return_value=(self.group, None))

    async def asyncTearDown(self):
        await self.engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    async def start(self):
        query = SimpleNamespace(data=f"settings:{self.CHAT}:filters:add:v0",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type=ChatType.PRIVATE), id=10),
            from_user=self.user, answer=AsyncMock())
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await settings.settings_callback(self.client, query)
        session = await self.engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        self.assertIsNotNone(session)
        self.assertEqual(session.chat_id, self.USER)
        self.assertEqual(session.target_chat_id, self.CHAT)
        return session, query

    async def submit(self, session, text):
        message = SimpleNamespace(chat=SimpleNamespace(id=self.USER, type=ChatType.PRIVATE),
            from_user=self.user, text=text,
            reply_to_message=SimpleNamespace(id=session.expected_message_id))
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.filter_editor_message(self.client, message)
        return await self.engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    def callback(self, session, action, *, actor_id=None):
        actor_id = self.USER if actor_id is None else actor_id
        return SimpleNamespace(data=f"filter_edit:{session.token}:{action}",
            message=SimpleNamespace(chat=SimpleNamespace(id=actor_id, type=ChatType.PRIVATE),
                                    id=session.expected_message_id),
            from_user=SimpleNamespace(id=actor_id), answer=AsyncMock())

    async def confirm(self, session, resolver=None):
        query = self.callback(session, "save")
        with patch("videl.app.connections.connected_target", new=resolver or self.resolver):
            await notes.filter_editor_callback(self.client, query)
        return query

    async def preview(self, session, keyword="welcome", response="Hello there"):
        session = await self.submit(session, keyword)
        session = await self.submit(session, response)
        return await self.engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    async def test_connected_settings_adds_filter_with_private_preview_and_target_write(self):
        screen = settings._screen(self.CHAT, "automations", connected_dm=True)
        callbacks = [b.callback_data for row in screen.keyboard.inline_keyboard for b in row if b.callback_data]
        self.assertIn(f"settings:{self.CHAT}:filters:add:v0", callbacks)
        self.assertTrue(any("filters:manage" in value for value in callbacks))
        session, _ = await self.start()
        self.assertEqual(self.client.send_message.await_args.args[0], self.USER)
        session = await self.preview(session)
        preview_text = self.client.send_message.await_args.args[1]
        self.assertIn("hello there", preview_text.lower())
        self.assertNotIn("chat_id", self.db["mgmt_filters"].find_one({"chat_id": self.CHAT}) or {})
        query = await self.confirm(session)
        row = self.db["mgmt_filters"].find_one({"chat_id": self.CHAT, "keyword": "welcome"})
        self.assertIsNotNone(row)
        self.assertEqual(row["reply"], "Hello there")
        self.assertIsNone(self.db["mgmt_filters"].find_one({"chat_id": self.USER}))
        self.assertEqual(query.answer.call_args.args[0], "Filter saved.")

    async def test_cancel_invalid_input_connection_revocation_and_forged_actor_do_not_save(self):
        session, _ = await self.start()
        session = await self.submit(session, "bad\\nkeyword")
        self.assertEqual(self.db["mgmt_filters"].count_documents({"chat_id": self.CHAT}), 0)
        forged = self.callback(session, "save", actor_id=self.USER + 1)
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.filter_editor_callback(self.client, forged)
        self.assertEqual(self.db["mgmt_filters"].count_documents({"chat_id": self.CHAT}), 0)

        session, _ = await self.start(); session = await self.preview(session)
        revoked = AsyncMock(return_value=(None, "connection revoked"))
        failed = await self.confirm(session, revoked)
        self.assertIn("connection or current group-admin access changed", failed.answer.call_args.args[0].lower())
        self.assertEqual(self.db["mgmt_filters"].count_documents({"chat_id": self.CHAT}), 0)

        session, _ = await self.start()
        cancel = SimpleNamespace(chat=SimpleNamespace(id=self.USER, type=ChatType.PRIVATE),
            from_user=self.user, text="/cancel", reply_to_message=None)
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.filter_editor_message(self.client, cancel)
        self.assertIsNone(await self.engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT))

    async def test_timeout_and_storage_failure_never_claim_success(self):
        session, _ = await self.start(); session = await self.preview(session)
        clock = self.engine._clock
        try:
            self.engine._clock = lambda: 10**12
            expired = self.callback(session, "save")
            with patch("videl.app.connections.connected_target", new=self.resolver):
                await notes.filter_editor_callback(self.client, expired)
        finally:
            self.engine._clock = clock
        self.assertIn("expired", expired.answer.call_args.args[0].lower())
        self.assertEqual(self.db["mgmt_filters"].count_documents({"chat_id": self.CHAT}), 0)

        session, _ = await self.start(); session = await self.preview(session)
        failure = self.callback(session, "save")
        with patch("videl.plugins.notes.base.db", return_value=None), patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.filter_editor_callback(self.client, failure)
        self.assertIn("could not save", failure.answer.call_args.args[0].lower())
        self.assertEqual(self.db["mgmt_filters"].count_documents({"chat_id": self.CHAT}), 0)


if __name__ == "__main__":
    unittest.main()
