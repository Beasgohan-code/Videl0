import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.app import music
from videl.app.routes import COMMANDS
from videl.core import player
from videl.utils import listening_recap


class ListeningHistoryTests(unittest.TestCase):
    def setUp(self):
        listening_recap._history.clear()

    def test_history_is_bounded_and_omits_requester_identity(self):
        at = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
        for index in range(55):
            listening_recap.record(-1001, {
                "title": f"Track {index}", "duration": "3:21",
                "requester": "Member Name", "requester_id": 987654,
            }, at=at)
        rows = listening_recap.get(-1001)
        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[0]["title"], "Track 5")
        self.assertNotIn("requester", rows[-1])
        self.assertNotIn("requester_id", rows[-1])

    def test_history_caps_number_of_chat_buckets(self):
        for chat_id in range(300):
            listening_recap.record(chat_id, {"title": "Track"})
        self.assertLessEqual(len(listening_recap._history), 256)
        self.assertEqual(listening_recap.get(0), [])
        self.assertEqual(len(listening_recap.get(299)), 1)


class VoiceVolumeTests(unittest.IsolatedAsyncioTestCase):
    CHAT = -100123

    async def asyncSetUp(self):
        player._voice_volume.clear()

    async def test_volume_callback_updates_voice_only_after_engine_ack(self):
        ctx = SimpleNamespace(
            message=SimpleNamespace(chat=SimpleNamespace(id=self.CHAT)),
            command=SimpleNamespace(name="volumeup", arguments=""),
        )
        with patch("videl.app.music.queue.peek_current", return_value={"title": "Track"}), \
             patch("videl.app.music.call_py.change_volume_call", new=AsyncMock(return_value=None)) as change, \
             patch("videl.app.music.player.refresh_np_ui", new=AsyncMock()):
            screen = await music.control(ctx)
        change.assert_awaited_once_with(self.CHAT, 120)
        self.assertEqual(player.volume_percent(self.CHAT), 120)
        self.assertIn("120%", screen.html)

    async def test_failed_voice_volume_change_does_not_change_reported_level(self):
        player.set_volume_percent(self.CHAT, 100)
        ctx = SimpleNamespace(
            message=SimpleNamespace(chat=SimpleNamespace(id=self.CHAT)),
            command=SimpleNamespace(name="volumedown", arguments=""),
        )
        with patch("videl.app.music.queue.peek_current", return_value={"title": "Track"}), \
             patch("videl.app.music.call_py.change_volume_call", new=AsyncMock(side_effect=RuntimeError("offline"))):
            with self.assertRaises(RuntimeError):
                await music.control(ctx)
        self.assertEqual(player.volume_percent(self.CHAT), 100)

    async def test_volume_state_is_clamped_and_bounded_by_chat_count(self):
        self.assertEqual(player.set_volume_percent(self.CHAT, 999), 200)
        self.assertEqual(player.set_volume_percent(self.CHAT, -1), 20)
        for chat_id in range(300):
            player.set_volume_percent(chat_id, 80)
        self.assertLessEqual(len(player._voice_volume), 256)

    async def test_volume_commands_are_admin_only_and_buttons_use_supported_premium_icons(self):
        from videl.app.music_callbacks import _ACTIONS
        policies = {item.name: item.policy for item in COMMANDS}
        self.assertEqual(_ACTIONS["show_history"], "history")
        self.assertEqual(_ACTIONS["volume_up"], "volumeup")
        self.assertEqual(_ACTIONS["volume_down"], "volumedown")
        self.assertEqual(policies["history"], "group")
        self.assertEqual(policies["volumeup"], "admin")
        self.assertEqual(policies["volumedown"], "admin")
        callbacks = {
            button.callback_data: button
            for row in player._now_playing_kb(self.CHAT).inline_keyboard
            for button in row
        }
        for callback in ("volume_up", "volume_down", "show_history"):
            self.assertIn(callback, callbacks)
            self.assertTrue(callbacks[callback].icon_custom_emoji_id)


if __name__ == "__main__":
    unittest.main()
