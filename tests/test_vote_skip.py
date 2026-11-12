import asyncio
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.modules import smartqueue


class VoteSkipTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        smartqueue._skip_votes.clear()
        smartqueue._vote_track.clear()
        smartqueue._skip_in_progress.clear()
        self.chat_id = -100123
        self.track = {"video_id": "abcdefghijk", "title": "Current track"}
        self.message = SimpleNamespace(id=77, chat=SimpleNamespace(id=self.chat_id), reply=AsyncMock())
        self.card = SimpleNamespace(id=77)
        self.player = SimpleNamespace(
            _np_msg={self.chat_id: self.card}, _np_song={self.chat_id: self.track}
        )
        self.settings = patch.object(smartqueue, "get_skip_votes_needed", return_value=2)
        self.current = patch.object(smartqueue, "peek_current", return_value=self.track)
        self.settings.start()
        self.current.start()
        self.addCleanup(self.settings.stop)
        self.addCleanup(self.current.stop)
        import videl.core as core
        self.player_patch = patch.object(core, "player", self.player, create=True)
        self.player_patch.start()
        self.addCleanup(self.player_patch.stop)
        self.send_patch = patch.object(smartqueue, "rich_send", new=AsyncMock())
        self.send_patch.start()
        self.addCleanup(self.send_patch.stop)
        self.transitions = types.ModuleType("videl.core.transitions")
        self.transition = AsyncMock()
        self.transitions.transition = self.transition
        self.transitions_patch = patch.dict(sys.modules, {"videl.core.transitions": self.transitions})
        self.transitions_patch.start()
        self.addCleanup(self.transitions_patch.stop)

    def callback(self, user_id, message=None):
        return SimpleNamespace(
            message=message or self.message,
            from_user=SimpleNamespace(id=user_id, mention=f"user-{user_id}"),
            answer=AsyncMock(),
        )

    async def test_stale_or_forwarded_player_card_cannot_cast_votes(self):
        other = SimpleNamespace(id=999, chat=SimpleNamespace(id=self.chat_id), reply=AsyncMock())
        cq = self.callback(1, other)
        await smartqueue.handle_vote_skip(cq)
        cq.answer.assert_awaited_once()
        self.assertEqual(smartqueue._skip_votes.get(self.chat_id, set()), set())

    async def test_forwarded_card_in_another_group_cannot_cast_votes(self):
        forwarded = SimpleNamespace(
            id=77, chat=SimpleNamespace(id=-100999), reply=AsyncMock()
        )
        cq = self.callback(1, forwarded)
        await smartqueue.handle_vote_skip(cq)
        cq.answer.assert_awaited_once()
        self.assertNotIn(-100999, smartqueue._skip_votes)

    async def test_threshold_uses_acknowledged_shared_transition_without_popping_first(self):
        self.transition.return_value = SimpleNamespace(title="Track skipped", body="Confirmed", confirmed=True)
        with patch("videl.core.queue.pop_current", side_effect=AssertionError("must not pop before acknowledgement")):
            await smartqueue.handle_vote_skip(self.callback(1))
            await smartqueue.handle_vote_skip(self.callback(2))
        self.transition.assert_awaited_once_with(self.chat_id, "skip", message=self.message, expected=self.track)
        self.assertEqual(smartqueue._skip_votes[self.chat_id], set())

    async def test_same_user_cannot_supply_multiple_votes(self):
        first = self.callback(5)
        duplicate = self.callback(5)
        await smartqueue.handle_vote_skip(first)
        await smartqueue.handle_vote_skip(duplicate)
        self.assertEqual(smartqueue._skip_votes[self.chat_id], {5})
        self.transition.assert_not_awaited()
        duplicate.answer.assert_awaited_once()

    async def test_unconfirmed_threshold_never_pre_pops_the_live_queue(self):
        from videl.core.queue import chat_queues
        self.current.stop()
        chat_queues[self.chat_id] = [self.track, {"video_id": "next-track-1", "title": "Next"}]
        self.addCleanup(chat_queues.pop, self.chat_id, None)
        original = list(chat_queues[self.chat_id])
        self.transition.return_value = SimpleNamespace(title="Skip not confirmed", body="Queue preserved", confirmed=False)
        await smartqueue.handle_vote_skip(self.callback(1))
        await smartqueue.handle_vote_skip(self.callback(2))
        self.assertEqual(chat_queues[self.chat_id], original)

    async def test_failed_transition_preserves_queue_and_allows_a_fresh_vote(self):
        self.transition.return_value = SimpleNamespace(title="Skip not confirmed", body="Queue preserved", confirmed=False)
        await smartqueue.handle_vote_skip(self.callback(1))
        await smartqueue.handle_vote_skip(self.callback(2))
        self.assertEqual(smartqueue._skip_votes[self.chat_id], set())
        self.assertNotIn(self.chat_id, smartqueue._skip_in_progress)

    async def test_concurrent_threshold_callbacks_start_only_one_transition(self):
        entered = asyncio.Event()
        release = asyncio.Event()

        async def delayed_transition(*args, **kwargs):
            entered.set()
            await release.wait()
            return SimpleNamespace(title="Track skipped", body="Confirmed", confirmed=True)

        self.transition.side_effect = delayed_transition
        first = asyncio.create_task(smartqueue.handle_vote_skip(self.callback(1)))
        await first
        second = asyncio.create_task(smartqueue.handle_vote_skip(self.callback(2)))
        await asyncio.wait_for(entered.wait(), timeout=2)
        third = asyncio.create_task(smartqueue.handle_vote_skip(self.callback(3)))
        await third
        self.assertEqual(self.transition.await_count, 1)
        release.set()
        await second

    async def test_threshold_change_clears_votes_cast_under_previous_rule(self):
        smartqueue._vote_track[self.chat_id] = "abcdefghijk"
        smartqueue._skip_votes[self.chat_id] = {10}
        message = SimpleNamespace(chat=SimpleNamespace(id=self.chat_id), command=["voteskip", "3"])
        with patch.object(smartqueue, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(smartqueue, "set_skip_votes_needed") as save_threshold:
            await smartqueue.set_voteskip_cmd(None, message)
        save_threshold.assert_called_once_with(self.chat_id, 3)
        self.assertEqual(smartqueue._skip_votes[self.chat_id], set())
        self.assertEqual(smartqueue._vote_track[self.chat_id], "abcdefghijk")

    async def test_player_vote_status_tracks_only_the_current_track(self):
        smartqueue._vote_track[self.chat_id] = "abcdefghijk"
        smartqueue._skip_votes[self.chat_id] = {10, 11}
        self.assertEqual(smartqueue.vote_status(self.chat_id), (2, 2))
        self.current.stop()
        self.current = patch.object(smartqueue, "peek_current", return_value={"video_id": "different"})
        self.current.start()
        self.addCleanup(self.current.stop)
        self.assertEqual(smartqueue.vote_status(self.chat_id), (0, 2))


if __name__ == "__main__":
    unittest.main()
