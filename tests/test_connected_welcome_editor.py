import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock

from videl.plugins import settings, welcome
from videl.utils.interactive_settings import InteractionEngine


class ConnectedWelcomeEditorTests(unittest.IsolatedAsyncioTestCase):
    GROUP = -1007654321
    USER = 778

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["mgmt_chat_settings"].insert_one({
            "chat_id": self.GROUP, "revision": 4, "welcome_message": "Old {name}",
            "welcome_enabled": True,
        })
        self.engine_patch = patch.object(welcome, "_interaction_engine", InteractionEngine())
        self.engine_patch.start()
        self.addCleanup(self.engine_patch.stop)
        self.group = SimpleNamespace(id=self.GROUP, type="supergroup", title="Connected group")
        self.client = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")),
            send_message=AsyncMock(side_effect=[SimpleNamespace(id=100), SimpleNamespace(id=101)]),
        )
        self.actor = SimpleNamespace(id=self.USER)
        self.private_message = SimpleNamespace(
            chat=SimpleNamespace(id=self.USER, type="private"), id=99,
        )
        self.start_query = SimpleNamespace(
            data=f"settings:{self.GROUP}:welcome_text:edit:v4",
            message=self.private_message, from_user=self.actor, answer=AsyncMock(),
        )

    async def test_private_prompt_preview_and_save_write_only_to_connected_group(self):
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))), \
             patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
            await settings.settings_callback(self.client, self.start_query)

        session = await welcome._interaction_engine.for_owner(
            chat_id=self.USER, actor_id=self.USER, target_chat_id=self.GROUP)
        self.assertIsNotNone(session)
        self.assertEqual(session.workflow, "welcome_text")
        self.assertEqual(session.chat_id, self.USER)
        self.assertEqual(session.target_chat_id, self.GROUP)
        self.assertEqual(self.client.send_message.await_args_list[0].args[0], self.USER)

        reply = SimpleNamespace(
            chat=SimpleNamespace(id=self.USER, type="private"),
            from_user=self.actor, text="Welcome {name} to {title}!",
            reply_to_message=SimpleNamespace(id=100),
        )
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))):
            await welcome.connected_welcome_reply(self.client, reply)

        session = await welcome._interaction_engine.for_owner(
            chat_id=self.USER, actor_id=self.USER, target_chat_id=self.GROUP)
        self.assertEqual(session.phase, "preview")
        preview_call = self.client.send_message.await_args_list[-1]
        self.assertEqual(preview_call.args[0], self.USER)
        self.assertIn("Welcome Alex to Connected group!", preview_call.args[1])
        self.assertIn("No settings have changed yet", preview_call.args[1])
        before_save = self.db["mgmt_chat_settings"].find_one({"chat_id": self.GROUP})
        self.assertEqual(before_save["welcome_message"], "Old {name}")
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.USER}))

        preview_message = SimpleNamespace(
            chat=SimpleNamespace(id=self.USER, type="private"),
            id=session.expected_message_id, edit_text=AsyncMock(),
        )
        save_query = SimpleNamespace(
            data=f"welcome_edit:{session.token}:save", message=preview_message,
            from_user=self.actor, answer=AsyncMock(),
        )
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))), \
             patch("videl.plugins.welcome.rich_edit", new=AsyncMock()):
            await welcome.welcome_edit_callback(self.client, save_query)

        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.GROUP})
        self.assertEqual(saved["welcome_message"], "Welcome {name} to {title}!")
        self.assertEqual(saved["revision"], 5)
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.USER}))
        self.assertIn("saved", save_query.answer.call_args.args[0].lower())

    async def test_goodbye_text_editor_saves_to_group_after_private_preview(self):
        self.client.send_message.side_effect = [SimpleNamespace(id=110), SimpleNamespace(id=111)]
        query = SimpleNamespace(
            data=f"settings:{self.GROUP}:goodbye_text:edit:v4", message=self.private_message,
            from_user=self.actor, answer=AsyncMock(),
        )
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))), \
             patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
            await settings.settings_callback(self.client, query)
        session = await welcome._interaction_engine.for_owner(
            chat_id=self.USER, actor_id=self.USER, target_chat_id=self.GROUP)
        reply = SimpleNamespace(
            chat=SimpleNamespace(id=self.USER, type="private"), from_user=self.actor,
            text="Goodbye {name} from {title}", reply_to_message=SimpleNamespace(id=110),
        )
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))):
            await welcome.connected_welcome_reply(self.client, reply)
        session = await welcome._interaction_engine.for_owner(
            chat_id=self.USER, actor_id=self.USER, target_chat_id=self.GROUP)
        self.assertIn("Goodbye Alex from Connected group", self.client.send_message.await_args.args[1])
        save_query = SimpleNamespace(
            data=f"welcome_edit:{session.token}:save",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"),
                                    id=session.expected_message_id),
            from_user=self.actor, answer=AsyncMock(),
        )
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))), \
             patch("videl.plugins.welcome.rich_edit", new=AsyncMock()):
            await welcome.welcome_edit_callback(self.client, save_query)
        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.GROUP})
        self.assertEqual(saved["goodbye_message"], "Goodbye {name} from {title}")
        self.assertEqual(saved["revision"], 5)

    async def test_welcome_media_preview_and_save_stay_private_and_target_scoped(self):
        self.client.send_message.side_effect = None
        self.client.send_message.return_value = SimpleNamespace(id=130)
        self.client.send_photo = AsyncMock(return_value=SimpleNamespace(id=131))
        query = SimpleNamespace(
            data=f"settings:{self.GROUP}:welcome_media:edit:v4", message=self.private_message,
            from_user=self.actor, answer=AsyncMock(),
        )
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))), \
             patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
            await settings.settings_callback(self.client, query)
        session = await welcome._interaction_engine.for_owner(
            chat_id=self.USER, actor_id=self.USER, target_chat_id=self.GROUP)
        media_reply = SimpleNamespace(
            chat=SimpleNamespace(id=self.USER, type="private"), from_user=self.actor,
            text=None, photo=SimpleNamespace(file_id="existing-telegram-file-id"),
            reply_to_message=SimpleNamespace(id=130),
        )
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))):
            await welcome.connected_welcome_reply(self.client, media_reply)
        session = await welcome._interaction_engine.for_owner(
            chat_id=self.USER, actor_id=self.USER, target_chat_id=self.GROUP)
        self.client.send_photo.assert_awaited_once()
        self.assertEqual(self.client.send_photo.await_args.args[:2],
                         (self.USER, "existing-telegram-file-id"))
        self.assertIn("Old Alex", self.client.send_photo.await_args.kwargs["caption"])
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.GROUP}).get("welcome_media"))
        save_query = SimpleNamespace(
            data=f"welcome_edit:{session.token}:save",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"),
                                    id=session.expected_message_id),
            from_user=self.actor, answer=AsyncMock(),
        )
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))), \
             patch("videl.plugins.welcome.rich_edit", new=AsyncMock()):
            await welcome.welcome_edit_callback(self.client, save_query)
        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.GROUP})
        self.assertEqual(saved["welcome_media"], {"type": "photo", "file_id": "existing-telegram-file-id"})
        self.assertEqual(saved["revision"], 5)
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.USER}))

    async def test_checklist_editor_validates_and_saves_links_in_connected_group(self):
        self.client.send_message.side_effect = [SimpleNamespace(id=140), SimpleNamespace(id=141)]
        with patch("videl.utils.db._db", self.db):
            await welcome.start_welcome_workflow(
                self.client, self.GROUP, self.USER, 4, "welcome_buttons", interaction_chat_id=self.USER)
        session = await welcome._interaction_engine.for_owner(
            chat_id=self.USER, actor_id=self.USER, target_chat_id=self.GROUP)
        reply = SimpleNamespace(
            chat=SimpleNamespace(id=self.USER, type="private"), from_user=self.actor,
            text="Start | https://example.com/start", reply_to_message=SimpleNamespace(id=140),
        )
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))):
            await welcome.connected_welcome_reply(self.client, reply)
        session = await welcome._interaction_engine.for_owner(
            chat_id=self.USER, actor_id=self.USER, target_chat_id=self.GROUP)
        self.assertIn("Start", self.client.send_message.await_args.args[1])
        save_query = SimpleNamespace(
            data=f"welcome_edit:{session.token}:save",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"),
                                    id=session.expected_message_id),
            from_user=self.actor, answer=AsyncMock(),
        )
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))), \
             patch("videl.plugins.welcome.rich_edit", new=AsyncMock()):
            await welcome.welcome_edit_callback(self.client, save_query)
        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.GROUP})
        self.assertEqual(saved["welcome_checklist"], [{"label": "Start", "url": "https://example.com/start"}])
        self.assertEqual(saved["revision"], 5)

    async def test_rules_clear_in_dm_requires_confirm_clear_preview(self):
        self.db["mgmt_chat_settings"].update_one(
            {"chat_id": self.GROUP}, {"$set": {"rules": "Existing rules"}})
        self.client.send_message.side_effect = [SimpleNamespace(id=120), SimpleNamespace(id=121)]
        with patch("videl.utils.db._db", self.db):
            await welcome.start_welcome_workflow(
                self.client, self.GROUP, self.USER, 4, "rules_text", interaction_chat_id=self.USER)
        session = await welcome._interaction_engine.for_owner(
            chat_id=self.USER, actor_id=self.USER, target_chat_id=self.GROUP)
        reply = SimpleNamespace(
            chat=SimpleNamespace(id=self.USER, type="private"), from_user=self.actor,
            text="/clear", reply_to_message=SimpleNamespace(id=120),
        )
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))):
            await welcome.connected_welcome_reply(self.client, reply)
        session = await welcome._interaction_engine.for_owner(
            chat_id=self.USER, actor_id=self.USER, target_chat_id=self.GROUP)
        preview_call = self.client.send_message.await_args
        self.assertIn("Current rules will be removed", preview_call.args[1])
        buttons = preview_call.kwargs["reply_markup"].inline_keyboard
        self.assertEqual(buttons[-1][1].text, "Confirm clear")
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.GROUP})["rules"], "Existing rules")
        save_query = SimpleNamespace(
            data=f"welcome_edit:{session.token}:save",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"),
                                    id=session.expected_message_id),
            from_user=self.actor, answer=AsyncMock(),
        )
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(self.group, None))), \
             patch("videl.plugins.welcome.rich_edit", new=AsyncMock()):
            await welcome.welcome_edit_callback(self.client, save_query)
        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.GROUP})
        self.assertIsNone(saved["rules"])
        self.assertEqual(saved["revision"], 5)

    async def test_disconnected_admin_cannot_capture_or_save_private_draft(self):
        with patch("videl.utils.db._db", self.db):
            await welcome.start_welcome_workflow(
                self.client, self.GROUP, self.USER, 4, "welcome_text", interaction_chat_id=self.USER)
        session = await welcome._interaction_engine.for_owner(
            chat_id=self.USER, actor_id=self.USER, target_chat_id=self.GROUP)
        reply = SimpleNamespace(
            chat=SimpleNamespace(id=self.USER, type="private"),
            from_user=self.actor, text="Changed {name}",
            reply_to_message=SimpleNamespace(id=session.expected_message_id),
        )
        with patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(
                None, "The connection has changed."))):
            await welcome.connected_welcome_reply(self.client, reply)
        stored = self.db["mgmt_chat_settings"].find_one({"chat_id": self.GROUP})
        self.assertEqual(stored["welcome_message"], "Old {name}")
        self.assertEqual(stored["revision"], 4)
        self.assertIsNone(await welcome._interaction_engine.get(
            session.token, chat_id=self.USER, actor_id=self.USER, target_chat_id=self.GROUP))
        self.assertIn("connection has changed", self.client.send_message.await_args.args[1].lower())


if __name__ == "__main__":
    unittest.main()
