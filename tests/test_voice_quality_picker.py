import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import config
from videl.core import audio_quality
from videl.modules import voice_admin


class VoiceQualityPickerTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        audio_quality.clear_runtime_quality()

    async def test_command_shows_all_presets_with_current_selection_and_buttons(self):
        msg = NS(
            from_user=NS(id=config.OWNER_ID),
            chat=NS(id=config.OWNER_ID, type=NS(value="private")),
            command=["/voicequality"],
        )
        with patch.object(voice_admin, "rich_reply", new=AsyncMock()) as reply:
            await voice_admin.voice_quality_command(None, msg)
        html = reply.await_args.args[1]
        markup = reply.await_args.kwargs["reply_markup"]
        self.assertIn("Studio · 96 kbps stereo", html)
        self.assertIn("applies to new streams", html)
        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertEqual(
            {button.callback_data for button in buttons},
            {f"voicequality:{name}" for name in voice_admin.PRESETS},
        )
        self.assertTrue(any("High" in button.text and "✓" in button.text for button in buttons))

    async def test_owner_selects_preset_from_private_panel_and_gets_updated_panel(self):
        owner = config.OWNER_ID
        message = NS(
            chat=NS(id=owner, type=NS(value="private")),
            from_user=NS(id=777),
        )
        query = NS(
            data="voicequality:medium",
            message=message,
            from_user=NS(id=owner),
            answer=AsyncMock(),
        )
        client = NS(me=NS(id=777))
        with patch.object(voice_admin, "set_bot_setting", return_value=True) as save, \
             patch.object(voice_admin, "rich_edit", new=AsyncMock()) as edit:
            await voice_admin.voice_quality_callback(client, query)
        save.assert_called_once_with("voice_audio_quality", "medium")
        self.assertEqual(audio_quality.current_quality(), "medium")
        query.answer.assert_awaited_once()
        self.assertIn("Medium · 36 kbps mono", edit.await_args.args[1])
        self.assertIn("Saved for future restarts", edit.await_args.args[1])

    async def test_revoked_sudo_cannot_change_global_quality_from_old_panel(self):
        owner = config.OWNER_ID + 100
        message = NS(
            chat=NS(id=owner, type=NS(value="private")),
            from_user=NS(id=777),
        )
        query = NS(
            data="voicequality:low",
            message=message,
            from_user=NS(id=owner),
            answer=AsyncMock(),
        )
        with patch.object(voice_admin.config, "OWNER_ID", config.OWNER_ID), \
             patch.object(voice_admin, "is_sudo_user", return_value=False), \
             patch.object(voice_admin, "set_bot_setting") as save:
            await voice_admin.voice_quality_callback(NS(me=NS(id=777)), query)
        save.assert_not_called()
        self.assertIsNone(audio_quality._runtime_quality)
        query.answer.assert_awaited_once()
        self.assertTrue(query.answer.await_args.kwargs.get("show_alert"))

    async def test_foreign_or_forwarded_panel_cannot_change_quality(self):
        owner = config.OWNER_ID
        message = NS(
            chat=NS(id=owner, type=NS(value="private")),
            from_user=NS(id=1234),
        )
        query = NS(
            data="voicequality:low",
            message=message,
            from_user=NS(id=owner),
            answer=AsyncMock(),
        )
        with patch.object(voice_admin, "set_bot_setting") as save:
            await voice_admin.voice_quality_callback(NS(me=NS(id=777)), query)
        save.assert_not_called()
        self.assertIsNone(audio_quality._runtime_quality)


if __name__ == "__main__":
    unittest.main()
