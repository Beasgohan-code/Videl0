"""Context-aware Premium Emoji rendering and rejection fallback contracts."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pyrogram.enums import ButtonStyle, MessageEntityType
from pyrogram.errors import BadRequest
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity

from videl.utils import premium_emojis
from videl.utils.bot_ui import (
    answer_callback,
    button,
    fallback_custom_emoji_entities,
    fallback_custom_emoji_keyboard,
    visual_call,
)


class PremiumEmojiRenderingTests(unittest.IsolatedAsyncioTestCase):
    def test_context_selects_html_or_unicode_without_changing_catalog_ids(self):
        emoji_id = premium_emojis.PREMIUM_IDS["music"]
        with patch.object(premium_emojis, "USE_PREMIUM", True):
            self.assertEqual(
                premium_emojis.render_emoji("music", "message_html"),
                f'<tg-emoji emoji-id="{emoji_id}">🎵</tg-emoji>',
            )
            self.assertEqual(
                premium_emojis.render_emoji("music", "caption_html"),
                f'<tg-emoji emoji-id="{emoji_id}">🎵</tg-emoji>',
            )
            for context in ("plain_text", "button_text", "callback"):
                self.assertEqual(premium_emojis.render_emoji("music", context), "🎵")
        with patch.object(premium_emojis, "USE_PREMIUM", False):
            self.assertEqual(premium_emojis.render_emoji("music", "message_html"), "🎵")
        self.assertEqual(premium_emojis.PREMIUM_IDS["music"], emoji_id)

    def test_rejected_html_uses_catalogued_glyph_and_unknown_id_keeps_entity_text(self):
        emoji_id = premium_emojis.PREMIUM_IDS["music"]
        rendered = premium_emojis.fallback_custom_emoji_html(
            f'<b>Track</b> <tg-emoji emoji-id="{emoji_id}">🎵</tg-emoji>'
        )
        self.assertEqual(rendered, "<b>Track</b> 🎵")
        self.assertNotIn("<tg-emoji", rendered)
        self.assertEqual(
            premium_emojis.fallback_custom_emoji_html(
                '<tg-emoji emoji-id="987654321">🚀</tg-emoji>'
            ),
            "🚀",
        )

    async def test_callback_text_is_plain_and_preserves_the_catalogued_fallback(self):
        emoji_id = premium_emojis.PREMIUM_IDS["music"]
        self.assertEqual(
            premium_emojis.callback_text(
                f'<b>Playing</b> <tg-emoji emoji-id="{emoji_id}">🎵</tg-emoji>'
            ),
            "Playing 🎵",
        )
        query = SimpleNamespace(answer=AsyncMock(return_value="answered"))
        result = await answer_callback(
            query,
            f'<tg-emoji emoji-id="{emoji_id}">🎵</tg-emoji> Added',
            show_alert=True,
        )
        self.assertEqual(result, "answered")
        query.answer.assert_awaited_once_with("🎵 Added", show_alert=True)

    def test_caption_entity_fallback_drops_only_custom_entity(self):
        custom = MessageEntity(
            type=MessageEntityType.CUSTOM_EMOJI,
            offset=1,
            length=2,
            custom_emoji_id=premium_emojis.PREMIUM_IDS["music"],
        )
        bold = MessageEntity(type=MessageEntityType.BOLD, offset=0, length=3)
        self.assertEqual(fallback_custom_emoji_entities([bold, custom]), [bold])

    def test_keyboard_fallback_keeps_action_style_and_uses_catalogued_glyph(self):
        with patch("videl.utils.bot_ui.ICONS_ENABLED", True):
            original = InlineKeyboardMarkup(
                [[button("🎵 Play", callback_data="play:1", style="primary")]]
            )
        original_button = original.inline_keyboard[0][0]
        fallback = fallback_custom_emoji_keyboard(original).inline_keyboard[0][0]
        self.assertEqual(original_button.text, "Play")
        self.assertEqual(original_button.callback_data, "play:1")
        self.assertEqual(original_button.style, ButtonStyle.PRIMARY)
        self.assertEqual(fallback.text, "🎵 Play")
        self.assertEqual(fallback.callback_data, "play:1")
        self.assertEqual(fallback.style, ButtonStyle.PRIMARY)
        self.assertIsNone(fallback.icon_custom_emoji_id)

    async def test_definite_rejection_retries_once_without_rejected_ids(self):
        emoji_id = premium_emojis.PREMIUM_IDS["music"]
        with patch("videl.utils.bot_ui.ICONS_ENABLED", True):
            markup = InlineKeyboardMarkup(
                [[button("🎵 Play", callback_data="play:1", style="primary")]]
            )
        send = AsyncMock(side_effect=[BadRequest("CUSTOM_EMOJI_INVALID"), "sent"])
        result = await visual_call(
            send,
            text=f'<b>Track</b> <tg-emoji emoji-id="{emoji_id}">🎵</tg-emoji>',
            parse_mode="html",
            reply_markup=markup,
        )
        self.assertEqual(result, "sent")
        self.assertEqual(send.await_count, 2)
        retry = send.await_args_list[1].kwargs
        self.assertEqual(retry["text"], "<b>Track</b> 🎵")
        fallback_button = retry["reply_markup"].inline_keyboard[0][0]
        self.assertEqual(fallback_button.text, "🎵 Play")
        self.assertEqual(fallback_button.callback_data, "play:1")
        self.assertEqual(fallback_button.style, ButtonStyle.PRIMARY)
        self.assertIsNone(fallback_button.icon_custom_emoji_id)
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "play:1")
        self.assertEqual(markup.inline_keyboard[0][0].icon_custom_emoji_id, emoji_id)

    async def test_caption_entity_rejection_retries_with_unicode_caption_and_same_action(self):
        custom = MessageEntity(
            type=MessageEntityType.CUSTOM_EMOJI,
            offset=0,
            length=2,
            custom_emoji_id=premium_emojis.PREMIUM_IDS["music"],
        )
        bold = MessageEntity(type=MessageEntityType.BOLD, offset=3, length=5)
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Open", callback_data="open:file")]]
        )
        send = AsyncMock(side_effect=[BadRequest("CUSTOM_EMOJI_INVALID"), "sent"])
        result = await visual_call(
            send,
            caption="🎵 Track",
            caption_entities=[custom, bold],
            reply_markup=markup,
        )
        self.assertEqual(result, "sent")
        self.assertEqual(send.await_count, 2)
        retry = send.await_args_list[1].kwargs
        self.assertEqual(retry["caption"], "🎵 Track")
        self.assertEqual(retry["caption_entities"], [bold])
        self.assertEqual(
            retry["reply_markup"].inline_keyboard[0][0].callback_data,
            "open:file",
        )

    async def test_positional_text_and_keyboard_adapters_use_the_same_fallback(self):
        emoji_id = premium_emojis.PREMIUM_IDS["music"]
        with patch("videl.utils.bot_ui.ICONS_ENABLED", True):
            markup = InlineKeyboardMarkup(
                [[button("🎵 Play", callback_data="play:2")]]
            )
        send = AsyncMock(side_effect=[BadRequest("CUSTOM_EMOJI_INVALID"), "sent"])
        result = await visual_call(
            send,
            f'<tg-emoji emoji-id="{emoji_id}">🎵</tg-emoji> Track',
            "html",
            markup,
        )
        self.assertEqual(result, "sent")
        self.assertEqual(send.await_count, 2)
        text, parse_mode, fallback_markup = send.await_args_list[1].args
        self.assertEqual(text, "🎵 Track")
        self.assertEqual(parse_mode, "html")
        item = fallback_markup.inline_keyboard[0][0]
        self.assertEqual(item.callback_data, "play:2")
        self.assertEqual(item.text, "🎵 Play")
        self.assertIsNone(item.icon_custom_emoji_id)

    async def test_network_and_unrelated_bad_request_are_never_emoji_downgrades(self):
        for failure in (TimeoutError("delivery unknown"), BadRequest("CHAT_WRITE_FORBIDDEN")):
            send = AsyncMock(side_effect=failure)
            with self.subTest(error=type(failure).__name__):
                with self.assertRaises(type(failure)):
                    await visual_call(
                        send,
                        text='<tg-emoji emoji-id="123">🎵</tg-emoji>',
                    )
                send.assert_awaited_once()

    async def test_unknown_button_icon_is_removed_without_changing_its_action(self):
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Open", callback_data="open", icon_custom_emoji_id="987654321")]]
        )
        send = AsyncMock(side_effect=[BadRequest("CUSTOM_EMOJI_INVALID"), "sent"])
        self.assertEqual(await visual_call(send, reply_markup=markup), "sent")
        fallback = send.await_args_list[1].kwargs["reply_markup"].inline_keyboard[0][0]
        self.assertEqual(fallback.text, "Open")
        self.assertEqual(fallback.callback_data, "open")
        self.assertIsNone(fallback.icon_custom_emoji_id)


if __name__ == "__main__":
    unittest.main()
