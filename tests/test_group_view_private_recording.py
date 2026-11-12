"""Private recording controls fail closed when Telegram supplies no actor."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from pyrogram.enums import ChatType

from videl.app.group_view import private_recording
from videl.app.router import CommandError


class GroupViewPrivateRecordingTests(unittest.IsolatedAsyncioTestCase):
    async def test_anonymous_or_missing_actor_cannot_reach_private_recording_control(self):
        ctx = SimpleNamespace(
            message=SimpleNamespace(chat=SimpleNamespace(id=42, type=ChatType.PRIVATE)),
            user=None,
            command=SimpleNamespace(arguments="off"),
        )
        with self.assertRaisesRegex(CommandError, "private conversation"):
            await private_recording(ctx)
