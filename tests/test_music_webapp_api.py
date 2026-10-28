import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from flask import Flask

from videl.api.eldian_routes import register_eldian_routes


class MusicWebAppApiTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        register_eldian_routes(self.app)
        self.client = self.app.test_client()
        self.env = patch.dict("os.environ", {"WEBAPP_SECRET": "test-internal-secret"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.headers = {"X-Videl-Internal": "test-internal-secret"}

    def test_search_requires_the_internal_backend_secret(self):
        response = self.client.get("/internal/music/search?q=hello")
        self.assertEqual(response.status_code, 403)

    def test_search_validates_input_before_touching_downloader(self):
        with patch("videl.utils.youtube.search_yt_multi", new=AsyncMock()) as search:
            response = self.client.get("/internal/music/search?q=%20", headers=self.headers)
        self.assertEqual(response.status_code, 400)
        search.assert_not_awaited()

    def test_search_returns_only_safe_track_metadata(self):
        rows = [{
            "video_id": "abcdefghijk",
            "title": "A song",
            "channel": "Artist",
            "duration": "3:21",
            "thumbnail": "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg",
            "url": "https://www.youtube.com/watch?v=abcdefghijk",
            "unsafe_extra": "never returned",
        }]
        with patch("videl.utils.youtube.search_yt_multi", new=AsyncMock(return_value=rows)) as search:
            response = self.client.get("/internal/music/search?q=artist&limit=999", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["tracks"][0]["video_id"], "abcdefghijk")
        self.assertNotIn("unsafe_extra", response.json["tracks"][0])
        search.assert_awaited_once_with("artist", 8)

    def test_track_rejects_invalid_ids_before_downloading(self):
        with patch("videl.utils.youtube.download_song", new=AsyncMock()) as download:
            response = self.client.get("/internal/music/track/not-an-id", headers=self.headers)
        self.assertEqual(response.status_code, 400)
        download.assert_not_awaited()

    def test_track_uses_the_existing_downloader_and_serves_inline_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            track = Path(directory) / "track.mp3"
            track.write_bytes(b"fake mp3 bytes")
            with patch("videl.utils.youtube.download_song", new=AsyncMock(return_value=str(track))):
                response = self.client.get("/internal/music/track/abcdefghijk", headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertIn("inline", response.headers["Content-Disposition"])
            self.assertEqual(response.headers["Cache-Control"], "private, no-store")
            response.close()


if __name__ == "__main__":
    unittest.main()
