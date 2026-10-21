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

    def test_nested_marks_are_normalized_before_sending(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(
            self.api, "_bot_api", return_value=(True, {"ok": True, "result": {"message_id": 11}})
        ) as send:
            response = self.client.post("/internal/channel-post", headers={"X-Videl-Internal": "offline-test-only"}, json={
                "chat_id": "-1001",
                "text": 'Hwy <u>hu<code>h<tg-spoiler>hhhh</tg-spoiler></code></u> '
                        '<tg-emoji emoji-id="5368324170671202286">\U0001F44D</tg-emoji>',
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(send.call_args.args[1]["text"],
                'Hwy <u>hu</u><code>hhhhh</code> <tg-emoji emoji-id="5368324170671202286">\U0001F44D</tg-emoji>')
            self.assertEqual(send.call_args.args[1]["parse_mode"], "HTML")

    def test_plain_text_post_does_not_send_html_parse_mode(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(
            self.api, "_bot_api", return_value=(True, {"ok": True, "result": {"message_id": 12}})
        ) as send:
            response = self.client.post("/internal/channel-post", headers={"X-Videl-Internal": "offline-test-only"}, json={
                "chat_id": "-1001", "text": "Just words & things",
            })
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("parse_mode", send.call_args.args[1])

    def test_oversize_caption_is_not_sent(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(self.api, "_bot_api") as send:
            response = self.client.post("/internal/channel-post", headers={"X-Videl-Internal": "offline-test-only"}, json={
                "chat_id": "-1001", "text": "<b>" + "a" * 1025 + "</b>", "media_url": "https://example.com/cover.png"
            })
            self.assertEqual(response.status_code, 400)
            send.assert_not_called()

    def test_custom_image_is_forwarded_as_multipart_photo(self):
        from io import BytesIO
        from PIL import Image
        stream = BytesIO()
        Image.new("RGB", (100, 100), "green").save(stream, format="PNG")
        stream.seek(0)
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(
            self.api, "_bot_api", return_value=(True, {"ok": True, "result": {"message_id": 8}})
        ) as send:
            response = self.client.post("/internal/channel-post", headers={"X-Videl-Internal": "offline-test-only"}, data={
                "chat_id": "-1001", "text": "<b>My custom design</b>", "image": (stream, "design.png"), "parse_mode": "HTML"
            }, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(send.call_args.args[0], "sendPhoto")
            self.assertEqual(send.call_args.args[1]["caption"], "<b>My custom design</b>")
            self.assertEqual(send.call_args.kwargs["files"]["photo"][2], "image/png")

    def test_invalid_image_is_not_forwarded(self):
        from io import BytesIO
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(self.api, "_bot_api") as send:
            response = self.client.post("/internal/channel-post", headers={"X-Videl-Internal": "offline-test-only"}, data={
                "chat_id": "-1001", "image": (BytesIO(b"not an image"), "fake.png")
            }, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 400)
            send.assert_not_called()

    def test_unauthorized_post_is_not_sent(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(self.api, "_bot_api") as send:
            response = self.client.post("/internal/channel-post", json={"chat_id": "-1001", "text": "hello"})
            self.assertEqual(response.status_code, 403)
            send.assert_not_called()

    def test_native_styles_copy_and_custom_icons_are_sent(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(self.api, "_bot_api", return_value=(True, {"ok":True,"result":{"message_id":9}})) as send:
            response=self.client.post("/internal/channel-post",headers={"X-Videl-Internal":"offline-test-only"},json={"chat_id":"-1001","text":"Hello","buttons":[[{"text":"Join","url":"https://example.com","style":"success","iconId":"5368324170671202286"},{"text":"Copy","copyText":"HELLO","style":"primary"}]]})
            self.assertEqual(response.status_code,200)
            buttons=send.call_args.args[1]["reply_markup"]["inline_keyboard"][0]
            self.assertEqual(buttons[0]["style"],"success")
            self.assertEqual(buttons[0]["icon_custom_emoji_id"],"5368324170671202286")
            self.assertEqual(buttons[1]["copy_text"],{"text":"HELLO"})
            self.assertNotIn("url",buttons[1])

    def test_invalid_native_button_fields_never_send(self):
        for item in [{"style":"fake","url":"https://example.com"},{"copyText":"😀"*129},{"url":"https://example.com","iconId":"9223372036854775808"}]:
            with self.subTest(item=item), patch.object(self.api.config,"WEBAPP_SECRET","offline-test-only"),patch.object(self.api,"_bot_api") as send:
                response=self.client.post("/internal/channel-post",headers={"X-Videl-Internal":"offline-test-only"},json={"chat_id":"-1001","text":"Hello","buttons":[[{"text":"Test",**item}]]})
                self.assertEqual(response.status_code,400)
                send.assert_not_called()

    def test_schedule_endpoint_never_sends_immediately(self):
        with patch.object(self.api.config,"WEBAPP_SECRET","offline-test-only"),patch("videl.utils.scheduled_posts.enqueue",return_value={"ok":True,"job_id":"test","status":"pending"}) as enqueue,patch.object(self.api,"_bot_api") as send:
            response=self.client.post("/internal/scheduled-posts",headers={"X-Videl-Internal":"offline-test-only"},json={"chat_id":"-1001","text":"Hello","schedule_at":"2026-10-21T12:00:00Z","request_id":"test"})
            self.assertEqual(response.status_code,200)
            enqueue.assert_called_once()
            send.assert_not_called()
            response=self.client.post("/internal/scheduled-posts",headers={"X-Videl-Internal":"offline-test-only"},json={"chat_id":"-1001","text":"Hello"})
            self.assertEqual(response.status_code,400)
            send.assert_not_called()

    def test_schedule_management_is_protected(self):
        for method in ['get','post','delete']:
            with patch.object(self.api.config,"WEBAPP_SECRET","offline-test-only"):
                self.assertEqual(getattr(self.client,method)("/internal/scheduled-posts").status_code,403)


class ScheduledSeriesApiTests(unittest.TestCase):
    """The HTTP surface for timezone-true series and their controls."""

    @classmethod
    def setUpClass(cls):
        cls.api = importlib.import_module("videl.__main__")
        cls.client = cls.api._flask.test_client()

    def test_the_zone_and_wall_clock_are_forwarded_to_the_queue(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch(
            "videl.utils.scheduled_posts.enqueue",
            return_value={"ok": True, "job_id": "test", "status": "pending"},
        ) as enqueue:
            response = self.client.post(
                "/internal/scheduled-posts",
                headers={"X-Videl-Internal": "offline-test-only"},
                json={"chat_id": "-1001", "text": "Hello", "schedule_at": "2026-10-21T12:00:00Z",
                      "request_id": "test", "repeat": "daily", "timezone": "Asia/Kolkata",
                      "wall_time": "09:00"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(enqueue.call_args.args[4], "daily")
            self.assertEqual(enqueue.call_args.args[5], "Asia/Kolkata")
            self.assertEqual(enqueue.call_args.args[6], "09:00")

    def test_an_invalid_zone_is_a_client_error_not_a_silent_utc(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch(
            "videl.utils.scheduled_posts.enqueue", side_effect=ValueError("That timezone is not recognised"),
        ):
            response = self.client.post(
                "/internal/scheduled-posts",
                headers={"X-Videl-Internal": "offline-test-only"},
                json={"chat_id": "-1001", "text": "Hello", "schedule_at": "2026-10-21T12:00:00Z",
                      "request_id": "test", "repeat": "daily", "timezone": "Mars/Olympus"},
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("not recognised", response.get_json()["error"])

    def test_series_actions_are_protected(self):
        response = self.client.post("/internal/scheduled-posts/series", json={"id": "x", "action": "pause"})
        self.assertEqual(response.status_code, 403)

    def test_series_actions_dispatch_to_the_queue(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch(
            "videl.utils.scheduled_posts.set_paused", return_value={"ok": True, "paused": True},
        ) as pause, patch(
            "videl.utils.scheduled_posts.skip_next", return_value={"ok": True, "skipped": 2},
        ) as skip:
            headers = {"X-Videl-Internal": "offline-test-only"}
            paused = self.client.post("/internal/scheduled-posts/series", headers=headers,
                                      json={"id": "job", "action": "pause"})
            skipped = self.client.post("/internal/scheduled-posts/series", headers=headers,
                                       json={"id": "job", "action": "skip"})
            self.assertEqual(paused.status_code, 200)
            self.assertEqual(skipped.status_code, 200)
            pause.assert_called_once_with("job", True)
            skip.assert_called_once_with("job")

    def test_an_unknown_action_and_a_refused_transition_are_explained(self):
        headers = {"X-Videl-Internal": "offline-test-only"}
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"):
            response = self.client.post("/internal/scheduled-posts/series", headers=headers,
                                        json={"id": "job", "action": "explode"})
            self.assertEqual(response.status_code, 400)
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch(
            "videl.utils.scheduled_posts.set_paused", side_effect=ValueError("This series is not waiting in the queue"),
        ):
            response = self.client.post("/internal/scheduled-posts/series", headers=headers,
                                        json={"id": "job", "action": "resume"})
            self.assertEqual(response.status_code, 409)
            self.assertIn("not waiting", response.get_json()["error"])

    def test_a_series_action_without_an_id_is_refused(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"):
            response = self.client.post("/internal/scheduled-posts/series",
                                        headers={"X-Videl-Internal": "offline-test-only"},
                                        json={"action": "pause"})
            self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
