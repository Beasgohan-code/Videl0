"""Player poster delivery keeps Premium Emoji HTML in Telegram caption edits."""
import io
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.core import player


CHAT_ID = -91034
PREMIUM = '<tg-emoji emoji-id="6037364759811068375">🎶</tg-emoji>'


class MainPlayerCardTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_player_card_uses_legacy_photo_caption_with_premium_entities(self):
        photo = io.BytesIO(b"generated-poster")
        caption = f"<b>{PREMIUM} Now playing</b>\nTrack"
        message = SimpleNamespace(photo=[object()])
        bot = SimpleNamespace(send_photo=AsyncMock(return_value=message))
        with patch.object(player, "bot", bot), patch.object(
            player, "visual_call", new=AsyncMock(return_value=message)
        ) as send:
            result = await player._send_player_card(
                CHAT_ID, None, caption, None, poster=photo,
                thumbnail="https://i.ytimg.com/vi/example/hqdefault.jpg",
            )

        self.assertIs(result, message)
        self.assertEqual(send.await_args.args[0], bot.send_photo)
        self.assertEqual(send.await_args.args[1], CHAT_ID)
        self.assertIs(send.await_args.kwargs["photo"], photo)
        self.assertEqual(send.await_args.kwargs["caption"], caption)
        self.assertIn(PREMIUM, send.await_args.kwargs["caption"])

    async def test_photo_caption_progress_edits_keep_premium_entities(self):
        message = SimpleNamespace(id=44, photo=[object()])
        song = {"title": "Track", "thumbnail": "https://i.ytimg.com/vi/example/hqdefault.jpg"}
        cap = f"<h2>{PREMIUM} Now playing</h2>"
        bot = SimpleNamespace(edit_message_caption=AsyncMock())
        with (
            patch.object(player, "bot", bot),
            patch.dict(player._np_msg, {CHAT_ID: message}),
            patch.dict(player._np_song, {CHAT_ID: song}),
            patch.dict(player._np_start, {CHAT_ID: 0}),
            patch.dict(player._np_total, {CHAT_ID: 180}),
            patch.object(player, "current_position", return_value=12),
            patch.object(player, "_now_playing_caption", return_value=cap),
            patch.object(player, "visual_call", new=AsyncMock()) as edit,
        ):
            await player.refresh_np_ui(CHAT_ID)
        self.assertEqual(edit.await_args.args[0], bot.edit_message_caption)
        self.assertEqual(edit.await_args.kwargs["caption"], cap)
        self.assertIn(PREMIUM, edit.await_args.kwargs["caption"])

    async def test_poster_rejection_uses_thumbnail_without_rewriting_caption(self):
        photo = io.BytesIO(b"generated-poster")
        thumbnail = "https://i.ytimg.com/vi/example/hqdefault.jpg"
        caption = f"{PREMIUM} Track"
        accepted = SimpleNamespace(photo=[object()])
        bot = SimpleNamespace(send_photo=AsyncMock())
        send = AsyncMock(side_effect=[player.BadRequest("PHOTO_EXT_INVALID"), accepted])
        with patch.object(player, "bot", bot), patch.object(player, "visual_call", send):
            result = await player._send_player_card(
                CHAT_ID, None, caption, None, poster=photo, thumbnail=thumbnail
            )
        self.assertIs(result, accepted)
        self.assertEqual(send.await_count, 2)
        self.assertIs(send.call_args_list[0].kwargs["photo"], photo)
        self.assertEqual(send.call_args_list[1].kwargs["photo"], thumbnail)
        self.assertTrue(all(call.kwargs["caption"] == caption for call in send.call_args_list))


if __name__ == "__main__":
    unittest.main()
