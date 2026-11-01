import json
import unittest
from unittest.mock import patch

import httpx

from videl.utils import gemini


def sse(*parts):
    return "\n".join("data: " + json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]}) + "\n" for text in parts)


class GeminiStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_uses_sse_endpoint_and_yields_bounded_deltas(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, content=sse("Hello ", "from ", "Gemini"), request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(gemini.config, "GEMINI_API_KEY", "test-key"), \
             patch.object(gemini.config, "GEMINI_MODEL", "gemini-2.5-flash"), \
             patch.object(gemini.httpx, "AsyncClient", return_value=client):
            chunks = [chunk async for chunk in gemini.generate_text_stream("question", system_instruction="rules")]
        self.assertEqual(chunks, ["Hello ", "from ", "Gemini"])
        self.assertEqual(len(requests), 1)
        self.assertTrue(requests[0].url.path.endswith(":streamGenerateContent"))
        self.assertEqual(requests[0].url.params["alt"], "sse")
        self.assertEqual(requests[0].headers["x-goog-api-key"], "test-key")
        self.assertTrue(client.is_closed)

    async def test_output_is_capped_and_empty_or_malformed_stream_is_refused(self):
        payload = sse("x" * (gemini.MAX_OUTPUT_CHARS + 100))
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=payload, request=request)))
        with patch.object(gemini.config, "GEMINI_API_KEY", "test-key"), \
             patch.object(gemini.httpx, "AsyncClient", return_value=client):
            chunks = [chunk async for chunk in gemini.generate_text_stream("question")]
        self.assertEqual(sum(map(len, chunks)), gemini.MAX_OUTPUT_CHARS)

        empty = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"not an event", request=request)))
        with patch.object(gemini.config, "GEMINI_API_KEY", "test-key"), \
             patch.object(gemini.httpx, "AsyncClient", return_value=empty):
            with self.assertRaises(gemini.GeminiUnavailable):
                _ = [chunk async for chunk in gemini.generate_text_stream("question")]

    async def test_cancelling_consumer_closes_the_underlying_request(self):
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=sse("first", "second"), request=request)))
        with patch.object(gemini.config, "GEMINI_API_KEY", "test-key"), \
             patch.object(gemini.httpx, "AsyncClient", return_value=client):
            stream = gemini.generate_text_stream("question")
            self.assertEqual(await stream.__anext__(), "first")
            await stream.aclose()
        self.assertTrue(client.is_closed)


if __name__ == "__main__":
    unittest.main()
