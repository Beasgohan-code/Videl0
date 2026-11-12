import unittest
from unittest.mock import AsyncMock, patch

from videl.utils import youtube


class YouTubeSearchDurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_numeric_result_does_not_abort_valid_search_results(self):
        rows = [
            {"id": "abcdefghijk", "title": "Live stream", "duration": "LIVE"},
            {"id": "lmnopqrstuv", "title": "Valid track", "duration": "1:02"},
        ]
        search = type("Search", (), {"next": AsyncMock(return_value={"result": rows})})()
        with patch.object(youtube, "VideosSearch", return_value=search):
            results = await youtube.search_yt_multi("test", limit=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["duration"], "LIVE")
        self.assertEqual(results[0]["duration_iso"], "PT0M0S")
        self.assertEqual(results[1]["duration_iso"], "PT1M2S")

    async def test_duration_parser_accepts_supported_colon_forms_and_rejects_bad_segments(self):
        cases = {
            "3600": 3600,
            "61:02": 3662,
            "1:02:03": 3723,
            "LIVE": 0,
            "1:60": 0,
            "1:02:60": 0,
            "1::2": 0,
            "-1:02": 0,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(youtube._parse_search_duration(value), expected)


if __name__ == "__main__":
    unittest.main()
