import unittest

from videl.core.queue import add_request, chat_queues, insert_next, requester_capacity


class InsertNextQueueTests(unittest.TestCase):
    def tearDown(self):
        for chat_id in (-91001, -91002):
            chat_queues.pop(chat_id, None)

    def test_insert_next_places_track_after_current_not_at_front(self):
        chat_id = -91001
        current, queued, next_track = ({"title": title} for title in ("current", "queued", "next"))
        chat_queues[chat_id] = [current, queued]

        position = insert_next(chat_id, next_track)

        self.assertEqual(position, 2)
        self.assertEqual(chat_queues[chat_id], [current, next_track, queued])

    def test_offset_keeps_playlist_insertion_order_before_existing_queue(self):
        chat_id = -91002
        current, queued = {"title": "current"}, {"title": "queued"}
        first, second = {"title": "first"}, {"title": "second"}
        chat_queues[chat_id] = [current, queued]

        self.assertEqual(insert_next(chat_id, first), 2)
        self.assertEqual(insert_next(chat_id, second, offset=1), 3)
        self.assertEqual(chat_queues[chat_id], [current, first, second, queued])

    def test_requester_is_limited_to_three_upcoming_tracks(self):
        chat_id = -91002
        chat_queues[chat_id] = [{"requester_id": 1, "title": "current"}]
        for index in range(3):
            self.assertIsNotNone(add_request(chat_id, {"requester_id": 7, "title": str(index)}))
        self.assertEqual(requester_capacity(chat_id, 7), 0)
        before = list(chat_queues[chat_id])
        self.assertIsNone(add_request(chat_id, {"requester_id": 7, "title": "blocked"}))
        self.assertEqual(chat_queues[chat_id], before)

    def test_fair_share_is_per_requester_and_allows_idle_chat_to_start(self):
        chat_id = -91001
        self.assertEqual(add_request(chat_id, {"requester_id": 7, "title": "first"}), 1)
        for index in range(3):
            self.assertIsNotNone(add_request(chat_id, {"requester_id": 7, "title": str(index)}))
        self.assertEqual(requester_capacity(chat_id, 8), 3)
        self.assertIsNotNone(add_request(chat_id, {"requester_id": 8, "title": "other"}))

    def test_insert_next_starts_current_track_when_queue_is_empty(self):
        chat_id = -91001
        track = {"title": "first"}

        self.assertEqual(insert_next(chat_id, track), 1)
        self.assertEqual(chat_queues[chat_id], [track])


if __name__ == "__main__":
    unittest.main()
