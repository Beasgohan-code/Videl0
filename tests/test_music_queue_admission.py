import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from videl.core import queue, request_approval
from videl.modules import play as play_module
from videl.plugins import music_approval


class MusicQueueAdmissionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.chat_id = -77002
        queue.chat_queues.pop(self.chat_id, None)
        request_approval.clear(self.chat_id)
        self.addCleanup(queue.chat_queues.pop, self.chat_id, None)
        self.addCleanup(request_approval.clear, self.chat_id)

    async def test_full_queue_rejects_play_before_assistant_or_provider_work(self):
        queue.chat_queues[self.chat_id] = [
            {"title": "Current"}, {"title": "Two"}, {"title": "Three"}
        ]
        message = NS(chat=NS(id=self.chat_id))
        with patch("config.QUEUE_LIMIT", 3), \
             patch.object(play_module, "rich_send", new=AsyncMock()) as send, \
             patch.object(play_module, "is_assistant_in", new=AsyncMock()) as assistant, \
             patch.object(play_module, "search_yt", new=AsyncMock()) as search:
            await play_module._process_play(message, "a track")

        self.assertIn("Queue is full", send.await_args.args[2])
        assistant.assert_not_awaited()
        search.assert_not_awaited()

    async def test_full_queue_rejects_local_media_before_download(self):
        queue.chat_queues[self.chat_id] = [{"title": "Current"}]
        media = NS(file_name="track.mp3", duration=60, file_size=1024)
        reply = NS(video=None, audio=media, voice=None, video_note=None, document=None)
        message = NS(reply_to_message=reply)
        with patch("config.QUEUE_LIMIT", 1), \
             patch.object(play_module, "rich_send", new=AsyncMock()) as send, \
             patch.object(play_module.bot, "get_messages", new=AsyncMock()) as get_messages, \
             patch.object(play_module.bot, "download_media", new=AsyncMock()) as download:
            handled = await play_module._play_local_media(message, self.chat_id, 77002)

        self.assertTrue(handled)
        self.assertIn("Queue is full", send.await_args.args[2])
        get_messages.assert_not_awaited()
        download.assert_not_awaited()

    async def test_url_playlist_is_partially_admitted_and_reports_capacity(self):
        queue.chat_queues[self.chat_id] = [
            {"title": "Current"}, {"title": "Already queued"}
        ]
        pm = NS(delete=AsyncMock())
        playlist = {
            "playlist": [
                {
                    "link": f"https://www.youtube.com/watch?v=videoid{i:04d}",
                    "title": f"New {i}",
                    "duration": "PT1M",
                    "thumbnail": "",
                }
                for i in range(4)
            ]
        }
        message = NS(
            chat=NS(id=self.chat_id),
            from_user=NS(id=77002, first_name="Listener"),
        )
        with patch("config.QUEUE_LIMIT", 3), \
             patch.object(play_module, "rich_send", new=AsyncMock(return_value=pm)) as send, \
             patch.object(play_module, "rich_edit", new=AsyncMock()) as edit, \
             patch.object(play_module, "is_assistant_in", new=AsyncMock(return_value=True)), \
             patch.object(play_module, "search_yt", new=AsyncMock(return_value=playlist)), \
             patch.object(play_module, "play_song", new=AsyncMock()) as play_song:
            await play_module._process_play(message, "https://youtube.com/playlist?list=abc")

        self.assertEqual(len(queue.get_queue(self.chat_id)), 3)
        self.assertEqual(queue.get_queue(self.chat_id)[-1]["title"], "New 0")
        self.assertIn("Queue capacity reached", send.await_args.args[2])
        self.assertIn("3 tracks were not added", send.await_args.args[2])
        edit.assert_not_awaited()
        play_song.assert_not_awaited()
        pm.delete.assert_awaited_once()

    async def test_autoplay_stops_fetching_when_capacity_is_reached(self):
        from videl.core import autoplay
        queue.chat_queues[self.chat_id] = [{"title": "Current"}, {"title": "Queued"}]
        autoplay.stop_autoplay(self.chat_id)
        autoplay._generations[self.chat_id] = object()
        autoplay._autoplay_active[self.chat_id] = True
        autoplay._autoplay_query[self.chat_id] = "ambient"
        autoplay._autoplay_fetched[self.chat_id] = set()
        self.addCleanup(autoplay.stop_autoplay, self.chat_id)
        playlist = {
            "playlist": [
                {
                    "link": f"https://www.youtube.com/watch?v=autovidid{i:04d}",
                    "title": f"Auto {i}",
                    "duration": "PT1M",
                    "thumbnail": "",
                }
                for i in range(3)
            ]
        }
        with patch("config.QUEUE_LIMIT", 3), patch.object(
            autoplay, "search_yt", new=AsyncMock(return_value=playlist)
        ) as search:
            added = await autoplay._fetch_more(self.chat_id, "Auto", 77002)

        self.assertEqual(added, 1)
        self.assertEqual(len(queue.get_queue(self.chat_id)), 3)
        search.assert_awaited_once()

    async def test_full_queue_does_not_consume_pending_approval(self):
        queue.chat_queues[self.chat_id] = [{"title": "Current"}, {"title": "Queued"}]
        token = request_approval.submit(
            self.chat_id,
            {"title": "Pending", "_queue_chat_id": self.chat_id},
        )
        ctx = NS(
            command=NS(arguments=f"approve {token}"),
            message=NS(chat=NS(id=self.chat_id)),
        )

        with patch("config.QUEUE_LIMIT", 2):
            with self.assertRaises(music_approval.CommandError):
                await music_approval.requests(ctx)

        pending = request_approval.list_pending(self.chat_id)
        self.assertEqual([item["id"] for item in pending], [token])
        self.assertEqual([item["song"]["title"] for item in pending], ["Pending"])


if __name__ == "__main__":
    unittest.main()
