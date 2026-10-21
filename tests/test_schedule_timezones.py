"""Repeating posts that keep their local clock, and the series controls.

A repeating post may carry an IANA timezone. The intended wall clock is then
the thing that stays fixed: 09:00 stays 09:00 across a daylight-saving change.
Two days a year that is not a function of UTC, so the policy is explicit:

* a wall time that does not exist (spring-forward gap) moves forward to the
  first minute that does, for that day only;
* a wall time that happens twice (autumn fall-back) resolves to its first
  occurrence, so the post is sent once and never twice.
"""
import hashlib
import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import mongomock
from zoneinfo import ZoneInfo

from videl.utils import scheduled_posts

UTC = timezone.utc
JOB = "22222222-2222-4222-8222-222222222222"
NEW_YORK = "America/New_York"


class WallClockTests(unittest.TestCase):
    def test_a_spring_forward_gap_moves_to_the_first_real_minute(self):
        wave = datetime(2027, 3, 14, 2, 30)
        instant, adjusted = scheduled_posts.localize_wall_time(wave, ZoneInfo(NEW_YORK))
        self.assertEqual(instant, datetime(2027, 3, 14, 7, 0, tzinfo=UTC))
        self.assertEqual(instant.astimezone(ZoneInfo(NEW_YORK)).hour, 3)
        self.assertTrue(adjusted, "the gap must be reported, not hidden")

    def test_a_fall_back_time_runs_once_at_its_first_occurrence(self):
        wave = datetime(2026, 11, 1, 1, 30)
        instant, adjusted = scheduled_posts.localize_wall_time(wave, ZoneInfo(NEW_YORK))
        # 05:30Z is 01:30 EDT (fold 0), not 01:30 EST an hour later.
        self.assertEqual(instant, datetime(2026, 11, 1, 5, 30, tzinfo=UTC))
        self.assertFalse(adjusted)
        again, _ = scheduled_posts.localize_wall_time(wave, ZoneInfo(NEW_YORK))
        self.assertEqual(again, instant, "the same wall time always maps to one instant")

    def test_a_zone_without_dst_is_unaffected(self):
        instant, adjusted = scheduled_posts.localize_wall_time(
            datetime(2026, 10, 25, 9, 0), ZoneInfo("Asia/Kolkata"))
        self.assertEqual(instant, datetime(2026, 10, 25, 3, 30, tzinfo=UTC))
        self.assertFalse(adjusted)

    def test_the_anchor_keeps_the_chosen_wall_time_when_the_first_run_is_shifted(self):
        due = datetime(2027, 3, 14, 7, 0, tzinfo=UTC)
        anchor = scheduled_posts._anchor_from(due, ZoneInfo(NEW_YORK), "02:30")
        self.assertEqual(anchor, datetime(2027, 3, 14, 2, 30))

    def test_a_wall_time_must_match_the_instant(self):
        due = datetime(2027, 3, 14, 7, 0, tzinfo=UTC)
        with self.assertRaises(ValueError):
            scheduled_posts._anchor_from(due, ZoneInfo(NEW_YORK), "09:00")
        with self.assertRaises(ValueError):
            scheduled_posts._anchor_from(due, ZoneInfo(NEW_YORK), "25:00")


class NextOccurrenceTests(unittest.TestCase):
    def doc(self, **extra):
        due = datetime(2027, 3, 13, 14, 0, tzinfo=UTC)  # 09:00 in New York (EST)
        base = {"_id": JOB, "owner_id": scheduled_posts.OWNER_ID, "status": "pending",
                "method": "sendMessage", "payload": {"chat_id": "@x", "text": "note"},
                "due_at": due, "repeat": "daily", "timezone": NEW_YORK,
                "repeat_anchor": "2027-03-13T09:00:00"}
        base.update(extra)
        return base

    def test_a_daily_series_keeps_its_local_hour_across_dst(self):
        run_at, anchor, adjusted = scheduled_posts._next_occurrence(self.doc())
        self.assertEqual(run_at, datetime(2027, 3, 14, 13, 0, tzinfo=UTC))  # 09:00 EDT
        # 23 hours of UTC time, not 24: that is the point of the feature.
        self.assertEqual(run_at - datetime(2027, 3, 13, 14, 0, tzinfo=UTC), timedelta(hours=23))
        self.assertEqual(anchor, datetime(2027, 3, 14, 9, 0))
        self.assertFalse(adjusted)

    def test_a_gap_only_moves_the_occurrence_that_falls_in_it(self):
        gap_doc = self.doc(due_at=datetime(2027, 3, 13, 7, 30, tzinfo=UTC),
                           repeat_anchor="2027-03-13T02:30:00")
        run_at, anchor, adjusted = scheduled_posts._next_occurrence(gap_doc)
        self.assertEqual(run_at, datetime(2027, 3, 14, 7, 0, tzinfo=UTC))  # 03:00 EDT
        self.assertEqual(anchor, datetime(2027, 3, 14, 2, 30), "the intended clock is kept")
        self.assertTrue(adjusted)
        following, anchor, adjusted = scheduled_posts._next_occurrence(
            dict(gap_doc, due_at=run_at, repeat_anchor=anchor.isoformat()))
        self.assertEqual(following, datetime(2027, 3, 15, 6, 30, tzinfo=UTC))  # 02:30 EDT
        self.assertFalse(adjusted)

    def test_a_weekly_series_keeps_its_local_hour(self):
        run_at, _, _ = scheduled_posts._next_occurrence(self.doc(repeat="weekly"))
        self.assertEqual(run_at, datetime(2027, 3, 20, 13, 0, tzinfo=UTC))  # 09:00 EDT

    def test_a_series_without_a_zone_keeps_the_old_utc_interval(self):
        doc = self.doc()
        doc.pop("timezone")
        doc.pop("repeat_anchor")
        run_at, anchor, adjusted = scheduled_posts._next_occurrence(doc)
        self.assertEqual(run_at, datetime(2027, 3, 14, 14, 0, tzinfo=UTC))
        self.assertIsNone(anchor)
        self.assertFalse(adjusted)


class EnqueueZoneTests(unittest.TestCase):
    def setUp(self):
        self.col = mongomock.MongoClient().videl["scheduled_posts"]
        self.patch = patch.object(scheduled_posts, "_collection", lambda: self.col)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def due(self):
        # A fixed 09:30 tomorrow in Kolkata. "Now + two hours" made this suite
        # depend on the hour it ran: after 10:00 local the instant drifted more
        # than the three-hour sanity window away from the 09:00 anchor, and the
        # test failed for a reason that had nothing to do with timezones.
        zone = ZoneInfo("Asia/Kolkata")
        local = (datetime.now(zone) + timedelta(days=1)).replace(
            hour=9, minute=30, second=0, microsecond=0)
        return local.astimezone(UTC).isoformat()

    def test_a_zone_is_stored_and_an_unknown_zone_is_refused(self):
        row = scheduled_posts.enqueue("sendMessage", {"chat_id": "@x", "text": "hi"},
                                      self.due(), JOB, "daily", "Asia/Kolkata", "09:00")
        stored = self.col.find_one({"_id": JOB})
        self.assertEqual(stored["timezone"], "Asia/Kolkata")
        self.assertEqual(stored["repeat_anchor"][-8:], "09:00:00")
        self.assertEqual(row["timezone"], "Asia/Kolkata")
        with self.assertRaises(ValueError):
            scheduled_posts.enqueue("sendMessage", {"chat_id": "@x", "text": "hi"},
                                    self.due(), str(uuid.uuid4()), "daily", "Mars/Olympus")
        with self.assertRaises(ValueError):
            scheduled_posts.enqueue("sendMessage", {"chat_id": "@x", "text": "hi"},
                                    self.due(), str(uuid.uuid4()), "daily", None, "09:00")

    def test_the_zone_is_part_of_the_request_identity(self):
        due = self.due()
        scheduled_posts.enqueue("sendMessage", {"chat_id": "@x", "text": "hi"},
                                due, JOB, "daily", "Asia/Kolkata", "09:00")
        with self.assertRaises(ValueError):
            scheduled_posts.enqueue("sendMessage", {"chat_id": "@x", "text": "hi"},
                                    due, JOB, "daily", "Asia/Tokyo", "09:00")

    def test_a_json_shaped_repeat_is_a_bad_request_not_a_crash(self):
        for bad in ([], {"daily": True}, 7):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                scheduled_posts.enqueue("sendMessage", {"chat_id": "@x", "text": "hi"},
                                        self.due(), JOB, repeat=bad)
        self.assertEqual(self.col.count_documents({}), 0)

    def test_a_request_queued_before_zones_can_still_be_retried(self):
        # The old digest had exactly four fields. A retry after the upgrade must
        # find its job, not be told the request ID belongs to a different post.
        payload = {"chat_id": "@x", "text": "hi"}
        due = datetime.fromisoformat(self.due()).astimezone(UTC)
        legacy = hashlib.sha256(json.dumps(
            ["sendMessage", payload, due.isoformat(), None], sort_keys=True).encode()).hexdigest()
        self.col.insert_one({"_id": JOB, "owner_id": scheduled_posts.OWNER_ID, "status": "pending",
                             "method": "sendMessage", "payload": payload, "due_at": due,
                             "created_at": datetime.now(UTC), "fingerprint": legacy})
        result = scheduled_posts.enqueue("sendMessage", payload, due.isoformat(), JOB)
        self.assertEqual(result["job_id"], JOB)
        self.assertEqual(self.col.count_documents({}), 1)

    def test_a_one_shot_may_carry_a_zone_for_display(self):
        scheduled_posts.enqueue("sendMessage", {"chat_id": "@x", "text": "hi"},
                                self.due(), JOB, None, "Asia/Kolkata")
        stored = self.col.find_one({"_id": JOB})
        self.assertEqual(stored["timezone"], "Asia/Kolkata")
        self.assertNotIn("repeat_anchor", stored)


class SeriesControlTests(unittest.TestCase):
    def setUp(self):
        self.store = mongomock.MongoClient().videl["scheduled_posts"]
        self.patch = patch.object(scheduled_posts, "_collection", lambda: self.store)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.api = patch.object(scheduled_posts, "call_bot_api",
                                return_value=(200, {"ok": True, "result": {"message_id": 7}}))
        self.telegram = self.api.start()
        self.addCleanup(self.api.stop)
        self.alert = patch.object(scheduled_posts, "_alert")
        self.alert.start()
        self.addCleanup(self.alert.stop)

    def queued(self, repeat="daily", **extra):
        due = datetime.now(UTC) + timedelta(hours=2)
        doc = {"_id": JOB, "owner_id": scheduled_posts.OWNER_ID, "status": "pending",
               "method": "sendMessage", "payload": {"chat_id": "@x", "text": "note"},
               "due_at": due, "created_at": datetime.now(UTC), "fingerprint": "x",
               "repeat": repeat, "timezone": "Asia/Kolkata",
               "repeat_anchor": due.astimezone(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None).isoformat()}
        doc.update(extra)
        self.store.insert_one(doc)
        return self.store.find_one({"_id": JOB})

    def test_a_paused_series_is_neither_sent_nor_declared_missed(self):
        self.queued()
        scheduled_posts.set_paused(JOB, True)
        self.store.update_one({"_id": JOB}, {"$set": {"due_at": datetime.now(UTC) - timedelta(days=3)}})
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": JOB})
        self.assertEqual(row["status"], "pending")
        self.assertTrue(row["paused"])
        self.telegram.assert_not_called()

    def test_resuming_skips_ahead_instead_of_firing_the_backlog(self):
        self.queued()
        scheduled_posts.set_paused(JOB, True)
        late = datetime.now(UTC) - timedelta(days=3, hours=1)
        self.store.update_one({"_id": JOB}, {"$set": {
            "due_at": late,
            "repeat_anchor": late.astimezone(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None).isoformat()}})
        result = scheduled_posts.set_paused(JOB, False)
        row = self.store.find_one({"_id": JOB})
        self.assertFalse(row["paused"])
        self.assertGreater(row["due_at"].replace(tzinfo=UTC), datetime.now(UTC))
        self.assertGreaterEqual(result["skipped"], 3)
        self.telegram.assert_not_called()

    def test_skip_next_advances_exactly_one_occurrence(self):
        doc = self.queued()
        before = doc["due_at"].replace(tzinfo=UTC)
        result = scheduled_posts.skip_next(JOB)
        row = self.store.find_one({"_id": JOB})
        self.assertEqual(row["skipped"], 1)
        self.assertEqual(row["note"], "Next occurrence skipped by the owner")
        self.assertIsNone(row.get("error"))
        self.assertIsNone(scheduled_posts._job_view(row)["error"])
        self.assertEqual(scheduled_posts._job_view(row)["note"], row["note"])
        self.assertEqual(row["status"], "pending")
        self.assertLess(abs((row["due_at"].replace(tzinfo=UTC) - (before + timedelta(days=1))).total_seconds()), 1)
        self.assertGreater(datetime.fromisoformat(result["scheduled_at"]), before)
        self.telegram.assert_not_called()

    def test_skip_is_refused_while_paused_or_without_a_repeat(self):
        self.queued()
        scheduled_posts.set_paused(JOB, True)
        with self.assertRaises(ValueError):
            scheduled_posts.skip_next(JOB)
        self.store.update_one({"_id": JOB}, {"$set": {"paused": False}})
        self.store.update_one({"_id": JOB}, {"$unset": {"repeat": ""}})
        with self.assertRaises(ValueError):
            scheduled_posts.skip_next(JOB)

    def test_a_paused_series_does_not_lose_its_anchor_when_resumed(self):
        doc = self.queued()
        anchor = datetime.fromisoformat(doc["repeat_anchor"]).strftime("%H:%M")
        scheduled_posts.set_paused(JOB, True)
        scheduled_posts.set_paused(JOB, False)
        row = self.store.find_one({"_id": JOB})
        self.assertEqual(datetime.fromisoformat(row["repeat_anchor"]).strftime("%H:%M"), anchor)

    def test_a_stale_series_skips_ahead_in_its_own_zone(self):
        late = datetime.now(UTC) - timedelta(days=3, hours=1)
        self.store.insert_one({
            "_id": JOB, "owner_id": scheduled_posts.OWNER_ID, "status": "pending",
            "method": "sendMessage", "payload": {"chat_id": "@x", "text": "note"},
            "due_at": late, "created_at": late, "fingerprint": "x",
            "repeat": "daily", "timezone": "Asia/Kolkata",
            "repeat_anchor": late.astimezone(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None).isoformat(),
        })
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": JOB})
        self.assertEqual(row["status"], "pending")
        self.assertGreater(row["due_at"].replace(tzinfo=UTC), datetime.now(UTC))
        self.assertGreaterEqual(row["skipped"], 3)
        # A catch-up is a note, not a failure: the panel must not red-flag it.
        self.assertIn("skipped", row.get("note") or "")
        self.assertIsNone(row.get("error"))
        anchor = datetime.fromisoformat(row["repeat_anchor"])
        self.assertEqual(anchor.strftime("%H:%M"),
                         late.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%H:%M"))
        self.telegram.assert_not_called()

    def test_a_refused_pause_says_the_view_is_stale(self):
        self.queued()
        with patch.object(self.store, "update_one", return_value=Mock(modified_count=0)):
            with self.assertRaises(ValueError):
                scheduled_posts.set_paused(JOB, True)

    def test_a_long_pause_is_skipped_in_one_step(self):
        self.queued()
        scheduled_posts.set_paused(JOB, True)
        long_ago = datetime.now(UTC) - timedelta(days=730)
        self.store.update_one({"_id": JOB}, {"$set": {
            "due_at": long_ago,
            "repeat_anchor": long_ago.astimezone(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None).isoformat()}})
        result = scheduled_posts.set_paused(JOB, False)
        row = self.store.find_one({"_id": JOB})
        self.assertEqual(row["status"], "pending")
        self.assertGreater(row["due_at"].replace(tzinfo=UTC), datetime.now(UTC))
        self.assertGreater(result["skipped"], 700, "two years of daily copies are skipped, not replayed")
        self.telegram.assert_not_called()

    def test_the_monitor_reports_zone_and_pause_state(self):
        self.queued()
        scheduled_posts.set_paused(JOB, True)
        job = [row for row in scheduled_posts.list_jobs() if row["id"] == JOB][0]
        self.assertEqual(job["timezone"], "Asia/Kolkata")
        self.assertTrue(job["paused"])
        self.assertIsNotNone(job["scheduled_local"])
        self.assertTrue(job["scheduled_local"].endswith("+05:30"))


if __name__ == "__main__":
    unittest.main()
