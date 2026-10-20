"""Badmunda05 Richgram native-keyboard bridge; no Telegram calls."""
import unittest
from unittest.mock import AsyncMock, patch
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from vendor.richgram.richgram import rich_ui as ui

class RichButtonTests(unittest.IsolatedAsyncioTestCase):
    def test_styles_actions_and_rows(self):
        source = '<h2>Manage</h2>' + ui.rich_button_row(
            ui.rich_button('Save &amp; continue',callback_data='save:42',style='success',icon_custom_emoji_id='5368324170671202286'),
            ui.rich_button('Guide',url='https://example.com?a=1&b=2',style='primary'))
        body, keyboard = ui._native_buttons(source)
        self.assertNotIn('tg-button',body)
        self.assertIn('Manage',body)
        first, second = keyboard.inline_keyboard[0]
        self.assertEqual(first.text,'Save & continue')
        self.assertEqual(first.callback_data,'save:42')
        self.assertEqual(first.style,ButtonStyle.SUCCESS)
        self.assertEqual(first.icon_custom_emoji_id,'5368324170671202286')
        self.assertEqual(second.url,'https://example.com?a=1&b=2')

    def test_explicit_markup_wins_and_invalid_actions_are_not_created(self):
        markup=InlineKeyboardMarkup([[InlineKeyboardButton('Existing',callback_data='existing')]])
        _, result=ui._native_buttons(ui.rich_button('Other',callback_data='other'),markup)
        self.assertIs(result,markup)
        for source in [ui.rich_button('Too long',callback_data='😀'*17),ui.rich_button('Unsafe',url='javascript:alert(1)')]:
            _, result=ui._native_buttons(source)
            self.assertIsNone(result)

    async def test_standard_send_has_actionable_keyboard_not_inert_bold(self):
        app=AsyncMock()
        with patch.object(ui,'RICH_AVAILABLE',False):
            await ui.rich_send(app,123,'<b>Controls</b>'+ui.rich_button_row(ui.rich_button('Resume',callback_data='resume',style='success')))
        options=app.send_message.call_args.kwargs
        self.assertEqual(options['reply_markup'].inline_keyboard[0][0].callback_data,'resume')
        self.assertNotIn('tg-button',str(options))

    def test_native_labels_strip_html_and_small_caps(self):
        from videl.utils.bot_ui import button
        result=button('<b>ʀᴇsᴜᴍᴇ</b>',callback_data='resume')
        self.assertEqual(result.text,'resume')
        self.assertEqual(result.style,ButtonStyle.SUCCESS)
