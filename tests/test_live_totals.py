import importlib
import unittest
from unittest.mock import MagicMock, patch


class LiveTotalsTests(unittest.TestCase):
    def test_counts_come_from_bot_collections(self):
        db_module = importlib.import_module("videl.utils.db")
        database = MagicMock()
        database.__getitem__.return_value = MagicMock()
        collections = {name: MagicMock() for name in ("served_chats", "served_users", "play_stats")}
        database.__getitem__.side_effect = collections.__getitem__
        collections["served_chats"].count_documents.return_value = 14
        collections["served_users"].count_documents.return_value = 15
        collections["play_stats"].aggregate.return_value = [{"total": 72}]
        with patch.object(db_module, "get_db", return_value=database):
            self.assertEqual(db_module.read_live_totals(), {"chats": 14, "users": 15, "plays": 72})
        collections["play_stats"].aggregate.assert_called_once()

    def test_database_error_is_not_reported_as_zero(self):
        db_module = importlib.import_module("videl.utils.db")
        database = MagicMock()
        database.__getitem__.return_value.count_documents.side_effect = RuntimeError("offline")
        with patch.object(db_module, "get_db", return_value=database):
            with self.assertRaises(RuntimeError):
                db_module.read_live_totals()
