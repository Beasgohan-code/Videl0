import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pytgcalls.exceptions import NoActiveGroupCall
from pyrogram.enums import ChatMemberStatus
from videl.core import voice_chat, playback_state


class VoiceChatRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_call_once_using_assistant_peer(self):
        assistant = SimpleNamespace(
            get_chat=AsyncMock(return_value=SimpleNamespace(id=-100123)),
            resolve_peer=AsyncMock(return_value="peer"),
            invoke=AsyncMock(),
        )
        with patch.object(voice_chat, "assistant", assistant), patch.object(voice_chat.asyncio, "sleep", new=AsyncMock()):
            self.assertTrue(await voice_chat.ensure_active_voice_chat(-100123))
        assistant.get_chat.assert_awaited_once_with(-100123)
        assistant.resolve_peer.assert_awaited_once_with(-100123)
        request = assistant.invoke.await_args.args[0]
        self.assertEqual(request.peer, "peer")
        self.assertGreater(request.random_id, 0)

    async def test_bot_can_start_call_if_it_already_has_manage_video_chats(self):
        assistant = SimpleNamespace(
            get_chat=AsyncMock(side_effect=RuntimeError("CHAT_ADMIN_REQUIRED")),
            resolve_peer=AsyncMock(),
            invoke=AsyncMock(),
        )
        privileges = SimpleNamespace(can_manage_video_chats=True)
        bot = SimpleNamespace(
            me=SimpleNamespace(id=99),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(
                status=ChatMemberStatus.ADMINISTRATOR, privileges=privileges,
            )),
            get_chat=AsyncMock(return_value=SimpleNamespace(id=-100123)),
            resolve_peer=AsyncMock(return_value="bot-peer"),
            invoke=AsyncMock(),
        )
        with patch.object(voice_chat, "assistant", assistant), patch.object(voice_chat, "bot", bot), patch.object(
            voice_chat.asyncio, "sleep", new=AsyncMock()
        ):
            self.assertTrue(await voice_chat.ensure_active_voice_chat(-100123))
        bot.invoke.assert_awaited_once()

    async def test_existing_call_is_treated_as_success(self):
        assistant = SimpleNamespace(
            get_chat=AsyncMock(side_effect=RuntimeError("GROUPCALL_ALREADY_STARTED")),
            resolve_peer=AsyncMock(),
            invoke=AsyncMock(),
        )
        with patch.object(voice_chat, "assistant", assistant):
            self.assertTrue(await voice_chat.ensure_active_voice_chat(-100123))
        assistant.resolve_peer.assert_not_awaited()

    async def test_permission_failure_is_reported_as_safe_failure(self):
        assistant = SimpleNamespace(
            get_chat=AsyncMock(side_effect=RuntimeError("CHAT_ADMIN_REQUIRED")),
            resolve_peer=AsyncMock(),
            invoke=AsyncMock(),
        )
        bot = SimpleNamespace(
            me=SimpleNamespace(id=99),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member", privileges=None)),
        )
        with patch.object(voice_chat, "assistant", assistant), patch.object(voice_chat, "bot", bot):
            self.assertFalse(await voice_chat.ensure_active_voice_chat(-100123))

    def test_only_known_missing_call_errors_are_retryable(self):
        self.assertTrue(voice_chat.is_missing_voice_chat(NoActiveGroupCall()))
        self.assertTrue(voice_chat.is_missing_voice_chat(RuntimeError("GROUPCALL_NOT_FOUND")))
        self.assertFalse(voice_chat.is_missing_voice_chat(RuntimeError("ClientNotStarted")))
        self.assertFalse(voice_chat.is_missing_voice_chat(RuntimeError("CHAT_ADMIN_REQUIRED")))

    async def test_no_active_call_creates_call_then_retries_play_once(self):
        player = SimpleNamespace(play=AsyncMock(side_effect=[NoActiveGroupCall(), "playing"]))
        with patch.object(voice_chat, "ensure_active_voice_chat", new=AsyncMock(return_value=True)) as ensure:
            result = await voice_chat.play_with_auto_start(player, -100123, "stream")
        self.assertEqual(result, "playing")
        ensure.assert_awaited_once_with(-100123)
        self.assertEqual(player.play.await_count, 2)

    async def test_client_not_started_is_not_misdiagnosed_as_missing_call(self):
        player = SimpleNamespace(play=AsyncMock(side_effect=RuntimeError("ClientNotStarted")))
        with patch.object(voice_chat, "ensure_active_voice_chat", new=AsyncMock()) as ensure:
            with self.assertRaisesRegex(RuntimeError, "ClientNotStarted"):
                await voice_chat.play_with_auto_start(player, -100123, "stream")
        ensure.assert_not_awaited()

    async def test_no_admin_rights_gives_actionable_voice_chat_failure(self):
        player = SimpleNamespace(play=AsyncMock(side_effect=NoActiveGroupCall()))
        with patch.object(voice_chat, "ensure_active_voice_chat", new=AsyncMock(return_value=False)):
            with self.assertRaisesRegex(voice_chat.VoiceChatStartError, "change permissions automatically"):
                await voice_chat.play_with_auto_start(player, -100123, "stream")
        self.assertEqual(player.play.await_count, 1)

    def test_expected_local_leave_update_is_consumed_once(self):
        playback_state.expect_voice_exit(-100123)
        self.assertTrue(playback_state.consume_expected_voice_exit(-100123))
        self.assertFalse(playback_state.consume_expected_voice_exit(-100123))
