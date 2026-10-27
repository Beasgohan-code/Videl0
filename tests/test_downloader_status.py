import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from videl.utils.downloader_status import DEFAULT_SHRUTI_URL, downloader_status
from videl.utils import youtube


class DownloaderStatusTests(unittest.TestCase):
    def test_default_host_reports_that_key_is_needed_without_exposing_secrets(self):
        status = downloader_status({})
        self.assertEqual(status["primary"], "shruti")
        self.assertEqual(status["shruti"], {"state": "needs_api_key", "configured": False, "keys_configured": 0})
        self.assertEqual(status["fallbacks"], ["eldian", "local_yt_dlp"])
        self.assertNotIn("api.shrutibots.in", repr(status))
        self.assertEqual(DEFAULT_SHRUTI_URL, "https://api.shrutibots.in")

    def test_https_endpoint_and_key_report_configured_without_returning_key(self):
        secret = "test-secret-never-return-this"
        status = downloader_status({"YT_API_URL": "https://media.example/api/", "YT_API_KEY": secret})
        self.assertEqual(status["shruti"]["state"], "configured")
        self.assertTrue(status["shruti"]["configured"])
        self.assertEqual(status["shruti"]["keys_configured"], 1)
        self.assertNotIn(secret, repr(status))

    def test_fallback_key_is_counted_without_exposing_secret(self):
        secret = "fallback-secret-never-return-this"
        status = downloader_status({"YT_API_URL": "https://media.example", "YT_API_KEY_FALLBACK": secret})
        self.assertTrue(status["shruti"]["configured"])
        self.assertEqual(status["shruti"]["keys_configured"], 1)
        self.assertNotIn(secret, repr(status))

    def test_http_endpoint_fails_closed(self):
        status = downloader_status({"YT_API_URL": "http://media.example", "YT_API_KEY": "secret"})
        self.assertEqual(status["shruti"]["state"], "invalid_url")
        self.assertFalse(status["shruti"]["configured"])


class ShrutiPlaybackOrderTests(unittest.IsolatedAsyncioTestCase):
    def test_quota_detection_is_narrow(self):
        self.assertTrue(youtube._shruti_quota_exhausted(429, ""))
        self.assertTrue(youtube._shruti_quota_exhausted(403, "daily quota exceeded"))
        self.assertTrue(youtube._shruti_quota_exhausted(200, '{"error":"rate limit reached"}'))
        self.assertFalse(youtube._shruti_quota_exhausted(403, "invalid api key"))
        self.assertFalse(youtube._shruti_quota_exhausted(500, "server busy"))

    async def test_fallback_key_is_used_only_after_quota_response(self):
        class Content:
            async def iter_chunked(self, _size):
                yield b"x" * 2048

        class Response:
            def __init__(self, status, content_type, message=""):
                self.status = status
                self.headers = {"Content-Type": content_type}
                self.content_length = 2048 if status == 200 else 0
                self.content = Content()
                self._message = message

            async def text(self):
                return self._message

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

        class Session:
            def __init__(self, **_kwargs):
                self.requests = []
                self.responses = [
                    Response(429, "application/json", "daily quota exceeded"),
                    Response(200, "audio/mpeg"),
                ]

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            def get(self, _url, *, params, allow_redirects):
                self.requests.append(dict(params))
                return self.responses.pop(0)

        with tempfile.TemporaryDirectory() as directory:
            session = Session()
            with (
                patch.object(youtube, "DOWNLOAD_DIR", directory),
                patch.object(youtube, "YT_API_URL", "https://media.example"),
                patch.object(youtube, "YT_API_KEY", "primary-secret"),
                patch.object(youtube, "YT_API_KEY_FALLBACK", "backup-secret"),
                patch.object(youtube.aiohttp, "ClientSession", return_value=session),
            ):
                result = await youtube._download_via_external_api("dQw4w9WgXcQ")
                self.assertTrue(result.endswith(".external.mp3"))
                self.assertTrue(os.path.isfile(result))
        self.assertEqual([call["api_key"] for call in session.requests], ["primary-secret", "backup-secret"])

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
