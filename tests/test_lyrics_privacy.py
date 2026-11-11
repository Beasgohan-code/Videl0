import unittest
from unittest.mock import patch

from videl.modules import lyrics


class LyricsPrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_exception_and_query_are_not_written_to_logs(self):
        query = "private conversation details"
        private_url = "https://lrclib.net/api/search?q=private conversation details&token=do-not-log"
        with patch.object(lyrics.aiohttp, "ClientSession", side_effect=RuntimeError(private_url)), \
             patch.object(lyrics.LOGGER, "warning") as warning:
            result = await lyrics.fetch_lyrics(query)

        self.assertIsNone(result)
        warning.assert_called_once()
        rendered = " ".join(map(str, warning.call_args.args))
        self.assertNotIn(query, rendered)
        self.assertNotIn("do-not-log", rendered)
        self.assertNotIn("lrclib.net", rendered)


if __name__ == "__main__":
    unittest.main()
