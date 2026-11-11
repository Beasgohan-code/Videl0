import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from pyrogram.enums import ChatMemberStatus, ChatType

from videl.plugins import locks, welcome


class InlineAdminSettingsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.chat_id = -94001
        self.message = NS(chat=NS(id=self.chat_id, type=ChatType.SUPERGROUP), id=55)
        self.admin = NS(id=944)
        self.client = NS(get_chat_member=AsyncMock(return_value=NS(status=ChatMemberStatus.ADMINISTRATOR)))
        self.query = NS(message=self.message, from_user=self.admin, answer=AsyncMock())

    async def test_lock_status_panel_has_specific_toggle_controls(self):
        with patch.object(locks.base, "get_setting", return_value=False):
            screen = locks.lock_status_screen(self.chat_id)
        callbacks = [
            button.callback_data
            for row in screen.keyboard.inline_keyboard
            for button in row
        ]
        self.assertIn("mgmt_lock:set:links:1", callbacks)
        self.assertIn(f"settings:{self.chat_id}:antispam:edit:v0", callbacks)
        self.assertFalse(any("mgmt_lock:set:antispam" in item for item in callbacks))
        self.assertIn("mgmt_lock:set:all:1", callbacks)
        self.assertLessEqual(max(map(len, callbacks)), 64)

    async def test_lock_toggle_rechecks_current_admin_then_edits_panel(self):
        self.query.data = "mgmt_lock:set:links:1"
        updates = {}
        with patch.object(locks.base, "set_settings", side_effect=lambda _chat, value: updates.update(value) or True), \
             patch.object(locks, "_record", new=AsyncMock()) as audit, \
             patch("videl.plugins.settings._bot_can_delete_messages", new=AsyncMock(return_value=True)), \
             patch.object(locks, "lock_status_screen", return_value=NS(html="updated", keyboard="markup")), \
             patch.object(locks, "rich_edit", new=AsyncMock()) as edit:
            await locks.lock_toggle_callback(self.client, self.query)
        self.assertEqual(updates, {"lock_links": True})
        self.client.get_chat_member.assert_awaited_once_with(self.chat_id, self.admin.id)
        audit.assert_awaited_once()
        self.query.answer.assert_awaited_once_with("Protection updated")
        edit.assert_awaited_once_with(self.message, "updated", reply_markup="markup")

    async def test_legacy_antispam_toggle_opens_revision_bound_preview_instead_of_writing(self):
        self.query.data = "mgmt_lock:set:antispam:1"
        with (
            patch("videl.plugins.settings._start_antispam_editor", new=AsyncMock(return_value="review")) as start,
            patch("videl.utils.settings_store.revision", return_value=9),
            patch.object(locks.base, "set_settings") as save,
        ):
            await locks.lock_toggle_callback(self.client, self.query)
        start.assert_awaited_once_with(self.client, self.chat_id, self.admin.id, 9)
        save.assert_not_called()
        self.query.answer.assert_awaited_once_with("review")

    async def test_lock_command_checks_bot_right_before_setting(self):
        from videl.app.router import CommandError
        context = NS(command=NS(arguments="links"), message=NS(chat=NS(id=self.chat_id), from_user=self.admin))
        with patch("videl.plugins.settings._bot_can_delete_messages", new=AsyncMock(return_value=False)) as rights, \
             patch.object(locks.base, "set_settings") as save:
            with self.assertRaises(CommandError):
                await locks.change_lock(context, True)
        rights.assert_awaited_once()
        save.assert_not_called()

    async def test_lock_toggle_requires_bot_delete_right_before_enable(self):
        self.query.data = "mgmt_lock:set:links:1"
        with patch("videl.plugins.settings._bot_can_delete_messages", new=AsyncMock(return_value=False)) as rights, \
             patch.object(locks.base, "set_settings") as save:
            await locks.lock_toggle_callback(self.client, self.query)
        rights.assert_awaited_once_with(self.client, self.chat_id)
        save.assert_not_called()
        self.assertIn("Delete Messages", self.query.answer.call_args.args[0])

    async def test_lock_toggle_rejects_non_admin_without_writing(self):
        self.query.data = "mgmt_lock:set:links:1"
        self.client.get_chat_member.return_value = NS(status=ChatMemberStatus.MEMBER)
        with patch.object(locks.base, "set_settings") as save:
            await locks.lock_toggle_callback(self.client, self.query)
        save.assert_not_called()
        self.assertTrue(self.query.answer.call_args.kwargs["show_alert"])

    async def test_greetings_panel_actions_are_live_and_scope_bound(self):
        self.query.data = "mgmt_greeting:welcome_enabled:0"
        updates = {}
        def set_setting(chat_id, key, value):
            updates[(chat_id, key)] = value
            return True
        with patch.object(welcome.base, "set_setting", side_effect=set_setting), \
             patch.object(welcome.base, "get_setting", side_effect=lambda _chat, key, default=None: updates.get((self.chat_id, key), default)), \
             patch.object(welcome, "rich_edit", new=AsyncMock()) as edit:
            await welcome.greeting_toggle_callback(self.client, self.query)
        self.assertEqual(updates[(self.chat_id, "welcome_enabled")], False)
        self.client.get_chat_member.assert_awaited_once_with(self.chat_id, self.admin.id)
        edit.assert_awaited_once()

    async def test_greeting_toggle_denies_removed_admin(self):
        self.query.data = "mgmt_greeting:captcha_enabled:1"
        self.client.get_chat_member.return_value = NS(status=ChatMemberStatus.MEMBER)
        with patch.object(welcome.base, "set_setting") as save:
            await welcome.greeting_toggle_callback(self.client, self.query)
        save.assert_not_called()
        self.assertTrue(self.query.answer.call_args.kwargs["show_alert"])


if __name__ == "__main__":
    unittest.main()
