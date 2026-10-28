"""Full command-facing presentation coverage, separate from user-payload delivery."""
import ast
import importlib
import unittest
import config
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from pathlib import Path
from pyrogram.enums import ButtonStyle,ChatType
from pyrogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from videl.utils import command_ui as ui
from videl.utils.bot_ui import button
from videl.utils.command_catalog import source_paths
from videl.utils.poll_options import build_poll
from vendor.richgram.richgram import rich_ui as transport
from videl import bot

with patch.object(bot,'add_handler'):
    tools=importlib.import_module('videl.modules.api_tools')

class PresentationTests(unittest.IsolatedAsyncioTestCase):
    def test_status_notices_get_matching_premium_badges_without_duplicate_icons(self):
        cases = (("success", "✅", "Saved"), ("error", "❌", "Unavailable"),
                 ("warning", "⚠️", "Check this"), ("info", "ℹ️", "Details"))
        for status, icon, title in cases:
            rendered = ui.notice("A safe detail.", status=status, title=title)
            self.assertIn(title, rendered)
            self.assertTrue(icon in rendered or "<tg-emoji" in rendered)
        warning = ui.notice("Check the destination.", status="warning", title="⚠️ Action unconfirmed")
        self.assertEqual(warning.count("⚠️"), 1)

    def test_legacy_heading_ornaments_are_replaced_by_semantic_icons(self):
        from videl.utils.rich_ui import rich_heading
        for source, expected in (("❍ Song blocked", "Song blocked"),
                                 ("❍ playlist added", "playlist added"),
                                 ("✫ #leftgroup ✫", "leftgroup")):
            rendered = rich_heading(source, level=3)
            self.assertNotIn("❍", rendered)
            self.assertNotIn("✫", rendered)
            self.assertIn(expected, rendered)
            self.assertTrue("<tg-emoji" in rendered or any(icon in rendered for icon in ("❌", "🎵", "✅", "🛡️", "✨")))

    def test_static_headings_in_every_command_module_drop_the_legacy_prefixes(self):
        from videl.utils.rich_ui import rich_heading
        paths = list(Path("videl/modules").glob("*.py")) + list(Path("videl/plugins").glob("*.py"))
        checked = 0
        for path in paths:
            for node in ast.walk(ast.parse(path.read_text())):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "rich_heading" and node.args):
                    continue
                try:
                    label = ast.literal_eval(node.args[0])
                except (ValueError, TypeError):
                    continue
                if not isinstance(label, str):
                    continue
                rendered = rich_heading(label)
                self.assertNotRegex(rendered, r"<h[1-6]>[❍✫⌯◍⬪]")
                checked += 1
        self.assertGreater(checked, 80, "command headings should be covered by the text UI audit")

    def test_music_headings_use_command_specific_premium_emojis(self):
        from videl.utils import premium_emojis
        from videl.utils.rich_ui import rich_heading
        cases = (
            ("Playback paused", "rijif_pause"),
            ("Playback resumed", "ios_play"),
            ("Upcoming queue cleared", "ios_trash"),
            ("Upcoming tracks shuffled", "ios_arrows"),
            ("Repeat updated", "ios_repeat"),
            ("Playlist loaded", "ios_folder"),
            ("Downloading…", "ios_down"),
            ("Searching lyrics…", "ios_memo"),
            ("Effects applied", "ios_controls"),
            ("Seeking…", "ios_arrows"),
            ("Channel linked", "ios_link"),
        )
        with patch.object(premium_emojis, "USE_PREMIUM", True):
            for label, key in cases:
                with self.subTest(label=label):
                    rendered = rich_heading(label, level=3)
                    self.assertIn(
                        f'<tg-emoji emoji-id="{premium_emojis.PREMIUM_IDS[key]}">',
                        rendered,
                    )

    def test_supplied_pack_ids_are_used_by_shared_command_headings_and_buttons(self):
        from videl.utils import premium_emojis
        from videl.utils.rich_ui import rich_heading
        with patch.object(premium_emojis, "USE_PREMIUM", True):
            rendered = rich_heading("📺 Media library", level=3)
        self.assertIn(
            f'<tg-emoji emoji-id="{premium_emojis.PREMIUM_IDS["ios_tv"]}">📺</tg-emoji>',
            rendered,
        )
        with patch("videl.utils.bot_ui.ICONS_ENABLED", True):
            self.assertEqual(
                button("Search videos", callback_data="search").icon_custom_emoji_id,
                premium_emojis.PREMIUM_IDS["ios_search"],
            )
        for source, key in (
            ("⚠️ Warning issued", "rijif_warning"),
            ("🚫 Member banned", "rijif_forbid"),
            ("📷 Profile photo", "rijif_camera"),
        ):
            rendered = rich_heading(source, level=3)
            self.assertIn(
                f'<tg-emoji emoji-id="{premium_emojis.PREMIUM_IDS[key]}">',
                rendered,
            )

    def test_every_user_supplied_pack_entry_has_an_addressable_id_and_fallback(self):
        from videl.utils import premium_emojis
        expected = {
            "tgiosicons": 100,
            "vector": 118,
            "android": 100,
            "emoji_fan": 100,
            "tgemoji": 100,
        }
        self.assertEqual(
            {name: len(rows.strip().splitlines()) for name, rows in premium_emojis.SUPPLIED_EMOJI_PACKS.items()},
            expected,
        )
        for pack, rows in premium_emojis.SUPPLIED_EMOJI_PACKS.items():
            for index, row in enumerate(rows.strip().splitlines(), start=1):
                fallback, emoji_id = row.rsplit(maxsplit=1)
                alias = f"{pack}_{index:03d}"
                self.assertEqual(premium_emojis.PREMIUM_IDS[alias], emoji_id)
                self.assertEqual(premium_emojis.FALLBACK[alias], fallback)
        self.assertFalse(set(premium_emojis.PREMIUM_IDS) - set(premium_emojis.FALLBACK))

    def test_emoji_browser_pages_every_supplied_pack_and_bounds_copy_buttons(self):
        from videl.utils.premium_emojis import SUPPLIED_EMOJI_PACKS
        body, menu = tools.emoji_browser_menu()
        self.assertEqual(len(menu.inline_keyboard), 3)
        self.assertIn("Premium emoji library", body)
        from videl.utils.premium_emojis import PREMIUM_IDS
        pack_buttons = [item for row in menu.inline_keyboard for item in row]
        self.assertEqual(
            [item.icon_custom_emoji_id for item in pack_buttons],
            [PREMIUM_IDS[f"{name}_001"] for name in SUPPLIED_EMOJI_PACKS],
        )
        for name, source in SUPPLIED_EMOJI_PACKS.items():
            first_fallback, first_id = source.strip().splitlines()[0].rsplit(maxsplit=1)
            page, markup = tools.emoji_browser_page(name, 0)
            self.assertIn(first_id, page)
            self.assertIn(first_fallback, page)
            callbacks = [item.callback_data for row in markup.inline_keyboard for item in row if item.callback_data]
            self.assertIn(f"emojilist:{name}:1", callbacks)
            copy_buttons = [item for row in markup.inline_keyboard for item in row if getattr(item, "copy_text", None)]
            self.assertEqual(len(copy_buttons), 2)
            self.assertTrue(any("_001" in item.copy_text.text for item in copy_buttons))
            self.assertLessEqual(max(len(item.copy_text.text) for item in copy_buttons), 256)
            self.assertIn(f"{name}_001", page)
            total_pages = (len(source.strip().splitlines()) + tools.EMOJI_BROWSER_PAGE_SIZE - 1) // tools.EMOJI_BROWSER_PAGE_SIZE
            last, _ = tools.emoji_browser_page(name, total_pages - 1)
            self.assertIn(source.strip().splitlines()[-1].rsplit(maxsplit=1)[1], last)
        with self.assertRaises(ValueError):
            tools.emoji_browser_page("missing", 0)
        with self.assertRaises(ValueError):
            tools.emoji_browser_page("vector", 999)

    def test_bot_profile_update_is_registered_as_owner_private_only(self):
        from videl.utils.command_catalog import commands
        entry = next(row for row in commands() if row["name"] == "setbotphoto")
        self.assertTrue(entry["owner"])
        self.assertEqual(entry["context"], "private")
        self.assertIn("setbotphoto", {row["command"] for row in __import__("videl.utils.bot_commands", fromlist=["command_menu"]).command_menu(owner=True)})

    def test_emoji_browser_is_documented_only_in_private_owner_help(self):
        owner = SimpleNamespace(
            from_user=SimpleNamespace(id=config.OWNER_ID),
            chat=SimpleNamespace(type=ChatType.PRIVATE),
        )
        guest = SimpleNamespace(
            from_user=SimpleNamespace(id=config.OWNER_ID + 1),
            chat=SimpleNamespace(type=ChatType.PRIVATE),
        )
        self.assertIn("/emojiinfo list", tools.public_help(owner))
        self.assertNotIn("/emojiinfo list", tools.public_help(guest))

    async def test_emoji_browser_callback_restricts_updates_to_private_owner(self):
        denied = SimpleNamespace(
            message=SimpleNamespace(chat=SimpleNamespace(type=ChatType.PRIVATE)),
            from_user=SimpleNamespace(id=config.OWNER_ID + 1),
            data="emojilist:vector:0",
            answer=AsyncMock(),
        )
        with patch.object(tools, "rich_edit", new=AsyncMock()) as edit:
            await tools.emoji_browser_callback(None, denied)
            denied.answer.assert_awaited_once()
            edit.assert_not_awaited()

        owner = SimpleNamespace(
            message=SimpleNamespace(chat=SimpleNamespace(type=ChatType.PRIVATE)),
            from_user=SimpleNamespace(id=config.OWNER_ID),
            data="emojilist:vector:0",
            answer=AsyncMock(),
        )
        with patch.object(tools, "rich_edit", new=AsyncMock()) as edit:
            await tools.emoji_browser_callback(None, owner)
            owner.answer.assert_awaited_once()
            edit.assert_awaited_once()

    def test_card_has_heading_and_real_navigation_without_body_rewriting(self):
        body='<aside>Saved &amp; ready</aside>'
        rendered=ui.present(body,navigation=True)
        self.assertIn(body,rendered)
        self.assertIn('<h3>',rendered)
        plain,keyboard=transport._native_buttons(rendered)
        self.assertNotIn('tg-button',plain)
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data,'help:home')
        self.assertEqual(keyboard.inline_keyboard[0][0].style,ButtonStyle.PRIMARY)
        self.assertEqual(keyboard.inline_keyboard[0][1].callback_data,'cmds:all:0')

    def test_global_navigation_is_opt_in_not_added_to_every_command_reply(self):
        rendered = ui.present('<h3>Ban confirmed</h3><blockquote>Telegram acknowledged the action.</blockquote>')
        self.assertNotIn('tg-button', rendered)
        self.assertNotIn('help:home', rendered)
        self.assertNotIn('cmds:all:0', rendered)

    def test_global_navigation_is_added_alongside_authored_buttons_only_once(self):
        body='<h2>Controls</h2>'+transport.rich_button('Pause',callback_data='pause',style='primary')
        rendered=ui.present(body,navigation=True)
        self.assertTrue(rendered.startswith(body))
        self.assertIn('data="help:home"',rendered)
        self.assertIn('data="cmds:all:0"',rendered)
        self.assertEqual(rendered.count('data="pause"'),1)
        already_complete=body+ui.rich_button_row(
            ui.rich_button('Help center',callback_data='help:home',style='primary'),
            ui.rich_button('Browse commands',callback_data='cmds:all:0'),
        )
        self.assertEqual(ui.present(already_complete,navigation=True),already_complete)
        self.assertIsNone(ui.present(None))
        self.assertEqual(ui.present(''),'')
        self.assertNotIn('tg-button',ui.present('No navigation',navigation=False))
        self.assertIn('<blockquote>',ui.present('A concise plain reply',navigation=False))
        full='a'*4096
        plain,_=transport._native_buttons(ui.present(full))
        self.assertEqual(plain,full)

    def test_narrow_footer_never_overflows_telegram_text_limit(self):
        long = '<h2>Result</h2>' + 'x' * 4088
        rendered = ui.present(long,navigation=True)
        from videl.utils.post_format import post_text_length
        self.assertLessEqual(post_text_length(rendered, "HTML"), 4096)
        self.assertNotIn('tg-button', rendered)
        self.assertNotIn('tg-button', ui.present('<h3>Loading…</h3>', navigation=False))

    async def test_reply_standard_fallback_keeps_topic_quote_and_real_buttons(self):
        app=SimpleNamespace(send_message=AsyncMock())
        message=SimpleNamespace(_client=app,chat=SimpleNamespace(id=-1001,type=ChatType.SUPERGROUP),
                                id=7,message_thread_id=22,from_user=SimpleNamespace(id=42))
        with patch.object(transport,'RICH_AVAILABLE',False):
            await ui.rich_reply(message,'<aside>Ready</aside>',navigation=True)
        options=app.send_message.call_args.kwargs
        self.assertEqual(options['chat_id'],-1001)
        self.assertEqual(options['message_thread_id'],22)
        self.assertEqual(options['reply_parameters'].message_id,7)
        self.assertEqual(options['reply_markup'].inline_keyboard[0][0].callback_data,'help:home')
        self.assertIn('Ready',options['text'])

    async def test_explicit_keyboard_is_cloned_with_help_navigation_and_original_actions(self):
        keyboard=InlineKeyboardMarkup([[button('Stop',callback_data='stop',style='danger')]])
        with patch.object(ui,'_send',AsyncMock()) as send:
            await ui.rich_send(object(),123,'<h2>Player</h2>',reply_markup=keyboard,protect_content=True,navigation=True)
        updated=send.call_args.kwargs['reply_markup']
        self.assertIsNot(updated,keyboard)
        self.assertEqual(updated.inline_keyboard[0][0].callback_data,'stop')
        self.assertEqual([item.callback_data for item in updated.inline_keyboard[-1]],['help:home','cmds:all:0'])
        self.assertEqual(len(keyboard.inline_keyboard),1)
        self.assertTrue(send.call_args.kwargs['protect_content'])
        self.assertNotIn('help:home',send.call_args.args[2])

    async def test_edit_keeps_action_rows_and_adds_navigation_once(self):
        keyboard=InlineKeyboardMarkup([[button('Refresh',callback_data='refresh')]])
        with patch.object(ui,'_edit',AsyncMock()) as edit:
            await ui.rich_edit(object(),'<h2>Settings</h2>',reply_markup=keyboard,navigation=True)
        updated=edit.call_args.kwargs['reply_markup']
        self.assertEqual(updated.inline_keyboard[0][0].callback_data,'refresh')
        self.assertEqual([item.callback_data for item in updated.inline_keyboard[-1]],['help:home','cmds:all:0'])
        self.assertEqual(len(keyboard.inline_keyboard),1)

    async def test_reply_keyboard_keeps_existing_actions_and_adds_help_commands(self):
        keyboard=ReplyKeyboardMarkup([[KeyboardButton('Continue')]],resize_keyboard=True)
        with patch.object(ui,'_send',AsyncMock()) as send:
            await ui.rich_send(object(),123,'<h3>Choose an action</h3>',reply_markup=keyboard,navigation=True)
        updated=send.call_args.kwargs['reply_markup']
        self.assertEqual(updated.keyboard[0][0].text,'Continue')
        self.assertEqual([item.text for item in updated.keyboard[-1]],['/help','/commands'])
        self.assertEqual(len(keyboard.keyboard),1)

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
