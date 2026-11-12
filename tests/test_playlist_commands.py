import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from videl.modules import playlist
from videl.utils.db import PlaylistStorageError


class PlaylistCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_corrupt_rows_are_skipped_and_reported_without_aborting_load(self):
        message = NS(
            chat=NS(id=-100101, type=NS(name="SUPERGROUP")),
            from_user=NS(id=90001, first_name="Listener"),
            command=["playlist", "favorites"],
        )
        stored = {
            "display_name": "Favorites",
            "songs": [None, "bad row", {}, {"title": "Track", "video_id": "dQw4w9WgXcQ"}],
        }
        queue = []

        def queue_size(_chat_id):
            return len(queue)

        def add_to_queue(_chat_id, song):
            queue.append(song)
            return len(queue)

        with patch.object(playlist, "get_playlist", return_value=stored), \
             patch.object(playlist, "queue_size", side_effect=queue_size), \
             patch.object(playlist, "add_to_queue", side_effect=add_to_queue), \
             patch("config.QUEUE_LIMIT", 10), \
             patch("videl.core.queue.peek_current", return_value=None), \
             patch.object(playlist, "rich_send", new=AsyncMock()) as send:
            await playlist.load_playlist_cmd(playlist.bot, message)

        self.assertEqual(len(queue), 1)
        self.assertIn("3 invalid", send.await_args.args[2].lower())

    async def test_saved_playlist_does_not_restore_tracks_over_duration_limit(self):
        message = NS(
            chat=NS(id=-100101, type=NS(name="SUPERGROUP")),
            from_user=NS(id=90001, first_name="Listener"),
            command=["playlist", "favorites"],
        )
        stored = {
            "display_name": "Favorites",
            "songs": [
                {"title": "Too long", "url": "https://example.test/long", "duration": "60:01"},
                {"title": "Valid", "url": "https://example.test/valid", "duration": "1:00"},
            ],
        }
        added = []
        def add_to_queue(_chat_id, song):
            added.append(song)
            return len(added)

        with (
            patch.object(playlist, "get_playlist", return_value=stored),
            patch.object(playlist, "queue_size", return_value=0),
            patch.object(playlist, "add_to_queue", side_effect=add_to_queue),
            patch("config.QUEUE_LIMIT", 10),
            patch("videl.core.queue.peek_current", return_value=None),
            patch("videl.core.player.play_song", new=AsyncMock()),
            patch.object(playlist, "rich_send", new=AsyncMock()) as send,
        ):
            await playlist.load_playlist_cmd(playlist.bot, message)

        self.assertEqual([song["title"] for song in added], ["Valid"])
        self.assertIn("skipped 1 track over", send.await_args.args[2].lower())

    async def test_all_corrupt_rows_do_not_claim_playlist_loaded(self):
        message = NS(
            chat=NS(id=-100101, type=NS(name="SUPERGROUP")),
            from_user=NS(id=90001, first_name="Listener"),
            command=["playlist", "favorites"],
        )
        stored = {"display_name": "Favorites", "songs": [None, {"title": "No URL"}]}

        with patch.object(playlist, "get_playlist", return_value=stored), \
             patch.object(playlist, "queue_size", return_value=0), \
             patch.object(playlist, "add_to_queue") as add, \
             patch.object(playlist, "rich_send", new=AsyncMock()) as send:
            await playlist.load_playlist_cmd(playlist.bot, message)

        add.assert_not_called()
        self.assertIn("no valid tracks", send.await_args.args[2].lower())

    async def test_explicit_group_scope_does_not_fall_back_to_personal_playlist(self):
        message = NS(
            chat=NS(id=-100101, type=NS(name="SUPERGROUP")),
            from_user=NS(id=90001, first_name="Listener"),
            command=["playlist", "g:favorites"],
        )
        personal_playlist = {"display_name": "Favorites", "songs": [{"title": "Private", "url": "https://example.test/private"}]}

        with patch.object(playlist, "get_playlist", side_effect=[None, personal_playlist]) as get_playlist, \
             patch.object(playlist, "queue_size", return_value=0), \
             patch.object(playlist, "add_to_queue") as add, \
             patch.object(playlist, "rich_send", new=AsyncMock()) as send:
            await playlist.load_playlist_cmd(playlist.bot, message)

        get_playlist.assert_called_once_with(message.chat.id, "favorites")
        add.assert_not_called()
        self.assertIn("not found", send.await_args.args[2].lower())

    async def test_load_reports_storage_failure_instead_of_not_found(self):
        message = NS(chat=NS(id=-100101), from_user=NS(id=90001), command=["playlist", "favorites"])
        with patch.object(playlist, "get_playlist", side_effect=PlaylistStorageError), \
             patch.object(playlist, "rich_send", new=AsyncMock()) as send:
            await playlist.load_playlist_cmd(playlist.bot, message)
        self.assertIn("storage", send.await_args.args[2].lower())
        self.assertNotIn("not found", send.await_args.args[2].lower())

    async def test_list_reports_storage_failure_instead_of_empty(self):
        message = NS(chat=NS(id=-100101, type=NS(name="SUPERGROUP")), from_user=NS(id=90001))
        with patch.object(playlist, "list_playlists", side_effect=PlaylistStorageError), \
             patch.object(playlist, "rich_send", new=AsyncMock()) as send:
            await playlist.list_playlists_cmd(playlist.bot, message)
        self.assertIn("storage", send.await_args.args[2].lower())
        self.assertNotIn("no playlists", send.await_args.args[2].lower())

    async def test_delete_reports_storage_failure_instead_of_not_found(self):
        message = NS(chat=NS(id=-100101), from_user=NS(id=90001), command=["deleteplaylist", "favorites"])
        with patch.object(playlist, "delete_playlist", side_effect=PlaylistStorageError), \
             patch.object(playlist, "rich_send", new=AsyncMock()) as send:
            await playlist.delete_playlist_cmd(playlist.bot, message)
        self.assertIn("storage", send.await_args.args[2].lower())
        self.assertNotIn("not found", send.await_args.args[2].lower())

    async def test_oversized_stored_playlist_is_capped_at_storage_limit(self):
        message = NS(
            chat=NS(id=-100101, type=NS(name="SUPERGROUP")),
            from_user=NS(id=90001, first_name="Listener"),
            command=["playlist", "favorites"],
        )
        stored = {
            "display_name": "Favorites",
            "songs": [{"title": f"Track {i}", "url": f"https://example.test/{i}"} for i in range(55)],
        }
        size = 0

        def queue_size(_chat_id):
            return size

        def add_to_queue(_chat_id, _song):
            nonlocal size
            size += 1
            return size

        with patch.object(playlist, "get_playlist", return_value=stored), \
             patch.object(playlist, "queue_size", side_effect=queue_size), \
             patch.object(playlist, "add_to_queue", side_effect=add_to_queue), \
             patch("config.QUEUE_LIMIT", 100), \
             patch("videl.core.queue.peek_current", return_value=None), \
             patch.object(playlist, "rich_send", new=AsyncMock()) as send:
            await playlist.load_playlist_cmd(playlist.bot, message)

        self.assertEqual(size, 50)
        self.assertIn("50-track limit", send.await_args.args[2].lower())

    async def test_partial_load_reports_requested_and_added_tracks_at_queue_limit(self):
        message = NS(
            chat=NS(id=-100101, type=NS(name="SUPERGROUP")),
            from_user=NS(id=90001, first_name="Listener"),
            command=["playlist", "favorites"],
        )
        stored = {
            "display_name": "Favorites",
            "songs": [{"title": f"Track {i}", "url": f"https://example.test/{i}"} for i in range(4)],
        }
        size = 1

        def queue_size(_chat_id):
            return size

        def add_to_queue(_chat_id, _song):
            nonlocal size
            size += 1
            return size

        with patch.object(playlist, "get_playlist", return_value=stored), \
             patch.object(playlist, "queue_size", side_effect=queue_size), \
             patch.object(playlist, "add_to_queue", side_effect=add_to_queue), \
             patch("config.QUEUE_LIMIT", 3), \
             patch("videl.core.queue.peek_current", return_value=None), \
             patch.object(playlist, "rich_send", new=AsyncMock()) as send:
            await playlist.load_playlist_cmd(playlist.bot, message)

        text = send.await_args.args[2].lower()
        self.assertIn("2 of 4", text)
        self.assertIn("queue capacity", text)


if __name__ == "__main__":
    unittest.main()
