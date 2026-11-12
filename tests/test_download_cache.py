"""Bounded playback-cache indexing, eviction and active-file safety."""
import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from videl.utils import youtube


class DownloadCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.patch_dir = patch.object(youtube, "DOWNLOAD_DIR", str(self.directory))
        self.patch_dir.start()
        self.addCleanup(self.patch_dir.stop)
        youtube._reset_download_cache()
        self.addCleanup(youtube._reset_download_cache)

    def _media(self, video_id, extension, size=2048):
        path = self.directory / f"{video_id}.{extension}"
        path.write_bytes(b"x" * size)
        return path

    def test_file_lookup_indexes_directory_once_instead_of_scanning_per_id(self):
        audio = self._media("dQw4w9WgXcQ", "mp3")
        self._media("9bZkp7q19f0", "mp4")
        original_scandir = os.scandir
        with patch.object(youtube.os, "scandir", wraps=original_scandir) as scan:
            self.assertEqual(youtube._find_file("dQw4w9WgXcQ", video=False), str(audio))
            first_scan_count = scan.call_count
            self.assertGreater(first_scan_count, 0)
            self.assertEqual(youtube._find_file("9bZkp7q19f0", video=True), str(self.directory / "9bZkp7q19f0.mp4"))
            self.assertEqual(scan.call_count, first_scan_count)

    def test_byte_eviction_never_removes_an_active_file(self):
        active = self._media("dQw4w9WgXcQ", "mp3")
        incoming = self._media("9bZkp7q19f0", "mp4")
        with patch.object(youtube, "CACHE_MAX_BYTES", 3000):
            youtube._register_cache_file(str(active), "dQw4w9WgXcQ")
            youtube.pin_cache_file(str(active))
            youtube._register_cache_file(str(incoming), "9bZkp7q19f0")
            self.assertTrue(active.exists())
            self.assertTrue(incoming.exists())
            youtube.release_cache_file(str(active))
            youtube._enforce_cache_limits()

        self.assertFalse(active.exists())
        self.assertTrue(incoming.exists())

    def test_resolve_stream_returns_a_releasable_cache_lease(self):
        cached = self._media("dQw4w9WgXcQ", "mp3")
        youtube._register_cache_file(str(cached), "dQw4w9WgXcQ")

        resolved = asyncio.run(youtube.resolve_stream("https://youtu.be/dQw4w9WgXcQ"))

        self.assertEqual(resolved, str(cached))
        self.assertEqual(youtube._active_cache_files[str(cached)], 1)
        youtube.release_cache_file(resolved)
        self.assertNotIn(str(cached), youtube._active_cache_files)

    def test_age_eviction_removes_old_idle_files(self):
        old = self._media("dQw4w9WgXcQ", "mp3")
        old_time = 1_600_000_000
        os.utime(old, (old_time, old_time))
        youtube._register_cache_file(str(old), "dQw4w9WgXcQ")
        youtube._enforce_cache_limits()
        self.assertFalse(old.exists())

    def test_url_lookup_cache_has_a_bounded_lru_size(self):
        files = [self._media(f"{index:011d}".replace("0", "a"), "mp3") for index in range(4)]
        with patch.object(youtube, "FILE_CACHE_MAX_ENTRIES", 2):
            for index, path in enumerate(files):
                youtube._remember_file_url(f"https://youtu.be/{index}", str(path))
        self.assertEqual(len(youtube._file_cache), 2)
        self.assertNotIn("https://youtu.be/0", youtube._file_cache)
        self.assertIn("https://youtu.be/3", youtube._file_cache)


if __name__ == "__main__":
    unittest.main()
