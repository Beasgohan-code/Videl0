import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock
from videl.plugins import settings
from videl.utils.interactive_settings import engine


class ConnectedPresetEditorTests(unittest.IsolatedAsyncioTestCase):
    CHAT, USER = -100881, 881

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["mgmt_chat_settings"].insert_one({"chat_id": self.CHAT, "revision": 0,
            "music_session_presets": [], "music_shuffle_enabled": True,
            "music_requests_enabled": True, "music_approval_required": False})
        self.next_id = 100
        async def send(*args, **kwargs):
            self.next_id += 1
            return SimpleNamespace(id=self.next_id)
        self.client = SimpleNamespace(send_message=AsyncMock(side_effect=send),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")))

    async def asyncTearDown(self):
        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    async def _start(self):
        query = SimpleNamespace(data=f"settings:{self.CHAT}:preset:save:v0",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=12),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.settings_callback(self.client, query)
        return await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    async def _reply(self, name):
        session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        reply = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
            text=name, reply_to_message=SimpleNamespace(id=session.expected_message_id))
        with patch("videl.utils.db._db", self.db), patch("videl.core.player.get_loop", return_value="all"):
            await settings.connected_preset_reply(self.client, reply)
        return await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    def _callback_query(self, action, session):
        return SimpleNamespace(data=f"preset_{action}:{session.token}",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=session.expected_message_id),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())

    async def test_success_saves_existing_schema_in_target_group(self):
        await self._start(); session = await self._reply("Friday")
        query = self._callback_query("save", session)
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.connected_preset_callback(self.client, query)
        row = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["music_session_presets"], [{"name": "Friday", "loop": "all",
            "shuffle": True, "requests": True, "approval": False}])
        self.assertEqual(row["revision"], 1)
        self.assertIsNone(await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT))

    async def test_cancel_leaves_settings_unchanged(self):
        await self._start(); session = await self._reply("Friday")
        query = self._callback_query("cancel", session)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_preset_callback(self.client, query)
        row = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["revision"], 0)
        self.assertEqual(row["music_session_presets"], [])

    async def test_edit_again_accepts_revised_draft(self):
        await self._start(); session = await self._reply("Friday")
        query = self._callback_query("edit", session)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_preset_callback(self.client, query)
        editing = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        self.assertEqual(editing.phase, "input")
        revised = await self._reply("Saturday")
        confirm = self._callback_query("save", revised)
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.connected_preset_callback(self.client, confirm)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["music_session_presets"][0]["name"], "Saturday")

    async def test_timeout_and_wrong_actor_do_not_commit(self):
        await self._start(); session = await self._reply("Friday")
        wrong_actor = self._callback_query("save", session)
        wrong_actor.from_user = SimpleNamespace(id=self.USER + 1)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_preset_callback(self.client, wrong_actor)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)
        clock = engine._clock
        try:
            engine._clock = lambda: 10**12
            query = self._callback_query("save", session)
            with patch("videl.utils.db._db", self.db):
                await settings.connected_preset_callback(self.client, query)
            self.assertIn("expired", query.answer.call_args.args[0].lower())
        finally:
            engine._clock = clock
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)

    async def test_invalid_duplicate_or_empty_name_keeps_draft_open(self):
        self.db["mgmt_chat_settings"].update_one({"chat_id": self.CHAT}, {"$set": {
            "music_session_presets": [{"name": "Friday"}]}})
        await self._start()
        for name in (" ", "Friday"):
            session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
            reply = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
                text=name, reply_to_message=SimpleNamespace(id=session.expected_message_id))
            with patch("videl.utils.db._db", self.db), patch("videl.core.player.get_loop", return_value="off"):
                await settings.connected_preset_reply(self.client, reply)
            self.assertEqual((await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)).phase, "input")
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)

    async def test_permission_or_connection_loss_prevents_save(self):
        await self._start(); session = await self._reply("Friday")
        query = self._callback_query("save", session)
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(None, "admin revoked or connection changed"))):
            await settings.connected_preset_callback(self.client, query)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)
        self.assertIn("access changed", query.answer.call_args.args[0].lower())

    async def test_revision_conflict_and_database_failure_are_not_success(self):
        await self._start(); session = await self._reply("Friday")
        self.db["mgmt_chat_settings"].update_one({"chat_id": self.CHAT}, {"$set": {"revision": 1}})
        query = self._callback_query("save", session)
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.connected_preset_callback(self.client, query)
        self.assertIn("could not save", query.answer.call_args.args[0].lower())
        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        self.db["mgmt_chat_settings"].update_one({"chat_id": self.CHAT}, {"$set": {"revision": 0}})
        await self._start(); session = await self._reply("Saturday")
        query = self._callback_query("save", session)
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))), \
             patch("videl.plugins.base.set_setting", return_value=False):
            await settings.connected_preset_callback(self.client, query)
        self.assertIn("could not save", query.answer.call_args.args[0].lower())
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["music_session_presets"], [])

    async def test_confirmation_is_single_flight(self):
        await self._start(); session = await self._reply("Friday")
        first = self._callback_query("save", session); second = self._callback_query("save", session)
        async def delayed(*args, **kwargs):
            await asyncio.sleep(0.02)
            return SimpleNamespace(id=self.CHAT), None
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target", new=delayed):
            await asyncio.gather(settings.connected_preset_callback(self.client, first),
                                 settings.connected_preset_callback(self.client, second))
        row = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["revision"], 1)
        self.assertEqual(len(row["music_session_presets"]), 1)


if __name__ == "__main__":
    unittest.main()
