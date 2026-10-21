import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from videl.modules.downloader import _get_yt_dlp_opts


class DownloaderOptionsTests(unittest.TestCase):
    def test_placeholder_cookie_template_is_not_passed_to_ytdlp(self):
        with patch.dict(os.environ, {"YTDLP_COOKIES": "cookies.txt", "YT_COOKIES_FILE": ""}, clear=False):
            opts = _get_yt_dlp_opts()
        self.assertNotIn("cookiefile", opts)

    def test_real_netscape_auth_cookie_is_used(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / "auth.txt"
            cookie.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tsecret-value\n")
            with patch.dict(os.environ, {"YTDLP_COOKIES": str(cookie), "YT_COOKIES_FILE": ""}, clear=False):
                opts = _get_yt_dlp_opts()
        self.assertEqual(opts.get("cookiefile"), str(cookie))

    def test_does_not_force_deprecated_player_clients_or_chunking(self):
        opts = _get_yt_dlp_opts()
        self.assertNotIn("extractor_args", opts)
        self.assertNotIn("http_chunk_size", opts)
