import importlib
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import mongomock


class OpsMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = importlib.import_module("videl.__main__")
        cls.client = cls.api._flask.test_client()

    def test_process_metrics_require_internal_secret_and_return_only_measurements(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "ops-test-secret"), \
             patch("videl.plugins.tools._resource_snapshot", return_value={
                 "cpu": 12.5, "process_cpu": 3.0, "logical_cpus": 4,
                 "cpu_limit": 2.0, "load": "0.10 · 0.20 · 0.30",
                 "memory_label": "Container RAM", "memory_used": 100,
                 "memory_total": 500, "memory_percent": 20.0,
                 "rss": 80, "vms": 120, "disk": "10% · 1 GiB free",
                 "threads": 3, "file_descriptors": 9,
                 "secret": "must not be returned", "path": "/private",
             }) as snapshot:
            denied = self.client.get("/internal/ops/metrics")
            self.assertEqual(denied.status_code, 403)
            snapshot.assert_not_called()
            response = self.client.get("/internal/ops/metrics", headers={"X-Videl-Internal": "ops-test-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["process"]["cpu"], 12.5)
        self.assertNotIn("secret", response.json["process"])
        self.assertNotIn("path", response.json["process"])
        self.assertIsInstance(response.json["process"]["measured_at"], int)

    def test_unavailable_metrics_fail_without_fabricated_values(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "ops-test-secret"), \
             patch("videl.plugins.tools._resource_snapshot", side_effect=RuntimeError("private failure")):
            response = self.client.get("/internal/ops/metrics", headers={"X-Videl-Internal": "ops-test-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json["process"])
        self.assertEqual(response.json["state"], "unavailable")

    def test_ops_event_feed_requires_secret_and_returns_only_bounded_safe_schema(self):
        db = mongomock.MongoClient().videl
        db["command_events"].insert_many([
            {"schema_version": 1, "at": datetime.now(timezone.utc), "command": "start", "chat_type": "private", "chat_id": 123, "user_id": 456, "message": "private"},
            {"at": datetime.now(timezone.utc), "command": "old"},
        ])
        with patch.object(self.api.config, "WEBAPP_SECRET", "ops-test-secret"):
            with patch("videl.utils.db.get_db", return_value=db):
                self.assertEqual(self.client.get("/internal/ops/events").status_code, 403)
                response = self.client.get("/internal/ops/events", headers={"X-Videl-Internal": "ops-test-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["schema_version"], 1)
        self.assertEqual(len(response.json["events"]), 1)
        event = response.json["events"][0]
        self.assertEqual(event["command"], "start")
        self.assertNotIn("chat_id", event)
        self.assertNotIn("user_id", event)
        self.assertNotIn("message", event)


if __name__ == "__main__":
    unittest.main()
