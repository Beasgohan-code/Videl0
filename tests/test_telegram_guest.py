import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.modules.telegram_features import guest_message


class GuestBotTests(unittest.IsolatedAsyncioTestCase):
    async def test_guest_fallback_is_explicit_that_ai_is_not_configured(self):
        message = SimpleNamespace(guest_query_id="123", text="@videl hello", caption=None)
        with patch("videl.utils.gemini.configured", return_value=False), \
             patch("videl.modules.telegram_features.bot.answer_guest_query", new=AsyncMock()) as answer:
            await guest_message(None, message)
        answer.assert_awaited_once()
        content = answer.call_args.kwargs["result"].input_message_content.message_text
        self.assertIn("AI replies are unavailable", content)
        self.assertIn("only see this mention", content)

    async def test_gemini_response_discloses_external_processing(self):
        message = SimpleNamespace(guest_query_id="456", text="@videl explain queues", caption=None)
        with patch("videl.utils.gemini.configured", return_value=True), \
             patch("videl.utils.gemini.generate_text", new=AsyncMock(return_value="A queue orders tracks.")) as generate, \
             patch("videl.modules.telegram_features.bot.answer_guest_query", new=AsyncMock()) as answer:
            await guest_message(None, message)
        generate.assert_awaited_once()
        self.assertEqual(generate.call_args.args[0], "@videl explain queues")
        content = answer.call_args.kwargs["result"].input_message_content.message_text
        self.assertIn("A queue orders tracks.", content)
        self.assertIn("sent to Google Gemini", content)


if __name__ == "__main__":
    unittest.main()
