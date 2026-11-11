import unittest
from unittest.mock import patch

from videl.modules import play


class MusicPickerCacheTests(unittest.TestCase):
    def setUp(self):
        self.previous = dict(play._search_cache)
        play._search_cache.clear()
        self.addCleanup(self._restore_cache)

    def _restore_cache(self):
        play._search_cache.clear()
        play._search_cache.update(self.previous)

    def test_store_prunes_expired_entries(self):
        play._search_cache["expired"] = {"ts": 100.0}
        play._search_cache["current"] = {"ts": 299.0}

        play._store_search_cache("new", {"ts": 300.0}, now=300.0)

        self.assertNotIn("expired", play._search_cache)
        self.assertIn("current", play._search_cache)
        self.assertIn("new", play._search_cache)

    def test_store_evicts_oldest_entry_at_capacity(self):
        play._search_cache["first"] = {"ts": 300.0}
        play._search_cache["second"] = {"ts": 300.0}
        with patch.object(play, "_SEARCH_CACHE_MAX_ENTRIES", 2):
            play._store_search_cache("third", {"ts": 300.0}, now=300.0)

        self.assertNotIn("first", play._search_cache)
        self.assertEqual(list(play._search_cache), ["second", "third"])


if __name__ == "__main__":
    unittest.main()
