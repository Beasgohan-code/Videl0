"""Profile lookup never presents an API failure as confirmed non-membership."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pyrogram.enums import ChatType
from pyrogram.errors import UserNotParticipant

from videl.plugins import tools


class ToolProfileTests(unittest.IsolatedAsyncioTestCase):
    def context(self, *, group=True, member_error=None, member_status="member"):
        user = SimpleNamespace(id=99, first_name="Ari", last_name=None,
                               username="ari", is_bot=False)
        message = SimpleNamespace(
            chat=SimpleNamespace(id=-10088 if group else 42,
                                 type=ChatType.SUPERGROUP if group else ChatType.PRIVATE),
            from_user=SimpleNamespace(id=42),
            reply_to_message=None,
        )
        client = SimpleNamespace(
            get_chat_member=AsyncMock(side_effect=member_error) if member_error else
                            AsyncMock(return_value=SimpleNamespace(status=member_status))
        )
        ctx = SimpleNamespace(
            client=client, message=message,
            command=SimpleNamespace(arguments=""),
        )
        return ctx, user

    async def test_membership_api_failure_is_not_reported_as_nonmembership(self):
        ctx, user = self.context(member_error=RuntimeError("Telegram unavailable"))
        with patch.object(tools.base, "resolve_target", new=AsyncMock(return_value=(user, None))):
            screen = await tools.whois(ctx)
        self.assertIn("could not be verified", screen.html.casefold())
        self.assertNotIn("not a member", screen.html.casefold())

    async def test_telegram_nonparticipant_error_is_still_reported_as_not_a_member(self):
        ctx, user = self.context(member_error=UserNotParticipant("not a participant"))
        with patch.object(tools.base, "resolve_target", new=AsyncMock(return_value=(user, None))):
            screen = await tools.whois(ctx)
        self.assertIn("not a member", screen.html.casefold())
        self.assertNotIn("could not be verified", screen.html.casefold())

    async def test_confirmed_membership_status_is_still_shown(self):
        ctx, user = self.context(member_status="administrator")
        with patch.object(tools.base, "resolve_target", new=AsyncMock(return_value=(user, None))):
            screen = await tools.whois(ctx)
        self.assertIn("administrator", screen.html.casefold())
        ctx.client.get_chat_member.assert_awaited_once_with(-10088, 99)

    async def test_private_profile_does_not_make_group_membership_request(self):
        ctx, user = self.context(group=False)
        with patch.object(tools.base, "resolve_target", new=AsyncMock(return_value=(user, None))):
            screen = await tools.whois(ctx)
        self.assertNotIn("Membership", screen.html)
        ctx.client.get_chat_member.assert_not_awaited()
