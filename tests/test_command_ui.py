"""Offline command UI/coverage checks; no Telegram requests."""
import ast
import importlib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from pyrogram.enums import ChatType
from videl import bot
from videl.utils.command_catalog import commands,directory,visible_commands,source_paths
from videl.utils.command_ui import notice,usage,result
from videl.utils.bot_commands import command_menu
from vendor.richgram.richgram.rich_ui import rich_to_plain

with patch.object(bot,'add_handler'):
    api=importlib.import_module('videl.modules.api_tools')
    professional=importlib.import_module('videl.app.navigation')
    ping=importlib.import_module('videl.plugins.tools')


def message(command,*,forum=False):
    return SimpleNamespace(command=command,reply_to_message=None,from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(id=-1001,type=ChatType.SUPERGROUP,is_forum=forum),message_thread_id=22,id=5)

class CatalogTests(unittest.TestCase):
    def test_menu_entries_and_regex_commands_have_registered_handlers(self):
        names={entry['name'] for entry in commands()}
        self.assertEqual(len(names),len(commands()))
        for item in command_menu(owner=True):self.assertIn(item['command'],names)
        for name in ['play','vplay','cplay','cvplay','seek','seekback','autoplay','speed','bass','effecton','remind','commands']:
            self.assertIn(name,names)
        # Every command-bearing decorator is audited, including regex routing.
        for path in source_paths():
            for node in ast.parse(path.read_text()).body:
                if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
                for decorator in node.decorator_list:
                    for call in ast.walk(decorator):
                        if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute) or not call.args:continue
                        if call.func.attr=='command' or (call.func.attr=='regex' and isinstance(call.args[0],ast.Constant) and str(call.args[0].value).startswith('^/')):
                            self.assertTrue(any(entry['source']==str(path.relative_to(Path.cwd())) for entry in commands()),path)

    def test_public_directory_hides_owner_commands_and_payloads_are_bounded(self):
        public={entry['name'] for entry in visible_commands()}
        for name in ['dbcleanup','watchdog','apiinfo','emojiinfo','logs','broadcast','sysinfo']:
            self.assertNotIn(name,public)
        for category in ['all','music','manage','tools','owner']:
            for page in (0,1,9999):
                text,markup=directory(category,page,owner=False)
                self.assertNotIn('/dbcleanup',text)
                self.assertLessEqual(len(rich_to_plain(text)),4096)
                for row in markup.inline_keyboard:
                    for button in row:
                        if button.callback_data:self.assertLessEqual(len(button.callback_data.encode()),64)

    def test_status_and_usage_cards_preserve_escaped_content(self):
        text=notice('User <code>&lt;name&gt;</code>',status='error')
        self.assertIn('Action unavailable',text)
        self.assertIn('&lt;name&gt;',text)
        self.assertIn('/copy',usage('/copy <text>','Use a reply'))
        from videl.utils import premium_emojis
        with patch.object(premium_emojis, 'USE_PREMIUM', True):
            card = result('Status',[('User','<value>'),('Duration','3:27'),('Channel','@mix')])
        self.assertIn('&lt;value&gt;',card)
        for key in ('boseh_person','boseh_clock','ios_link'):
            self.assertIn(f'emoji-id="{premium_emojis.PREMIUM_IDS[key]}"',card)
        self.assertIn('<table',card)
        from videl.utils.rich_ui import rich_table
        with patch.object(premium_emojis, 'USE_PREMIUM', True):
            table = rich_table(['Status','Channel'], [('Ready','@mix')])
        self.assertIn(f'emoji-id="{premium_emojis.PREMIUM_IDS["ios_symbols"]}"', table)
        self.assertIn(f'emoji-id="{premium_emojis.PREMIUM_IDS["ios_link"]}"', table)
        with patch.object(premium_emojis, 'USE_PREMIUM', False):
            fallback = result('Status',[('User','Ready')])
        self.assertIn(premium_emojis.FALLBACK['boseh_person'], fallback)
        with self.assertRaises(ValueError):notice('bad',status='made-up')

    def test_each_registered_command_has_a_premium_directory_icon(self):
        from videl.utils.command_catalog import _command_icon
        from videl.utils.premium_emojis import PREMIUM_IDS, FALLBACK
        entries = commands()
        self.assertGreaterEqual(len(entries), 160)
        self.assertIn("adminlist", {entry["name"] for entry in entries})
        for entry in entries:
            key = _command_icon(entry)
            self.assertIn(key, PREMIUM_IDS, entry['name'])
            self.assertIn(key, FALLBACK, entry['name'])

    def test_approved_member_actions_are_visible_and_keep_callback_targets(self):
        from videl.modules.approve import _approved_keyboard
        from pyrogram.enums import ButtonStyle
        keyboard = _approved_keyboard(list(range(101, 131)), allow_clear=True)
        buttons = [button for row in keyboard.inline_keyboard for button in row]
        removal = [button for button in buttons if button.callback_data and button.callback_data.startswith('approve:rm:')]
        self.assertEqual([button.callback_data for button in removal], [f'approve:rm:{uid}' for uid in range(101, 129)])
        self.assertTrue(all(button.style == ButtonStyle.DANGER for button in removal))
        self.assertIn('approve:clear', [button.callback_data for button in buttons])
        self.assertIn('approve:close', [button.callback_data for button in buttons])

    def test_reference_matches_registered_sources(self):
        from tools.command_reference import reference
        self.assertEqual(Path('docs/COMMAND_REFERENCE.md').read_text(),reference())

class ModernCommandsTests(unittest.IsolatedAsyncioTestCase):
    async def test_copy_action_preserves_plain_text_not_html(self):
        msg=message(['copy','<unsafe>','😀'])
        with patch.object(api,'rich_reply',AsyncMock()) as reply:
            await api.copy_command(None,msg)
        keyboard=reply.call_args.kwargs['reply_markup']
        self.assertEqual(keyboard.inline_keyboard[0][0].copy_text.text,'<unsafe> 😀')
        self.assertIn('&lt;unsafe&gt;',reply.call_args.args[1])

    async def test_oversize_utf16_copy_does_not_create_a_button(self):
        msg=message(['copy','😀'*129])
        with patch.object(api,'rich_reply',AsyncMock()) as reply:await api.copy_command(None,msg)
        self.assertNotIn('reply_markup',reply.call_args.kwargs)

    async def test_pollstop_denied_before_api_call(self):
        with patch.object(api,'is_user_authorized',AsyncMock(return_value=False)),patch.object(api,'bot_api',AsyncMock()) as send,patch.object(api,'rich_reply',AsyncMock()):
            await api.stop_poll_command(None,message(['pollstop']))
            send.assert_not_awaited()

    async def test_pollstop_uses_replied_message_and_real_api(self):
        msg=message(['pollstop']);msg.reply_to_message=SimpleNamespace(id=9,poll=object())
        with patch.object(api,'is_user_authorized',AsyncMock(return_value=True)),patch.object(api,'bot_api',AsyncMock(return_value=(200,{'ok':True,'result':{}}))) as send,patch.object(api,'rich_reply',AsyncMock()):
            await api.stop_poll_command(None,msg)
            send.assert_awaited_once_with('stopPoll',{'chat_id':-1001,'message_id':9})

    async def test_owner_callback_never_leaks_directory_in_group(self):
        query=SimpleNamespace(message=message([]),from_user=SimpleNamespace(id=6265999542),data='cmds:owner:0',answer=AsyncMock())
        with patch.object(professional,'rich_edit',AsyncMock()) as edit:
            await professional.navigate(None,query)
            edit.assert_not_awaited()
            self.assertTrue(query.answer.call_args.kwargs['show_alert'])

    async def test_ping_has_one_read_only_request_and_no_probe_message(self):
        from videl.app.router import Context,Parsed
        client=SimpleNamespace(get_me=AsyncMock())
        ctx=Context(client,message(['ping']),Parsed('ping',''))
        screen=await ping.ping(ctx)
        client.get_me.assert_awaited_once()
        self.assertIn('Connection',__import__('videl.plugins.base',fromlist=['plain']).plain(screen.html))

    def test_public_telegram_tools_help_omits_private_operations(self):
        self.assertNotIn('/apiinfo',api.public_help(message(['help'])))

    def test_telegram_tools_help_uses_rich_sections_and_command_tables(self):
        public = api.public_help(message(['help']))
        self.assertGreaterEqual(public.count('<table'), 3)
        self.assertIn('<h3>', public)
        self.assertNotIn('/emojiinfo', public)
        self.assertIn('/emojiinfo', api.HELP)
        self.assertTrue('<tg-emoji' in public or '🎛' in public)

class StyledFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_rich_send_retries_premium_emoji_rejection_with_unicode_fallback(self):
        from pyrogram.errors import BadRequest
        from videl.utils.command_ui import rich_send
        send = AsyncMock(side_effect=[BadRequest("CUSTOM_EMOJI_INVALID"), "sent"])
        with patch("videl.utils.command_ui._send", send):
            result = await rich_send(
                SimpleNamespace(), 123,
                '<tg-emoji emoji-id="123">🎵</tg-emoji>', navigation=False,
            )
        self.assertEqual(result, "sent")
        self.assertEqual(send.await_count, 2)
        retry_text = send.await_args.args[2]
        self.assertNotIn("<tg-emoji", retry_text)
        self.assertIn("🎵", retry_text)

    async def test_unrelated_bad_request_does_not_strip_premium_emoji_or_retry(self):
        from pyrogram.errors import BadRequest
        from videl.utils.bot_ui import visual_call
        send = AsyncMock(side_effect=BadRequest("CHAT_WRITE_FORBIDDEN"))
        with self.assertRaises(BadRequest):
            await visual_call(send, text='<tg-emoji emoji-id="123">🎵</tg-emoji> Track')
        send.assert_awaited_once()

    async def test_definite_style_rejection_drops_only_visuals(self):
        from pyrogram.errors import BadRequest
        from pyrogram.enums import ButtonStyle
        from videl.utils.bot_ui import button,visual_call
        from pyrogram.types import InlineKeyboardMarkup
        keyboard=InlineKeyboardMarkup([[button('Music',callback_data='help:music',style='primary')]])
        action=AsyncMock(side_effect=[BadRequest('STYLE_INVALID'),object()])
        await visual_call(action,text='Controls',reply_markup=keyboard)
        fallback=action.call_args.kwargs['reply_markup'].inline_keyboard[0][0]
        self.assertEqual(fallback.callback_data,'help:music')
        self.assertEqual(fallback.style,ButtonStyle.DEFAULT)
        self.assertEqual(keyboard.inline_keyboard[0][0].style,ButtonStyle.PRIMARY)

    def test_richgram_markup_uses_same_semantic_style_as_native_buttons(self):
        from videl.utils.rich_ui import rich_button
        from vendor.richgram.richgram.rich_ui import _native_buttons
        from pyrogram.enums import ButtonStyle
        _,markup=_native_buttons(rich_button('Save changes',callback_data='save:1'))
        self.assertEqual(markup.inline_keyboard[0][0].style,ButtonStyle.SUCCESS)
        self.assertEqual(markup.inline_keyboard[0][0].callback_data,'save:1')

    async def test_unstyled_command_buttons_gain_icons_without_mutating_actions(self):
        from pyrogram.types import InlineKeyboardButton,InlineKeyboardMarkup
        from videl.utils import premium_emojis
        from videl.utils.bot_ui import visual_call
        from unittest.mock import AsyncMock
        original=InlineKeyboardMarkup([[InlineKeyboardButton('Ban member',callback_data='ban:7')]])
        send=AsyncMock(return_value='sent')
        with patch('videl.utils.bot_ui.ICONS_ENABLED',True):
            await visual_call(send,reply_markup=original)
        decorated=send.call_args.kwargs['reply_markup'].inline_keyboard[0][0]
        self.assertEqual(decorated.callback_data,'ban:7')
        self.assertEqual(decorated.icon_custom_emoji_id,premium_emojis.PREMIUM_IDS['rijif_forbid'])
        self.assertIsNone(original.inline_keyboard[0][0].icon_custom_emoji_id)
