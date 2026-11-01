import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.core import call as call_events, playback_state, queue


class ExternalCallLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.chat_id = -1001234567890
        self.song = {"title": "Lifecycle test", "file_path": None}
        queue.clear_queue(self.chat_id)
        playback_state.forget(self.chat_id)
        playback_state.cancel_expected_voice_exit(self.chat_id)

    def tearDown(self):
        queue.clear_queue(self.chat_id)
        playback_state.forget(self.chat_id)
        playback_state.cancel_expected_voice_exit(self.chat_id)

    async def test_external_call_end_clears_ghost_queue_and_notifies(self):
        queue.add_to_queue(self.chat_id, self.song)
        playback_state.acknowledged(self.chat_id, self.song)
        notice = AsyncMock()
        with patch.object(call_events.player, "stop_progress") as stop_progress, \
             patch("videl.core.autoplay.stop_autoplay") as stop_autoplay, \
             patch.object(call_events, "cleanup") as cleanup, \
             patch("videl.utils.command_ui.rich_send", notice):
            await call_events.on_call_left(None, SimpleNamespace(chat_id=self.chat_id, status="CLOSED_VOICE_CHAT"))
        self.assertEqual(queue.get_queue(self.chat_id), [])
        self.assertNotIn(self.chat_id, playback_state.sessions)
        stop_progress.assert_called_once_with(self.chat_id)
        stop_autoplay.assert_called_once_with(self.chat_id)
        cleanup.assert_called_once_with([self.song])
        notice.assert_awaited_once()

    async def test_our_own_stop_update_does_not_clear_or_announce_twice(self):
        queue.add_to_queue(self.chat_id, self.song)
        playback_state.acknowledged(self.chat_id, self.song)
        playback_state.expect_voice_exit(self.chat_id)
        notice = AsyncMock()
        with patch.object(call_events.player, "stop_progress") as stop_progress, \
             patch("videl.utils.command_ui.rich_send", notice):
            await call_events.on_call_left(None, SimpleNamespace(chat_id=self.chat_id, status="LEFT_GROUP"))
        self.assertEqual(queue.get_queue(self.chat_id), [self.song])
        self.assertIn(self.chat_id, playback_state.sessions)
        stop_progress.assert_not_called()
        notice.assert_not_awaited()
