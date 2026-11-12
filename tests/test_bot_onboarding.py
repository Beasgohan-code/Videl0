import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from videl.modules import bot as bot_module


class BotOnboardingTests(unittest.IsolatedAsyncioTestCase):
    def test_admin_setup_panel_has_clear_rights_and_no_fake_promotion_button(self):
        text, keyboard = bot_module._admin_setup_panel()
        self.assertIn("Delete messages", text)
        self.assertIn("Manage video chats", text)
        self.assertIn("Invite users", text)
        from videl.utils.premium_emojis import PREMIUM_IDS
        self.assertIn(f'<tg-emoji emoji-id="{PREMIUM_IDS["ios_trash"]}">🗑</tg-emoji> Delete messages', text)
        self.assertIn(f'<tg-emoji emoji-id="{PREMIUM_IDS["boseh_video"]}">🎥</tg-emoji> Manage video chats', text)
        self.assertIn(f'<tg-emoji emoji-id="{PREMIUM_IDS["ios_add"]}">➕</tg-emoji> Invite users', text)
        self.assertIn("doesn’t let me grant myself admin rights", text)
        self.assertEqual(len(keyboard.inline_keyboard), 1)
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "bot_setup:permissions")
        self.assertEqual(keyboard.inline_keyboard[0][0].text, "Permission checklist")
        self.assertEqual(keyboard.inline_keyboard[0][0].icon_custom_emoji_id, PREMIUM_IDS["info"])
        self.assertNotIn("make me admin", str(keyboard))

    async def test_permission_checklist_gives_valid_manual_instructions(self):
        query = NS(answer=AsyncMock())
        await bot_module.bot_setup_permissions(None, query)
        query.answer.assert_awaited_once()
        answer = query.answer.call_args.args[0]
        self.assertIn("Administrators → Add administrator", answer)
        self.assertIn("Videl cannot promote itself", answer)
        self.assertTrue(query.answer.call_args.kwargs["show_alert"])


if __name__ == "__main__":
    unittest.main()
