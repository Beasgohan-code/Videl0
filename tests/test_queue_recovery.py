import unittest
from unittest.mock import patch

from videl.core import queue


class QueueRecoveryTests(unittest.IsolatedAsyncioTestCase):
    CHAT = -190001

    def tearDown(self):
        queue.chat_queues.pop(self.CHAT, None)
        queue._recoverable.pop(self.CHAT, None)
        queue._revisions.pop(self.CHAT, None)
        queue._persist_locks.pop(self.CHAT, None)

    def test_persisted_track_contains_only_safe_metadata(self):
        row = queue._record({
            "url": "https://www.youtube.com/watch?v=abcdefghijk&token=temporary",
            "title": "A track", "duration": "3:21", "requester": "Alice",
            "requester_id": 123, "thumbnail": "https://example.test/private",
            "duration_seconds": 201,
        })
        self.assertEqual(row, {
            "video_id": "abcdefghijk", "title": "A track", "duration": "3:21",
            "duration_seconds": 201, "video": False,
        })
        self.assertNotIn("url", row)
        self.assertNotIn("requester_id", row)

    def test_unsupported_track_urls_are_not_saved(self):
        self.assertIsNone(queue._record({"url": "https://example.test/audio.mp3", "title": "Track"}))

    def test_snapshot_marks_active_interrupted_and_persists_only_upcoming_ids(self):
        captured = {}
        class Collection:
            def update_one(self, selector, update, upsert):
                captured.update(selector=selector, update=update, upsert=upsert)
        class DB:
            def __getitem__(self, name):
                self.name = name
                return Collection()
        active = {"url": "https://youtube.com/watch?v=abcdefghijk&sig=temporary", "title": "Playing", "requester_id": 1}
        pending = {"url": "https://youtu.be/lmnopqrstuv", "title": "Next", "requester_id": 2}
        with patch("videl.utils.db.get_db", return_value=DB()):
            queue._write_snapshot(self.CHAT, 4, [active, pending])
        doc = captured["update"]["$set"]
        self.assertEqual(captured["selector"], {"_id": self.CHAT, "revision": {"$lt": 4}})
        self.assertEqual(doc["active_interrupted"]["video_id"], "abcdefghijk")
        self.assertEqual(doc["upcoming"][0]["video_id"], "lmnopqrstuv")
        self.assertNotIn("url", doc["active_interrupted"])
        self.assertNotIn("requester_id", doc["upcoming"][0])

    async def test_recovery_loads_for_explicit_restore_without_resuming(self):
        doc = {"_id": self.CHAT, "version": 1, "revision": 8,
               "active_interrupted": {"title": "Old active"},
               "upcoming": [{"video_id": "abcdefghijk", "title": "Next", "duration": "2:00", "duration_seconds": 120}]}
        class Collection:
            def find(self, query, projection):
                self.query = query
                return self
            def limit(self, count):
                return [doc]
        class DB:
            def __getitem__(self, name):
                self.collection = Collection()
                return self.collection
        with patch("videl.utils.db.get_db", return_value=DB()):
            self.assertEqual(await queue.initialize_recovery(), 1)
        self.assertNotIn(self.CHAT, queue.chat_queues)
        self.assertEqual(queue.recovery_info(self.CHAT)["count"], 1)

    def test_restore_requires_a_fresh_active_track_and_appends_upcoming_only(self):
        current = {"title": "Fresh current"}
        queue.chat_queues[self.CHAT] = [current]
        queue._recoverable[self.CHAT] = {"tracks": [{
            "video_id": "abcdefghijk", "title": "Saved next", "duration": "2:00",
            "duration_seconds": 120, "video": False,
        }]}
        self.assertEqual(queue.restore_upcoming(self.CHAT), 1)
        self.assertIs(queue.chat_queues[self.CHAT][0], current)
        self.assertEqual(queue.chat_queues[self.CHAT][1]["url"], "https://www.youtube.com/watch?v=abcdefghijk")
        self.assertEqual(queue.chat_queues[self.CHAT][1]["requester"], "Restored queue")
        self.assertIsNone(queue.recovery_info(self.CHAT))

    def test_empty_queue_cannot_restore_a_saved_active_stream(self):
        queue._recoverable[self.CHAT] = {"tracks": [{"video_id": "abcdefghijk"}]}
        self.assertEqual(queue.restore_upcoming(self.CHAT), 0)
        self.assertNotIn(self.CHAT, queue.chat_queues)


if __name__ == "__main__":
    unittest.main()
