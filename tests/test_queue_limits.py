import unittest
from unittest.mock import patch

from videl.core import queue


class QueueLimitTests(unittest.TestCase):
    def setUp(self):
        self.chat_id = -77001
        queue.chat_queues.pop(self.chat_id, None)
        queue._recoverable.pop(self.chat_id, None)
        self.limit = patch("config.QUEUE_LIMIT", 3)
        self.limit.start()
        self.addCleanup(self.limit.stop)
        self.addCleanup(queue.chat_queues.pop, self.chat_id, None)
        self.addCleanup(queue._recoverable.pop, self.chat_id, None)

    def test_append_and_insert_refuse_growth_past_limit(self):
        current, upcoming, extra, new = (
            {"title": title} for title in ("current", "upcoming", "extra", "new")
        )
        queue.chat_queues[self.chat_id] = [current, upcoming, extra]
        original = list(queue.chat_queues[self.chat_id])
        revision = queue.mutation_revision(self.chat_id)

        self.assertIsNone(queue.add_to_queue(self.chat_id, new))
        self.assertIsNone(queue.insert_next(self.chat_id, new))
        self.assertEqual(queue.chat_queues[self.chat_id], original)
        self.assertEqual(queue.mutation_revision(self.chat_id), revision)

    def test_queue_limit_counts_current_track_and_accepts_until_capacity(self):
        current = {"title": "current"}
        queue.chat_queues[self.chat_id] = [current]
        second, third, fourth = ({"title": str(i)} for i in range(3))

        self.assertEqual(queue.add_to_queue(self.chat_id, second), 2)
        self.assertEqual(queue.insert_next(self.chat_id, third), 2)
        self.assertIsNone(queue.add_to_queue(self.chat_id, fourth))
        self.assertEqual(len(queue.get_queue(self.chat_id)), 3)
        self.assertIsNone(queue.add_to_queue(self.chat_id, {"title": "over limit"}))

    def test_recovery_restore_is_all_or_nothing_and_can_retry_after_freeing_slots(self):
        current, queued = {"title": "current"}, {"title": "queued"}
        queue.chat_queues[self.chat_id] = [current, queued]
        records = [
            {"video_id": f"videoid{i:04d}", "title": f"Restored {i}"}
            for i in range(2)
        ]
        queue._recoverable[self.chat_id] = {"tracks": records.copy(), "revision": 1}
        revision = queue.mutation_revision(self.chat_id)

        self.assertEqual(queue.restore_upcoming(self.chat_id), 0)
        self.assertEqual(queue.get_queue(self.chat_id), [current, queued])
        self.assertEqual(queue._recoverable[self.chat_id]["tracks"], records)
        self.assertEqual(queue.mutation_revision(self.chat_id), revision)

        queue.remove_upcoming(self.chat_id, 1)
        self.assertEqual(queue.restore_upcoming(self.chat_id), 2)
        self.assertEqual([song["title"] for song in queue.get_queue(self.chat_id)], [
            "current", "Restored 0", "Restored 1"
        ])
        self.assertIsNone(queue.recovery_info(self.chat_id))

    def test_queue_snapshot_respects_recovery_capacity(self):
        current = {"video_id": "current0001", "title": "Current"}
        upcoming = [
            {"video_id": f"upcom{i:06d}", "title": f"Track {i}"}
            for i in range(5)
        ]

        class Collection:
            def update_one(self, query, update, upsert=False):
                self.document = update["$set"]

        collection = Collection()
        database = {"music_queue_recovery": collection}
        with patch("videl.utils.db.get_db", return_value=database):
            queue._write_snapshot(self.chat_id, 2, [current, *upcoming])

        self.assertEqual(
            [row["video_id"] for row in collection.document["upcoming"]],
            ["upcom000000", "upcom000001"],
        )

    def test_full_queue_keeps_unrestored_recovery_records(self):
        queue.chat_queues[self.chat_id] = [
            {"title": "Current"}, {"title": "One"}, {"title": "Two"}
        ]
        records = [{"video_id": "videoid00001", "title": "Restored"}]
        queue._recoverable[self.chat_id] = {"tracks": records.copy(), "revision": 1}
        revision = queue.mutation_revision(self.chat_id)

        self.assertEqual(queue.restore_upcoming(self.chat_id), 0)
        self.assertEqual(queue._recoverable[self.chat_id]["tracks"], records)
        self.assertEqual(queue.mutation_revision(self.chat_id), revision)

    def test_rotation_can_preserve_existing_queue_order_at_capacity(self):
        queue.chat_queues[self.chat_id] = [
            {"title": "current"}, {"title": "next"}, {"title": "last"}
        ]
        finished = queue.pop_current(self.chat_id)
        self.assertEqual(queue.add_to_queue(self.chat_id, finished, internal=True), 3)
        self.assertEqual([song["title"] for song in queue.get_queue(self.chat_id)], ["next", "last", "current"])


if __name__ == "__main__":
    unittest.main()
