"""Offline API regression checks. Telegram sends are mocked, never delivered."""
import importlib
import unittest
from unittest.mock import patch


class RichPostApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = importlib.import_module("videl.__main__")
        cls.client = cls.api._flask.test_client()

    def test_formatted_caption_uses_visible_limit_and_html(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(
            self.api, "_bot_api", return_value=(True, {"ok": True, "result": {"message_id": 7, "chat": {"id": -1001}}})
        ) as send:
            caption = "<b>" + "a" * 1024 + "</b>"
            response = self.client.post("/internal/channel-post", headers={"X-Videl-Internal": "offline-test-only"}, json={
                "chat_id": "-1001", "text": caption, "parse_mode": "HTML", "media_url": "https://example.com/cover.png"
            })
            self.assertEqual(response.status_code, 200)
            method, payload = send.call_args.args
            self.assertEqual(method, "sendPhoto")
            self.assertEqual(payload["caption"], caption)
            self.assertEqual(payload["parse_mode"], "HTML")

    def test_oversize_caption_is_not_sent(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(self.api, "_bot_api") as send:
            response = self.client.post("/internal/channel-post", headers={"X-Videl-Internal": "offline-test-only"}, json={
                "chat_id": "-1001", "text": "<b>" + "a" * 1025 + "</b>", "media_url": "https://example.com/cover.png"
            })
            self.assertEqual(response.status_code, 400)
            send.assert_not_called()

    def test_unauthorized_post_is_not_sent(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(self.api, "_bot_api") as send:
            response = self.client.post("/internal/channel-post", json={"chat_id": "-1001", "text": "hello"})
            self.assertEqual(response.status_code, 403)
            send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
