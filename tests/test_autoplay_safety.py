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
