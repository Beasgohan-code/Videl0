"""Warning decay and the escalation ladder.

Both surfaces that hand out warnings must agree, so these tests pin the shared
verdict rather than either caller: how old warnings stop counting, which rung a
repeat offender lands on, and what the stored document looks like afterwards.
"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import mongomock

from videl.utils import automation, db as database, warnings
from videl.utils import group_view as view

CID = -1001234567
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def document(*ages_in_days, stages=0):
    reasons = [{"reason": f"r{index}", "ts": (NOW - timedelta(days=age)).isoformat()}
               for index, age in enumerate(ages_in_days)]
    return {"chat_id": CID, "user_id": 55, "count": len(reasons), "reasons": reasons, "stages": stages}


class DecayTests(unittest.TestCase):
    def test_without_a_window_every_warning_counts(self):
        state = warnings.active_warnings(document(400, 200, 1), 0, NOW)
        self.assertEqual((state["count"], state["total"], state["decayed"]), (3, 3, 0))
        self.assertIsNone(state["expires_at"])

    def test_only_warnings_inside_the_window_count(self):
        state = warnings.active_warnings(document(90, 30, 2), 60, NOW)
        self.assertEqual((state["count"], state["total"], state["decayed"]), (2, 3, 1))
        # The oldest live warning lapses 60 days after it was written, so 30
        # days from now.
        self.assertEqual(state["expires_at"], NOW + timedelta(days=30))

    def test_an_undated_legacy_reason_is_kept_rather_than_guessed_old(self):
        legacy = {"count": 1, "reasons": ["spam"]}
        state = warnings.active_warnings(legacy, 30, NOW)
        self.assertEqual(state["count"], 1, "we cannot prove it is old, so it stands")
        self.assertIsNone(state["expires_at"])

    def test_a_corrupt_timestamp_does_not_break_counting(self):
        state = warnings.active_warnings({"reasons": [{"reason": "x", "ts": "not-a-date"}, "y"]}, 30, NOW)
        self.assertEqual(state["count"], 2)

    def test_everything_expiring_means_no_warnings(self):
        state = warnings.active_warnings(document(200, 100), 30, NOW)
        self.assertEqual(state["count"], 0)
        self.assertEqual(state["decayed"], 2)


class NextStageTests(unittest.TestCase):
    def test_the_limit_is_reached_using_only_live_warnings(self):
        # Three stored, two of them stale: the next warning is only number two.
        plan = warnings.next_stage(document(200, 100, 1), 3, 30, NOW)
        self.assertEqual((plan["count"], plan["reached"], plan["decayed"]), (2, False, 2))

    def test_a_repeat_offender_advances_a_rung(self):
        plan = warnings.next_stage(document(1, 2, 3, stages=1), 3, 0, NOW)
        self.assertEqual((plan["count"], plan["reached"], plan["stage"]), (4, True, 1))
        self.assertEqual(plan["next_stage"], 2)

    def test_a_first_offender_starts_at_the_first_rung(self):
        plan = warnings.next_stage(document(1, 2), 3, 0, NOW)
        self.assertEqual((plan["reached"], plan["stage"]), (True, 0))


class LadderTests(unittest.TestCase):
    def test_an_empty_ladder_keeps_the_single_action_behaviour(self):
        config = {"action": "kick", "ladder": ()}
        self.assertEqual([warnings.ladder_action(config, stage) for stage in range(3)], ["kick", "kick", "kick"])

    def test_the_ladder_escalates_and_then_repeats_its_last_rung(self):
        config = {"action": "ban", "ladder": ("mute", "kick", "ban")}
        self.assertEqual([warnings.ladder_action(config, stage) for stage in range(5)],
                         ["mute", "kick", "ban", "ban", "ban"])

    def test_a_negative_or_broken_stage_starts_at_the_first_rung(self):
        config = {"action": "ban", "ladder": ("mute", "ban")}
        self.assertEqual(warnings.ladder_action(config, -4), "mute")
        self.assertEqual(warnings.ladder_action(config, "x"), "mute")

    def test_an_unknown_action_falls_back_to_ban(self):
        self.assertEqual(warnings.ladder_action({"action": "explode"}, 0), "ban")

    def test_ladder_summary_reports_what_will_run(self):
        self.assertEqual(warnings.ladder_summary({"action": "ban", "ladder": ("mute", "ban")}), ["mute", "ban"])
        self.assertEqual(warnings.ladder_summary({"action": "none", "ladder": ()}), [])
        self.assertEqual(warnings.ladder_summary({"action": "kick", "ladder": ()}), ["kick"])


class NormalizationTests(unittest.TestCase):
    def test_new_fields_have_safe_defaults(self):
        config = automation.normalize_escalation({})
        self.assertEqual(config["decay_days"], 0)
        self.assertEqual(tuple(config["ladder"]), ())
        self.assertEqual(config["action"], "ban", "historic behaviour is unchanged")

    def test_decay_is_clamped_to_a_year(self):
        self.assertEqual(automation.normalize_escalation({"decay_days": 10000})["decay_days"], 365)
        self.assertEqual(automation.normalize_escalation({"decay_days": -5})["decay_days"], 0)
        self.assertEqual(automation.normalize_escalation({"decay_days": "soon"})["decay_days"], 0)
        self.assertEqual(automation.normalize_escalation({"decay_days": True})["decay_days"], 0,
                         "a boolean is not a day count")

    def test_the_ladder_rejects_unknown_actions_and_duplicates(self):
        config = automation.normalize_escalation({"ladder": ["mute", "nuke", "mute", "ban", "kick"]})
        self.assertEqual(tuple(config["ladder"]), ("mute", "ban"),
                         "unknown and duplicate rungs drop out, and so does a weaker step after ban")

    def test_a_de_escalating_rung_is_dropped_not_obeyed(self):
        config = automation.normalize_escalation({"ladder": ["ban", "mute"]})
        self.assertEqual(tuple(config["ladder"]), ("ban",), "a repeat offender must never get a gentler action")
        self.assertEqual(config["action"], "ban")

    def test_ladder_length_is_capped(self):
        config = automation.normalize_escalation({"ladder": ["mute", "kick", "ban", "ban", "ban"]})
        self.assertLessEqual(len(config["ladder"]), 3)


class PanelContractTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["served_chats"].insert_one({"_id": CID})
        self.db["mgmt_chat_settings"].insert_one({"chat_id": CID, "automation": {}})
        self.view = view.GroupView(self.db, lambda *a, **k: (500, {"ok": False}))
        self.patch_db = patch("videl.utils.db._db", self.db)
        self.patch_db.start()

    def tearDown(self):
        self.patch_db.stop()

    def test_the_panel_accepts_decay_and_a_ladder(self):
        payload = self.view.admin(CID, 1, {"action": "automation", "escalation": {
            "decay_days": 90, "ladder": ["mute", "kick", "ban"]}})
        escalation = payload["automation"]["escalation"]
        self.assertEqual(escalation["decay_days"], 90)
        self.assertEqual(list(escalation["ladder"]), ["mute", "kick", "ban"])

    def test_the_panel_rejects_an_out_of_order_ladder(self):
        with self.assertRaises(view.ViewError):
            self.view.admin(CID, 1, {"action": "automation", "escalation": {"ladder": ["kick", "mute"]}})

    def test_the_panel_rejects_an_impossible_decay_window(self):
        with self.assertRaises(view.ViewError):
            self.view.admin(CID, 1, {"action": "automation", "escalation": {"decay_days": 400}})

    def test_the_warning_list_hides_members_whose_warnings_all_lapsed(self):
        old = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        fresh = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        self.db["mgmt_warnings"].insert_many([
            {"chat_id": CID, "user_id": 10, "count": 1, "reasons": [{"reason": "old", "ts": old}]},
            {"chat_id": CID, "user_id": 11, "count": 2,
             "reasons": [{"reason": "new", "ts": fresh}, {"reason": "old", "ts": old}]},
        ])
        self.db["mgmt_chat_settings"].update_one({"chat_id": CID},
                                                 {"$set": {"automation": {"escalation": {"decay_days": 30}}}})
        community = self.view.describe(CID)["community"]
        self.assertEqual([row["user_id"] for row in community["warns"]], [11])
        self.assertEqual(community["warns"][0]["count"], 1, "the stale reason no longer counts")
        self.assertEqual(community["warns"][0]["total"], 2, "but the record is still visible")
        self.assertEqual(community["warns"][0]["decayed"], 1)


class ReportTriageTests(unittest.TestCase):
    """The panel's warn button must reach the same rung as /warn."""

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["served_chats"].insert_one({"_id": CID})
        self.db["mgmt_chat_settings"].insert_one({
            "chat_id": CID, "warn_threshold": 2,
            "automation": {"escalation": {"ladder": ["mute", "ban"], "mute_hours": 2}},
        })
        self.calls = []
        self.view = view.GroupView(self.db, self.telegram)
        self.patch_db = patch("videl.utils.db._db", self.db)
        self.patch_db.start()

    def tearDown(self):
        self.patch_db.stop()

    def telegram(self, method, payload):
        self.calls.append((method, payload))
        if method == "getMe":
            result = {"id": 777, "first_name": "Videl", "username": "ExampleBot"}
        elif method == "getChatMember":
            result = {"status": "administrator", "can_restrict_members": True}
        elif method == "getChat":
            result = {"id": payload.get("chat_id"), "title": "Test group", "type": "supergroup"}
        elif method == "getChatMemberCount":
            result = 42
        else:
            result = True
        return 200, {"ok": True, "result": result}

    def report(self, identifier, target=55):
        from bson import ObjectId
        self.db["mgmt_reports"].insert_one({"_id": ObjectId(identifier), "chat_id": CID, "status": "open",
                                            "target": target, "reporter": 9, "text": "spam"})
        return identifier

    def test_the_ladder_mutes_at_the_limit_and_bans_the_next_time(self):
        from bson import ObjectId
        first = str(ObjectId())
        self.report(first)
        below = self.view.admin(CID, 9, {"action": "report_update", "id": first, "decision": "warn"})
        self.assertEqual(below["note"], "1/2 warnings", "one warning is below a limit of two")

        second = str(ObjectId())
        self.report(second)
        muted = self.view.admin(CID, 9, {"action": "report_update", "id": second, "decision": "warn"})
        self.assertIn("2/2 warnings", muted["note"])
        self.assertIn("muted 2h", muted["note"])

        third = str(ObjectId())
        self.report(third)
        banned = self.view.admin(CID, 9, {"action": "report_update", "id": third, "decision": "warn"})
        self.assertIn("member banned", banned["note"])
        self.assertIn("2/2 warnings", banned["note"], "the count is capped at the limit, not shown as 3/2")
        bans = [payload for name, payload in self.calls if name == "banChatMember"]
        self.assertEqual(len(bans), 2, "the mute and the ban both called Telegram")

    def test_the_note_says_when_older_warnings_no_longer_count(self):
        from bson import ObjectId
        old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        self.db["mgmt_chat_settings"].update_one({"chat_id": CID}, {"$set": {
            "automation": {"escalation": {"decay_days": 30, "action": "ban"}}}})
        self.db["mgmt_warnings"].insert_one({"chat_id": CID, "user_id": 55, "count": 1,
                                             "reasons": [{"reason": "old", "ts": old}]})
        identifier = str(ObjectId())
        self.report(identifier)
        result = self.view.admin(CID, 9, {"action": "report_update", "id": identifier, "decision": "warn"})
        self.assertIn("1 older lapsed", result["note"])
        self.assertIn("1/2 warnings", result["note"], "the stale warning did not push the member to the limit")


class DecayResetsTheLadderTests(unittest.TestCase):
    def test_a_member_whose_warnings_all_lapsed_starts_at_the_first_rung(self):
        # Three warnings, two limit hits already spent: the ladder sits at rung 2.
        fresh = document(1, 1, 1, stages=2)
        self.assertEqual(warnings.next_stage(fresh, 3, 0, NOW)["stage"], 2)
        # The same record a year later, with decay on, is empty again.
        old = document(400, 400, 400, stages=2)
        plan = warnings.next_stage(old, 3, 90, NOW)
        self.assertEqual(plan["count"], 1, "one new warning, and nothing else counts")
        self.assertFalse(plan["reached"])
        self.assertEqual(plan["stage"], 0, "the ladder restarts instead of resuming at rung 2")
        self.assertEqual(plan["next_stage"], 0)

    def test_a_partly_lapsed_record_keeps_the_rung_it_earned(self):
        # One warning still counts, so the member is still on their ladder.
        mixed = document(400, 10, stages=2)
        plan = warnings.next_stage(mixed, 3, 90, NOW)
        self.assertEqual(plan["decayed"], 1)
        self.assertEqual(plan["stage"], 1, "one live warning that does not reach the limit steps back one rung")


class CaseFileTests(unittest.TestCase):
    """The panel shows the whole case, not only the part that still counts."""

    def test_every_entry_says_whether_it_still_counts(self):
        state = warnings.case_file(document(120, 30, 2), 60, NOW)
        self.assertEqual([entry["active"] for entry in state["entries"]], [False, True, True])
        self.assertEqual([entry["reason"] for entry in state["entries"]], ["r0", "r1", "r2"])
        self.assertEqual((state["count"], state["total"], state["decayed"]), (2, 3, 1))

    def test_the_lapsed_entry_keeps_its_date(self):
        state = warnings.case_file(document(400), 60, NOW)
        self.assertEqual(state["entries"][0]["ts"], NOW - timedelta(days=400))
        self.assertFalse(state["entries"][0]["active"])

    def test_the_verdict_matches_the_engine_exactly(self):
        for days in (0, 30, 90):
            with self.subTest(days=days):
                doc = document(200, 45, 3)
                full = warnings.case_file(doc, days, NOW)
                live = warnings.active_warnings(doc, days, NOW)
                self.assertEqual([entry for entry in full["entries"] if entry["active"]], live["entries"])
                self.assertEqual((full["count"], full["expires_at"]), (live["count"], live["expires_at"]))

    def test_the_member_list_carries_the_case_history_newest_first(self):
        db = mongomock.MongoClient().videl
        db["mgmt_warnings"].insert_one(document(40, 10))
        with patch("videl.utils.db._db", db):
            rows = database.list_warns(CID, decay_days=30)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["count"], row["total"], row["decayed"]), (1, 2, 1))
        self.assertEqual([item["reason"] for item in row["history"]], ["r1", "r0"])
        self.assertEqual([item["active"] for item in row["history"]], [True, False])
        self.assertIsNotNone(row["expires_at"])


class StorageTests(unittest.TestCase):
    def test_resetting_a_member_clears_the_ladder_progress(self):
        db = mongomock.MongoClient().videl
        db["mgmt_warnings"].insert_one({"chat_id": CID, "user_id": 55, "count": 3, "stages": 2})
        with patch("videl.utils.db._db", db):
            database.reset_warns(CID, 55)
            self.assertIsNone(db["mgmt_warnings"].find_one({"chat_id": CID, "user_id": 55}))
            # A fresh document starts at stage zero, so the ladder starts over.
            plan = warnings.next_stage(None, 3, 0)
            self.assertEqual(plan["stage"], 0)


if __name__ == "__main__":
    unittest.main()
