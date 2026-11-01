import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock
from pyrogram.enums import ChatMemberStatus

from videl.app.connections import connected_target
from videl.plugins import settings


class ConnectedSettingsDashboardTests(unittest.IsolatedAsyncioTestCase):
    CHAT = -100123
    USER = 42

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["mgmt_chat_settings"].insert_one({
            "chat_id": self.CHAT, "music_requests_enabled": True, "revision": 0,
        })
        self.query = SimpleNamespace(
            data=f"settings:{self.CHAT}:music_requests_enabled:off:v0",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=8),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock(),
        )
        self.client = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")),
            send_message=AsyncMock(),
        )

    async def test_settings_handler_uses_proxy_target_not_private_interaction_id(self):
        context = SimpleNamespace(
            message=SimpleNamespace(chat=SimpleNamespace(id=self.CHAT, type="supergroup"),
                                    target_chat_id=self.CHAT, interaction_chat_id=self.USER),
            command=SimpleNamespace(arguments=""),
        )
        expected_screen = object()
        with patch("videl.plugins.settings._screen", return_value=expected_screen) as screen:
            result = await settings.settings(context)
        self.assertIs(result, expected_screen)
        screen.assert_called_once_with(self.CHAT, connected_dm=True)

    async def test_dm_callback_checks_connection_and_current_admin_before_target_write(self):
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(
                 SimpleNamespace(id=self.CHAT), None))) as resolve, \
             patch("videl.plugins.settings.rich_edit", new=AsyncMock()) as edit:
            await settings.settings_callback(self.client, self.query)
        resolve.assert_awaited_once_with(self.client, self.USER, expected_chat_id=self.CHAT)
        self.client.get_chat_member.assert_awaited_once_with(self.CHAT, self.USER)
        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertFalse(saved["music_requests_enabled"])
        self.assertEqual(saved["revision"], 1)
        edit.assert_awaited_once()

    async def test_stale_dm_callback_refreshes_without_mutation(self):
        self.db["mgmt_chat_settings"].update_one({"chat_id": self.CHAT}, {"$set": {"revision": 1}})
        self.query.data = f"settings:{self.CHAT}:music_requests_enabled:off:v0"
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(
                 SimpleNamespace(id=self.CHAT), None))), \
             patch("videl.plugins.settings.rich_edit", new=AsyncMock()) as edit:
            await settings.settings_callback(self.client, self.query)
        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertTrue(saved["music_requests_enabled"])
        self.assertEqual(saved["revision"], 1)
        self.assertIn("changed", self.query.answer.call_args.args[0].lower())
        edit.assert_awaited_once()

    async def test_changed_connection_blocks_dm_write(self):
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(
                 None, "This panel belongs to a different group."))):
            await settings.settings_callback(self.client, self.query)
        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertTrue(saved["music_requests_enabled"])
        self.assertEqual(saved["revision"], 0)
        self.client.get_chat_member.assert_not_awaited()

    async def test_connected_dm_welcome_text_callback_starts_private_prompt(self):
        from videl.plugins import welcome
        self.query.data = f"settings:{self.CHAT}:welcome_text:edit:v0"
        self.client.send_message.return_value = SimpleNamespace(id=71)
        with patch("videl.utils.db._db", self.db), \
             patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(
                 SimpleNamespace(id=self.CHAT, type="supergroup", title="Target group"), None))):
            await settings.settings_callback(self.client, self.query)
        session = await welcome._interaction_engine.for_owner(
            chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        try:
            self.assertEqual(session.workflow, "welcome_text")
            self.assertEqual(session.chat_id, self.USER)
            self.assertEqual(session.target_chat_id, self.CHAT)
            self.client.send_message.assert_awaited_once()
            self.assertEqual(self.client.send_message.await_args.args[0], self.USER)
            self.assertIn("welcome text", self.client.send_message.await_args.args[1].lower())
            self.assertEqual(session.expected_message_id, 71)
        finally:
            await welcome._interaction_engine.cancel(session.token, chat_id=self.USER, actor_id=self.USER)

    async def test_target_resolver_checks_current_connection_and_admin_role(self):
        group = SimpleNamespace(id=self.CHAT, type="supergroup")
        client = SimpleNamespace(
            get_chat=AsyncMock(return_value=group),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status=ChatMemberStatus.ADMINISTRATOR)),
        )
        with patch("videl.utils.db.get_connected_chat", return_value=self.CHAT):
            resolved, error = await connected_target(client, self.USER, expected_chat_id=self.CHAT)
        self.assertIs(resolved, group)
        self.assertIsNone(error)
        client.get_chat_member.assert_awaited_once_with(self.CHAT, self.USER)

        client.get_chat_member.return_value = SimpleNamespace(status=ChatMemberStatus.MEMBER)
        with patch("videl.utils.db.get_connected_chat", return_value=self.CHAT):
            resolved, error = await connected_target(client, self.USER, expected_chat_id=self.CHAT)
        self.assertIsNone(resolved)
        self.assertIn("no longer a current administrator", error)

    def test_connected_dm_hides_prompt_based_controls_across_sections(self):
        unsupported = (":filters:", ":blocklist:add:", ":blocklist:remove:", ":preset:save",
                       ":preset:delete:", ":session:schedule")
        with patch("videl.plugins.settings._revision", return_value=0):
            screens = [settings._screen(self.CHAT, section, connected_dm=True)
                       for section in ("home", "music", "welcome", "safety", "moderation",
                                       "retention", "blocklist", "presets", "sessions",
                                       "automations", "commands", "more")]
        callbacks = [button.callback_data for screen in screens
                     for row in screen.keyboard.inline_keyboard for button in row
                     if button.callback_data]
        self.assertTrue(any(":tab:home:" in callback for callback in callbacks))
        self.assertFalse(any(fragment in callback for callback in callbacks for fragment in unsupported))
        self.assertTrue(any(":welcome_text:edit:" in callback for callback in callbacks))
        self.assertTrue(any(":goodbye_text:edit:" in callback for callback in callbacks))
        self.assertTrue(any(":rules_text:edit:" in callback for callback in callbacks))
        self.assertTrue(any(":welcome_media:edit:" in callback for callback in callbacks))
        self.assertTrue(any(":welcome_buttons:edit:" in callback for callback in callbacks))
        self.assertTrue(any(":captcha:edit:" in callback for callback in callbacks))
        self.assertTrue(any(":antispam:edit:" in callback for callback in callbacks))
        self.assertTrue(any(":warn_threshold:edit:" in callback for callback in callbacks))
        self.assertFalse(any(":retention:" in callback and ":tab:retention:" not in callback
                             for callback in callbacks))
        self.assertTrue(all(callback.endswith(":v0") for callback in callbacks))
        self.assertTrue(all("other prompt and media workflows remain hidden" in screen.html for screen in screens))


if __name__ == "__main__":
    unittest.main()
