import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock

from videl.plugins import settings


class TelegramSettingsRevisionTests(unittest.IsolatedAsyncioTestCase):
    CHAT = -1001234567

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.connection = patch("videl.utils.db._db", self.db)
        self.connection.start()
        self.addCleanup(self.connection.stop)
        self.message = SimpleNamespace(chat=SimpleNamespace(id=self.CHAT, type="supergroup"))
        self.actor = SimpleNamespace(id=345)
        self.query = SimpleNamespace(
            data="", message=self.message, from_user=self.actor,
            answer=AsyncMock(),
        )
        self.client = SimpleNamespace(get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")))

    async def test_compact_navigation_has_more_hub_and_back_links(self):
        home = settings._screen(self.CHAT)
        home_labels = [button.text for row in home.keyboard.inline_keyboard for button in row]
        self.assertIn("More settings", home_labels)
        self.assertLessEqual(len(home_labels), 8)

        more = settings._screen(self.CHAT, "more")
        more_labels = [button.text for row in more.keyboard.inline_keyboard for button in row]
        self.assertIn("← Overview", more_labels)
        self.assertIn("Automations", more_labels)
        self.assertIn("⌘ Commands", more_labels)

        detail = settings._screen(self.CHAT, "music")
        detail_labels = [button.text for row in detail.keyboard.inline_keyboard for button in row]
        self.assertIn("← Overview", detail_labels)
        self.assertIn("More settings", detail_labels)

    async def test_rendered_keyboard_has_revision_and_respects_callback_limit(self):
        screen = settings._screen(self.CHAT)
        buttons = [button for row in screen.keyboard.inline_keyboard for button in row]
        callbacks = [button.callback_data for button in buttons if button.callback_data]
        self.assertTrue(callbacks)
        self.assertTrue(all(item.endswith(":v0") for item in callbacks))
        self.assertLessEqual(max(map(len, callbacks)), 64)

    async def test_stale_toggle_is_rejected_and_current_screen_refreshed(self):
        self.db["mgmt_chat_settings"].insert_one({
            "chat_id": self.CHAT, "music_requests_enabled": True, "revision": 1,
        })
        self.query.data = f"settings:{self.CHAT}:music_requests_enabled:off:v0"
        with patch("videl.plugins.settings.rich_edit", new=AsyncMock()) as edit:
            await settings.settings_callback(self.client, self.query)
        self.query.answer.assert_awaited_once()
        self.assertIn("changed", self.query.answer.call_args.args[0].lower())
        self.assertTrue(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["music_requests_enabled"])
        edit.assert_awaited_once()

    async def test_confirmed_reset_is_previewed_cas_guarded_and_audited(self):
        self.db["mgmt_chat_settings"].insert_one({
            "chat_id": self.CHAT, "music_requests_enabled": False,
            "music_approval_required": True, "welcome_message": "Keep this", "revision": 3,
        })
        signature = settings._reset_signature(self.CHAT, "music")
        self.query.data = f"settings:{self.CHAT}:resetconfirm:music:{signature}:v3"
        with patch("videl.plugins.settings.rich_edit", new=AsyncMock()) as edit, \
             patch("videl.utils.audit.record_bot") as audit:
            await settings.settings_callback(self.client, self.query)
        document = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertTrue(document["music_requests_enabled"])
        self.assertFalse(document["music_approval_required"])
        self.assertEqual(document["welcome_message"], "Keep this")
        self.assertEqual(document["revision"], 4)
        audit.assert_called_once()
        edit.assert_awaited_once()

    async def test_removed_ai_setting_callback_is_not_registered_and_stored_value_is_untouched(self):
        import re
        self.db["mgmt_chat_settings"].insert_one({
            "chat_id": self.CHAT, "gemini_guardian_enabled": True, "revision": 0,
        })
        stale = f"settings:{self.CHAT}:gemini_guardian_enabled:on:v0"
        self.assertIsNone(re.fullmatch(settings._PATTERN, stale))
        document = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertTrue(document["gemini_guardian_enabled"])
        self.assertEqual(document["revision"], 0)

    async def test_stale_reset_callback_never_applies(self):
        self.db["mgmt_chat_settings"].insert_one({
            "chat_id": self.CHAT, "warn_threshold": 5, "revision": 2,
        })
        token = settings._reset_signature(self.CHAT, "moderation")
        self.query.data = f"settings:{self.CHAT}:resetconfirm:moderation:{token}:v1"
        with patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
            await settings.settings_callback(self.client, self.query)
        document = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(document["warn_threshold"], 5)
        self.assertEqual(document["revision"], 2)


if __name__ == "__main__":
    unittest.main()
