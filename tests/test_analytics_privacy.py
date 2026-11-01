import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from videl.utils.analytics_privacy import command_event, fingerprint, recent_events, summarize


class Cursor(list):
    def sort(self, key, direction):
        return Cursor(sorted(self, key=lambda row: row.get(key), reverse=direction < 0))

    def limit(self, count):
        return Cursor(self[:count])


class Collection:
    def __init__(self, rows):
        self.rows = rows

    def count_documents(self, selector):
        since = selector["at"]["$gte"]
        return sum(row.get("at") >= since for row in self.rows)

    def find(self, selector, projection):
        since = selector["at"]["$gte"]
        version = selector.get("schema_version")
        return Cursor([row for row in self.rows if row.get("at") >= since
                       and (version is None or row.get("schema_version") == version)])


class Database:
    def __init__(self, rows):
        self.collection = Collection(rows)

    def __getitem__(self, name):
        assert name == "command_events"
        return self.collection


class AnalyticsPrivacyTests(unittest.TestCase):
    def test_fingerprint_is_stable_keyed_and_domain_separated(self):
        with patch("config.ANALYTICS_SALT", "test-salt"):
            chat_a = fingerprint("chat", -123456)
            self.assertEqual(chat_a, fingerprint("chat", -123456))
            self.assertNotEqual(chat_a, fingerprint("user", -123456))
        with patch("config.ANALYTICS_SALT", "other-salt"):
            self.assertNotEqual(chat_a, fingerprint("chat", -123456))

    def test_new_events_never_store_raw_ids(self):
        with patch("config.ANALYTICS_SALT", "test-salt"):
            event = command_event("PLAY", -100123, 777, "supergroup")
        self.assertEqual(event["command"], "play")
        self.assertNotIn("chat_id", event)
        self.assertNotIn("user_id", event)
        self.assertTrue(event["chat_key"])
        self.assertTrue(event["user_key"])

    def test_no_salt_means_no_identifiers_are_stored(self):
        with patch("config.ANALYTICS_SALT", ""), patch("config.WEBAPP_SECRET", ""):
            event = command_event("help", -100123, 777, "group")
        self.assertNotIn("chat_id", event)
        self.assertNotIn("user_id", event)
        self.assertNotIn("chat_key", event)
        self.assertNotIn("user_key", event)

    def test_recent_ops_feed_is_versioned_bounded_and_identifier_free(self):
        now = datetime.now(timezone.utc)
        rows = [
            {"schema_version": 1, "at": now - timedelta(minutes=i), "command": f"cmd_{i}",
             "chat_type": "supergroup", "chat_id": -100000 - i, "user_id": 900000 + i,
             "message_text": "private text"}
            for i in range(25)
        ]
        rows.append({"at": now, "command": "legacy", "chat_id": -999})
        result = recent_events(Database(rows), limit=200, hours=24, now=now)
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(len(result["events"]), 20)
        self.assertEqual(result["events"][0]["command"], "cmd_0")
        self.assertNotIn("chat_id", repr(result))
        self.assertNotIn("user_id", repr(result))
        self.assertNotIn("private text", repr(result))
        self.assertTrue(all(event["schema_version"] == 1 for event in result["events"]))

    def test_summary_never_returns_raw_legacy_ids(self):
        now = datetime.now(timezone.utc)
        rows = [{
            "at": now - timedelta(minutes=4),
            "command": "play",
            "chat_id": -100123456,
            "user_id": 987654321,
        }]
        with patch("config.ANALYTICS_SALT", "test-salt"):
            result = summarize(Database(rows), now=now)
        self.assertTrue(result["ok"])
        self.assertEqual(result["total_commands"], 1)
        self.assertEqual(result["identity_mode"], "pseudonymous")
        self.assertEqual(len(result["top_chats"]), 1)
        self.assertTrue(result["top_chats"][0]["id"].startswith("chat-"))
        self.assertNotIn(str(rows[0]["chat_id"]), repr(result))
        self.assertNotIn(str(rows[0]["user_id"]), repr(result))
        self.assertNotIn("recent_events", result)

    def test_truncated_summary_does_not_claim_an_exact_active_user_count(self):
        now = datetime.now(timezone.utc)
        rows = [
            {"at": now - timedelta(minutes=2), "command": "help", "chat_id": 41, "user_id": 91},
            {"at": now - timedelta(minutes=1), "command": "play", "chat_id": 42, "user_id": 92},
        ]
        with patch("config.ANALYTICS_SALT", "test-salt"), patch("videl.utils.analytics_privacy.MAX_EVENTS", 1):
            result = summarize(Database(rows), now=now)
        self.assertTrue(result["truncated"])
        self.assertIsNone(result["active_users"])

    def test_summary_is_aggregate_only_without_a_secret(self):
        now = datetime.now(timezone.utc)
        rows = [{"at": now, "command": "help", "chat_id": 42, "user_id": 99}]
        with patch("config.ANALYTICS_SALT", ""), patch("config.WEBAPP_SECRET", ""):
            result = summarize(Database(rows), now=now)
        self.assertEqual(result["identity_mode"], "aggregate_only")
        self.assertIsNone(result["active_users"])
        self.assertEqual(result["top_chats"], [])


if __name__ == "__main__":
    unittest.main()
