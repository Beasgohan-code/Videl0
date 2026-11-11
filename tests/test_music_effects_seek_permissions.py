"""Group-admin policy tests for legacy music effects and seek commands."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import Message

from videl.modules import block, effects, seek
from videl.utils import permissions


class MusicMutationPermissionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = Mock(spec=Message)
        self.message.chat = SimpleNamespace(id=-100123, title="Test group", type=ChatType.SUPERGROUP)
        self.message.from_user = SimpleNamespace(id=123)
        self.message.matches = []
        self.message.delete = AsyncMock()

    async def test_every_effect_command_rejects_non_admin_before_read_or_mutation(self):
        handlers = (
            effects.speed_cmd,
            effects.speedreset_cmd,
            effects.bass_cmd,
            effects.bassoff_cmd,
            effects.effecton_cmd,
            effects.effectoff_cmd,
            effects.effects_status_cmd,
        )
        for handler in handlers:
            with self.subTest(handler=handler.__name__):
                with (
                    patch.object(effects, "is_user_authorized", new=AsyncMock(return_value=False)) as authorize,
                    patch.object(effects, "rich_send", new=AsyncMock()) as send,
                    patch.object(effects, "_get", side_effect=AssertionError("denied command read state")),
                    patch.object(effects, "set_speed") as set_speed,
                    patch.object(effects, "set_bass") as set_bass,
                    patch.object(effects, "set_enabled") as set_enabled,
                    patch.object(effects, "apply_effects_now", new=AsyncMock()) as apply,
                    patch.object(effects, "peek_current", side_effect=AssertionError("denied command read playback")),
                ):
                    await handler(None, self.message)
                authorize.assert_awaited_once_with(self.message)
                send.assert_awaited_once()
                set_speed.assert_not_called()
                set_bass.assert_not_called()
                set_enabled.assert_not_called()
                apply.assert_not_awaited()
                self.message.delete.assert_not_awaited()

    async def test_every_seek_command_rejects_non_admin_before_playback_access(self):
        for handler in (seek.seek_cmd, seek.seekback_cmd, seek.seek_usage):
            with self.subTest(handler=handler.__name__):
                with (
                    patch.object(seek, "is_user_authorized", new=AsyncMock(return_value=False)) as authorize,
                    patch.object(seek, "rich_send", new=AsyncMock()) as send,
                    patch.object(seek, "peek_current", side_effect=AssertionError("denied command read playback")),
                    patch.object(seek, "get_current_position", side_effect=AssertionError("denied command read position")),
                    patch.object(seek, "_seek_to", new=AsyncMock()) as seek_to,
                ):
                    await handler(None, self.message)
                authorize.assert_awaited_once_with(self.message)
                send.assert_awaited_once()
                seek_to.assert_not_awaited()
                self.message.delete.assert_not_awaited()

    async def test_effects_and_seek_admin_gate_delegates_to_shared_authorization(self):
        for module in (effects, seek):
            with self.subTest(module=module.__name__), patch.object(
                module, "is_user_authorized", new=AsyncMock(return_value=True)
            ) as authorize, patch.object(module, "rich_send", new=AsyncMock()):
                self.assertTrue(await module._require_group_admin(self.message))
                authorize.assert_awaited_once_with(self.message)

    async def test_read_only_status_and_usage_are_available_after_admin_check(self):
        state = {"speed": 1.0, "bass": 0, "enabled": False}
        with (
            patch.object(effects, "is_user_authorized", new=AsyncMock(return_value=True)),
            patch.object(effects, "_get", return_value=state),
            patch.object(effects, "peek_current", return_value=None),
            patch.object(effects, "rich_send", new=AsyncMock()) as status_send,
        ):
            await effects.effects_status_cmd(None, self.message)
        status_send.assert_awaited_once()

        with (
            patch.object(seek, "is_user_authorized", new=AsyncMock(return_value=True)),
            patch.object(seek, "peek_current", return_value=None),
            patch.object(seek, "rich_send", new=AsyncMock()) as usage_send,
        ):
            await seek.seek_usage(None, self.message)
        usage_send.assert_awaited_once()

    async def test_shared_authorizer_allows_owner_and_group_admin_but_denies_member(self):
        owner_id = 999001
        admin_id = 999002
        member_id = 999003

        owner_message = Mock(spec=Message)
        owner_message.chat = self.message.chat
        owner_message.from_user = SimpleNamespace(id=owner_id)
        owner_message._client = SimpleNamespace(get_chat_member=AsyncMock())
        with patch.object(permissions, "TRUSTED_IDS", {owner_id}):
            self.assertTrue(await permissions.is_user_authorized(owner_message))
        owner_message._client.get_chat_member.assert_not_awaited()

        async def status_for(_chat_id, user_id):
            status = ChatMemberStatus.ADMINISTRATOR if user_id == admin_id else ChatMemberStatus.MEMBER
            return SimpleNamespace(status=status)

        client = SimpleNamespace(get_chat_member=AsyncMock(side_effect=status_for))
        for user_id, expected in ((admin_id, True), (member_id, False)):
            message = Mock(spec=Message)
            message.chat = self.message.chat
            message.from_user = SimpleNamespace(id=user_id)
            message._client = client
            self.assertEqual(await permissions.is_user_authorized(message), expected)

    async def test_existing_blocked_group_and_user_filters_still_reject(self):
        with patch.object(block, "is_group_blocked", return_value=True):
            self.assertFalse(block._group_not_blocked(None, None, self.message))
        with patch.object(block, "is_user_blocked_db", return_value=True):
            self.assertFalse(block._user_not_blocked(None, None, self.message))


if __name__ == "__main__":
    unittest.main()
