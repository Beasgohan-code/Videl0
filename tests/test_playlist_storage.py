import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from videl.utils import db


class PlaylistStorageTests(unittest.TestCase):
    def test_save_reports_unacknowledged_database_write_as_failure(self):
        collection = Mock()
        collection.update_one.return_value = NS(acknowledged=False)
        with patch.object(db, "_col", return_value=collection):
            self.assertFalse(db.save_playlist(123, "favorites", [{"title": "Track"}]))

    def test_read_distinguishes_unavailable_storage_from_missing_playlist(self):
        with patch.object(db, "_col", return_value=None):
            with self.assertRaises(RuntimeError):
                db.get_playlist(123, "favorites")
            with self.assertRaises(RuntimeError):
                db.list_playlists(123)
            with self.assertRaises(RuntimeError):
                db.delete_playlist(123, "favorites")

    def test_read_write_errors_are_not_returned_as_missing_data(self):
        collection = Mock()
        collection.find_one.side_effect = RuntimeError("read failed")
        collection.find.side_effect = RuntimeError("list failed")
        collection.delete_one.side_effect = RuntimeError("delete failed")
        with patch.object(db, "_col", return_value=collection):
            with self.assertRaises(db.PlaylistStorageError):
                db.get_playlist(123, "favorites")
            with self.assertRaises(db.PlaylistStorageError):
                db.list_playlists(123)
            with self.assertRaises(db.PlaylistStorageError):
                db.delete_playlist(123, "favorites")

    def test_save_reports_acknowledged_write_as_success(self):
        collection = Mock()
        collection.update_one.return_value = NS(acknowledged=True)
        with patch.object(db, "_col", return_value=collection):
            self.assertTrue(db.save_playlist(123, "favorites", [{"title": "Track"}]))

    def test_save_reports_missing_collection_or_exception_as_failure(self):
        with patch.object(db, "_col", return_value=None):
            self.assertFalse(db.save_playlist(123, "favorites", []))

        collection = Mock()
        collection.update_one.side_effect = RuntimeError("storage unavailable")
        with patch.object(db, "_col", return_value=collection):
            self.assertFalse(db.save_playlist(123, "favorites", []))


if __name__ == "__main__":
    unittest.main()
