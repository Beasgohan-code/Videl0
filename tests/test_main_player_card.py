"""The main player and seek card share Richgram's embedded-image path."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.core import player
from videl.utils.rich_ui import rich_img


CHAT_ID = -91034


class MainPlayerCardTests(unittest.IsolatedAsyncioTestCase):
    def test_player_embeds_only_allowlisted_thumbnail_urls(self):
        thumbnail = "https://i.ytimg.com/vi/example/hqdefault.jpg"
        self.assertEqual(player._player_image({"thumbnail": thumbnail}), rich_img(thumbnail))
        self.assertEqual(player._player_image({"thumbnail": "https://attacker.example/image.jpg"}), "")
        self.assertEqual(player._player_image({"thumbnail": "http://i.ytimg.com/image.jpg"}), "")

    async def test_progress_refresh_keeps_image_inside_the_rich_player_message(self):
        message = SimpleNamespace(photo=None)
        song = {"title": "Track", "thumbnail": "https://i.ytimg.com/vi/example/hqdefault.jpg"}
        with (
            patch.dict(player._np_msg, {CHAT_ID: message}),
            patch.dict(player._np_song, {CHAT_ID: song}),
            patch.dict(player._np_start, {CHAT_ID: 0}),
            patch.dict(player._np_total, {CHAT_ID: 180}),
            patch.object(player, "current_position", return_value=12),
            patch.object(player, "_now_playing_caption", return_value="<h2>Now playing</h2>"),
            patch.object(player, "_player_image", return_value='<img src="https://i.ytimg.com/vi/example/hqdefault.jpg" />'),
            patch.object(player, "rich_edit", new=AsyncMock()) as edit,
        ):
            await player.refresh_np_ui(CHAT_ID)
        self.assertIn("<img src=", edit.await_args.args[1])
        self.assertIn("Now playing", edit.await_args.args[1])


if __name__ == "__main__":
    unittest.main()
