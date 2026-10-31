from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from videl.games import community_events


class MemoryEvents:
    def __init__(self):
        self.rows = {}

    def insert_one(self, row):
        self.rows[row["_id"]] = deepcopy(row)

    def find_one(self, query):
        row = self.rows.get(query.get("_id"))
        return deepcopy(row) if row else None

    def update_one(self, query, update, **kwargs):
        row = self.rows[query["_id"]]
        attendee_filter = update.get("$pull", {}).get("attendees")
        if isinstance(attendee_filter, dict):
            user_id = attendee_filter.get("user_id")
            row["attendees"] = [item for item in row.get("attendees", []) if item.get("user_id") != user_id]
        if "attendees" in update.get("$push", {}):
            row.setdefault("attendees", []).append(deepcopy(update["$push"]["attendees"]))
        for key, value in update.get("$set", {}).items():
            if not key.startswith("reminders.$["):
                row[key] = deepcopy(value)
        return type("UpdateResult", (), {"matched_count": 1})()


class CommunityEventTests(unittest.TestCase):
    def test_creation_requires_timezone_and_limits_window(self):
        base = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
        with patch.object(community_events, "_now", return_value=base):
            with self.assertRaisesRegex(community_events.EventError, "timezone"):
                community_events.create(4, "Host", {"title": "Game night", "starts_at": "2026-10-30T12:00"}, -100, "Test group")
            with self.assertRaisesRegex(community_events.EventError, "90 days"):
                community_events.create(4, "Host", {"title": "Game night", "starts_at": (base + timedelta(days=91)).isoformat()}, -100, "Test group")

    def test_creation_stores_optional_music_game_and_staggered_reminders(self):
        base = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
        events = MemoryEvents()
        start = base + timedelta(days=2)
        with patch.object(community_events, "_now", return_value=base), patch.object(community_events, "_collection", return_value=events):
            event = community_events.create(4, "Host", {
                "title": "Game night", "description": "Bring a friend", "starts_at": start.isoformat(),
                "music_query": "Daft Punk", "game_room": "ABCD2",
            }, -100, "Test group")
        saved = events.find_one({"_id": event["id"]})
        self.assertEqual(event["music_query"], "Daft Punk")
        self.assertEqual(event["game_room"], "ABCD2")
        self.assertEqual(saved["chat_id"], -100)
        self.assertEqual([item["key"] for item in saved["reminders"]], ["24h", "1h", "15m"])

    def test_rsvp_is_actor_scoped_and_updates_existing_choice(self):
        base = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
        events = MemoryEvents()
        start = base + timedelta(hours=3)
        with patch.object(community_events, "_now", return_value=base), patch.object(community_events, "_collection", return_value=events):
            event = community_events.create(4, "Host", {"title": "Game night", "starts_at": start.isoformat()}, -100, "Test group")
            community_events.rsvp(event["id"], 9, "Player", "going")
            changed = community_events.rsvp(event["id"], 9, "Player", "maybe")
        self.assertEqual(changed["my_rsvp"], "maybe")
        self.assertEqual(changed["rsvp_counts"]["going"], 0)
        self.assertEqual(changed["rsvp_counts"]["maybe"], 1)
        self.assertEqual(len(events.find_one({"_id": event["id"]})["attendees"]), 1)

    def test_host_can_edit_event_and_refresh_reminders_but_other_members_cannot(self):
        base = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
        events = MemoryEvents()
        start = base + timedelta(days=2)
        with patch.object(community_events, "_now", return_value=base), patch.object(community_events, "_collection", return_value=events):
            event = community_events.create(4, "Host", {"title": "Game night", "starts_at": start.isoformat()}, -100, "Test group")
            community_events.rsvp(event["id"], 9, "Player", "going")
            with self.assertRaisesRegex(community_events.EventError, "host"):
                community_events.update(event["id"], 9, {"title": "Changed", "starts_at": (start + timedelta(hours=1)).isoformat()})
            updated = community_events.update(event["id"], 4, {
                "title": "New game night", "description": "Updated plan",
                "starts_at": (start + timedelta(hours=1)).isoformat(),
            })
        stored = events.find_one({"_id": event["id"]})
        self.assertEqual(updated["title"], "New game night")
        self.assertEqual(updated["rsvp_counts"]["going"], 1)
        self.assertEqual([item["key"] for item in stored["reminders"]], ["24h", "1h", "15m"])

    def test_invalid_rsvp_and_game_room_codes_are_refused(self):
        base = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
        with patch.object(community_events, "_now", return_value=base):
            with self.assertRaisesRegex(community_events.EventError, "Arcade room code"):
                community_events.create(4, "Host", {
                    "title": "Game night", "starts_at": (base + timedelta(hours=2)).isoformat(), "game_room": "bad!",
                }, -100, "Test group")
            with self.assertRaisesRegex(community_events.EventError, "Going"):
                community_events.rsvp("ABCDEFGH", 9, "Player", "invalid")


if __name__ == "__main__":
    unittest.main()
