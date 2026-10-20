"""Scheduled publishing: rate limits, final failures and the alert.

A 429 proves nothing was delivered, so it is the one failure the queue may
handle alone. Everything else waits for the owner — a duplicate post is worse
than a missing one — and a terminal failure must be said out loud once.
"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import mongomock

from videl.utils import scheduled_posts

UTC = timezone.utc
JOB = "11111111-1111-4111-8111-111111111111"


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.store = self.db["scheduled_posts"]
        self.patch_collection = patch.object(scheduled_posts, "_collection", lambda: self.store)
        self.patch_collection.start()
        self.api = patch.object(scheduled_posts, "call_bot_api", return_value=(200, {"ok": True}))
        self.telegram = self.api.start()
        self.alerts = []
        self.patch_alert = patch.object(scheduled_posts, "_alert",
                                        side_effect=lambda job, state, reason: self.alerts.append((state, reason)))
        self.patch_alert.start()

    def tearDown(self):
        self.patch_alert.stop()
        self.api.stop()
        self.patch_collection.stop()

    def job(self, **extra):
        self.store.insert_one({"_id": JOB, "owner_id": scheduled_posts.OWNER_ID, "status": "pending",
                               "method": "sendMessage", "payload": {"chat_id": "@x", "text": "hi"},
                               "due_at": datetime.now(UTC) - timedelta(minutes=1),
                               "created_at": datetime.now(UTC), **extra})
        return self.store.find_one({"_id": JOB})

    def test_a_rate_limit_goes_back_to_the_queue_with_telegrams_delay(self):
        self.job()
        self.telegram.return_value = (429, {"ok": False, "description": "Too Many Requests",
                                            "parameters": {"retry_after": 20}})
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": JOB})
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["attempts"], 1)
        self.assertIn("retrying in 20s", row["error"])
        self.assertGreater(row["due_at"].replace(tzinfo=UTC), datetime.now(UTC) + timedelta(seconds=15))
        self.assertEqual(self.alerts, [], "a retry is not a failure worth alerting")

    def test_the_retry_interval_is_sane_when_telegram_is_silent(self):
        self.job()
        self.telegram.return_value = (429, {"ok": False})
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": JOB})
        self.assertEqual(row["status"], "pending")
        self.assertIn("retrying in 30s", row["error"])

    def test_a_persistent_rate_limit_stops_retrying_and_alerts(self):
        self.job(attempts=scheduled_posts.MAX_RATE_LIMITED_RETRIES)
        self.telegram.return_value = (429, {"ok": False, "parameters": {"retry_after": 10}})
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": JOB})
        self.assertEqual(row["status"], "failed")
        self.assertIn("Rate limit persisted", row["error"])
        self.assertEqual(self.alerts[0][0], "failed")

    def test_a_rejection_is_final_and_explained(self):
        self.job()
        self.telegram.return_value = (400, {"ok": False, "description": "Bad Request: chat not found"})
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": JOB})
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["error"], "Bad Request: chat not found")
        self.assertEqual(self.alerts, [("failed", "Bad Request: chat not found")])

    def test_an_accepted_post_records_the_message_and_stays_quiet(self):
        self.job()
        self.telegram.return_value = (200, {"ok": True, "result": {"message_id": 91}})
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": JOB})
        self.assertEqual(row["status"], "sent")
        self.assertEqual(row["message_id"], 91)
        self.assertEqual(self.alerts, [])

    def test_an_unknown_outcome_is_never_resent(self):
        self.job()
        self.telegram.return_value = (502, {"ok": False, "description": "Bad Gateway"})
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": JOB})
        self.assertEqual(row["status"], "unconfirmed", "a 5xx may have delivered")
        self.assertEqual(self.alerts[0][0], "unconfirmed")
        # And the owner cannot retry it by hand either.
        with self.assertRaises(ValueError):
            scheduled_posts.retry_job(JOB)

    def test_a_crashed_dispatch_is_marked_unconfirmed(self):
        self.job()
        self.telegram.side_effect = RuntimeError("socket closed")
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": JOB})
        self.assertEqual(row["status"], "unconfirmed")
        self.assertEqual(len(self.alerts), 1)

    def test_jobs_over_a_day_late_are_missed_not_sent(self):
        self.store.insert_one({"_id": JOB, "owner_id": scheduled_posts.OWNER_ID, "status": "pending",
                               "method": "sendMessage", "payload": {"chat_id": "@x", "text": "hi"},
                               "due_at": datetime.now(UTC) - timedelta(days=2),
                               "created_at": datetime.now(UTC)})
        scheduled_posts.dispatch_one()
        self.assertEqual(self.store.find_one({"_id": JOB})["status"], "missed")
        self.telegram.assert_not_called()

    def test_a_stuck_send_is_unconfirmed_not_pending(self):
        self.store.insert_one({"_id": JOB, "owner_id": scheduled_posts.OWNER_ID, "status": "sending",
                               "method": "sendMessage", "payload": {"chat_id": "@x", "text": "hi"},
                               "due_at": datetime.now(UTC), "created_at": datetime.now(UTC),
                               "claimed_at": datetime.now(UTC) - timedelta(minutes=30)})
        scheduled_posts.dispatch_one()
        self.assertEqual(self.store.find_one({"_id": JOB})["status"], "unconfirmed")

    def test_the_monitor_reports_automatic_attempts(self):
        self.job(attempts=2)
        self.assertEqual(scheduled_posts.list_jobs()[0]["attempts"], 2)


class AlertTests(unittest.TestCase):
    def setUp(self):
        import config
        self.previous = getattr(config, "LOG_CHANNEL_ID", 0)
        self.addCleanup(setattr, config, "LOG_CHANNEL_ID", self.previous)
        self.api = patch.object(scheduled_posts, "call_bot_api", return_value=(200, {"ok": True}))
        self.telegram = self.api.start()
        self.addCleanup(self.api.stop)

    def test_the_alert_names_the_job_and_the_reason(self):
        import config
        config.LOG_CHANNEL_ID = -1009
        self.assertTrue(scheduled_posts._alert({"_id": JOB, "payload": {"chat_id": "@x"}}, "failed", "chat not found"))
        method, payload = self.telegram.call_args.args
        self.assertEqual(method, "sendMessage")
        self.assertEqual(payload["chat_id"], -1009)
        self.assertIn(JOB, payload["text"])
        self.assertIn("chat not found", payload["text"])

    def test_no_channel_configured_is_not_an_error(self):
        import config
        config.LOG_CHANNEL_ID = 0
        self.assertFalse(scheduled_posts._alert({"_id": JOB, "payload": {}}, "failed", "x"))
        self.telegram.assert_not_called()

    def test_a_failed_alert_never_raises(self):
        import config
        config.LOG_CHANNEL_ID = -1009
        self.telegram.side_effect = RuntimeError("blocked by the user")
        self.assertFalse(scheduled_posts._alert({"_id": JOB, "payload": {}}, "failed", "x"))


class RepeatTests(unittest.TestCase):
    """A daily or weekly post keeps one record and advances its own clock."""

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.store = self.db["scheduled_posts"]
        self.patch_collection = patch.object(scheduled_posts, "_collection", lambda: self.store)
        self.patch_collection.start()
        self.api = patch.object(scheduled_posts, "call_bot_api",
                                return_value=(200, {"ok": True, "result": {"message_id": 5}}))
        self.telegram = self.api.start()
        self.alerts = []
        self.patch_alert = patch.object(scheduled_posts, "_alert",
                                        side_effect=lambda job, state, reason: self.alerts.append(state))
        self.patch_alert.start()

    def tearDown(self):
        self.patch_alert.stop()
        self.api.stop()
        self.patch_collection.stop()

    def queued(self, repeat, hours_ago=0):
        # Enqueue in the future (the only time the queue accepts), then the test
        # moves the record back to pretend the clock has passed.
        due = datetime.now(UTC) + timedelta(hours=2)
        return scheduled_posts.enqueue("sendMessage", {"chat_id": "@x", "text": "note"},
                                       due.isoformat(), JOB, repeat)

    def test_a_daily_post_advances_instead_of_finishing(self):
        result = self.queued("daily")
        self.store.update_one({"_id": result["job_id"]}, {"$set": {"due_at": datetime.now(UTC) - timedelta(minutes=1)}})
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": result["job_id"]})
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["sent_count"], 1)
        self.assertEqual(row["message_id"], 5)
        self.assertGreater(row["due_at"].replace(tzinfo=UTC), datetime.now(UTC) + timedelta(hours=23))
        self.assertIsNone(row["finished_at"])
        self.assertEqual(self.alerts, [])

    def test_a_weekly_post_waits_a_week(self):
        result = self.queued("weekly")
        self.store.update_one({"_id": result["job_id"]}, {"$set": {"due_at": datetime.now(UTC) - timedelta(minutes=1)}})
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": result["job_id"]})
        self.assertGreater(row["due_at"].replace(tzinfo=UTC), datetime.now(UTC) + timedelta(days=6))

    def test_an_unknown_repeat_is_refused(self):
        with self.assertRaises(ValueError):
            self.queued("hourly")
        self.assertEqual(self.store.count_documents({}), 0)

    def test_a_stale_series_skips_ahead_instead_of_dying(self):
        result = self.queued("daily")
        self.store.update_one({"_id": result["job_id"]},
                              {"$set": {"due_at": datetime.now(UTC) - timedelta(days=3, hours=2)}})
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": result["job_id"]})
        self.assertEqual(row["status"], "pending")
        self.assertGreater(row["due_at"].replace(tzinfo=UTC), datetime.now(UTC))
        self.assertEqual(row["skipped"], 4)
        self.assertIn("skipped", row["error"])
        self.telegram.assert_not_called()

    def test_a_failed_series_stops_and_asks_for_a_decision(self):
        result = self.queued("daily")
        self.store.update_one({"_id": result["job_id"]}, {"$set": {"due_at": datetime.now(UTC) - timedelta(minutes=1)}})
        self.telegram.return_value = (400, {"ok": False, "description": "chat not found"})
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": result["job_id"]})
        self.assertEqual(row["status"], "failed")
        self.assertFalse(row.get("sent_count"), "a rejected delivery is not a send")
        self.assertEqual(self.alerts, ["failed"])

    def test_the_monitor_reports_the_series_state(self):
        result = self.queued("daily")
        job = [row for row in scheduled_posts.list_jobs() if row["id"] == result["job_id"]][0]
        self.assertEqual(job["repeat"], "daily")
        self.assertEqual(job["sent_count"], 0)

    def test_a_one_shot_job_stays_one_shot(self):
        result = self.queued(None)
        self.store.update_one({"_id": result["job_id"]}, {"$set": {"due_at": datetime.now(UTC) - timedelta(minutes=1)}})
        scheduled_posts.dispatch_one()
        row = self.store.find_one({"_id": result["job_id"]})
        self.assertEqual(row["status"], "sent")
        self.assertNotIn("repeat", row)


class DuplicateTests(unittest.TestCase):
    """A copy is a new job, so it can follow any finished outcome safely."""

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.store = self.db["scheduled_posts"]
        self.patch_collection = patch.object(scheduled_posts, "_collection", lambda: self.store)
        self.patch_collection.start()
        self.store.insert_one({"_id": JOB, "owner_id": scheduled_posts.OWNER_ID, "status": "sent",
                               "method": "sendMessage", "payload": {"chat_id": "@x", "text": "hello"},
                               "due_at": datetime.now(UTC) - timedelta(hours=2),
                               "created_at": datetime.now(UTC) - timedelta(hours=3),
                               "message_id": 9, "finished_at": datetime.now(UTC) - timedelta(hours=2)})

    def tearDown(self):
        self.patch_collection.stop()

    def test_a_copy_keeps_the_payload_and_gets_a_new_identity(self):
        result = scheduled_posts.duplicate_job(JOB)
        copy = self.store.find_one({"_id": result["job_id"]})
        self.assertNotEqual(result["job_id"], JOB)
        self.assertEqual(copy["status"], "pending")
        self.assertEqual(copy["payload"], {"chat_id": "@x", "text": "hello"})
        self.assertEqual(copy["method"], "sendMessage")
        self.assertEqual(copy["duplicated_from"], JOB)
        self.assertNotIn("message_id", copy)
        self.assertIsNone(copy.get("finished_at"))
        due = copy["due_at"].replace(tzinfo=UTC)
        self.assertGreater(due, datetime.now(UTC) + timedelta(minutes=50))
        # The original is untouched, so a copy can never rewrite history.
        self.assertEqual(self.store.find_one({"_id": JOB})["status"], "sent")

    def test_an_explicit_time_is_honoured_and_a_naive_one_refused(self):
        when = (datetime.now(UTC) + timedelta(days=2)).isoformat()
        result = scheduled_posts.duplicate_job(JOB, when)
        stored = self.store.find_one({"_id": result["job_id"]})["due_at"].replace(tzinfo=UTC)
        # Mongomock keeps milliseconds, so compare to the same precision.
        self.assertEqual(stored, datetime.fromisoformat(when).replace(microsecond=stored.microsecond))
        with self.assertRaises(ValueError):
            scheduled_posts.duplicate_job(JOB, "2030-01-01T10:00:00")
        with self.assertRaises(ValueError):
            scheduled_posts.duplicate_job(JOB, (datetime.now(UTC) + timedelta(days=91)).isoformat())

    def test_a_job_still_in_the_queue_is_not_copied(self):
        self.store.update_one({"_id": JOB}, {"$set": {"status": "pending"}})
        with self.assertRaises(ValueError):
            scheduled_posts.duplicate_job(JOB)
        self.store.update_one({"_id": JOB}, {"$set": {"status": "sending"}})
        with self.assertRaises(ValueError):
            scheduled_posts.duplicate_job(JOB)
        self.assertEqual(self.store.count_documents({}), 1)

    def test_an_unknown_job_and_a_bad_id_are_refused(self):
        with self.assertRaises(ValueError):
            scheduled_posts.duplicate_job("22222222-2222-4222-8222-222222222222")
        with self.assertRaises(ValueError):
            scheduled_posts.duplicate_job("not-a-uuid")


if __name__ == "__main__":
    unittest.main()
