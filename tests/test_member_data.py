import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "member_data", Path(__file__).parents[1] / "videl/utils/member_data.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def matches(row, query):
    for key, value in query.items():
        if key == "$or":
            if not any(matches(row, option) for option in value): return False
        elif row.get(key) != value:
            return False
    return True


class Cursor(list):
    def limit(self, count): return Cursor(self[:count])
    def sort(self, key, direction=-1):
        super().sort(key=lambda item: item.get(key) or "", reverse=direction < 0)
        return self


class Collection:
    def __init__(self, rows=()): self.rows=list(rows)
    def find(self, query, projection=None):
        found=[dict(row) for row in self.rows if matches(row,query)]
        if projection and any(value for key,value in projection.items() if key!="_id"):
            keys={key for key,value in projection.items() if value}
            found=[{key:value for key,value in row.items() if key in keys or key=="_id"} for row in found]
        return Cursor(found)
    def delete_many(self, query):
        before=len(self.rows); self.rows=[row for row in self.rows if not matches(row,query)]
        return type("Result",(),{"deleted_count":before-len(self.rows)})()
    def update_many(self, query, update):
        count=0
        for row in self.rows:
            if matches(row,query): row.update(update.get("$set",{}));count+=1
        return type("Result",(),{"modified_count":count})()
    def insert_one(self, row): self.rows.append(dict(row))
    def create_index(self,*_args,**_kwargs): return True


class DB(dict):
    def __missing__(self,key): self[key]=Collection();return self[key]


class MemberDataTests(unittest.TestCase):
    def setUp(self):
        self.db=DB({
            "mgmt_warnings":Collection([{"chat_id":-1,"user_id":7,"reasons":[{"reason":"spam"}]},
                                        {"chat_id":-1,"user_id":8,"reasons":[]}]),
            "mgmt_reports":Collection([{"chat_id":-1,"reporter":7,"target":8,"reason":"filed"},
                                       {"chat_id":-1,"reporter":8,"target":7,"reason":"about"}]),
            "mgmt_case_notes":Collection([{"chat_id":-1,"user_id":7,"text":"note"}]),
            "mgmt_appeals":Collection([{"chat_id":-1,"user_id":7,"reason":"please review"}]),
            "mgmt_escalations":Collection([{"chat_id":-1,"user_id":7,"status":"open"}]),
            "plugin_reminders":Collection([{"user_id":7,"chat_id":-1,"text":"drink water","status":"pending"}]),
            "user_activity":Collection([{"_id":7,"last_active":123.5}]),
            "mgmt_audit":Collection([{"chat_id":-1,"detail":"member 7 changed"}]),
        })

    def test_export_only_includes_records_linked_to_self(self):
        data=module.export_user_data(self.db,7)
        self.assertEqual(len(data["records"]["warnings"]),1)
        self.assertEqual(len(data["records"]["reports_filed"]),1)
        self.assertEqual(len(data["records"]["reports_about_member"]),1)
        self.assertEqual(len(data["records"]["appeals"]),1)
        self.assertEqual(data["records"]["reminders"][0]["text"],"drink water")
        self.assertEqual(data["records"]["last_active_record"][0]["last_active"],123.5)
        self.assertNotIn("reporter",data["records"]["reports_about_member"][0])
        self.assertEqual(data["records"]["warnings"][0]["reasons"][0]["reason"],"spam")

    def test_removal_is_group_scoped_cancels_pending_review_and_keeps_audit(self):
        counts=module.delete_member_group_data(self.db,-1,7)
        self.assertEqual(counts["warnings"],1)
        self.assertEqual(counts["reports"],2)
        self.assertEqual(counts["appeals"],1)
        self.assertEqual(self.db["mgmt_escalations"].rows[0]["status"],"cancelled_data_request")
        self.assertEqual(len(self.db["mgmt_audit"].rows),1)
        with self.assertRaises(ValueError): module.delete_member_group_data(self.db,-1,0)

    def test_anonymous_feedback_does_not_store_sender_metadata(self):
        identifier=module.submit_feedback(self.db,"Please improve group setup")
        row=self.db["anonymous_feedback"].rows[0]
        self.assertEqual(row["_id"],identifier)
        self.assertEqual(row["text"],"Please improve group setup")
        self.assertNotIn("user_id",row)
        self.assertNotIn("chat_id",row)
        self.assertIsNone(module.submit_feedback(self.db,""))
