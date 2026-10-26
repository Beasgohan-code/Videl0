import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from videl.utils.downloader_status import DEFAULT_SHRUTI_URL, downloader_status
from videl.utils import youtube


class DownloaderStatusTests(unittest.TestCase):
    def test_default_host_reports_that_key_is_needed_without_exposing_secrets(self):
        status = downloader_status({})
        self.assertEqual(status["primary"], "shruti")
        self.assertEqual(status["shruti"], {"state": "needs_api_key", "configured": False})
        self.assertEqual(status["fallbacks"], ["eldian", "local_yt_dlp"])
        self.assertNotIn("api.shrutibots.in", repr(status))
        self.assertEqual(DEFAULT_SHRUTI_URL, "https://api.shrutibots.in")

    def test_https_endpoint_and_key_report_configured_without_returning_key(self):
        secret = "test-secret-never-return-this"
        status = downloader_status({"YT_API_URL": "https://media.example/api/", "YT_API_KEY": secret})
        self.assertEqual(status["shruti"]["state"], "configured")
        self.assertTrue(status["shruti"]["configured"])
        self.assertNotIn(secret, repr(status))

    def test_http_endpoint_fails_closed(self):
        status = downloader_status({"YT_API_URL": "http://media.example", "YT_API_KEY": "secret"})
        self.assertEqual(status["shruti"]["state"], "invalid_url")
        self.assertFalse(status["shruti"]["configured"])


class ShrutiPlaybackOrderTests(unittest.IsolatedAsyncioTestCase):
    async def test_music_download_tries_shruti_before_eldian(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(youtube, "DOWNLOAD_DIR", directory), \
             patch.object(youtube, "_find_file", return_value=None), \
             patch.object(youtube, "_download_via_external_api", new=AsyncMock(return_value="shruti.mp3")) as shruti, \
             patch.object(youtube, "_download_via_eldian", new=AsyncMock()) as eldian:
            result = await youtube.download_song("dQw4w9WgXcQ")
        self.assertEqual(result, "shruti.mp3")
        shruti.assert_awaited_once_with("dQw4w9WgXcQ", video=False)
        eldian.assert_not_awaited()

    async def test_missing_key_error_is_actionable_and_does_not_expose_credentials(self):
        with patch.object(youtube, "_find_file", return_value=None), \
             patch.object(youtube, "download_song", new=AsyncMock(return_value=None)), \
             patch.object(youtube, "downloader_status", return_value={"shruti": {"state": "needs_api_key"}}):
            with self.assertRaises(youtube.MediaDownloadError) as caught:
                await youtube.resolve_stream("dQw4w9WgXcQ")
        self.assertIn("configure YT_API_KEY", str(caught.exception))
        self.assertNotIn("secret", str(caught.exception).lower())
