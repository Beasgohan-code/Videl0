import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from videl.core.queue import chat_queues
from videl.modules import play as play_module


class PlayNextPickerTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_selection_inserts_immediately_after_current_track(self):
        chat_id, user_id = -92001, 92001
        key = f"{chat_id}:{user_id}"
        current = {"title": "Currently playing"}
        queued = {"title": "Already queued"}
        chat_queues[chat_id] = [current, queued]
        message = NS(chat=NS(id=chat_id), delete=AsyncMock())
        query = NS(
            data=f"ytpick:0:{key}",
            from_user=NS(id=user_id),
            message=message,
            answer=AsyncMock(),
        )
        play_module._search_cache[key] = {
            "results": [{
                "url": "https://youtube.example/next-track",
                "title": "Play this next",
                "duration": "2:00",
                "duration_iso": "PT2M",
                "thumbnail": "",
                "video_id": "next-track",
            }],
            "video": False,
            "play_next": True,
            "requester": "Listener",
            "requester_id": user_id,
            "ts": time.time(),
        }

        try:
            with patch.object(play_module, "play_song", new=AsyncMock()) as play_song:
                await play_module.ytpick_callback(None, query)

            self.assertEqual([song["title"] for song in chat_queues[chat_id]], [
                "Currently playing", "Play this next", "Already queued"
            ])
            query.answer.assert_awaited_once_with("Added next")
            message.delete.assert_awaited_once()
            play_song.assert_not_awaited()
        finally:
            chat_queues.pop(chat_id, None)
            play_module._search_cache.pop(key, None)


if __name__ == "__main__":
    unittest.main()
