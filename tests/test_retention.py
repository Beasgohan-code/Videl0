import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "retention", Path(__file__).parents[1] / "videl/utils/retention.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def matches(row, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(matches(row, option) for option in expected): return False
            continue
        actual = row.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]: return False
            if "$type" in expected and expected["$type"] == "date" and not isinstance(actual, datetime): return False
            if "$lt" in expected and (actual is None or not actual < expected["$lt"]): return False
        elif actual != expected:
            return False
    return True


class Collection:
    def __init__(self, rows=()): self.rows=list(rows); self.policy=None
    def find(self, query, projection=None): return [dict(row) for row in self.rows if matches(row,query)]
    def find_one(self, query, projection=None):
        return next((dict(row) for row in self.rows if matches(row,query)),None)
    def update_one(self, query, update, upsert=False):
        row=self.find_one(query)
        if row is None:
            row={**query, **update.get("$set",{})};self.rows.append(row)
        else:row.update(update.get("$set",{}))
    def count_documents(self, query): return sum(matches(row,query) for row in self.rows)
    def delete_many(self, query):
        before=len(self.rows);self.rows=[row for row in self.rows if not matches(row,query)]
        return type("Result",(),{"deleted_count":before-len(self.rows)})()


class RetentionTests(unittest.TestCase):
    def setUp(self):
        now=datetime(2026,1,1,tzinfo=timezone.utc)
        old=now-timedelta(days=100)
        fresh=now-timedelta(days=10)
        self.db={
            "mgmt_chat_settings":Collection([{"chat_id":-100,"data_retention":{"case_notes":30,"resolved_reports":30,"resolved_join_requests":30}}]),
            "mgmt_case_notes":Collection([{"chat_id":-100,"ts":old,"text":"old note"},{"chat_id":-100,"ts":fresh,"text":"fresh note"}]),
            "mgmt_reports":Collection([{"chat_id":-100,"status":"resolved","resolved":old},{"chat_id":-100,"status":"open","resolved":old}]),
            "mgmt_join_requests":Collection([{"chat_id":-100,"status":"approved","resolved":old},
                {"chat_id":-100,"status":"pending","ts":old},
                {"chat_id":-100,"status":"expired","ts":old}]),
            "mgmt_appeals":Collection(),"mgmt_escalations":Collection(),
        }
        self.now=now

    def test_group_admin_policy_values_are_validated_and_independent(self):
        policy=module.save(self.db,-100,"case_notes",90)
        self.assertEqual(policy["case_notes"],90)
        self.assertEqual(policy["resolved_reports"],30)
        self.assertIsNone(module.save(self.db,-100,"case_notes",400))
        self.assertIsNone(module.save(self.db,-100,"unknown",90))

    def test_unconfigured_categories_are_preserved_and_resolved_only_are_counted(self):
        preview=module.cleanup_group_history(self.db,now=self.now)
        self.assertTrue(preview["ok"])
        self.assertFalse(preview["applied"])
        self.assertEqual(preview["counts"]["-100:case_notes"],1)
        self.assertEqual(preview["counts"]["-100:resolved_reports"],1)
        self.assertEqual(preview["counts"]["-100:resolved_join_requests"],2)
        self.assertEqual(len(self.db["mgmt_case_notes"].rows),2)
        self.assertEqual(len(self.db["mgmt_reports"].rows),2)

    def test_apply_prunes_only_expired_rows_using_same_predicate(self):
        result=module.cleanup_group_history(self.db,apply=True,now=self.now)
        self.assertTrue(result["ok"])
        self.assertEqual(result["counts"]["-100:case_notes"],1)
        self.assertEqual(len(self.db["mgmt_case_notes"].rows),1)
        self.assertEqual(len(self.db["mgmt_reports"].rows),1)
        self.assertEqual(self.db["mgmt_reports"].rows[0]["status"],"open")
        self.assertEqual(len(self.db["mgmt_join_requests"].rows),1)
        self.assertEqual(self.db["mgmt_join_requests"].rows[0]["status"],"pending")
