"""Broadcast button validation and delivery request tests; Telegram is mocked."""
import importlib
import unittest
from unittest.mock import patch


class Cursor(list):
    def limit(self, _count):
        return self


class Collection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, *_args, **_kwargs):
        return Cursor(self.docs)


class Database(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


class BroadcastApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = importlib.import_module("videl.__main__")
        cls.client = cls.api._flask.test_client()

    def test_https_buttons_are_attached_to_broadcast_and_delivery_is_counted(self):
        db = Database({"served_chats": Collection([{"_id": -1001}]), "served_users": Collection([])})
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch(
            "videl.utils.db.get_db", return_value=db
        ), patch.object(self.api, "_bot_api", return_value=(200, {"ok": True})) as send:
            response = self.client.post(
                "/internal/broadcast",
                headers={"X-Videl-Internal": "offline-test-only"},
                json={"text": "Hello", "scope": "chats", "buttons": [{"text": "Read more", "url": "https://example.com/news"}]},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True, "sent": 1, "failed": 0, "total": 1})
        self.assertEqual(send.call_args.args[1]["reply_markup"], {"inline_keyboard": [[{"text": "Read more", "url": "https://example.com/news"}]]})

    def test_uploaded_image_is_sent_as_a_photo_with_caption_and_buttons(self):
        from io import BytesIO
        from PIL import Image
        stream = BytesIO()
        Image.new("RGB", (20, 20), "blue").save(stream, format="PNG")
        stream.seek(0)
        db = Database({"served_chats": Collection([{"_id": -1001}]), "served_users": Collection([])})
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch(
            "videl.utils.db.get_db", return_value=db
        ), patch.object(self.api, "_bot_api", return_value=(200, {"ok": True})) as send:
            response = self.client.post(
                "/internal/broadcast",
                headers={"X-Videl-Internal": "offline-test-only"},
                data={"text": "Caption", "scope": "chats", "buttons": '[{"text":"Read more","url":"https://example.com"}]', "image": (stream, "cover.png")},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 200)
        method, payload = send.call_args.args
        self.assertEqual(method, "sendPhoto")
        self.assertEqual(payload["caption"], "Caption")
        self.assertEqual(payload["reply_markup"]["inline_keyboard"][0][0]["text"], "Read more")
        self.assertEqual(send.call_args.kwargs["files"]["photo"][2], "image/png")

    def test_image_album_is_sent_with_the_caption_on_the_first_item(self):
        from io import BytesIO
        from PIL import Image
        images = []
        for color in ("red", "green"):
            stream = BytesIO()
            Image.new("RGB", (16, 16), color).save(stream, format="PNG")
            stream.seek(0)
            images.append((stream, f"{color}.png"))
        db = Database({"served_chats": Collection([{"_id": -1001}]), "served_users": Collection([])})
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch(
            "videl.utils.db.get_db", return_value=db
        ), patch.object(self.api, "_bot_api", return_value=(200, {"ok": True, "result": [{}, {}]})) as send:
            data = {"text": "Album caption", "scope": "chats", "images": images}
            response = self.client.post("/internal/broadcast", headers={"X-Videl-Internal": "offline-test-only"}, data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        method, payload = send.call_args.args
        self.assertEqual(method, "sendMediaGroup")
        self.assertEqual(payload["media"][0]["caption"], "Album caption")
        self.assertNotIn("caption", payload["media"][1])
        self.assertEqual(set(send.call_args.kwargs["files"]), {"photo0", "photo1"})

    def test_album_with_inline_buttons_is_rejected_before_delivery(self):
        from io import BytesIO
        from PIL import Image
        streams = []
        for color in ("red", "green"):
            stream = BytesIO()
            Image.new("RGB", (16, 16), color).save(stream, format="PNG")
            stream.seek(0)
            streams.append((stream, f"{color}.png"))
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(self.api, "_bot_api") as send:
            response = self.client.post("/internal/broadcast", headers={"X-Videl-Internal": "offline-test-only"}, data={"text": "Album", "buttons": '[{"text":"Link","url":"https://example.com"}]', "images": streams}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        send.assert_not_called()

    def test_unsafe_or_oversized_buttons_are_rejected_before_any_delivery(self):
        for button in (
            {"text": "bad", "url": "javascript:alert(1)"},
            {"text": "bad", "url": "https://user:pass@example.com"},
            {"text": "x" * 65, "url": "https://example.com"},
        ):
            with self.subTest(button=button), patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(self.api, "_bot_api") as send:
                response = self.client.post(
                    "/internal/broadcast",
                    headers={"X-Videl-Internal": "offline-test-only"},
                    json={"text": "Hello", "scope": "chats", "buttons": [button]},
                )
            self.assertEqual(response.status_code, 400)
            send.assert_not_called()
