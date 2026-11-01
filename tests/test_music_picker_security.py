import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from videl.core.queue import chat_queues
from videl.modules import play as play_module


class MusicPickerBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.chat_id, self.user_id = -98001, 98001
        self.key = f"{self.chat_id}:{self.user_id}"
        chat_queues.pop(self.chat_id, None)
        play_module._search_cache[self.key] = {
            "results": [{
                "url": "https://youtube.example/picked-track",
                "title": "Picked track",
                "duration": "2:00",
                "duration_iso": "PT2M",
                "thumbnail": "",
                "video_id": "picked-track",
            }],
            "video": False,
            "play_next": False,
            "requester": "Requester",
            "requester_id": self.user_id,
            "ts": time.time(),
        }
        self.message = NS(chat=NS(id=self.chat_id), delete=AsyncMock())

    async def asyncTearDown(self):
        chat_queues.pop(self.chat_id, None)
        play_module._search_cache.pop(self.key, None)

    def query(self, actor_id, *, choice="cancel", chat_id=None):
        message = self.message
        if chat_id is not None:
            message = NS(chat=NS(id=chat_id), delete=AsyncMock())
        return NS(
            data=f"ytpick:{choice}:{self.key}",
            from_user=NS(id=actor_id) if actor_id is not None else None,
            message=message,
            answer=AsyncMock(),
        )

    async def test_another_member_cannot_cancel_requester_picker(self):
        query = self.query(98002)
        await play_module.ytpick_callback(None, query)
        query.answer.assert_awaited_once_with("Only the requester can choose", show_alert=True)
        self.message.delete.assert_not_awaited()
        self.assertIn(self.key, play_module._search_cache)

    async def test_owner_does_not_bypass_requester_bound_picker(self):
        import config
        query = self.query(config.OWNER_ID)
        await play_module.ytpick_callback(None, query)
        query.answer.assert_awaited_once_with("Only the requester can choose", show_alert=True)
        self.assertIn(self.key, play_module._search_cache)
        self.assertEqual(chat_queues.get(self.chat_id), None)

    async def test_picker_callback_must_remain_in_originating_chat(self):
        query = self.query(self.user_id, chat_id=self.chat_id - 1)
        await play_module.ytpick_callback(None, query)
        query.answer.assert_awaited_once_with("This track picker belongs to another chat", show_alert=True)
        self.assertIn(self.key, play_module._search_cache)

    async def test_picker_requires_identified_actor(self):
        query = self.query(None)
        await play_module.ytpick_callback(None, query)
        query.answer.assert_awaited_once_with("Only the requester can choose", show_alert=True)
        self.assertIn(self.key, play_module._search_cache)


if __name__ == "__main__":
    unittest.main()
