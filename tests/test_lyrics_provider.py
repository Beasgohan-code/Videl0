import unittest
from unittest.mock import patch

from videl.modules import lyrics


class _Response:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def json(self):
        return self.payload


class _Session:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def get(self, *_args, **_kwargs):
        return _Response(self.payload)


class LyricsProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_malformed_provider_rows_are_skipped_without_aborting_results(self):
        payload = [
            None,
            "not an object",
            {"plainLyrics": 42},
            {"trackName": "A Valid Track", "artistName": "Artist", "plainLyrics": "These are enough valid lyrics to return."},
        ]
        with patch.object(lyrics.aiohttp, "ClientSession", return_value=_Session(payload)):
            result = await lyrics.fetch_lyrics("A Valid Track")

        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "A Valid Track")
        self.assertEqual(result["lyrics"], "These are enough valid lyrics to return.")

    async def test_malformed_only_provider_rows_return_no_result(self):
        with patch.object(lyrics.aiohttp, "ClientSession", return_value=_Session([None, "bad", {"plainLyrics": 9}])):
            result = await lyrics.fetch_lyrics("A Valid Track")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
