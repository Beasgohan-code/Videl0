import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock

from videl.plugins import settings
from videl.utils.interactive_settings import engine


class ConnectedWarningEditorTests(unittest.IsolatedAsyncioTestCase):
    GROUP = -100321
    USER = 481

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["mgmt_chat_settings"].insert_one({
            "chat_id": self.GROUP, "warn_threshold": 3, "revision": 2,
        })
        self.message = SimpleNamespace(
            chat=SimpleNamespace(id=self.USER, type="private"), id=710,
        )
        self.actor = SimpleNamespace(id=self.USER)
        self.client = SimpleNamespace(get_chat_member=AsyncMock(
            return_value=SimpleNamespace(status="administrator")))
        self.query = SimpleNamespace(
            message=self.message, from_user=self.actor, data="",
            answer=AsyncMock(),
        )

    async def _start(self):
        with patch("videl.utils.db._db", self.db), \
             patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
            session = await settings._start_warn_threshold_editor(
                self.message, self.GROUP, self.USER, 2, interaction_chat_id=self.USER)
        self.query.data = f"warn_threshold_edit:{session.token}:pick:5"
        return session

    async def test_private_interaction_session_keeps_group_target_and_saves_there(self):
        session = await self._start()
        try:
            self.assertEqual(session.chat_id, self.USER)
            self.assertEqual(session.target_chat_id, self.GROUP)
            self.assertIsNone(await engine.get(session.token, chat_id=self.GROUP,
                                               actor_id=self.USER, target_chat_id=self.GROUP))
            with patch("videl.utils.db._db", self.db), \
                 patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(
                     SimpleNamespace(id=self.GROUP), None))), \
                 patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
                await settings.warn_threshold_editor_callback(self.client, self.query)
            preview = await engine.get(session.token, chat_id=self.USER, actor_id=self.USER,
                                       target_chat_id=self.GROUP)
            self.assertEqual(preview.phase, "preview")
            self.query.data = f"warn_threshold_edit:{session.token}:save"
            with patch("videl.utils.db._db", self.db), \
                 patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(
                     SimpleNamespace(id=self.GROUP), None))), \
                 patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
                await settings.warn_threshold_editor_callback(self.client, self.query)
            document = self.db["mgmt_chat_settings"].find_one({"chat_id": self.GROUP})
            self.assertEqual(document["warn_threshold"], 5)
            self.assertEqual(document["revision"], 3)
        finally:
            await engine.cancel(session.token, chat_id=self.USER, actor_id=self.USER)

    async def test_connection_revocation_before_save_discards_private_draft(self):
        session = await self._start()
        try:
            with patch("videl.utils.db._db", self.db), \
                 patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(
                     SimpleNamespace(id=self.GROUP), None))), \
                 patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
                await settings.warn_threshold_editor_callback(self.client, self.query)
            self.query.answer.reset_mock()
            self.query.data = f"warn_threshold_edit:{session.token}:save"
            with patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(
                    None, "The connection has changed."))):
                await settings.warn_threshold_editor_callback(self.client, self.query)
            document = self.db["mgmt_chat_settings"].find_one({"chat_id": self.GROUP})
            self.assertEqual(document["warn_threshold"], 3)
            self.assertEqual(document["revision"], 2)
            self.assertIn("connection has changed", self.query.answer.call_args.args[0].lower())
        finally:
            await engine.cancel(session.token, chat_id=self.USER, actor_id=self.USER)


if __name__ == "__main__":
    unittest.main()
