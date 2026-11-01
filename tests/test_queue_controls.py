"""Admin queue edits never mutate the currently playing head."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.app import music
from videl.core.queue import chat_queues
from videl.core.transitions import Outcome


CHAT_ID = -91033


def context(name, arguments=""):
    return SimpleNamespace(
        message=SimpleNamespace(chat=SimpleNamespace(id=CHAT_ID)),
        command=SimpleNamespace(name=name, arguments=arguments),
    )


class QueueControlTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        chat_queues.pop(CHAT_ID, None)

    async def test_remove_changes_only_the_selected_upcoming_item(self):
        current, first, second = ({"title": title} for title in ("current", "first", "second"))
        chat_queues[CHAT_ID] = [current, first, second]

        result = await music.manage_queue(context("remove", "2"))

        self.assertEqual(chat_queues[CHAT_ID], [current, first])
        self.assertIn("Removed upcoming track #2", result.html)

    async def test_move_reorders_upcoming_tracks_without_touching_current(self):
        current, first, second, third = ({"title": title} for title in ("current", "first", "second", "third"))
        chat_queues[CHAT_ID] = [current, first, second, third]

        await music.manage_queue(context("move", "1 3"))

        self.assertEqual(chat_queues[CHAT_ID], [current, second, third, first])
        self.assertIs(chat_queues[CHAT_ID][0], current)

    async def test_jump_advances_only_after_transition_is_confirmed(self):
        current, first, selected = ({"title": title} for title in ("current", "first", "selected"))
        chat_queues[CHAT_ID] = [current, first, selected]

        async def confirmed_skip(chat_id, action, *, expected):
            self.assertEqual((chat_id, action, expected), (CHAT_ID, "skip", current))
            chat_queues[CHAT_ID].pop(0)
            return Outcome("Skipped", "Voice playback confirmed.")

        with patch("videl.core.transitions.transition", new=AsyncMock(side_effect=confirmed_skip)) as transition:
            await music.manage_queue(context("jump", "2"))

        transition.assert_awaited_once()
        self.assertEqual(chat_queues[CHAT_ID], [selected, first])

    async def test_jump_restores_original_order_when_transition_is_unconfirmed(self):
        current, first, selected = ({"title": title} for title in ("current", "first", "selected"))
        original = [current, first, selected]
        chat_queues[CHAT_ID] = list(original)
        with patch("videl.core.transitions.transition", new=AsyncMock(return_value=Outcome("Unconfirmed", "Queue preserved.", False))):
            with self.assertRaisesRegex(music.CommandError, "Queue preserved"):
                await music.manage_queue(context("jump", "2"))
        self.assertEqual(chat_queues[CHAT_ID], original)
        self.assertIs(chat_queues[CHAT_ID][0], current)

    async def test_positions_cannot_target_the_current_track_or_exceed_queue(self):
        current, upcoming = {"title": "current"}, {"title": "upcoming"}
        chat_queues[CHAT_ID] = [current, upcoming]
        for name, arguments in (("remove", "0"), ("remove", "2"), ("move", "1 0"), ("jump", "2")):
            with self.subTest(name=name, arguments=arguments):
                with self.assertRaises(music.CommandError):
                    await music.manage_queue(context(name, arguments))
        self.assertEqual(chat_queues[CHAT_ID], [current, upcoming])

    async def test_all_queue_edits_are_registered_for_current_group_admins(self):
        from videl.app.routes import router

        for name in ("remove", "move", "jump", "clearqueue"):
            with self.subTest(command=name):
                self.assertIn(name, router.commands)
                self.assertEqual(router.commands[name].policy, "admin")
                self.assertEqual(router.commands[name].block_policy, "chat")
        self.assertIs(router.commands["clearqueue"].handler, music.control)


if __name__ == "__main__":
    unittest.main()
