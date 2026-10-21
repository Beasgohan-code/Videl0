"""Boot-time index contract.

Every panel screen reads per-group documents. If an index silently stops being
created, the panel still works on a small fleet and quietly degrades on a real
one, so the names are asserted rather than assumed.
"""
import unittest

import mongomock

from videl.utils import db as database


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl

    def test_every_declared_index_is_created_once(self):
        created = database.ensure_indexes(self.db)
        self.assertIn("mgmt_chat_settings:chat_id", created)
        self.assertIn("mgmt_warnings:chat_id+user_id", created)
        self.assertIn("mgmt_join_requests:chat_id+status", created)
        self.assertIn("mgmt_reports:chat_id+status", created)
        self.assertIn("disabled_cmds:chat+cmd", created)
        self.assertIn("scheduled_posts:owner_id+status+due_at", created)
        names = set(self.db["mgmt_reports"].index_information())
        self.assertIn("chat_id_1_status_1", names)
        # Idempotent: a second boot must not raise or duplicate work.
        again = database.ensure_indexes(self.db)
        self.assertEqual(set(created), set(again))

    def test_a_missing_database_is_not_an_error(self):
        self.assertEqual(database.ensure_indexes(None), {})


if __name__ == "__main__":
    unittest.main()
