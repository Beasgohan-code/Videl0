import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "admin_digest", Path(__file__).parents[1] / "videl/utils/admin_digest.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class _Cursor(list):
    def sort(self, keys, direction=None):
        if isinstance(keys, list):
            super().sort(key=lambda row: tuple(row.get(key, 0) for key, _ in keys))
        else:
            super().sort(key=lambda row: row.get(keys, 0), reverse=direction == -1)
        return self

    def limit(self, count):
        return _Cursor(self[:count])


class _Collection:
    def __init__(self, rows=None, count=0):
        self.rows = list(rows or [])
        self.count = count

    def find(self, query):
        return _Cursor([row for row in self.rows if row.get("enabled") is True
                        and row.get("last_attempt_date") != query["last_attempt_date"]["$ne"]])

    def update_one(self, query, update):
        row = next((item for item in self.rows if item.get("_id") == query.get("_id")), None)
        if row is None or row.get("last_attempt_date") == query.get("last_attempt_date", {}).get("$ne"):
            return type("Result", (), {"modified_count": 0})()
        row.update(update.get("$set", {}))
        for key in update.get("$unset", {}):
            row.pop(key, None)
        return type("Result", (), {"modified_count": 1})()

    def count_documents(self, _query):
        return self.count

    def find_one(self, _query):
        return {"title": "Example group"}

    def create_index(self, *_args, **_kwargs):
        return True


class _DB(dict):
    def __missing__(self, key):
        value = _Collection()
        self[key] = value
        return value


class AdminDigestScheduleTests(unittest.TestCase):
    def test_schedule_parser_accepts_only_real_24_hour_times(self):
        self.assertEqual(module.parse_time("09:30"), (9, 30))
        self.assertEqual(module.parse_time("00:00"), (0, 0))
        self.assertEqual(module.parse_time("23:59"), (23, 59))
        for invalid in ("24:00", "12:60", "9:30", "noon", "12:30:00", ""):
            self.assertIsNone(module.parse_time(invalid), invalid)

    def test_subscription_is_group_scoped_and_requires_valid_user_and_time(self):
        self.assertFalse(module.subscribe(None, -1001, 10, "09:00"))
        self.assertFalse(module.subscribe({}, 1001, 10, "09:00"))
        self.assertFalse(module.subscribe({}, -1001, 0, "09:00"))
        self.assertFalse(module.subscribe({}, -1001, 10, "25:00"))

    def test_daily_digest_is_claimed_once_and_contains_only_aggregate_counts(self):
        from datetime import datetime, timezone
        row={"_id":"subscription-1","chat_id":-1001,"user_id":77,"hour_utc":9,
             "minute_utc":30,"enabled":True}
        db=_DB({module.COLLECTION:_Collection([row]),
                "mgmt_reports":_Collection(count=2),
                "mgmt_join_requests":_Collection(count=1),
                "mgmt_escalations":_Collection(count=3),
                "mgmt_audit":_Collection(count=4),
                "served_chats":_Collection()})
        calls=[]
        def api(method, payload):
            calls.append((method,payload))
            if method=="getChatMember":
                return 200,{"ok":True,"result":{"status":"administrator"}}
            return 200,{"ok":True,"result":{"message_id":1}}
        now=datetime(2026,10,30,9,31,tzinfo=timezone.utc)
        result=module.dispatch_one(db,api,now)
        self.assertTrue(result["sent"])
        self.assertEqual(row["last_delivery"],"delivered")
        self.assertEqual(row["last_attempt_date"],"2026-10-30")
        text=calls[-1][1]["text"]
        self.assertIn("Open reports: 2",text)
        self.assertIn("Pending join requests: 1",text)
        self.assertNotIn("user_id",text)
        second=module.dispatch_one(db,api,now)
        self.assertEqual(second["reason"],"nothing due")
        self.assertEqual(len(calls),2)
