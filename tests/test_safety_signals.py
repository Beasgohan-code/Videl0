import importlib.util
from pathlib import Path
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).parents[1]

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

raid = load("raid_signals", "videl/utils/raid.py")
duplicates = load("duplicate_signals", "videl/utils/duplicate_messages.py")
identity = load("identity_signals", "videl/utils/identity_signals.py")
effectiveness = load("rule_effectiveness", "videl/utils/rule_effectiveness.py")


class RaidSignalTests(unittest.TestCase):
    def test_threshold_and_expiry(self):
        raid.clear(123)
        cfg = {"enabled": True, "window_seconds": 10, "join_threshold": 3,
               "duration_minutes": 1}
        self.assertFalse(raid.record(123, "joins", cfg, 100)["active"])
        self.assertFalse(raid.record(123, "joins", cfg, 101)["started"])
        self.assertTrue(raid.record(123, "joins", cfg, 102)["started"])
        self.assertFalse(raid.record(123, "joins", cfg, 103)["started"])
        self.assertTrue(raid.status(123, 150)["active"])
        self.assertFalse(raid.status(123, 163)["active"])

    def test_limits_are_clamped_and_default_is_opt_in(self):
        self.assertFalse(raid.normalize(None)["enabled"])
        cfg = raid.normalize({"enabled": True, "window_seconds": 9000, "join_threshold": 0})
        self.assertEqual(cfg["window_seconds"], 300)
        self.assertEqual(cfg["join_threshold"], 2)


class DuplicateSignalTests(unittest.TestCase):
    def test_three_distinct_senders_raise_one_hash_only_alert(self):
        duplicates.clear()
        text = "Please visit our community rules before posting links."
        self.assertFalse(duplicates.observe(44, 1, text, now=1)["alert"])
        self.assertFalse(duplicates.observe(44, 2, text, now=2)["alert"])
        result = duplicates.observe(44, 3, text, now=3)
        self.assertTrue(result["alert"])
        self.assertEqual(result["distinct_senders"], 3)
        self.assertNotIn(text, result["fingerprint"])
        self.assertFalse(duplicates.observe(44, 4, text, now=4)["alert"])

    def test_short_or_blank_text_is_ignored(self):
        self.assertIsNone(duplicates.fingerprint("same"))


class _FakeCollection:
    def __init__(self):
        self.rows = {}

    def update_one(self, query, update, upsert=False):
        row = self.rows.setdefault((query["chat_id"], query["rule"]), dict(query))
        for key, value in update.get("$inc", {}).items():
            row[key] = row.get(key, 0) + value
        row.update(update.get("$set", {}))

    def find(self, query):
        return [row for (chat, _), row in self.rows.items() if chat == query["chat_id"]]


class _FakeDB(dict):
    def __missing__(self, key):
        value = _FakeCollection()
        self[key] = value
        return value


class RuleEffectivenessTests(unittest.TestCase):
    def test_aggregate_hits_and_feedback_have_no_member_data(self):
        db = _FakeDB()
        self.assertTrue(effectiveness.record(db, -100, "content_lock"))
        self.assertTrue(effectiveness.record(db, -100, "content_lock", "false_positive"))
        row = next(item for item in effectiveness.summary(db, -100) if item["rule"] == "content_lock")
        self.assertEqual(row, {"rule": "content_lock", "hits": 1, "confirmed": 0, "false_positives": 1})
        stored = next(iter(db[effectiveness.COLLECTION].rows.values()))
        self.assertNotIn("user_id", stored)
        self.assertNotIn("text", stored)


class ImpersonationSignalTests(unittest.TestCase):
    def test_lookalike_warns_but_exact_admin_is_not_flagged_as_self(self):
        admin = SimpleNamespace(id=10, first_name="ModeratorAlpha", last_name="", username="modalpha")
        similar = SimpleNamespace(id=11, first_name="ModeratorAlphaa", last_name="", username="modalphaa")
        self.assertIsNotNone(identity.lookalike(similar, [admin]))
        self.assertIsNone(identity.lookalike(admin, [admin]))

    def test_short_names_are_not_flagged(self):
        user = SimpleNamespace(id=12, first_name="Ava", last_name="", username="ava")
        admin = SimpleNamespace(id=10, first_name="Ava", last_name="", username="ava")
        self.assertIsNone(identity.lookalike(user, [admin]))
