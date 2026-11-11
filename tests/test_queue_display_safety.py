import unittest
from types import SimpleNamespace
from unittest.mock import patch

from videl.app.music import view_queue


class QueueDisplaySafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_malformed_queue_rows_are_ignored_without_mutating_queue(self):
        tracks = [
            {"title": "Current", "duration": "3:00"},
            None,
            "not-a-track-record",
            {"title": "Next", "duration": "2:00"},
        ]
        ctx = SimpleNamespace(message=SimpleNamespace(chat=SimpleNamespace(id=-99022)))
        with patch("videl.app.music.queue.get_queue", return_value=tracks), \
             patch("videl.app.music.player.is_paused", return_value=False), \
             patch("videl.app.music.player.get_loop", return_value="off"):
            screen = await view_queue(ctx)

        self.assertIsNotNone(screen)
        self.assertEqual(tracks[1], None)
        self.assertEqual(tracks[2], "not-a-track-record")


if __name__ == "__main__":
    unittest.main()
