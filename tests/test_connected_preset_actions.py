import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock
from videl.core import player, queue
from videl.plugins import settings
from videl.utils.interactive_settings import engine


class ConnectedPresetActionTests(unittest.IsolatedAsyncioTestCase):
    CHAT, USER, BOT = -100923, 923, 999
    PRESET = {"name": "Dance", "loop": "all", "shuffle": True, "requests": False, "approval": True}

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["mgmt_chat_settings"].insert_one({"chat_id": self.CHAT, "revision": 0,
            "music_session_presets": [dict(self.PRESET)], "music_shuffle_enabled": False,
            "music_requests_enabled": True, "music_approval_required": False})
        self.original = [
            {"title": "Current", "url": "https://youtu.be/aaaaaaaaaaa"},
            {"title": "Next A", "url": "https://youtu.be/bbbbbbbbbbb"},
            {"title": "Next B", "url": "https://youtu.be/ccccccccccc"},
        ]
        queue.chat_queues[self.CHAT] = list(self.original)
        queue._revisions[self.CHAT] = 0
        player.set_loop(self.CHAT, "off")
        self.next_id = 300
        async def send(*args, **kwargs):
            self.next_id += 1
            return SimpleNamespace(id=self.next_id)
        self.client = SimpleNamespace(me=SimpleNamespace(id=self.BOT), send_message=AsyncMock(side_effect=send),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")))

    async def asyncTearDown(self):
        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        queue.chat_queues.pop(self.CHAT, None)
        queue._revisions.pop(self.CHAT, None)
        player.set_loop(self.CHAT, "off")

    async def _start(self, action="apply"):
        query = SimpleNamespace(data=f"settings:{self.CHAT}:preset:{action}:1:v0",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=31),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.settings_callback(self.client, query)
        return await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    async def _preview(self, session=None):
        session = session or await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        msg = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
            text="PREVIEW", reply_to_message=SimpleNamespace(id=session.expected_message_id))
        with patch("videl.utils.db._db", self.db):
            await settings.connected_preset_action_reply(self.client, msg)
        return await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    def _callback(self, action, session, actor_id=None, message_id=None):
        return SimpleNamespace(data=f"preset_action_{action}:{session.token}",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"),
                                    id=session.expected_message_id if message_id is None else message_id),
            from_user=SimpleNamespace(id=self.USER if actor_id is None else actor_id), answer=AsyncMock())

    async def _confirm(self, session, resolver=None):
        query = self._callback("save", session)
        resolver = resolver or AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target", resolver):
            await settings.connected_preset_action_callback(self.client, query)
        return query, resolver

    async def test_apply_preview_is_read_only_and_success_preserves_current_then_shuffles_upcoming(self):
        session = await self._start("apply")
        self.assertEqual(session.chat_id, self.USER)
        self.assertEqual(session.target_chat_id, self.CHAT)
        self.assertEqual(queue.get_queue(self.CHAT), self.original)
        session = await self._preview(session)
        preview_text = self.client.send_message.await_args_list[-1].args[1]
        self.assertIn("current track remains in place", preview_text.lower())
        self.assertIn("will be shuffled in place", preview_text)
        self.assertEqual(queue.get_queue(self.CHAT), self.original)
        with patch("random.shuffle", side_effect=lambda rows: rows.reverse()):
            query, resolver = await self._confirm(session)
        resolver.assert_awaited_once_with(self.client, self.USER, expected_chat_id=self.CHAT)
        self.assertEqual([song["title"] for song in queue.get_queue(self.CHAT)], ["Current", "Next B", "Next A"])
        self.assertEqual(player.get_loop(self.CHAT), "all")
        row = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertFalse(row["music_shuffle_enabled"] is False)
        self.assertFalse(row["music_requests_enabled"])
        self.assertTrue(row["music_approval_required"])
        self.assertEqual(row["revision"], 1)
        self.assertEqual(query.answer.call_args.args[0], "Preset applied.")

    async def test_shuffle_off_preserves_queue_order_and_changes_shuffle_setting(self):
        self.db["mgmt_chat_settings"].update_one({"chat_id": self.CHAT}, {"$set": {
            "music_session_presets": [{**self.PRESET, "shuffle": False}]}})
        session = await self._start("apply"); session = await self._preview(session)
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.connected_preset_action_callback(self.client, self._callback("save", session))
        self.assertEqual(queue.get_queue(self.CHAT), self.original)
        self.assertEqual(queue.mutation_revision(self.CHAT), 0)
        self.assertFalse(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["music_shuffle_enabled"])

    async def test_queue_change_after_preview_rejects_apply(self):
        session = await self._start("apply"); session = await self._preview(session)
        queue.add_to_queue(self.CHAT, {"title": "Added meanwhile", "url": "https://youtu.be/ddddddddddd"})
        before = list(queue.get_queue(self.CHAT))
        query, _ = await self._confirm(session)
        self.assertIn("queue changed", query.answer.call_args.args[0].lower())
        self.assertEqual(queue.get_queue(self.CHAT), before)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)

    async def test_preset_change_after_preview_rejects_apply(self):
        session = await self._start("apply"); session = await self._preview(session)
        changed = {**self.PRESET, "loop": "one"}
        self.db["mgmt_chat_settings"].update_one({"chat_id": self.CHAT}, {"$set": {
            "music_session_presets": [changed], "revision": 1}})
        before = list(queue.get_queue(self.CHAT))
        query, _ = await self._confirm(session)
        self.assertIn("changed", query.answer.call_args.args[0].lower())
        self.assertEqual(queue.get_queue(self.CHAT), before)
        self.assertEqual(player.get_loop(self.CHAT), "off")

    async def test_cancel_timeout_forgery_and_replay_never_apply(self):
        session = await self._start("apply"); session = await self._preview(session)
        forged = self._callback("save", session, actor_id=self.USER + 1)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_preset_action_callback(self.client, forged)
        self.assertEqual(queue.get_queue(self.CHAT), self.original)
        cancel = self._callback("cancel", session)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_preset_action_callback(self.client, cancel)
        self.assertEqual(queue.get_queue(self.CHAT), self.original)
        session = await self._start("apply"); session = await self._preview(session)
        clock = engine._clock
        try:
            engine._clock = lambda: 10**12
            expired = self._callback("save", session)
            with patch("videl.utils.db._db", self.db):
                await settings.connected_preset_action_callback(self.client, expired)
            self.assertIn("expired", expired.answer.call_args.args[0].lower())
        finally:
            engine._clock = clock
        self.assertEqual(queue.get_queue(self.CHAT), self.original)

    async def test_connection_failure_stale_message_and_db_failure_do_not_apply(self):
        session = await self._start("apply"); session = await self._preview(session)
        query = self._callback("save", session, message_id=session.expected_message_id + 1)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_preset_action_callback(self.client, query)
        self.assertIn("stale", query.answer.call_args.args[0].lower())
        query, _ = await self._confirm(session, AsyncMock(return_value=(None, "connection changed")))
        self.assertIn("connection", query.answer.call_args.args[0].lower())
        self.assertEqual(queue.get_queue(self.CHAT), self.original)

        with patch("videl.plugins.settings.base.set_settings", return_value=False):
            query, _ = await self._confirm(session, AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None)))
        self.assertIn("nothing was reported", query.answer.call_args.args[0].lower())
        self.assertEqual(queue.get_queue(self.CHAT), self.original)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)

    async def test_queue_operation_failure_rolls_back_and_concurrent_confirm_only_applies_once(self):
        session = await self._start("apply"); session = await self._preview(session)
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))), \
             patch("videl.core.queue.note_queue_mutation", side_effect=RuntimeError("queue failure")):
            failed = self._callback("save", session)
            await settings.connected_preset_action_callback(self.client, failed)
        self.assertEqual(queue.get_queue(self.CHAT), self.original)
        self.assertEqual(player.get_loop(self.CHAT), "off")
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)

        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        session = await self._start("apply"); session = await self._preview(session)
        first, second = self._callback("save", session), self._callback("save", session)
        async def slow_resolver(*args, **kwargs):
            await asyncio.sleep(0.02)
            return SimpleNamespace(id=self.CHAT), None
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target", new=slow_resolver), \
             patch("random.shuffle", side_effect=lambda rows: rows.reverse()):
            await asyncio.gather(settings.connected_preset_action_callback(self.client, first),
                                 settings.connected_preset_action_callback(self.client, second))
        self.assertEqual([song["title"] for song in queue.get_queue(self.CHAT)], ["Current", "Next B", "Next A"])
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 1)

    async def test_delete_preview_cancel_success_and_active_queue_unchanged(self):
        session = await self._start("delete")
        session = await self._preview(session)
        preview = self.client.send_message.await_args_list[-1].args[1]
        self.assertIn("Preset to delete", preview)
        self.assertIn("active queue and playback settings will not change", preview)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["music_session_presets"], [self.PRESET])
        cancel = self._callback("cancel", session)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_preset_action_callback(self.client, cancel)
        self.assertEqual(queue.get_queue(self.CHAT), self.original)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["music_session_presets"], [self.PRESET])

        session = await self._start("delete"); session = await self._preview(session)
        query, resolver = await self._confirm(session)
        resolver.assert_awaited_once_with(self.client, self.USER, expected_chat_id=self.CHAT)
        row = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["music_session_presets"], [])
        self.assertEqual(row["revision"], 1)
        self.assertEqual(queue.get_queue(self.CHAT), self.original)
        self.assertEqual(player.get_loop(self.CHAT), "off")
        self.assertEqual(query.answer.call_args.args[0], "Preset deleted.")

    async def test_delete_timeout_permission_connection_stale_and_db_failure(self):
        session = await self._start("delete"); session = await self._preview(session)
        clock = engine._clock
        try:
            engine._clock = lambda: 10**12
            expired = self._callback("save", session)
            with patch("videl.utils.db._db", self.db):
                await settings.connected_preset_action_callback(self.client, expired)
        finally:
            engine._clock = clock
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["music_session_presets"], [self.PRESET])
        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

        session = await self._start("delete"); session = await self._preview(session)
        denied, _ = await self._confirm(session, AsyncMock(return_value=(None, "permission revoked")))
        self.assertIn("permission changed", denied.answer.call_args.args[0].lower())
        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

        session = await self._start("delete"); session = await self._preview(session)
        self.db["mgmt_chat_settings"].update_one({"chat_id": self.CHAT}, {"$set": {"revision": 1, "music_session_presets": []}})
        stale, _ = await self._confirm(session)
        self.assertIn("changed", stale.answer.call_args.args[0].lower())
        self.assertEqual(queue.get_queue(self.CHAT), self.original)

    async def test_group_context_apply_and_delete_callbacks_stay_immediate(self):
        group_message = SimpleNamespace(chat=SimpleNamespace(id=self.CHAT, type="supergroup"), id=54)
        apply = SimpleNamespace(data=f"settings:{self.CHAT}:preset:apply:1:v0", message=group_message,
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
        with patch("videl.utils.db._db", self.db), patch("random.shuffle", side_effect=lambda rows: rows.reverse()), \
             patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
            await settings.settings_callback(self.client, apply)
        self.assertEqual([song["title"] for song in queue.get_queue(self.CHAT)], ["Current", "Next B", "Next A"])
        self.db["mgmt_chat_settings"].update_one({"chat_id": self.CHAT}, {"$set": {"revision": 0,
            "music_session_presets": [dict(self.PRESET)]}})
        delete = SimpleNamespace(data=f"settings:{self.CHAT}:preset:delete:1:v0", message=group_message,
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
        with patch("videl.utils.db._db", self.db), patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
            await settings.settings_callback(self.client, delete)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["music_session_presets"], [])


if __name__ == "__main__":
    unittest.main()
