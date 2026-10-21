"""Exercise the actual callback dispatcher, new onboarding, and real action boundary."""
import asyncio
import importlib
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,patch
from pyrogram.enums import ChatMemberStatus,ChatType
from videl import bot
with patch.object(bot,'add_handler'):
    callbacks=importlib.import_module('videl.modules.callbacks')
from videl.app import music,music_callbacks
from videl.plugins import start as general
from videl.app.readiness import inspect_setup
from videl.core.queue import chat_queues


def query(data='pause',uid=42,qid='test'):
    return NS(id=qid,data=data,from_user=NS(id=uid),answer=AsyncMock(),
        message=NS(chat=NS(id=-321,type=ChatType.SUPERGROUP),id=8,from_user=NS(id=777)))


def client(admin=True):
    return NS(me=NS(id=777,username='ExampleBot'),get_chat_member=AsyncMock(
        return_value=NS(status=ChatMemberStatus.ADMINISTRATOR if admin else ChatMemberStatus.MEMBER,
                        privileges=NS(can_restrict_members=True))))


class PlayerExperienceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        chat_queues[-321]=[{'title':'Current'},{'title':'Next'}]
        music.player.set_paused(-321,False)
        music_callbacks._completed.clear();music_callbacks._inflight.clear()

    def tearDown(self):
        chat_queues.pop(-321,None);music.player.stop_progress(-321)

    async def test_real_dispatcher_uses_clicker_not_bot_message_author(self):
        app=client(False);q=query()
        with patch.object(music,'call_py',NS(pause=AsyncMock())) as engine:
            await callbacks.on_callback(app,q)
        engine.pause.assert_not_awaited()
        app.get_chat_member.assert_awaited_once_with(-321,42)
        self.assertTrue(q.answer.call_args.kwargs['show_alert'])

    async def test_confirmed_button_pause_survives_card_refresh_failure(self):
        app=client();q=query()
        with patch.object(music,'call_py',NS(pause=AsyncMock(return_value=True))) as engine,patch.object(music.player,'refresh_np_ui',AsyncMock(side_effect=TimeoutError())):
            await callbacks.on_callback(app,q)
        engine.pause.assert_awaited_once_with(-321)
        self.assertTrue(music.player.is_paused(-321))
        q.answer.assert_awaited_once_with('Player is paused',show_alert=False)

    async def test_lost_callback_answer_never_retries_engine(self):
        app=client();q=query();q.answer.side_effect=TimeoutError()
        with patch.object(music,'call_py',NS(pause=AsyncMock(return_value=True))) as engine,patch.object(music.player,'refresh_np_ui',AsyncMock()):
            with self.assertRaises(TimeoutError):await callbacks.on_callback(app,q)
            await callbacks.on_callback(app,q)
            engine.pause.assert_awaited_once()
            q.answer.assert_awaited_once()
        self.assertTrue(music.player.is_paused(-321))

    async def test_engine_timeout_does_not_change_state_or_expose_provider_error(self):
        q=query()
        with patch.object(music,'call_py',NS(pause=AsyncMock(side_effect=RuntimeError('secret-cookie')))):
            await callbacks.on_callback(client(),q)
        self.assertFalse(music.player.is_paused(-321))
        self.assertIn('could not be confirmed',q.answer.call_args.args[0])
        self.assertNotIn('secret',q.answer.call_args.args[0]);q.answer.assert_awaited_once()

    async def test_clear_button_keeps_track_and_stops_autoplay(self):
        q=query('clear');current=chat_queues[-321][0]
        with patch('videl.core.autoplay.stop_autoplay') as stop,patch.object(music.player,'refresh_np_ui',AsyncMock()):
            await callbacks.on_callback(client(),q)
        self.assertEqual(chat_queues[-321],[current]);stop.assert_called_once_with(-321)
        self.assertIn('current track kept',q.answer.call_args.args[0])

    async def test_simultaneous_repeat_clicks_cycle_under_the_shared_lock(self):
        with patch.object(music.player,'refresh_np_ui',AsyncMock()):
            await asyncio.gather(music_callbacks.handle(client(),query('cycle_loop',qid='one')),
                                 music_callbacks.handle(client(),query('cycle_loop',qid='two')))
        self.assertEqual(music.player.get_loop(-321),'all')

    async def test_repeated_callback_update_does_not_cycle_twice(self):
        q=query('cycle_loop')
        with patch.object(music.player,'refresh_np_ui',AsyncMock()):
            await callbacks.on_callback(client(),q);await callbacks.on_callback(client(),q)
        self.assertEqual(music.player.get_loop(-321),'one');q.answer.assert_awaited_once()

    async def test_saved_group_block_applies_to_buttons_as_well_as_commands(self):
        q=query()
        with patch('videl.utils.db.is_group_blocked',return_value=True),patch.object(music,'call_py',NS(pause=AsyncMock())) as engine:
            await callbacks.on_callback(client(),q)
        engine.pause.assert_not_awaited();self.assertTrue(q.answer.call_args.kwargs['show_alert'])

    async def test_queue_button_is_readable_by_members_and_preserves_callback_context(self):
        q=query('show_queue')
        with patch.object(music_callbacks,'rich_reply',AsyncMock()) as reply:
            await callbacks.on_callback(client(False),q)
        self.assertIs(reply.call_args.args[0],q)
        self.assertIn('Current',reply.call_args.args[1]);q.answer.assert_awaited_once()

    async def test_unsupported_callbacks_are_not_consumed_by_replacement(self):
        q=query('topicctl:open:-321:3')
        self.assertFalse(await music_callbacks.handle(client(),q));q.answer.assert_not_awaited()


class OnboardingTests(unittest.IsolatedAsyncioTestCase):
    async def test_bot_first_actions_and_valid_group_add_link(self):
        keyboard=general.private_keyboard(False,'ExampleBot').inline_keyboard
        self.assertEqual(keyboard[0][1].url,'https://t.me/ExampleBot?startgroup=true')
        self.assertEqual(keyboard[2][0].callback_data,'v2:setup')
        self.assertIsNotNone(keyboard[-1][0].web_app)

    async def test_private_onboarding_does_not_promise_private_voice_playback(self):
        text=general.member_caption('<Visitor>',True)
        self.assertIn('not in this private chat',text)
        self.assertIn('&lt;Visitor&gt;',text)
        group=general.member_caption('Visitor',False)
        self.assertNotIn('this private chat',group);self.assertIn('Start a voice chat',group)
        self.assertIn('/tagall [message]',group)
        self.assertIn('up to 50 members',group)

    async def test_private_setup_never_queries_group_membership(self):
        app=client();message=NS(chat=NS(type=ChatType.PRIVATE,id=42))
        screen=await inspect_setup(app,message)
        app.get_chat_member.assert_not_awaited();self.assertIn('Add the bot to your group',screen.html)

    async def test_setup_reports_actual_rights_and_unverified_dependencies(self):
        app=client();screen=await inspect_setup(app,query().message)
        app.get_chat_member.assert_awaited_once_with(-321,777)
        self.assertIn('Missing',screen.html);self.assertIn('Granted',screen.html)
        self.assertIn('not verified by this check',screen.html)
        self.assertIn('No permissions, settings or memberships were changed',screen.html)

    async def test_setup_timeout_is_not_ready_or_fabricated_missing_rights(self):
        app=client();app.get_chat_member.side_effect=TimeoutError()
        screen=await inspect_setup(app,query().message)
        self.assertIn('could not be checked',screen.html)
        self.assertNotIn('Granted',screen.html);self.assertNotIn('Missing',screen.html)
