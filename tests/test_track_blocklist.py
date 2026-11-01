import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("track_blocklist", Path(__file__).parents[1] / "videl/utils/track_blocklist.py")
blocklist = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blocklist)


class TrackBlocklistTests(unittest.TestCase):
    def test_matches_titles_and_artist_metadata_case_insensitively(self):
        entries = [
            {"kind": "track", "value": "Bad Track"},
            {"kind": "artist", "value": "Some Artist"},
        ]
        self.assertEqual(blocklist.matches(entries, {"title": "BAD TRACK (Live)"})["kind"], "track")
        self.assertEqual(blocklist.matches(entries, {"title": "Good Song", "artists": ["Some Artist", "Guest"]})["kind"], "artist")
        self.assertEqual(blocklist.matches(entries, {"title": "Some Artist - New Song"})["kind"], "artist")
        self.assertIsNone(blocklist.matches(entries, {"title": "Allowed Song", "artist": "Allowed Artist"}))

    def test_add_remove_validate_and_bound_entries(self):
        items = blocklist.add([], "track", "Song")
        self.assertEqual(blocklist.add(items, "track", " song "), items)
        self.assertEqual(blocklist.remove(items, 1), [])
        with self.assertRaises(ValueError): blocklist.add([], "album", "Name")
        with self.assertRaises(ValueError): blocklist.add([], "artist", "x" * (blocklist.MAX_TEXT + 1))
        for index in range(blocklist.MAX_ENTRIES - 1):
            items = blocklist.add(items, "artist", f"Artist {index}")
        with self.assertRaises(ValueError): blocklist.add(items, "artist", "overflow")

    def test_corrupt_saved_values_are_ignored(self):
        self.assertEqual(blocklist.normalize([None, {"kind": "artist", "value": " A "}, {"kind": "x", "value": "B"}]),
                         [{"kind": "artist", "value": "A"}])
