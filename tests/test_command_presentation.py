"""Full command-facing presentation coverage, separate from user-payload delivery."""
import ast
import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from pathlib import Path
from pyrogram.enums import ButtonStyle,ChatType
from pyrogram.types import InlineKeyboardMarkup
from videl.utils import command_ui as ui
from videl.utils.bot_ui import button
from videl.utils.command_catalog import source_paths
from videl.utils.poll_options import build_poll
from vendor.richgram.richgram import rich_ui as transport
from videl import bot

with patch.object(bot,'add_handler'):
    tools=importlib.import_module('videl.modules.api_tools')

class PresentationTests(unittest.IsolatedAsyncioTestCase):
    def test_card_has_heading_and_real_navigation_without_body_rewriting(self):
        body='<aside>Saved &amp; ready</aside>'
        rendered=ui.present(body)
        self.assertIn(body,rendered)
        self.assertIn('<h3>',rendered)
        plain,keyboard=transport._native_buttons(rendered)
        self.assertNotIn('tg-button',plain)
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data,'help:home')
        self.assertEqual(keyboard.inline_keyboard[0][0].style,ButtonStyle.PRIMARY)
        self.assertEqual(keyboard.inline_keyboard[0][1].callback_data,'cmds:all:0')

    def test_existing_heading_and_authored_buttons_are_not_duplicated(self):
        body='<h2>Controls</h2>'+transport.rich_button('Pause',callback_data='pause',style='primary')
        self.assertEqual(ui.present(body),body)
        self.assertIsNone(ui.present(None))
        self.assertEqual(ui.present(''),'')
        self.assertNotIn('tg-button',ui.present('No navigation',navigation=False))
        full='a'*4096
        plain,_=transport._native_buttons(ui.present(full))
        self.assertEqual(plain,full)

    async def test_reply_standard_fallback_keeps_topic_quote_and_real_buttons(self):
        app=SimpleNamespace(send_message=AsyncMock())
        message=SimpleNamespace(_client=app,chat=SimpleNamespace(id=-1001,type=ChatType.SUPERGROUP),
                                id=7,message_thread_id=22,from_user=SimpleNamespace(id=42))
        with patch.object(transport,'RICH_AVAILABLE',False):
            await ui.rich_reply(message,'<aside>Ready</aside>')
        options=app.send_message.call_args.kwargs
        self.assertEqual(options['chat_id'],-1001)
        self.assertEqual(options['message_thread_id'],22)
        self.assertEqual(options['reply_parameters'].message_id,7)
        self.assertEqual(options['reply_markup'].inline_keyboard[0][0].callback_data,'help:home')
        self.assertIn('Ready',options['text'])

    async def test_explicit_keyboard_is_preserved_and_not_replaced_with_help(self):
        keyboard=InlineKeyboardMarkup([[button('Stop',callback_data='stop',style='danger')]])
        with patch.object(ui,'_send',AsyncMock()) as send:
            await ui.rich_send(object(),123,'<h2>Player</h2>',reply_markup=keyboard,protect_content=True)
        self.assertIs(send.call_args.kwargs['reply_markup'],keyboard)
        self.assertTrue(send.call_args.kwargs['protect_content'])
        self.assertNotIn('help:home',send.call_args.args[2])

    async def test_edit_explicit_none_clears_controls_and_unknown_send_not_retried(self):
        with patch.object(ui,'_edit',AsyncMock()) as edit:
            await ui.rich_edit(object(),'Closed',reply_markup=None)
        self.assertIsNone(edit.call_args.kwargs['reply_markup'])
        self.assertNotIn('tg-button',edit.call_args.args[1])
        with patch.object(ui,'_send',AsyncMock(return_value=None)) as send:
            self.assertIsNone(await ui.rich_send(object(),1,'Working'))
            send.assert_awaited_once()

    def test_active_modules_use_adapter_not_raw_rich_text_transport(self):
        for path in source_paths():
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node,ast.ImportFrom) and node.module=='videl.utils.rich_ui':
                    self.assertFalse({alias.name for alias in node.names}&{'rich_send','rich_reply','rich_edit'},str(path))
        afk=Path('videl/plugins/afk.py').read_text()
        self.assertIn('from videl.utils.command_ui import rich_reply',afk)

    def test_raw_text_delivery_is_reserved_for_user_payloads(self):
        allowed={('notes','filter_watcher'),('notes','send_note'),('welcome','welcome_handler'),
                 ('welcome','goodbye_handler'),('reminder','deliver'),('broadcast','_send')}
        for path in source_paths():
            for function in ast.parse(path.read_text()).body:
                if not isinstance(function,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
                for call in ast.walk(function):
                    if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr in {'send_message','reply_text','edit_text'}:
                        self.assertIn((path.stem,function.name),allowed,str(path))

class ModernFeatureTests(unittest.IsolatedAsyncioTestCase):
    def test_poll_timer_silent_and_content_protection_are_explicit(self):
        payload=build_poll('--seconds=60 --silent --protect Pick one | A | B')
        self.assertEqual(payload['open_period'],60)
        self.assertTrue(payload['disable_notification'])
        self.assertTrue(payload['protect_content'])
        default=build_poll('Choose | A | B')
        self.assertNotIn('open_period',default)
        self.assertNotIn('disable_notification',default)
        for prefix in ('--seconds=4','--seconds=601','--seconds=no','--seconds=60 --seconds=90'):
            with self.assertRaises(ValueError):build_poll(prefix+' Choose | A | B')

    async def test_topic_controls_recheck_permissions_and_group_context(self):
        query=SimpleNamespace(message=SimpleNamespace(chat=SimpleNamespace(id=-1001)),
                              from_user=SimpleNamespace(id=42),data='topicctl:close:-1001:22',answer=AsyncMock())
        with patch.object(tools,'is_user_authorized',AsyncMock(return_value=False)),patch.object(tools,'bot_api',AsyncMock()) as api:
            await tools.topic_control_callback(None,query)
            api.assert_not_awaited()
        query.data='topicctl:close:-1002:22'
        with patch.object(tools,'is_user_authorized',AsyncMock(return_value=True)),patch.object(tools,'bot_api',AsyncMock()) as api:
            await tools.topic_control_callback(None,query)
            api.assert_not_awaited()

    async def test_authorized_topic_button_calls_real_api_and_updates_controls(self):
        query=SimpleNamespace(message=SimpleNamespace(chat=SimpleNamespace(id=-1001)),
                              from_user=SimpleNamespace(id=42),data='topicctl:open:-1001:22',answer=AsyncMock())
        with patch.object(tools,'is_user_authorized',AsyncMock(return_value=True)),patch.object(tools,'bot_api',AsyncMock(return_value=(200,{'ok':True}))) as api,patch.object(tools,'rich_edit',AsyncMock()) as edit:
            await tools.topic_control_callback(None,query)
            api.assert_awaited_once_with('reopenForumTopic',{'chat_id':-1001,'message_thread_id':22})
            self.assertEqual(edit.call_args.kwargs['reply_markup'].inline_keyboard[0][0].style,ButtonStyle.DANGER)

class StartPrivacyTests(unittest.TestCase):
    def test_public_start_does_not_read_owner_totals_or_expose_owner_navigation(self):
        from videl.plugins.start import member_caption,private_keyboard
        with patch('videl.plugins.start.read_live_totals') as totals:
            public=member_caption('Visitor',True)
            totals.assert_not_called()
        self.assertNotIn('At a glance',public)
        self.assertNotIn('Streams',public)
        self.assertFalse(any(item.callback_data=='cmds:owner:0' for row in private_keyboard(False,'Videl0Bot').inline_keyboard for item in row))
