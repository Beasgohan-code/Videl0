"""Premium emoji proxy: id validation, Telegram lookup and bounded caching."""
import unittest
from unittest.mock import Mock, patch

from videl.utils import premium_emoji as emoji


class FakeResponse:
    status_code = 200
    headers = {"Content-Type": "image/webp"}

    def __init__(self, payload=b"RIFFwebp-bytes"):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, size):
        yield self.payload


class PremiumEmojiTests(unittest.TestCase):
    def setUp(self):
        emoji.clear_cache()
        self.api = Mock(side_effect=self.telegram)

    def telegram(self, method, payload):
        if method == "getCustomEmojiStickers":
            return 200, {"ok": True, "result": [{"file_id": "big", "thumbnail": {"file_id": "thumb"}}]}
        if method == "getFile":
            self.assertEqual(payload["file_id"], "thumb")
            return 200, {"ok": True, "result": {"file_path": "documents/file_1.webp"}}
        return 200, {"ok": True, "result": True}

    def test_rejects_non_numeric_ids_without_calling_telegram(self):
        for value in ["", "abc", "1" * 21, "../etc"]:
            with self.assertRaises(emoji.EmojiError) as error:
                emoji.fetch_emoji(self.api, value)
            self.assertEqual(error.exception.status, 400)
        self.api.assert_not_called()

    def test_resolves_and_caches_artwork(self):
        with patch.object(emoji.config, "BOT_TOKEN", "123:token"), patch.object(emoji.requests, "get", return_value=FakeResponse()) as get:
            mime, payload = emoji.fetch_emoji(self.api, "5368324170671202286")
            self.assertEqual(mime, "image/webp")
            self.assertEqual(payload, b"RIFFwebp-bytes")
            self.assertTrue(get.call_args.args[0].endswith("/documents/file_1.webp"))
            emoji.fetch_emoji(self.api, "5368324170671202286")
        self.assertEqual(self.api.call_count, 2, "second call must be served from cache")
        self.assertEqual(get.call_count, 1)

    def test_unknown_emoji_is_not_cached_as_success(self):
        def missing(method, payload):
            return 200, {"ok": False, "description": "Bad Request: custom emoji not found"}

        self.api.side_effect = missing
        with patch.object(emoji.config, "BOT_TOKEN", "123:token"):
            with self.assertRaises(emoji.EmojiError) as error:
                emoji.fetch_emoji(self.api, "1234567890123456789")
        self.assertEqual(error.exception.status, 404)
        self.assertIn("not available", str(error.exception))

    def test_missing_bot_token_is_a_service_error(self):
        with patch.object(emoji.config, "BOT_TOKEN", ""):
            with self.assertRaises(emoji.EmojiError) as error:
                emoji.fetch_emoji(self.api, "5368324170671202286")
        self.assertEqual(error.exception.status, 503)


if __name__ == "__main__":
    unittest.main()
