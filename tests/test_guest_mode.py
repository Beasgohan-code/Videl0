import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from videl.plugins import guest_mode


class GuestModeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        guest_mode._TIMES.clear()
        guest_mode._SEEN.clear()

    async def test_guest_reply_is_static_and_never_repeats_or_exposes_query_text(self):
        client = SimpleNamespace(answer_guest_query=AsyncMock(return_value=True))
        message = SimpleNamespace(guest_query_id="guest-query-123", text="private phone 555-0101 secret question")
        self.assertTrue(await guest_mode.handle_guest_message(client, message))
        client.answer_guest_query.assert_awaited_once()
        query_id, result = client.answer_guest_query.await_args.args
        self.assertEqual(query_id, "guest-query-123")
        self.assertNotIn("private phone", result.input_message_content.message_text)
        self.assertNotIn("555-0101", result.input_message_content.message_text)
        self.assertIn("do not access group settings", result.input_message_content.message_text)
        self.assertFalse(await guest_mode.handle_guest_message(client, message))
        client.answer_guest_query.assert_awaited_once()

    async def test_global_guest_rate_limit_bounds_work_without_identity_tracking(self):
        now = 1000.0
        for i in range(guest_mode._MAX_PER_WINDOW):
            self.assertTrue(guest_mode._allowed(f"q{i}", now))
        self.assertFalse(guest_mode._allowed("over-limit", now))
        self.assertFalse(any("user_id" in key for key in guest_mode._SEEN))
        self.assertTrue(guest_mode._allowed("later", now + guest_mode._WINDOW_SECONDS))

    async def test_invalid_guest_query_is_ignored(self):
        client = SimpleNamespace(answer_guest_query=AsyncMock())
        self.assertFalse(await guest_mode.handle_guest_message(client, SimpleNamespace(guest_query_id="")))
        client.answer_guest_query.assert_not_awaited()

    async def test_installation_adds_guest_handler_only_when_the_client_probes_support(self):
        from videl.app.install import install

        class Client:
            def __init__(self, supports_guest, supports_business=False):
                self.handlers = []
                self.on_guest_message = (lambda: None) if supports_guest else None
                self.on_business_connection = (lambda: None) if supports_business else None
                self.get_business_connection = (lambda *args, **kwargs: None) if supports_business else None
            def add_handler(self, handler, group=0): self.handlers.append(handler)
            def remove_handler(self, handler, group=0): self.handlers.remove(handler)
            async def answer_guest_query(self, *args, **kwargs): pass

        legacy = Client(False)
        guest_only = Client(True)
        current = Client(True, supports_business=True)
        install(legacy)
        install(guest_only)
        install(current)
        self.assertEqual(len(legacy.handlers), 2)
        self.assertEqual(len(guest_only.handlers), 3)
        self.assertEqual(type(guest_only.handlers[-1]).__name__, "GuestMessageHandler")
        self.assertEqual(len(current.handlers), 4)
        self.assertEqual(type(current.handlers[-1]).__name__, "BusinessConnectionHandler")


if __name__ == "__main__":
    unittest.main()
