"""RichMessage photo blocks keep the existing one-message Premium Emoji card."""
import io
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.core import player


CHAT_ID = -91034
PREMIUM_ID = "6037364759811068375"
PREMIUM = f'<tg-emoji emoji-id="{PREMIUM_ID}">🎶</tg-emoji>'


class MainPlayerCardTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_card_uses_one_rich_photo_block_with_caption_and_controls(self):
        from pyrogram.types import InputRichBlockPhoto, RichTextCustomEmoji

        poster = io.BytesIO(b"generated-poster")
        message = SimpleNamespace(rich_message=SimpleNamespace(blocks=[
            SimpleNamespace(photo=SimpleNamespace(file_id="poster-file-id"))
        ]))
        bot = SimpleNamespace(send_rich_message=AsyncMock(return_value=message))
        media_ids = {}
        rich_chats = set()
        caption = f"<h2>{PREMIUM} Now playing</h2>\n\n<b>Track</b>"
        with (
            patch.object(player, "bot", bot),
            patch.object(player, "RICH_AVAILABLE", True),
            patch.object(player, "_player_media_file_ids", media_ids),
            patch.object(player, "_rich_player_chats", rich_chats),
        ):
            result = await player._send_player_card(
                CHAT_ID, None, caption, "keyboard", poster=poster,
                thumbnail="https://i.ytimg.com/vi/example/hqdefault.jpg",
            )

        self.assertIs(result, message)
        bot.send_rich_message.assert_awaited_once()
        self.assertEqual(bot.send_rich_message.await_args.kwargs["reply_markup"], "keyboard")
        rich = bot.send_rich_message.await_args.kwargs["rich_message"]
        self.assertEqual(len(rich.blocks), 1)
        self.assertIsInstance(rich.blocks[0], InputRichBlockPhoto)
        self.assertEqual(rich.blocks[0].photo.media.getvalue(), poster.getvalue())
        caption_text = rich.blocks[0].caption.text
        custom = next(item for item in caption_text if isinstance(item, RichTextCustomEmoji))
        self.assertEqual(custom.custom_emoji_id, PREMIUM_ID)
        self.assertTrue(any(getattr(item, "text", None) in ("Track", ["Track"]) for item in caption_text))
        raw_caption = await rich.blocks[0].caption.write(client=None)
        self.assertEqual(raw_caption.text.texts[0].document_id, int(PREMIUM_ID))
        self.assertEqual(media_ids[CHAT_ID], "poster-file-id")
        self.assertIn(CHAT_ID, rich_chats)

    async def test_progress_edit_reuses_rich_photo_and_caption_emoji_entities(self):
        from pyrogram.types import InputRichBlockPhoto, RichTextCustomEmoji

        message = SimpleNamespace(id=44, photo=None)
        bot = SimpleNamespace(edit_message_text=AsyncMock())
        with (
            patch.object(player, "bot", bot),
            patch.dict(player._np_msg, {CHAT_ID: message}),
            patch.dict(player._np_song, {CHAT_ID: {"title": "Track", "duration": "2:58"}}),
            patch.dict(player._np_start, {CHAT_ID: 0}),
            patch.dict(player._np_total, {CHAT_ID: 178}),
            patch.dict(player._player_media_file_ids, {CHAT_ID: "poster-file-id"}),
            patch.object(player, "_rich_player_chats", {CHAT_ID}),
            patch.object(player, "current_position", return_value=12),
            patch.object(player, "visual_call", new=AsyncMock()) as edit,
        ):
            await player.refresh_np_ui(CHAT_ID)

        self.assertEqual(edit.await_args.args[0], bot.edit_message_text)
        rich = edit.await_args.kwargs["rich_message"]
        block = rich.blocks[0]
        self.assertIsInstance(block, InputRichBlockPhoto)
        self.assertEqual(block.photo.media, "poster-file-id")
        custom_ids = [
            item.custom_emoji_id for item in block.caption.text
            if isinstance(item, RichTextCustomEmoji)
        ]
        self.assertIn("5463107823946717464", custom_ids)

    async def test_legacy_transport_remains_only_a_richmessage_unavailable_fallback(self):
        photo = io.BytesIO(b"generated-poster")
        caption = f"<b>{PREMIUM} Now playing</b>\nTrack"
        message = SimpleNamespace(photo=[object()])
        bot = SimpleNamespace(send_photo=AsyncMock(return_value=message))
        with (
            patch.object(player, "bot", bot),
            patch.object(player, "RICH_AVAILABLE", False),
            patch.object(player, "visual_call", new=AsyncMock(return_value=message)) as send,
        ):
            result = await player._send_player_card(
                CHAT_ID, None, caption, None, poster=photo,
                thumbnail="https://i.ytimg.com/vi/example/hqdefault.jpg",
            )
        self.assertIs(result, message)
        self.assertEqual(send.await_args.args[0], bot.send_photo)
        self.assertIn(PREMIUM, send.await_args.kwargs["caption"])


if __name__ == "__main__":
    unittest.main()
