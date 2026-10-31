import unittest
from unittest.mock import AsyncMock, patch

from videl.utils import gemini


class GeminiProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_key_disables_provider_without_network(self):
        with patch.object(gemini.config, "GEMINI_API_KEY", ""):
            self.assertFalse(gemini.configured())
            with self.assertRaises(gemini.GeminiUnavailable):
                await gemini.generate_text("hello")

    async def test_whitespace_api_key_is_not_configured(self):
        with patch.object(gemini.config, "GEMINI_API_KEY", "   "):
            self.assertFalse(gemini.configured())
            with self.assertRaises(gemini.GeminiUnavailable):
                await gemini.generate_text("hello")

    async def test_request_is_bounded_and_parses_candidate_text(self):
        response = AsyncMock()
        response.raise_for_status = lambda: None
        response.json = lambda: {"candidates": [{"content": {"parts": [{"text": "Hello back"}]}}]}
        client = AsyncMock()
        client.post.return_value = response
        client_context = AsyncMock()
        client_context.__aenter__.return_value = client
        client_context.__aexit__.return_value = False
        with patch.object(gemini.config, "GEMINI_API_KEY", "test-key"), \
             patch.object(gemini.config, "GEMINI_MODEL", "gemini-2.5-flash"), \
             patch.object(gemini.httpx, "AsyncClient", return_value=client_context):
            result = await gemini.generate_text("x" * 5000, system_instruction="system")
        self.assertEqual(result, "Hello back")
        kwargs = client.post.call_args.kwargs
        self.assertEqual(len(kwargs["json"]["contents"][0]["parts"][0]["text"]), gemini.MAX_PROMPT_CHARS)
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-key")
        self.assertNotIn("test-key", kwargs["url"] if "url" in kwargs else client.post.call_args.args[0])

    async def test_provider_errors_are_sanitized(self):
        client = AsyncMock()
        client.post.side_effect = RuntimeError("provider url leaked secret")
        client_context = AsyncMock()
        client_context.__aenter__.return_value = client
        client_context.__aexit__.return_value = False
        with patch.object(gemini.config, "GEMINI_API_KEY", "a-secret-key"), \
             patch.object(gemini.config, "GEMINI_MODEL", "gemini-2.5-flash"), \
             patch.object(gemini.httpx, "AsyncClient", return_value=client_context):
            with self.assertRaises(gemini.GeminiUnavailable) as caught:
                await gemini.generate_text("hello")
        self.assertNotIn("a-secret-key", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
