import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import mongomock

from videl.utils import onboarding


class OnboardingAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.now = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)

    def test_daily_events_are_whitelisted_aggregates_without_member_identity(self):
        self.assertFalse(onboarding.record(-1001, "user_id", db=self.db, at=self.now))
        self.assertTrue(onboarding.record(-1001, "joins", db=self.db, at=self.now))
        self.assertTrue(onboarding.record(-1001, "challenged", db=self.db, at=self.now))
        self.assertTrue(onboarding.record(-1001, "verified", db=self.db, at=self.now))
        self.assertTrue(onboarding.record(-1002, "joins", db=self.db, at=self.now))
        rows = list(self.db["onboarding_daily"].find({}))
        self.assertEqual(len(rows), 2)
        self.assertNotIn("user_id", rows[0])
        self.assertEqual(rows[0]["day"], datetime(2026, 10, 31))

    def test_summary_counts_funnel_and_days_without_member_level_data(self):
        onboarding.record(-1001, "joins", db=self.db, at=self.now)
        onboarding.record(-1001, "challenged", db=self.db, at=self.now)
        onboarding.record(-1001, "verified", db=self.db, at=self.now)
        onboarding.record(-1001, "timed_out", db=self.db, at=self.now - timedelta(days=2))
        onboarding.record(-1002, "joins", db=self.db, at=self.now - timedelta(days=1))
        onboarding.record(-1003, "joins", db=self.db, at=self.now - timedelta(days=9))

        result = onboarding.summary(self.db, days=7, now=self.now)
        self.assertTrue(result["ok"])
        self.assertEqual(result["window_days"], 7)
        self.assertEqual(result["groups_with_joins"], 2)
        self.assertEqual(result["totals"], {"joins": 2, "challenged": 1, "verified": 1, "timed_out": 1})
        self.assertEqual(len(result["series"]), 3)
        self.assertEqual([item["day"] for item in result["series"]], ["2026-10-29", "2026-10-30", "2026-10-31"])
        self.assertNotIn("user_id", repr(result))
        self.assertNotIn("member", repr(result))

    def test_window_is_clamped_and_unavailable_db_is_explicit(self):
        self.assertEqual(onboarding.summary(self.db, days=90, now=self.now)["window_days"], 30)
        self.assertEqual(onboarding.summary(None)["ok"], False)

    def test_internal_analytics_route_requires_the_shared_secret(self):
        import config
        import videl.__main__ as backend

        previous = getattr(config, "WEBAPP_SECRET", "")
        config.WEBAPP_SECRET = "onboarding-test-secret"
        try:
            client = backend._flask.test_client()
            with patch("videl.utils.db.get_db", return_value=self.db):
                self.assertEqual(client.get("/internal/onboarding-analytics").status_code, 403)
                response = client.get(
                    "/internal/onboarding-analytics",
                    headers={"X-Videl-Internal": "onboarding-test-secret"},
                )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_json()["ok"])
        finally:
            config.WEBAPP_SECRET = previous


if __name__ == "__main__":
    unittest.main()
