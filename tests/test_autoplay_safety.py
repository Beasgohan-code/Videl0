import unittest
from unittest.mock import AsyncMock, patch

from videl.core import autoplay
from videl.core.queue import chat_queues


class AutoplayFailureLoggingTests(unittest.IsolatedAsyncioTestCase):
    chat_id = -99021

    async def asyncSetUp(self):
        chat_queues.pop(self.chat_id, None)
        autoplay.stop_autoplay(self.chat_id)

    async def asyncTearDown(self):
        autoplay.stop_autoplay(self.chat_id)
        chat_queues.pop(self.chat_id, None)

    async def test_missing_provider_title_gets_safe_display_fallback(self):
        result = ("https://www.youtube.com/watch?v=abcdefghijk", None, "PT3M", "")
        with patch.object(autoplay, "search_yt", new=AsyncMock(return_value=result)):
            added = await autoplay.start_autoplay(self.chat_id, "seed", "Listener", 12)

        self.assertEqual(added, 1)
        self.assertEqual(chat_queues[self.chat_id][0]["title"], "Unknown")

    async def test_autoplay_skips_tracks_over_the_configured_duration_limit(self):
        playlist = {"playlist": [
            {"link": "https://www.youtube.com/watch?v=too_long_001", "title": "Too long", "duration": "PT3601S", "thumbnail": ""},
            {"link": "https://www.youtube.com/watch?v=valid000001", "title": "Valid", "duration": "PT60S", "thumbnail": ""},
        ]}
        with (
            patch("config.MAX_DURATION_SECONDS", 1800),
            patch.object(autoplay, "search_yt", new=AsyncMock(return_value=playlist)),
        ):
            added = await autoplay.start_autoplay(self.chat_id, "seed", "Listener", 12)

        self.assertEqual(added, 1)
        self.assertEqual([song["title"] for song in chat_queues[self.chat_id]], ["Valid"])

    async def test_malformed_playlist_rows_do_not_block_later_valid_tracks(self):
        playlist = {"playlist": [
            None,
            {"link": "https://www.youtube.com/watch?v=valid000001", "title": "Valid", "duration": "PT60S", "thumbnail": ""},
        ]}
        with patch.object(autoplay, "search_yt", new=AsyncMock(return_value=playlist)), \
             patch.object(autoplay.random, "shuffle"):
            added = await autoplay.start_autoplay(self.chat_id, "seed", "Listener", 12)

        self.assertEqual(added, 1)
        self.assertEqual([song["title"] for song in chat_queues[self.chat_id]], ["Valid"])

    async def test_non_list_playlist_payload_is_ignored_safely(self):
        with patch.object(autoplay, "search_yt", new=AsyncMock(return_value={"playlist": None})):
            added = await autoplay.start_autoplay(self.chat_id, "seed", "Listener", 12)

        self.assertEqual(added, 0)
        self.assertEqual(chat_queues.get(self.chat_id, []), [])

    async def test_provider_exception_details_and_query_are_not_written_to_logs(self):
        private_query = "private-query-token"
        provider_secret = "api_key=do-not-log-this"
        error = RuntimeError(f"https://provider.example/search?q={private_query}&{provider_secret}")
        with patch.object(autoplay, "search_yt", new=AsyncMock(side_effect=error)), \
             patch.object(autoplay.logger, "warning") as warning:
            await autoplay.start_autoplay(self.chat_id, private_query, "Listener", 12)

        self.assertEqual(warning.call_count, 5)
        for call in warning.call_args_list:
            rendered = " ".join(map(str, call.args))
            self.assertNotIn(private_query, rendered)
            self.assertNotIn(provider_secret, rendered)
            self.assertNotIn("provider.example", rendered)


if __name__ == "__main__":
    unittest.main()
