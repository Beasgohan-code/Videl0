import os
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch, AsyncMock

from videl.modules import downloader
from videl.modules.downloader import _get_yt_dlp_opts
from videl.utils import youtube


class DownloaderOptionsTests(unittest.IsolatedAsyncioTestCase):
    def test_missing_explicit_cookie_path_is_not_passed_to_ytdlp(self):
        with patch.dict(os.environ, {"YTDLP_COOKIES": "cookies.txt", "YT_COOKIES_FILE": ""}, clear=False):
            opts = _get_yt_dlp_opts()
        self.assertNotIn("cookiefile", opts)

    def test_real_netscape_auth_cookie_is_used_only_from_explicit_path(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / "auth.txt"
            cookie.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tsecret-value\n")
            with patch.dict(os.environ, {"YTDLP_COOKIES": str(cookie), "YT_COOKIES_FILE": ""}, clear=False):
                opts = _get_yt_dlp_opts()
                self.assertEqual(youtube._cookies_path(), str(cookie))
        self.assertEqual(opts.get("cookiefile"), str(cookie))

    def test_working_directory_cookie_file_is_never_discovered_or_used_by_relative_path(self):
        names = {"YTDLP_COOKIES": "", "YT_COOKIES_FILE": "", "COOKIES_PATH": "", "YOUTUBE_COOKIES_FILE": ""}
        previous_directory = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / "cookies.txt"
            cookie.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tsecret-value\n")
            try:
                os.chdir(directory)
                with patch.dict(os.environ, names, clear=False):
                    self.assertNotIn("cookiefile", _get_yt_dlp_opts())
                    self.assertIsNone(youtube._cookies_path())
                with patch.dict(os.environ, {"YTDLP_COOKIES": "cookies.txt", "YT_COOKIES_FILE": ""}, clear=False):
                    self.assertNotIn("cookiefile", _get_yt_dlp_opts())
                    self.assertIsNone(youtube._cookies_path())
            finally:
                os.chdir(previous_directory)

    def test_explicit_cookie_path_inside_checkout_is_rejected(self):
        from videl.utils import cookie_security

        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / "auth.txt"
            cookie.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tsecret-value\n")
            with patch.object(cookie_security, "_REPOSITORY_ROOT", Path(directory)):
                self.assertIsNone(cookie_security.configured_cookie_path({"YTDLP_COOKIES": str(cookie)}))

    def test_cookie_paths_and_contents_are_never_written_to_downloader_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / "private-auth.txt"
            cookie.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tsecret-value\n")
            with patch.dict(os.environ, {"YTDLP_COOKIES": str(cookie), "YT_COOKIES_FILE": ""}, clear=False):
                with self.assertLogs("videl.downloader", level="DEBUG") as captured:
                    opts = _get_yt_dlp_opts()
            self.assertIn("cookiefile", opts)
            output = "\\n".join(captured.output)
            self.assertNotIn(str(cookie), output)
            self.assertNotIn("secret-value", output)

    def test_malformed_cookie_file_is_rejected_even_if_it_mentions_auth_cookie_names(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / "bad.txt"
            cookie.write_text("SID appears in a comment, not a Netscape auth row\n")
            with patch.dict(os.environ, {"YTDLP_COOKIES": str(cookie), "YT_COOKIES_FILE": ""}, clear=False):
                self.assertNotIn("cookiefile", _get_yt_dlp_opts())
                self.assertIsNone(youtube._cookies_path())

    def test_docker_and_git_context_ignore_cookie_jars(self):
        for filename in (".gitignore", ".dockerignore"):
            text = Path(filename).read_text()
            for pattern in ("cookies.txt", "cookies*.txt", "*.cookie", "*.cookies"):
                self.assertIn(pattern, text)

    def test_eldian_video_downloader_uses_the_same_external_path_policy(self):
        from videl.api import eldian_routes

        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / "auth.txt"
            cookie.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tsecret-value\n")
            captured = {}

            class FakeYDL:
                def __init__(self, options):
                    captured.update(options)

                def __enter__(self):
                    return self

                def __exit__(self, *_):
                    return False

                def extract_info(self, _url, download=True):
                    return {"id": "abcdefghijk"}

                def prepare_filename(self, _info):
                    return str(Path(directory) / "result.mp4")

            with patch.object(eldian_routes.yt_dlp, "YoutubeDL", FakeYDL), patch.dict(
                os.environ, {"YTDLP_COOKIES": str(cookie), "YT_COOKIES_FILE": ""}, clear=False
            ):
                eldian_routes._download("abcdefghijk", video=True, directory=Path(directory))
            self.assertEqual(captured.get("cookiefile"), str(cookie))

    def test_does_not_force_deprecated_player_clients_or_chunking(self):
        opts = _get_yt_dlp_opts()
        self.assertNotIn("extractor_args", opts)
        self.assertNotIn("http_chunk_size", opts)

    def test_song_metadata_helpers_use_real_values_and_safe_block_word_boundaries(self):
        self.assertEqual(downloader._duration_label(3661), "1:01:01")
        self.assertEqual(downloader._duration_label(None), "Unknown")
        self.assertEqual(downloader._media_title({"track": "Live Cut", "title": "Upload"}, Path("fallback.mp3")), "Live Cut")
        self.assertTrue(downloader._blocked_request("find explicit content", ["explicit content"]))
        self.assertFalse(downloader._blocked_request("Essex is a place", ["sex"]))
        self.assertTrue(downloader._blocked_request("play SEX tonight", ["sex"]))

    async def test_download_can_return_its_extractor_metadata_without_a_second_search(self):
        with tempfile.TemporaryDirectory() as directory:
            info = {"title": "Track", "artist": "Artist", "duration": 123}

            class FakeYDL:
                def __init__(self, options):
                    self.options = options

                def __enter__(self):
                    return self

                def __exit__(self, *_):
                    return False

                def extract_info(self, url, download=True):
                    output = self.options["outtmpl"]
                    path = Path(output.replace("%(title).80s", "Track").replace("%(id)s", "x").replace("%(ext)s", "mp3"))
                    path.write_bytes(b"x" * 2048)
                    return info

                def prepare_filename(self, metadata):
                    return self.options["outtmpl"].replace("%(title).80s", "Track").replace("%(id)s", "x").replace("%(ext)s", "mp3")

            fake_module = ModuleType("yt_dlp")
            fake_module.YoutubeDL = FakeYDL
            with patch.object(downloader, "DOWNLOAD_DIR", Path(directory)), \
                 patch.object(downloader, "_is_url", return_value=True), \
                 patch.object(downloader, "_get_yt_dlp_opts", side_effect=lambda **kw: {"outtmpl": kw["out_path"]}), \
                 patch.dict("sys.modules", {"yt_dlp": fake_module}), \
                 patch.object(downloader, "_search_youtube", new=AsyncMock()) as search:
                path, result = await downloader._download_media("https://youtube.com/watch?v=abc", include_info=True)
                self.assertEqual(result, info)
                self.assertEqual(path.stat().st_size, 2048)
                search.assert_not_awaited()
                downloader._cleanup_download(path)

    async def test_song_falls_back_to_configured_youtube_audio_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "shared-cache.mp3"
            source.write_bytes(b"a" * 4096)
            temp_downloads = root / "requests"
            temp_downloads.mkdir()

            class FailingYDL:
                def __init__(self, _options):
                    pass

                def __enter__(self):
                    return self

                def __exit__(self, *_):
                    return False

                def extract_info(self, _url, download=True):
                    raise RuntimeError("YouTube player extraction failed")

            fake_module = ModuleType("yt_dlp")
            fake_module.YoutubeDL = FailingYDL
            with patch.object(downloader, "DOWNLOAD_DIR", temp_downloads), \
                 patch.object(downloader, "_get_yt_dlp_opts", side_effect=lambda **kw: {"outtmpl": kw["out_path"]}), \
                 patch.dict("sys.modules", {"yt_dlp": fake_module}), \
                 patch("videl.utils.youtube.resolve_stream", new=AsyncMock(return_value=str(source))) as fallback:
                path, info = await downloader._download_media(
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ", include_info=True
                )
            fallback.assert_awaited_once_with("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            self.assertEqual(path.read_bytes(), source.read_bytes())
            self.assertEqual(info["title"], "shared-cache")
            self.assertTrue(path.is_relative_to(temp_downloads))
            downloader._cleanup_download(path)
            self.assertTrue(source.exists(), "request cleanup must not remove the shared provider cache")

    async def test_no_search_result_removes_the_empty_temporary_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(downloader, "DOWNLOAD_DIR", Path(directory)), \
                 patch.object(downloader, "_is_url", return_value=False), \
                 patch.object(downloader, "_search_youtube", new=AsyncMock(return_value=[])):
                with self.assertRaises(ValueError):
                    await downloader._download_media("missing title")
            self.assertEqual(list(Path(directory).iterdir()), [])
