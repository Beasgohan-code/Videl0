import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from videl.modules import seek


class SeekReliabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.chat_id = -98761
        self.song = {
            "url": "https://youtube.com/watch?v=abcdefghijk",
            "title": "Test track",
            "duration": "3:00",
            "duration_seconds": 180,
            "requester": "Listener",
        }
        self.status = NS(delete=AsyncMock())

    async def _invoke(self, change_stream):
        call_py = NS(change_stream=change_stream, play=AsyncMock())
        with (
            patch.object(seek, "peek_current", return_value=self.song),
            patch.object(seek, "resolve_stream", new=AsyncMock(return_value="/tmp/seek-test.mp3")),
            patch.object(seek, "release_cache_file") as release,
            patch.object(seek, "call_py", call_py),
            patch.object(seek, "rich_send", new=AsyncMock(return_value=self.status)),
            patch.object(seek, "rich_edit", new=AsyncMock()) as edit,
            patch.object(seek, "set_seek_state") as set_state,
            patch("videl.core.player._np_start", {}),
            patch("videl.core.player._pause_started", {}),
            patch("videl.core.player.set_paused") as set_paused,
        ):
            await seek._seek_to(self.chat_id, 45, NS())
        return call_py, edit, set_state, set_paused, release

    async def test_false_engine_ack_is_not_reported_as_a_successful_seek(self):
        call_py, edit, set_state, set_paused, release = await self._invoke(AsyncMock(return_value=False))

        call_py.change_stream.assert_awaited_once()
        call_py.play.assert_not_awaited()
        edit.assert_awaited_once()
        self.assertIn("not confirmed", edit.await_args.args[1].lower())
        set_state.assert_not_called()
        set_paused.assert_not_called()
        release.assert_called_once_with("/tmp/seek-test.mp3")

    async def test_ambiguous_stream_change_exception_is_not_followed_by_an_unfenced_play(self):
        call_py, edit, set_state, set_paused, release = await self._invoke(
            AsyncMock(side_effect=RuntimeError("transport timed out"))
        )

        call_py.change_stream.assert_awaited_once()
        call_py.play.assert_not_awaited()
        edit.assert_awaited_once()
        self.assertIn("not confirmed", edit.await_args.args[1].lower())
        set_state.assert_not_called()
        set_paused.assert_not_called()
        release.assert_called_once_with("/tmp/seek-test.mp3")

    async def test_confirmed_stream_change_updates_seek_state(self):
        call_py, edit, set_state, set_paused, release = await self._invoke(AsyncMock(return_value=True))

        call_py.change_stream.assert_awaited_once()
        call_py.play.assert_not_awaited()
        edit.assert_not_awaited()
        set_state.assert_called_once_with(self.chat_id, 45)
        set_paused.assert_called_once_with(self.chat_id, False)
        release.assert_called_once_with("/tmp/seek-test.mp3")


if __name__ == "__main__":
    unittest.main()
