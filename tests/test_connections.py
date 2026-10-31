from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from pyrogram.enums import ChatMemberStatus

from videl.app.router import Command, Context, Parsed, Router, Screen, CommandError
from videl.app.connections import CONNECTED_COMMANDS
from videl.app.routes import router as command_router
from videl.plugins.connections import connect, disconnect


def private_message(text="/ban @target"):
    return SimpleNamespace(
        id=10,
        text=text,
        chat=SimpleNamespace(id=77, type="private"),
        from_user=SimpleNamespace(id=42),
        reply_to_message=SimpleNamespace(id=9),
        message_thread_id=None,
    )


class ConnectedRoutingTests(IsolatedAsyncioTestCase):
    async def _setup(self, member_status=ChatMemberStatus.ADMINISTRATOR):
        group = SimpleNamespace(id=-100123, title="Safe Group", type="supergroup")
        client = SimpleNamespace(
            me=SimpleNamespace(username="testbot"),
            get_chat=AsyncMock(return_value=group),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status=member_status, privileges=None)),
        )
        calls = []

        async def handler(ctx):
            calls.append(ctx)
            return Screen("Done")

        router = Router([Command("ban", handler, "Ban", policy="admin")])
        return client, router, calls

    async def test_connected_command_uses_server_group_real_actor_and_private_reply(self):
        client, router, calls = await self._setup()
        message = private_message()
        with patch("videl.utils.db.get_connected_chat", return_value=-100123), patch(
            "videl.app.router.rich_reply", new_callable=AsyncMock
        ) as reply:
            self.assertTrue(await router.dispatch(client, message))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].user.id, 42)
        self.assertEqual(calls[0].message.chat.id, -100123)
        self.assertIsNone(calls[0].message.reply_to_message)
        self.assertEqual(client.get_chat_member.await_args_list, [((-100123, 42), {}), ((-100123, 42), {})])
        reply.assert_awaited_once()
        self.assertIs(reply.await_args.args[0], message)

    async def test_remote_action_denied_after_admin_rights_are_revoked(self):
        client, router, calls = await self._setup(ChatMemberStatus.MEMBER)
        message = private_message()
        with patch("videl.utils.db.get_connected_chat", return_value=-100123), patch(
            "videl.app.router.rich_reply", new_callable=AsyncMock
        ) as reply:
            await router.dispatch(client, message)
        self.assertEqual(calls, [])
        reply.assert_awaited_once()
        self.assertIs(reply.await_args.args[0], message)

    async def test_private_message_reply_target_is_never_forwarded_to_group(self):
        client, router, calls = await self._setup()
        message = private_message("/ban")
        with patch("videl.utils.db.get_connected_chat", return_value=-100123), patch(
            "videl.app.router.rich_reply", new_callable=AsyncMock
        ):
            await router.dispatch(client, message)
        self.assertIsNone(calls[0].message.reply_to_message)

    async def test_remote_action_requires_a_saved_connection(self):
        client, router, calls = await self._setup()
        with patch("videl.utils.db.get_connected_chat", return_value=None), patch(
            "videl.app.router.rich_reply", new_callable=AsyncMock
        ) as reply:
            await router.dispatch(client, private_message())
        self.assertEqual(calls, [])
        reply.assert_awaited_once()

    async def test_unlisted_private_command_is_not_proxied(self):
        client, router, calls = await self._setup()
        with patch("videl.utils.db.get_connected_chat") as lookup:
            result = await router.dispatch(client, private_message("/other"))
        self.assertFalse(result)
        lookup.assert_not_called()
        self.assertEqual(calls, [])

    async def test_remote_allowlist_only_contains_registered_commands(self):
        self.assertLessEqual(CONNECTED_COMMANDS, command_router.commands.keys())

    async def test_connect_requires_current_group_admin_and_persists_user_link(self):
        client = SimpleNamespace(
            me=SimpleNamespace(username="testbot"),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status=ChatMemberStatus.ADMINISTRATOR)),
        )
        message = SimpleNamespace(
            chat=SimpleNamespace(id=-100123, title="Safe Group", type="supergroup"),
            from_user=SimpleNamespace(id=42),
        )
        ctx = Context(client, message, Parsed("connect", ""))
        with patch("videl.plugins.connections.connect_user", return_value=True) as save:
            screen = await connect(ctx)
        save.assert_called_once_with(42, -100123)
        self.assertIn("connected to your DM", screen.html)

    async def test_connect_rejects_non_admin(self):
        client = SimpleNamespace(
            me=SimpleNamespace(username="testbot"),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status=ChatMemberStatus.MEMBER)),
        )
        message = SimpleNamespace(
            chat=SimpleNamespace(id=-100123, title="Safe Group", type="supergroup"),
            from_user=SimpleNamespace(id=42),
        )
        ctx = Context(client, message, Parsed("connect", ""))
        with patch("videl.plugins.connections.connect_user") as save:
            with self.assertRaises(CommandError):
                await connect(ctx)
        save.assert_not_called()

    async def test_disconnect_is_per_user(self):
        client = SimpleNamespace()
        ctx = Context(client, private_message("/disconnect"), Parsed("disconnect", ""))
        with patch("videl.plugins.connections.get_connected_chat", return_value=-100123), patch(
            "videl.plugins.connections.disconnect_user", return_value=True
        ) as remove:
            screen = await disconnect(ctx)
        remove.assert_called_once_with(42)
        self.assertIn("Group disconnected", screen.html)
