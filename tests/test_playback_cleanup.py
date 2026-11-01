import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from videl.core import player, transitions
from videl.core.playback_state import Session, sessions
from videl.core.queue import chat_queues
from videl.modules import play as play_module


class PlayerCardCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_natural_end_deletes_player_card_when_queue_is_empty(self):
        chat_id = -700001
        song = {"title": "Finished track"}
        observed = Session(song, 1.0)
        chat_queues[chat_id] = [song]
        sessions[chat_id] = observed
        try:
            with patch.object(player, "get_loop", return_value="off"), \
                 patch("videl.core.autoplay.refill", new=AsyncMock()), \
                 patch.object(transitions, "stop", new=AsyncMock()) as stop:
                await transitions.finished(chat_id, observed)
            stop.assert_awaited_once_with(
                chat_id,
                delete_player_card=True,
                queue_finished=True,
                completed_song=song,
            )
        finally:
            chat_queues.pop(chat_id, None)
            sessions.pop(chat_id, None)

    async def test_queue_completion_notice_includes_track_and_navigation(self):
        chat_id = -700003
        song = {"title": "A <bright> finale", "requester": "Listener"}
        with patch("videl.utils.command_ui.rich_send", new=AsyncMock()) as send:
            await transitions.announce_queue_finished(chat_id, song)
        self.assertEqual(send.call_args.args[:2], (player.bot, chat_id))
        body = send.call_args.args[2]
        self.assertIn("Queue complete", body)
        self.assertIn("A &lt;bright&gt; finale", body)
        self.assertIn("Requested by", body)
        self.assertIn("/play", body)

    async def test_picker_is_deleted_after_track_is_selected_and_started(self):
        chat_id, user_id = -700002, 700002
        key = f"{chat_id}:{user_id}"
        message = NS(
            id=51,
            chat=NS(id=chat_id),
            delete=AsyncMock(),
        )
        query = NS(
            data=f"ytpick:0:{key}",
            from_user=NS(id=user_id),
            message=message,
            answer=AsyncMock(),
        )
        chat_queues.pop(chat_id, None)
        play_module._search_cache[key] = {
            "results": [{
                "url": "https://youtube.example/track",
                "title": "Selected track",
                "duration": "2:14",
                "duration_iso": "PT2M14S",
                "thumbnail": "",
                "video_id": "track",
            }],
            "video": False,
            "requester": "Listener",
            "requester_id": user_id,
            "ts": __import__("time").time(),
        }
        try:
            with patch.object(play_module, "play_song", new=AsyncMock(return_value=True)):
                await play_module.ytpick_callback(None, query)
            query.answer.assert_awaited_once_with("Starting playback")
            message.delete.assert_awaited_once()
        finally:
            chat_queues.pop(chat_id, None)
            play_module._search_cache.pop(key, None)

    async def test_replaced_player_card_is_deleted_only_after_new_card_exists(self):
        old = NS(id=10, delete=AsyncMock())
        new = NS(id=11, delete=AsyncMock())
        self.assertFalse(player._same_message(old, new))
        self.assertTrue(player._same_message(old, NS(id=10)))
        self.assertTrue(await player._delete_message(old))
        old.delete.assert_awaited_once()
