import re
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import config
from videl.app.router import CommandError
from videl.plugins import business_profile as profile


class BusinessProfileTests(unittest.IsolatedAsyncioTestCase):
    CONNECTION_ID = "Business_Conn-0123456789"

    def setUp(self):
        profile._PENDING.clear()
        profile._APPLY_TIMES.clear()
        profile._CONNECTIONS.clear()
        self.owner = int(config.OWNER_ID)
        self.connection = SimpleNamespace(
            id=self.CONNECTION_ID, is_enabled=True,
            user=SimpleNamespace(id=self.owner),
            rights=SimpleNamespace(can_edit_name=True, can_edit_bio=True, can_edit_username=True),
        )
        profile.remember_business_connection(self.connection)
        self.reference = next(iter(profile._CONNECTIONS))

    def ctx(self, arguments, actor=None):
        return SimpleNamespace(
            user=SimpleNamespace(id=self.owner if actor is None else actor),
            command=SimpleNamespace(arguments=arguments),
        )

    async def test_connection_registry_is_owner_scoped_and_revocation_removes_reference(self):
        outsider = SimpleNamespace(id="outsider_connection", is_enabled=True,
                                  user=SimpleNamespace(id=self.owner + 1))
        profile.remember_business_connection(outsider)
        self.assertEqual(list(profile._CONNECTIONS), [self.reference])
        revoked = SimpleNamespace(id=self.CONNECTION_ID, is_enabled=False,
                                  user=SimpleNamespace(id=self.owner))
        profile.remember_business_connection(revoked)
        self.assertNotIn(self.reference, profile._CONNECTIONS)
        with self.assertRaises(CommandError):
            profile._resolve_connection(self.reference)

    async def test_aiogram_pinned_bot_api_has_the_required_profile_methods(self):
        from aiogram import Bot

        self.assertTrue(profile._aiogram_methods_available())
        for name in ("get_business_connection", "set_business_account_name",
                     "set_business_account_bio", "set_business_account_username"):
            self.assertTrue(callable(getattr(Bot, name, None)))

    async def test_aiogram_adapter_closes_its_api_session_and_uses_only_the_configured_token(self):
        class Session:
            def __init__(self): self.closed = False
            async def close(self): self.closed = True

        class FakeBot:
            instance = None
            def __init__(self, token):
                self.token = token
                self.session = Session()
                FakeBot.instance = self
            async def get_business_connection(self, **kwargs):
                return self.connection
            async def set_business_account_name(self, **kwargs): return True
            async def set_business_account_bio(self, **kwargs): return True
            async def set_business_account_username(self, **kwargs): return True

        FakeBot.connection = self.connection
        with patch("aiogram.Bot", FakeBot), patch.object(config, "BOT_TOKEN", "test-configured-token"):
            result = await profile._bot_api("get_business_connection", business_connection_id=self.CONNECTION_ID)
        self.assertIs(result, self.connection)
        self.assertEqual(FakeBot.instance.token, "test-configured-token")
        self.assertTrue(FakeBot.instance.session.closed)

    async def test_preview_does_not_mutate_and_confirm_rechecks_connection_and_applies_once(self):
        with patch.object(profile, "_bot_api", new=AsyncMock(side_effect=[self.connection, self.connection, True])) as call:
            preview = await profile.business_profile(self.ctx(f"preview {self.reference} name Ada Lovelace"))
            self.assertIn("Ada Lovelace", preview.html)
            self.assertNotIn(self.CONNECTION_ID, preview.html)
            self.assertEqual(call.await_count, 1)
            nonce = re.search(r"/businessprofile confirm ([A-Za-z0-9_-]+)", preview.html).group(1)
            result = await profile.business_profile(self.ctx(f"confirm {nonce}"))
        self.assertIn("Telegram confirmed", result.html)
        self.assertEqual(call.await_count, 3)
        self.assertEqual(call.await_args.args[0], "set_business_account_name")
        self.assertEqual(call.await_args.kwargs, {
            "business_connection_id": self.CONNECTION_ID,
            "first_name": "Ada",
            "last_name": "Lovelace",
        })
        self.assertFalse(profile._PENDING)

    async def test_disabled_or_wrong_owner_connection_is_refused_without_edit(self):
        wrong_owner = SimpleNamespace(is_enabled=True, user=SimpleNamespace(id=123), rights=self.connection.rights)
        with patch.object(profile, "_bot_api", new=AsyncMock(return_value=wrong_owner)) as call:
            with self.assertRaises(CommandError):
                await profile.business_profile(self.ctx(f"preview {self.reference} bio Hello"))
        self.assertEqual(call.await_count, 1)
        with patch.object(profile, "_bot_api", new=AsyncMock()) as call:
            with self.assertRaises(CommandError):
                await profile.business_profile(self.ctx(f"preview {self.reference} bio Hello", actor=123))
        call.assert_not_awaited()

    async def test_rights_are_checked_again_at_confirmation(self):
        revoked = SimpleNamespace(is_enabled=True, user=SimpleNamespace(id=self.owner),
                                  rights=SimpleNamespace(can_edit_bio=False))
        with patch.object(profile, "_bot_api", new=AsyncMock(side_effect=[self.connection, revoked])) as call:
            preview = await profile.business_profile(self.ctx(f"preview {self.reference} bio New bio"))
            nonce = re.search(r"/businessprofile confirm ([A-Za-z0-9_-]+)", preview.html).group(1)
            with self.assertRaises(CommandError) as caught:
                await profile.business_profile(self.ctx(f"confirm {nonce}"))
        self.assertIn("Nothing changed", str(caught.exception))
        self.assertEqual(call.await_count, 2)
        self.assertEqual(call.await_args.args[0], "get_business_connection")
        self.assertFalse(profile._PENDING)

    async def test_preview_is_single_use_expires_and_enforces_field_validation(self):
        with self.assertRaises(CommandError):
            profile._profile_value("username", "bad user")
        with self.assertRaises(CommandError):
            profile._profile_value("bio", "x" * 141)
        with patch.object(profile, "_bot_api", new=AsyncMock(return_value=self.connection)):
            preview = await profile.business_profile(self.ctx(f"preview {self.reference} username example_bot"))
        nonce = re.search(r"/businessprofile confirm ([A-Za-z0-9_-]+)", preview.html).group(1)
        profile._PENDING[nonce]["created"] -= profile._PENDING_TTL + 1
        with patch.object(profile, "_bot_api", new=AsyncMock()) as call:
            with self.assertRaises(CommandError):
                await profile.business_profile(self.ctx(f"confirm {nonce}"))
        call.assert_not_awaited()

    async def test_edits_are_rate_limited_per_connection(self):
        now = 10000.0
        for index in range(5):
            self.assertTrue(profile._rate_limit(self.CONNECTION_ID, now + 61 * index))
        self.assertFalse(profile._rate_limit(self.CONNECTION_ID, now + 61 * 4 + 1))


if __name__ == "__main__":
    unittest.main()
