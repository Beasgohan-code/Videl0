import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.utils import assistant as assistant_utils


class AssistantReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        assistant_utils.assistant_startup_complete(False)

    async def test_voice_command_waits_for_in_progress_assistant_start(self):
        assistant_utils.assistant_starting()
        get_me = AsyncMock(return_value=SimpleNamespace(id=51))
        get_member = AsyncMock(return_value=SimpleNamespace(status="member"))
        with patch.object(assistant_utils.assistant, "is_connected", True), \
             patch.object(assistant_utils.assistant, "get_me", get_me), \
             patch.object(assistant_utils.assistant, "get_chat_member", get_member):
            check = asyncio.create_task(assistant_utils.is_assistant_in(-1001))
            await asyncio.sleep(0)
            assistant_utils.assistant_startup_complete(True)
            self.assertTrue(await check)
        get_me.assert_awaited_once()
        get_member.assert_awaited_once_with(-1001, 51)

    async def test_unstarted_client_does_not_attempt_membership_rpc(self):
        assistant_utils.assistant_starting()
        assistant_utils.assistant_startup_complete(False)
        with patch.object(assistant_utils.assistant, "get_me", new=AsyncMock()) as get_me:
            self.assertEqual(await assistant_utils.is_assistant_in(-1001), "not_started")
        get_me.assert_not_awaited()
