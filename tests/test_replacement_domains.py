"""Real action boundaries for the replacement command domains."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,Mock,patch
from pyrogram.enums import ChatMemberStatus,ChatType
from videl.app.router import Context,Parsed,CommandError,authorize
from videl.app.routes import COMMANDS
from videl.plugins import moderation
from videl.app import music
from videl.core.queue import chat_queues
from videl.plugins.base import plain as plain_caps


def context(name='ban',args='reason'):
    target=NS(id=99,first_name='<Target>')
    message=NS(chat=NS(id=-123,type=ChatType.SUPERGROUP),id=7,from_user=NS(id=42),
        reply_to_message=NS(id=6,from_user=target))
    client=NS(me=NS(id=777),get_chat_member=AsyncMock(side_effect=lambda c,u:NS(
        status=ChatMemberStatus.ADMINISTRATOR if u==777 else ChatMemberStatus.MEMBER,
        privileges=NS(can_restrict_members=True,can_delete_messages=True))),
        ban_chat_member=AsyncMock(return_value=True),unban_chat_member=AsyncMock(return_value=True),
        restrict_chat_member=AsyncMock(return_value=True),delete_messages=AsyncMock(return_value=True),
        get_chat=AsyncMock(return_value=NS(permissions=object())),get_users=AsyncMock())
    return Context(client,message,Parsed(name,args))


class ModerationTests(unittest.IsolatedAsyncioTestCase):
    def test_temporary_duration_rejects_forever_coercions_and_bad_units(self):
        self.assertEqual(moderation.duration('2h'),7200)
        self.assertEqual(moderation.duration('365d'),31536000)
        for value in ['0m','10s','366d','99999999w','-10m','10','10years','1.5h']:
            with self.assertRaises(CommandError):moderation.duration(value)

    async def test_ban_confirmed_even_when_audit_write_fails(self):
        ctx=context()
        with patch.object(moderation,'_audit',Mock(side_effect=RuntimeError('mongo'))):screen=await moderation.moderate(ctx)
        ctx.client.ban_chat_member.assert_awaited_once()
        html=plain_caps(screen.html)
        self.assertIn('Member banned',html)
        self.assertIn('could not be saved',html)
        self.assertIn('&lt;Target&gt;',html)

    async def test_temporary_action_requires_duration_before_any_telegram_mutation(self):
        ctx=context('tban','not-a-duration')
        with self.assertRaises(CommandError):await moderation.moderate(ctx)
        ctx.client.ban_chat_member.assert_not_awaited()
        ctx=context('tmute','10m reason')
        screen=await moderation.moderate(ctx)
        self.assertIn('Member muted',plain_caps(screen.html))
        self.assertIsNotNone(ctx.client.restrict_chat_member.call_args.kwargs['until_date'])

    async def test_both_target_admins_and_bot_owner_are_protected(self):
        ctx=context();ctx.client.get_chat_member.return_value=NS(status=ChatMemberStatus.ADMINISTRATOR)
        ctx.client.get_chat_member.side_effect=None
        with self.assertRaises(CommandError):await moderation.moderate(ctx)
        ctx.client.ban_chat_member.assert_not_awaited()
        ctx=context();ctx.message.reply_to_message.from_user.id=6265999542
        with self.assertRaises(CommandError):await moderation.moderate(ctx)
        ctx.client.ban_chat_member.assert_not_awaited()

    async def test_actor_needs_telegram_restrict_right_not_merely_admin_status(self):
        ctx=context()
        ctx.client.get_chat_member.side_effect=None
        ctx.client.get_chat_member.return_value=NS(status=ChatMemberStatus.ADMINISTRATOR,privileges=NS(can_restrict_members=False))
        command=next(command for command in COMMANDS if command.name=='ban')
        self.assertFalse(await authorize(command,ctx))
        ctx.client.get_chat_member.return_value.status=ChatMemberStatus.OWNER
        self.assertTrue(await authorize(command,ctx))

    async def test_bot_needs_its_own_restrict_permission(self):
        ctx=context()
        ctx.client.get_chat_member.side_effect=lambda c,u:NS(status=ChatMemberStatus.ADMINISTRATOR if u==777 else ChatMemberStatus.MEMBER,privileges=NS(can_restrict_members=False))
        with self.assertRaises(CommandError):await moderation.moderate(ctx)
        ctx.client.ban_chat_member.assert_not_awaited()

    async def test_kick_partial_release_is_reported_without_retry(self):
        ctx=context('kick');ctx.client.unban_chat_member.side_effect=TimeoutError()
        screen=await moderation.moderate(ctx)
        html=plain_caps(screen.html).lower()
        self.assertIn('partly confirmed',html)
        self.assertIn('about a minute',html)
        ctx.client.ban_chat_member.assert_awaited_once();ctx.client.unban_chat_member.assert_awaited_once()
        self.assertIsNotNone(ctx.client.ban_chat_member.call_args.kwargs['until_date'])

    async def test_delete_failure_does_not_misreport_confirmed_ban(self):
        ctx=context('dban');ctx.client.delete_messages.side_effect=TimeoutError()
        with patch.object(moderation,'_audit',Mock(return_value=True)):screen=await moderation.moderate(ctx)
        html=plain_caps(screen.html)
        self.assertIn('Member banned',html)
        self.assertIn('message deletion is not',html)
        ctx.client.ban_chat_member.assert_awaited_once()

    async def test_unmute_restores_exact_group_defaults(self):
        ctx=context('unmute');permissions=object();ctx.client.get_chat.return_value.permissions=permissions
        await moderation.moderate(ctx)
        self.assertIs(ctx.client.restrict_chat_member.call_args.args[2],permissions)
        ctx=context('unmute');ctx.client.get_chat.return_value.permissions=None
        with self.assertRaises(CommandError):await moderation.moderate(ctx)
        ctx.client.restrict_chat_member.assert_not_awaited()

    async def test_unknown_membership_fails_closed(self):
        ctx=context();ctx.client.get_chat_member.side_effect=TimeoutError()
        with self.assertRaises(CommandError):await moderation.moderate(ctx)
        ctx.client.ban_chat_member.assert_not_awaited()

    async def test_explicit_target_is_resolved_without_stealing_reply_reason(self):
        ctx=context(args='@example reason');ctx.message.reply_to_message=None
        ctx.client.get_users.return_value=NS(id=100,first_name='Example')
        user,tokens=await moderation.resolve(ctx)
        ctx.client.get_users.assert_awaited_once_with('@example');self.assertEqual(tokens,['reason'])
        self.assertEqual(user.id,100)
        ctx=context(args='the full reason')
        _,tokens=await moderation.resolve(ctx);self.assertEqual(tokens,['the','full','reason'])


class MusicTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        chat_queues[-123]=[{'title':'Current <track>'},{'title':'Second'},{'title':'Third'}]
        music.player.set_paused(-123,False)

    def tearDown(self):
        chat_queues.pop(-123,None);music.player.stop_progress(-123)

    async def test_engine_timeout_cannot_change_pause_state(self):
        with patch.object(music,'call_py',NS(pause=AsyncMock(side_effect=TimeoutError()))):
            with self.assertRaises(TimeoutError):await music.control(context('pause',''))
        self.assertFalse(music.player.is_paused(-123))

    async def test_confirmed_pause_survives_player_card_refresh_failure(self):
        engine=NS(pause=AsyncMock(return_value=True))
        with patch.object(music,'call_py',engine),patch.object(music.player,'refresh_np_ui',AsyncMock(side_effect=TimeoutError())):
            screen=await music.control(context('pause',''))
        engine.pause.assert_awaited_once();self.assertTrue(music.player.is_paused(-123))
        self.assertIn('Playback paused',screen.html)
        self.assertEqual(len(chat_queues[-123]),3)

    async def test_clear_preserves_current_track_and_disables_autoplay(self):
        current=chat_queues[-123][0]
        with patch('videl.core.autoplay.stop_autoplay') as stop,patch.object(music.player,'refresh_np_ui',AsyncMock()):
            screen=await music.control(context('clear',''))
        self.assertEqual(chat_queues[-123],[current]);stop.assert_called_once_with(-123)
        self.assertIn('2 pending tracks removed',screen.html)

    async def test_shuffle_keeps_current_track_first(self):
        current=chat_queues[-123][0]
        with patch.object(music.player,'refresh_np_ui',AsyncMock()):await music.control(context('shuffle',''))
        self.assertIs(chat_queues[-123][0],current)
        self.assertEqual({track['title'] for track in chat_queues[-123][1:]},{'Second','Third'})

    async def test_queue_render_has_a_fixed_budget_and_escapes_metadata(self):
        chat_queues[-123]=[{'title':'<script>'+('x'*5000)} for _ in range(100)]
        screen=await music.view_queue(context('queue',''))
        self.assertLess(len(screen.html),4000);self.assertNotIn('<script>',screen.html)
        self.assertIn('99 upcoming',screen.html)

    async def test_invalid_loop_does_not_change_repeat_state(self):
        music.player.set_loop(-123,'off')
        with self.assertRaises(CommandError):await music.control(context('loop','infinite'))
        self.assertEqual(music.player.get_loop(-123),'off')

    async def test_denied_playback_command_does_not_contact_voice_engine(self):
        from videl.app.router import Router
        command=next(item for item in COMMANDS if item.name=='resume')
        ctx=context('resume','');ctx.message.text='/resume'
        ctx.client.get_chat_member.side_effect=None
        ctx.client.get_chat_member.return_value=NS(status=ChatMemberStatus.MEMBER)
        with patch.object(music,'call_py',NS(resume=AsyncMock())) as engine,patch('videl.app.router.rich_reply',AsyncMock()):
            await Router([command]).dispatch(ctx.client,ctx.message)
            engine.resume.assert_not_awaited()

    async def test_negative_engine_acknowledgement_cannot_change_pause_state(self):
        with patch.object(music,'call_py',NS(pause=AsyncMock(return_value=False))):
            with self.assertRaises(RuntimeError):await music.control(context('pause',''))
        self.assertFalse(music.player.is_paused(-123))
