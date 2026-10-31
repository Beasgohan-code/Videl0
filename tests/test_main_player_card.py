"""Player RichMessage cards preserve Premium Emoji IDs through sends and edits."""
import io
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.core import player


CHAT_ID = -91034
PREMIUM_ID = "5463107823946717464"
PREMIUM = '<tg-emoji emoji-id="6037364759811068375">🎶</tg-emoji>'
SONG = {"title": "Track", "duration": "2:58", "requester": "Member"}


class MainPlayerCardTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_card_uses_rich_photo_block_and_native_premium_emoji_ids(self):
        from pyrogram.types import InputRichBlockPhoto, RichTextCustomEmoji

        poster = io.BytesIO(b"generated-poster")
        message = SimpleNamespace(rich_message=SimpleNamespace(blocks=[
            SimpleNamespace(photo=SimpleNamespace(file_id="poster-file-id"))
        ]))
        bot = SimpleNamespace(send_rich_message=AsyncMock(return_value=message))
        with patch.object(player, "bot", bot), patch.object(player, "RICH_AVAILABLE", True):
            result = await player._send_player_card(
                CHAT_ID, None, "ignored html fallback", None,
                song=SONG, total=178, poster=poster,
                thumbnail="https://i.ytimg.com/vi/example/hqdefault.jpg",
            )

        self.assertIs(result, message)
        rich = bot.send_rich_message.await_args.kwargs["rich_message"]
        self.assertIsInstance(rich.blocks[0], InputRichBlockPhoto)
        self.assertEqual(rich.blocks[0].photo.media.getvalue(), poster.getvalue())
        self.assertIsInstance(rich.blocks[1].text[0], RichTextCustomEmoji)
        self.assertEqual(rich.blocks[1].text[0].custom_emoji_id, PREMIUM_ID)
        self.assertEqual(player._player_media_file_ids[CHAT_ID], "poster-file-id")
        self.assertIn(CHAT_ID, player._rich_player_chats)

    async def test_rich_progress_edit_reuses_photo_and_custom_emoji_entities(self):
        from pyrogram.types import RichTextCustomEmoji

        message = SimpleNamespace(id=44, photo=None)
        song = dict(SONG)
        bot = SimpleNamespace(edit_message_text=AsyncMock())
        with (
            patch.object(player, "bot", bot),
            patch.dict(player._np_msg, {CHAT_ID: message}),
            patch.dict(player._np_song, {CHAT_ID: song}),
            patch.dict(player._np_start, {CHAT_ID: 0}),
            patch.dict(player._np_total, {CHAT_ID: 180}),
            patch.dict(player._player_media_file_ids, {CHAT_ID: "poster-file-id"}),
            patch.object(player, "_rich_player_chats", {CHAT_ID}),
            patch.object(player, "current_position", return_value=12),
            patch.object(player, "visual_call", new=AsyncMock()) as edit,
        ):
            await player.refresh_np_ui(CHAT_ID)

        self.assertEqual(edit.await_args.args[0], bot.edit_message_text)
        rich = edit.await_args.kwargs["rich_message"]
        self.assertEqual(rich.blocks[0].photo.media, "poster-file-id")
        self.assertIsInstance(rich.blocks[1].text[0], RichTextCustomEmoji)
        self.assertEqual(rich.blocks[1].text[0].custom_emoji_id, PREMIUM_ID)

    async def test_legacy_photo_fallback_keeps_premium_caption_entities(self):
        photo = io.BytesIO(b"generated-poster")
        caption = f"<b>{PREMIUM} Now playing</b>\nTrack"
        message = SimpleNamespace(photo=[object()])
        bot = SimpleNamespace(send_photo=AsyncMock(return_value=message))
        with patch.object(player, "bot", bot), patch.object(
            player, "RICH_AVAILABLE", False
        ), patch.object(player, "visual_call", new=AsyncMock(return_value=message)) as send:
            result = await player._send_player_card(
                CHAT_ID, None, caption, None, song=SONG, total=178,
                poster=photo, thumbnail="https://i.ytimg.com/vi/example/hqdefault.jpg",
            )
        self.assertIs(result, message)
        self.assertEqual(send.await_args.args[0], bot.send_photo)
        self.assertEqual(send.await_args.kwargs["photo"].getvalue(), photo.getvalue())
        self.assertIn(PREMIUM, send.await_args.kwargs["caption"])


if __name__ == "__main__":
    unittest.main()
