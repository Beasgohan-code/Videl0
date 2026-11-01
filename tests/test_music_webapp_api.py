import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import mongomock
from flask import Flask

from videl.api import eldian_routes
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
        eldian_routes._MUSIC_TASKS.clear()

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

    def test_status_requires_internal_auth_and_valid_task_id(self):
        denied = self.client.get("/internal/music/status?task_id=0123456789abcdef")
        malformed = self.client.get("/internal/music/status?task_id=bad", headers=self.headers)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(malformed.status_code, 400)

    def test_status_survives_process_local_registry_loss_when_database_is_available(self):
        task_id = "persisted-task-0123456789012345"
        db = mongomock.MongoClient().videl
        with patch("videl.utils.db.get_db", return_value=db):
            eldian_routes._set_music_task(task_id, "abcdefghijk", "ready", size_bytes=2048)
            eldian_routes._MUSIC_TASKS.clear()
            response = self.client.get(f"/internal/music/status?task_id={task_id}", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["task"]["status"], "ready")
        self.assertEqual(response.json["task"]["durability"], "database")
        self.assertEqual(response.json["task"]["size_bytes"], 2048)
        self.assertNotIn("path", response.json["task"])

    def test_status_reports_preparation_failure_without_provider_details(self):
        task_id = "0123456789abcdef0123456789abcdef"
        with patch("videl.utils.youtube.download_song", new=AsyncMock(return_value=None)):
            failed = self.client.get(f"/internal/music/track/abcdefghijk?task_id={task_id}", headers=self.headers)
        status = self.client.get(f"/internal/music/status?task_id={task_id}", headers=self.headers)
        self.assertEqual(failed.status_code, 502)
        self.assertEqual(status.json["task"]["status"], "failed")
        self.assertIn("configured downloaders", status.json["task"]["error"])
        self.assertNotIn("provider key", status.json["task"]["error"].lower())

    def test_status_reports_prepared_size_without_claiming_delivery(self):
        task_id = "fedcba9876543210fedcba9876543210"
        with tempfile.TemporaryDirectory() as directory:
            track = Path(directory) / "track.mp3"
            track.write_bytes(b"prepared audio")
            with patch("videl.utils.youtube.download_song", new=AsyncMock(return_value=str(track))):
                response = self.client.get(f"/internal/music/track/abcdefghijk?task_id={task_id}", headers=self.headers)
            status = self.client.get(f"/internal/music/status?task_id={task_id}", headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(status.json["task"]["status"], "ready")
            self.assertEqual(status.json["task"]["size_bytes"], len(b"prepared audio"))
            self.assertNotIn("path", status.json["task"])
            response.close()

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

    def test_track_supports_http_range_requests_for_seeking(self):
        with tempfile.TemporaryDirectory() as directory:
            track = Path(directory) / "track.mp3"
            track.write_bytes(b"0123456789")
            with patch("videl.utils.youtube.download_song", new=AsyncMock(return_value=str(track))):
                response = self.client.get("/internal/music/track/abcdefghijk", headers={**self.headers, "Range": "bytes=2-5"})
            self.assertEqual(response.status_code, 206)
            self.assertEqual(response.headers.get("Content-Range"), "bytes 2-5/10")
            self.assertEqual(response.get_data(), b"2345")
            response.close()


if __name__ == "__main__":
    unittest.main()
