import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from videl.utils import db


class LinkedChannelStorageTests(unittest.TestCase):
    def test_link_write_reports_acknowledged_success(self):
        collection = Mock()
        collection.update_one.return_value = NS(acknowledged=True)

        with patch.object(db, "_col", return_value=collection):
            self.assertTrue(db.set_linked_channel(-100101, -100202))

        collection.update_one.assert_called_once_with(
            {"chat_id": -100101}, {"$set": {"linked_channel": -100202}}, upsert=True
        )

    def test_link_write_reports_missing_collection_and_database_failure(self):
        with patch.object(db, "_col", return_value=None):
            self.assertFalse(db.set_linked_channel(-100101, -100202))
            self.assertFalse(db.clear_linked_channel(-100101))

        collection = Mock()
        collection.update_one.side_effect = RuntimeError("storage unavailable")
        with patch.object(db, "_col", return_value=collection):
            self.assertFalse(db.set_linked_channel(-100101, -100202))
            self.assertFalse(db.clear_linked_channel(-100101))

    def test_clear_writes_null_and_reports_acknowledgement(self):
        collection = Mock()
        collection.update_one.return_value = NS(acknowledged=True)

        with patch.object(db, "_col", return_value=collection):
            self.assertTrue(db.clear_linked_channel(-100101))

        collection.update_one.assert_called_once_with(
            {"chat_id": -100101}, {"$set": {"linked_channel": None}}, upsert=True
        )


if __name__ == "__main__":
    unittest.main()
