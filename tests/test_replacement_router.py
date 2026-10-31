"""Replacement runtime tests; no secrets, Mongo changes or Telegram effects."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock,patch
from pyrogram.enums import ChatMemberStatus,ChatType
from videl.app.router import Router,Command,Context,Parsed,Screen,CommandError,parse,authorize
from videl.app.routes import COMMANDS
from videl.plugins import start as general, tools


def message(text='/start',uid=42,kind=ChatType.PRIVATE,mid=5):
    return SimpleNamespace(text=text,id=mid,from_user=SimpleNamespace(id=uid,first_name='<User>'),
        chat=SimpleNamespace(id=123,type=kind),reply_to_message=None,message_thread_id=None)


class ParserTests(unittest.TestCase):
    def test_mentions_arguments_and_foreign_bots(self):
        self.assertEqual(parse('/HeLP@Videl0Bot music','videl0bot'),Parsed('help','music'))
        self.assertIsNone(parse('/help@OtherBot','Videl0Bot'))
        self.assertIsNone(parse('/help@OtherBot',''))
        self.assertEqual(parse('/id 123\nignored').arguments,'123\nignored')
        for prefix in '!?&.#~$+':
            self.assertEqual(parse(f'{prefix}help music'),Parsed('help','music'))
            self.assertEqual(parse(f'{prefix}help@Videl0Bot','videl0bot'),Parsed('help',''))
        self.assertIsNone(parse('!help@OtherBot','Videl0Bot'))
        for text in ['plain text','/','/bad-name','/a'*40000,None]:self.assertIsNone(parse(text))

    def test_manifest_is_unique_and_has_no_import_time_registration(self):
        self.assertEqual(len({c.name for c in COMMANDS}),len(COMMANDS))
        with self.assertRaises(ValueError):Router([COMMANDS[0],COMMANDS[0]])
        with self.assertRaises(ValueError):Command('Bad',AsyncMock(),'bad')
        with self.assertRaises(ValueError):Command('good',AsyncMock(),'bad',policy='all-admins')


class RouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_render_and_no_duplicate_completed_update(self):
        handler=AsyncMock(return_value=Screen('<h2>Ready</h2>'))
        router=Router([Command('test',handler,'Test')])
        client=SimpleNamespace(me=SimpleNamespace(username='Videl0Bot'))
        msg=message('/test')
        with patch('videl.app.router.rich_reply',AsyncMock()) as render:
            await router.dispatch(client,msg)
            await router.dispatch(client,msg)
            handler.assert_awaited_once();render.assert_awaited_once()

    async def test_duplicate_inflight_update_is_not_executed_twice(self):
        begin,finish=asyncio.Event(),asyncio.Event()
        calls=[]
        async def handler(ctx):
            calls.append(ctx.command.name);begin.set();await finish.wait();return Screen('Ready')
        router=Router([Command('test',handler,'Test')]);msg=message('/test')
        with patch('videl.app.router.rich_reply',AsyncMock()):
            task=asyncio.create_task(router.dispatch(SimpleNamespace(),msg))
            await begin.wait()
            await router.dispatch(SimpleNamespace(),msg)
            finish.set();await task
        self.assertEqual(calls,['test'])

    async def test_owner_requires_exact_account_and_private_chat(self):
        action=AsyncMock(return_value=None)
        router=Router([Command('owner',action,'Owner',policy='owner',category='owner')])
        with patch('videl.app.router.rich_reply',AsyncMock()):
            await router.dispatch(SimpleNamespace(),message('/owner',uid=43))
            await router.dispatch(SimpleNamespace(),message('/owner',uid=6265999542,kind=ChatType.SUPERGROUP))
            action.assert_not_awaited()
            await router.dispatch(SimpleNamespace(),message('/owner',uid=6265999542))
            action.assert_awaited_once()

    async def test_admin_requires_fresh_current_group_membership(self):
        command=Command('admin',AsyncMock(),'Admin',policy='admin',category='manage')
        client=SimpleNamespace(get_chat_member=AsyncMock(return_value=SimpleNamespace(status=ChatMemberStatus.MEMBER)))
        ctx=Context(client,message(kind=ChatType.SUPERGROUP),Parsed('admin',''))
        self.assertFalse(await authorize(command,ctx))
        client.get_chat_member.return_value.status=ChatMemberStatus.ADMINISTRATOR
        self.assertTrue(await authorize(command,ctx))
        self.assertEqual(client.get_chat_member.await_count,2)
        client.get_chat_member.side_effect=TimeoutError()
        self.assertFalse(await authorize(command,ctx))

    async def test_dj_policy_allows_assigned_member_but_denies_unassigned(self):
        command=Command('control',AsyncMock(),'Control',policy='dj',category='music')
        client=SimpleNamespace(get_chat_member=AsyncMock(return_value=SimpleNamespace(status=ChatMemberStatus.MEMBER)))
        ctx=Context(client,message(kind=ChatType.SUPERGROUP,uid=43),Parsed('control',''))
        with patch('videl.plugins.base.get_setting',return_value={'user_id': 43}):
            self.assertTrue(await authorize(command,ctx))
        with patch('videl.plugins.base.get_setting',return_value={'user_id': 99}):
            self.assertFalse(await authorize(command,ctx))
        client.get_chat_member.return_value.status=ChatMemberStatus.LEFT
        with patch('videl.plugins.base.get_setting',return_value={'user_id': 43}):
            self.assertFalse(await authorize(command,ctx), 'a stale DJ assignment must not authorize someone outside the group')
        client.get_chat_member.return_value.status=ChatMemberStatus.ADMINISTRATOR
        with patch('videl.plugins.base.get_setting',return_value={}):
            self.assertTrue(await authorize(command,ctx))

    async def test_safe_validation_escapes_content_and_provider_errors_are_not_exposed(self):
        handler=AsyncMock(side_effect=CommandError('<unsafe>'))
        router=Router([Command('test',handler,'Test')])
        with patch('videl.app.router.rich_reply',AsyncMock()) as render:
            await router.dispatch(SimpleNamespace(),message('/test'))
            self.assertIn('&lt;unsafe&gt;',render.call_args.args[1])
        handler.side_effect=RuntimeError('secret-token-provider-url')
        with patch('videl.app.router.rich_reply',AsyncMock()) as render:
            await router.dispatch(SimpleNamespace(),message('/test',mid=6))
            self.assertNotIn('secret-token',render.call_args.args[1])
        self.assertEqual(handler.await_count,2)

    async def test_render_failure_does_not_reexecute_action_or_resend(self):
        action=AsyncMock(return_value=Screen('Ready'));router=Router([Command('test',action,'Test')])
        with patch('videl.app.router.rich_reply',AsyncMock(side_effect=TimeoutError())) as render:
            with self.assertRaises(TimeoutError):await router.dispatch(SimpleNamespace(),message('/test'))
            await router.dispatch(SimpleNamespace(),message('/test'))
            action.assert_awaited_once();render.assert_awaited_once()

    async def test_cancellation_propagates_and_does_not_leave_active_state(self):
        action=AsyncMock(side_effect=asyncio.CancelledError())
        router=Router([Command('test',action,'Test')])
        with self.assertRaises(asyncio.CancelledError):await router.dispatch(SimpleNamespace(),message('/test'))
        self.assertFalse(router._active)

    async def test_foreign_bot_mention_does_not_invoke_handler(self):
        action=AsyncMock();router=Router([Command('test',action,'Test')])
        self.assertFalse(await router.dispatch(SimpleNamespace(me=SimpleNamespace(username='Videl0Bot')),message('/test@OtherBot')))
        action.assert_not_awaited()

    async def test_general_start_never_reads_owner_totals_in_group(self):
        msg=message(uid=6265999542,kind=ChatType.SUPERGROUP)
        with patch('videl.utils.db.read_live_totals') as totals:
            screen=await general.start(Context(SimpleNamespace(),msg,Parsed('start','')))
        totals.assert_not_called()
        self.assertNotIn('Owner workspace',screen.html)
        self.assertFalse(any(b.callback_data=='cmds:owner:0' for row in screen.keyboard.inline_keyboard for b in row))

    async def test_identifiers_dont_use_fake_user_links_for_groups(self):
        msg=message('/id',kind=ChatType.SUPERGROUP)
        screen=await tools.identifiers(Context(SimpleNamespace(),msg,Parsed('id','')))
        self.assertIn('Chat ID',screen.html)
        self.assertNotIn('tg://user?id=123',screen.html)


class InstallationTests(unittest.TestCase):
    def test_installation_is_explicit_idempotent_and_rolls_back_partial_registration(self):
        from videl.app.install import install,_installed
        class Client:
            def __init__(self):self.handlers=[];self.fail=False
            def add_handler(self,handler,group=0):
                if self.fail and self.handlers:raise RuntimeError('failed')
                self.handlers.append(handler)
            def remove_handler(self,handler,group=0):self.handlers.remove(handler)
        client=Client();first=install(client)
        self.assertIs(install(client),first);self.assertEqual(len(client.handlers),2)
        broken=Client();broken.fail=True
        with self.assertRaises(RuntimeError):install(broken)
        self.assertEqual(broken.handlers,[]);self.assertNotIn(broken,_installed)

class BlockPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocked_account_and_group_get_distinct_explanations(self):
        command=Command('dj',AsyncMock(),'Assign DJ',policy='admin',block_policy='chat')
        router=Router([command])
        client=SimpleNamespace(me=SimpleNamespace(username='Videl0Bot'),get_chat_member=AsyncMock())
        msg=message('/dj',kind=ChatType.SUPERGROUP)
        with patch('videl.utils.db.is_user_blocked_db',return_value=True),patch('videl.utils.db.is_group_blocked',return_value=False),patch('videl.app.router.rich_reply',AsyncMock()) as reply:
            await router.dispatch(client,msg)
            self.assertIn('Your account is blocked',reply.call_args.args[1])
            self.assertNotIn('requires current group administrator',reply.call_args.args[1])
        with patch('videl.utils.db.is_user_blocked_db',return_value=False),patch('videl.utils.db.is_group_blocked',return_value=True),patch('videl.app.router.rich_reply',AsyncMock()) as reply:
            await router.dispatch(client,msg)
            self.assertIn('Bot commands are disabled in this chat',reply.call_args.args[1])
        client.get_chat_member.assert_not_awaited()

    async def test_migrated_music_controls_still_honor_saved_blocklists(self):
        command=next(item for item in COMMANDS if item.name=='pause')
        client=SimpleNamespace(get_chat_member=AsyncMock(return_value=SimpleNamespace(status=ChatMemberStatus.ADMINISTRATOR)))
        ctx=Context(client,message(kind=ChatType.SUPERGROUP),Parsed('pause',''))
        with patch('videl.utils.db.is_user_blocked_db',return_value=True),patch('videl.utils.db.is_group_blocked',return_value=False):
            self.assertFalse(await authorize(command,ctx))
        with patch('videl.utils.db.is_user_blocked_db',return_value=False),patch('videl.utils.db.is_group_blocked',return_value=True):
            self.assertFalse(await authorize(command,ctx))
        client.get_chat_member.assert_not_awaited()
