import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock
from videl.plugins import settings
from videl.utils.interactive_settings import engine


class ConnectedBlocklistEditorTests(unittest.IsolatedAsyncioTestCase):
    CHAT, USER = -100771, 771

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["mgmt_chat_settings"].insert_one({"chat_id": self.CHAT, "revision": 0,
                                                   "music_track_blocklist": []})
        self.client = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(id=101)),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")))

    async def asyncTearDown(self):
        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    async def _start_add(self):
        query = SimpleNamespace(data=f"settings:{self.CHAT}:blocklist:add:track:v0",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=12),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.settings_callback(self.client, query)
        session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        return query, session

    async def test_add_is_staged_then_confirmed_with_connection_recheck(self):
        _, session = await self._start_add()
        reply = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
            text="Song Name", reply_to_message=SimpleNamespace(id=101))
        with patch("videl.utils.db._db", self.db):
            await settings.connected_blocklist_reply(self.client, reply)
        session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        preview_id = session.expected_message_id
        query = SimpleNamespace(data=f"blocklist_save:{session.token}",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=preview_id),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
        resolver = AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target", resolver):
            await settings.connected_blocklist_callback(self.client, query)
        resolver.assert_awaited_once_with(self.client, self.USER, expected_chat_id=self.CHAT)
        row = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["music_track_blocklist"], [{"kind": "track", "value": "Song Name"}])
        self.assertEqual(row["revision"], 1)

    async def test_remove_uses_private_prompt_and_existing_group_storage(self):
        self.db["mgmt_chat_settings"].update_one({"chat_id": self.CHAT}, {"$set": {
            "music_track_blocklist": [{"kind": "artist", "value": "Artist"}]}})
        query = SimpleNamespace(data=f"settings:{self.CHAT}:blocklist:remove:1:v0",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=12),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.settings_callback(self.client, query)
        session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        self.assertEqual(session.chat_id, self.USER)
        self.assertEqual(session.target_chat_id, self.CHAT)
        reply = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
            text="1", reply_to_message=SimpleNamespace(id=101))
        with patch("videl.utils.db._db", self.db):
            await settings.connected_blocklist_reply(self.client, reply)
        session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        confirm = SimpleNamespace(data=f"blocklist_save:{session.token}",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=session.expected_message_id),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.connected_blocklist_callback(self.client, confirm)
        row = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["music_track_blocklist"], [])
        self.assertEqual(row["revision"], 1)

    async def test_cancel_leaves_storage_unchanged(self):
        _, session = await self._start_add()
        reply = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
            text="Song", reply_to_message=SimpleNamespace(id=101))
        with patch("videl.utils.db._db", self.db):
            await settings.connected_blocklist_reply(self.client, reply)
        session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        query = SimpleNamespace(data=f"blocklist_cancel:{session.token}",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=session.expected_message_id),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
        with patch("videl.utils.db._db", self.db):
            await settings.connected_blocklist_callback(self.client, query)
        row = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["revision"], 0)
        self.assertEqual(row["music_track_blocklist"], [])

    async def test_connection_change_blocks_confirmation(self):
        _, _ = await self._start_add()
        reply = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
            text="Song", reply_to_message=SimpleNamespace(id=101))
        with patch("videl.utils.db._db", self.db):
            await settings.connected_blocklist_reply(self.client, reply)
        session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        query = SimpleNamespace(data=f"blocklist_save:{session.token}",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=session.expected_message_id),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(None, "connection changed"))):
            await settings.connected_blocklist_callback(self.client, query)
        row = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["revision"], 0)
        self.assertEqual(row["music_track_blocklist"], [])

    async def test_revision_conflict_and_database_failure_do_not_claim_success(self):
        _, _ = await self._start_add()
        reply = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
            text="Song", reply_to_message=SimpleNamespace(id=101))
        with patch("videl.utils.db._db", self.db):
            await settings.connected_blocklist_reply(self.client, reply)
        session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        self.db["mgmt_chat_settings"].update_one({"chat_id": self.CHAT}, {"$set": {"revision": 1}})
        query = SimpleNamespace(data=f"blocklist_save:{session.token}",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=session.expected_message_id),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.connected_blocklist_callback(self.client, query)
        row = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["music_track_blocklist"], [])
        self.assertIn("save", query.answer.call_args.args[0].lower())


    async def _preview_query(self, text="Song"):
        _, _ = await self._start_add()
        reply = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
            text=text, reply_to_message=SimpleNamespace(id=101))
        with patch("videl.utils.db._db", self.db):
            await settings.connected_blocklist_reply(self.client, reply)
        session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        return SimpleNamespace(data=f"blocklist_save:{session.token}",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=session.expected_message_id),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())

    async def test_invalid_input_and_expired_session_do_not_write(self):
        _, session = await self._start_add()
        reply = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
            text="x" * 101, reply_to_message=SimpleNamespace(id=101))
        with patch("videl.utils.db._db", self.db):
            await settings.connected_blocklist_reply(self.client, reply)
        self.assertEqual((await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)).phase, "input")
        clock = engine._clock
        try:
            engine._clock = lambda: 10**12
            query = SimpleNamespace(data=f"blocklist_save:{session.token}",
                message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=101),
                from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
            await settings.connected_blocklist_callback(self.client, query)
            self.assertIn("expired", query.answer.call_args.args[0].lower())
        finally:
            engine._clock = clock
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)

    async def test_permission_loss_and_database_failure_are_reported(self):
        query = await self._preview_query()
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(None, "admin role changed"))):
            await settings.connected_blocklist_callback(self.client, query)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)
        self.assertIn("access changed", query.answer.call_args.args[0].lower())

        query = await self._preview_query("Another song")
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))), \
             patch("videl.plugins.base.set_setting", return_value=False):
            await settings.connected_blocklist_callback(self.client, query)
        self.assertIn("could not save", query.answer.call_args.args[0].lower())
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)

    async def test_concurrent_confirmations_only_commit_once(self):
        query = await self._preview_query()
        async def slow_resolver(*args, **kwargs):
            import asyncio
            await asyncio.sleep(0.02)
            return SimpleNamespace(id=self.CHAT), None
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=slow_resolver):
            await __import__("asyncio").gather(
                settings.connected_blocklist_callback(self.client, query),
                settings.connected_blocklist_callback(self.client, query))
        row = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["revision"], 1)
        self.assertEqual(row["music_track_blocklist"], [{"kind": "track", "value": "Song"}])


if __name__ == "__main__":
    unittest.main()
