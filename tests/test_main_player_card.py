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
    async def test_initial_card_uses_rich_photo_and_sends_premium_caption_as_native_html(self):
        from pyrogram.types import InputRichBlockPhoto

        poster = io.BytesIO(b"generated-poster")
        media_message = SimpleNamespace(rich_message=SimpleNamespace(blocks=[
            SimpleNamespace(photo=SimpleNamespace(file_id="poster-file-id"))
        ]))
        text_message = SimpleNamespace(id=46, photo=None)
        bot = SimpleNamespace(
            send_rich_message=AsyncMock(return_value=media_message),
            send_message=AsyncMock(return_value=text_message),
        )
        media_ids = {}
        media_messages = {}
        rich_chats = set()
        with (
            patch.object(player, "bot", bot),
            patch.object(player, "RICH_AVAILABLE", True),
            patch.object(player, "_player_media_file_ids", media_ids),
            patch.object(player, "_player_media_messages", media_messages),
            patch.object(player, "_rich_player_chats", rich_chats),
        ):
            result = await player._send_player_card(
                CHAT_ID, None, "<tg-emoji emoji-id=\"5463107823946717464\">🎵</tg-emoji> Now playing", None,
                song=SONG, total=178, poster=poster,
                thumbnail="https://i.ytimg.com/vi/example/hqdefault.jpg",
            )

        self.assertIs(result, text_message)
        rich = bot.send_rich_message.await_args.kwargs["rich_message"]
        self.assertEqual(len(rich.blocks), 1)
        self.assertIsInstance(rich.blocks[0], InputRichBlockPhoto)
        self.assertEqual(rich.blocks[0].photo.media.getvalue(), poster.getvalue())
        bot.send_message.assert_awaited_once()
        self.assertEqual(bot.send_message.await_args.kwargs["parse_mode"], player.ParseMode.HTML)
        self.assertIn('emoji-id="5463107823946717464"', bot.send_message.await_args.kwargs["text"])
        self.assertEqual(media_ids[CHAT_ID], "poster-file-id")
        self.assertIs(media_messages[CHAT_ID], media_message)
        self.assertIn(CHAT_ID, rich_chats)

    async def test_rich_image_progress_edits_premium_caption_via_html_entities(self):
        message = SimpleNamespace(id=44, photo=None)
        song = dict(SONG)
        bot = SimpleNamespace(edit_message_text=AsyncMock())
        with (
            patch.object(player, "bot", bot),
            patch.dict(player._np_msg, {CHAT_ID: message}),
            patch.dict(player._np_song, {CHAT_ID: song}),
            patch.dict(player._np_start, {CHAT_ID: 0}),
            patch.dict(player._np_total, {CHAT_ID: 180}),
            patch.object(player, "_rich_player_chats", {CHAT_ID}),
            patch.object(player, "current_position", return_value=12),
            patch.object(player, "visual_call", new=AsyncMock()) as edit,
        ):
            await player.refresh_np_ui(CHAT_ID)

        self.assertEqual(edit.await_args.args[0], bot.edit_message_text)
        kwargs = edit.await_args.kwargs
        self.assertIn('emoji-id="5463107823946717464"', kwargs["text"])
        self.assertEqual(kwargs["parse_mode"], player.ParseMode.HTML)

    async def test_rich_image_caption_edits_do_not_depend_on_photo_file_id(self):
        message = SimpleNamespace(id=45, photo=None)
        bot = SimpleNamespace(edit_message_text=AsyncMock())
        with (
            patch.object(player, "bot", bot),
            patch.dict(player._np_msg, {CHAT_ID: message}),
            patch.dict(player._np_song, {CHAT_ID: dict(SONG)}),
            patch.dict(player._np_start, {CHAT_ID: 0}),
            patch.dict(player._np_total, {CHAT_ID: 180}),
            patch.object(player, "_player_media_file_ids", {}),
            patch.object(player, "_rich_player_chats", {CHAT_ID}),
            patch.object(player, "current_position", return_value=12),
            patch.object(player, "visual_call", new=AsyncMock()) as edit,
        ):
            await player.refresh_np_ui(CHAT_ID)
        self.assertEqual(edit.await_args.args[0], bot.edit_message_text)
        self.assertIn('emoji-id="5463107823946717464"', edit.await_args.kwargs["text"])

    def test_player_caption_always_uses_premium_ids_even_when_global_fallback_is_enabled(self):
        from videl.utils import premium_emojis

        with patch.object(premium_emojis, "USE_PREMIUM", False):
            caption = player._now_playing_caption(SONG, total=178)
        self.assertIn('emoji-id="5463107823946717464"', caption)
        self.assertIn('emoji-id="6035162669948867129"', caption)

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
