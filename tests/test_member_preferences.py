import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "member_preferences", Path(__file__).parents[1] / "videl/utils/member_preferences.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class Collection:
    def __init__(self): self.row = None
    def find_one(self, query): return dict(self.row) if self.row else None
    def find(self, query, projection=None):
        return [dict(self.row)] if self.row and self.row.get("notifications_enabled") is True else []
    def update_one(self, query, update, upsert=False):
        self.row = {"_id": query["_id"], **(self.row or {}), **update["$set"]}


class PreferencesTests(unittest.TestCase):
    def setUp(self): self.db = {"user_preferences": Collection()}

    def test_private_updates_are_opt_in_and_changeable(self):
        self.assertFalse(module.read(self.db, 42)["notifications_enabled"])
        saved = module.update(self.db, 42, notifications_enabled=True)
        self.assertTrue(saved["notifications_enabled"])
        self.assertFalse(module.update(self.db, 42, notifications_enabled=1))
        self.assertFalse(module.update(self.db, 42, notifications_enabled=False)["notifications_enabled"])

    def test_private_broadcast_recipients_require_an_opt_in(self):
        collection = self.db["user_preferences"]
        collection.row = {"_id": 7, "notifications_enabled": True}
        private = [{"chat_id": 7}, {"chat_id": 8}]
        selected, skipped = module.opted_in_private_chats(self.db, private)
        self.assertEqual(selected, [{"chat_id": 7}])
        self.assertEqual(skipped, 1)
        self.assertEqual(module.opted_in_private_chats(None, private), ([], 2))

    def test_quiet_window_defers_to_local_end_and_off_is_immediate(self):
        quiet = {"enabled": True, "start": "22:00", "end": "07:00", "utc_offset_minutes": 330}
        now = datetime(2026, 1, 1, 16, 30, tzinfo=timezone.utc)  # 22:00 at UTC+05:30
        self.assertEqual(module.next_allowed_delivery(now, quiet),
                         datetime(2026, 1, 2, 1, 30, tzinfo=timezone.utc))
        self.assertEqual(module.next_allowed_delivery(now, {**quiet, "enabled": False}), now)

    def test_invalid_quiet_window_fails_closed_to_disabled(self):
        quiet = module.normalize_quiet_hours({"enabled": True, "start": "25:90", "end": "07:00", "utc_offset_minutes": 900})
        self.assertFalse(quiet["enabled"])
        self.assertIsNone(module.parse_time("24:00"))
