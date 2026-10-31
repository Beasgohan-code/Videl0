import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import mongomock

from videl.plugins import group


class AdminActivityTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_is_group_scoped_aggregate_and_content_free(self):
        db = mongomock.MongoClient().videl
        now = datetime.now(timezone.utc)
        db["mgmt_audit"].insert_many([
            {"chat_id": -1001, "actor": 11, "kind": "settings", "action": "lock_links", "ts": now, "details": "secret text"},
            {"chat_id": -1001, "actor": 11, "kind": "settings", "action": "lock_links", "ts": now, "details": "other text"},
            {"chat_id": -1001, "actor": 12, "kind": "moderation", "action": "warn", "ts": now, "details": "private member"},
            {"chat_id": -1001, "actor": None, "kind": "automated", "ts": now},
            {"chat_id": -1001, "actor": 13, "kind": "old", "ts": now - timedelta(days=31)},
            {"chat_id": -2002, "actor": 99, "kind": "ban", "ts": now},
        ])
        ctx = SimpleNamespace(message=SimpleNamespace(chat=SimpleNamespace(id=-1001)))
        with patch.object(group.base, "db", return_value=db):
            result = await group.admin_activity(ctx)

        self.assertIn("Admin 11", result.html)
        self.assertIn("2 events", result.html)
        self.assertIn("lock_links", result.html)
        self.assertIn("Admin 12", result.html)
        for private in ("secret text", "other text", "private member", "Admin 13", "Admin 99"):
            self.assertNotIn(private, result.html)

    async def test_command_is_registered_for_admins_only(self):
        command = next(command for command in group.COMMANDS if command.name == "adminactivity")
        self.assertEqual(command.policy, "admin")


if __name__ == "__main__":
    unittest.main()
