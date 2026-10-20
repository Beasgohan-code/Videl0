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


if __name__ == "__main__":
    unittest.main()
