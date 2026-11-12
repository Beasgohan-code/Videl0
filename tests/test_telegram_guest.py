import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.modules.telegram_features import guest_message


class GuestBotTests(unittest.IsolatedAsyncioTestCase):
    async def test_guest_reply_is_non_ai_and_limits_its_claimed_context(self):
        message = SimpleNamespace(guest_query_id="123", text="@videl hello", caption=None)
        with patch("videl.modules.telegram_features.bot.answer_guest_query", new=AsyncMock()) as answer:
            await guest_message(None, message)
        answer.assert_awaited_once()
        result = answer.call_args.kwargs["result"]
        content = result.input_message_content.message_text
        self.assertIn("only see this mention", content)
        self.assertIn("group-management bot", content)
        self.assertNotIn("Gemini", content)
        self.assertNotIn("AI", content)
        self.assertNotIn("AI", result.description)

    async def test_missing_guest_query_id_has_no_side_effect(self):
        message = SimpleNamespace(guest_query_id=None, text="@videl hello", caption=None)
        with patch("videl.modules.telegram_features.bot.answer_guest_query", new=AsyncMock()) as answer:
            await guest_message(None, message)
        answer.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
