import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.app.routes import COMMANDS
from videl.app.router import Command, Router, Screen
from videl.utils.stickers import add_to_personal_pack
from videl.utils.bot_commands import command_menu


class AnimationDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_animation_reply_keeps_chat_context_without_global_navigation(self):
        async def handler(_ctx):
            return Screen("<b>Animated preview</b>", animation=b"GIF89a-test")

        router = Router((Command("animated", handler, "Animated preview"),))
        client = SimpleNamespace(
            me=SimpleNamespace(username="VidelBot"),
            send_animation=AsyncMock(),
        )
        message = SimpleNamespace(
            text="/animated", id=7, message_thread_id=22,
            chat=SimpleNamespace(id=-1001, type=SimpleNamespace(value="supergroup")),
            from_user=SimpleNamespace(id=42),
        )
        with patch("videl.utils.db.is_disabled", return_value=False), \
             patch("videl.utils.bot_ui.visual_call", AsyncMock()) as deliver:
            self.assertTrue(await router.dispatch(client, message))
        self.assertIs(deliver.call_args.args[0], client.send_animation)
        options = deliver.call_args.kwargs
        self.assertEqual(options["chat_id"], -1001)
        self.assertEqual(options["reply_to_message_id"], 7)
        self.assertEqual(options["message_thread_id"], 22)
        self.assertEqual(options["animation"].getvalue(), b"GIF89a-test")
        self.assertEqual(options["caption"], "<b>Animated preview</b>")
        self.assertNotIn("reply_markup", options)


class FeatureCommandTests(unittest.TestCase):
    def test_unreliable_fun_commands_are_not_registered_or_advertised(self):
        removed = {"dance", "font", "highfive", "hug", "kiss", "like", "wave"}
        registered = {command.name for command in COMMANDS}
        advertised = {item["command"] for item in command_menu()}
        self.assertTrue(removed.isdisjoint(registered))
        self.assertTrue(removed.isdisjoint(advertised))

    def test_kang_creates_a_personal_pack_with_the_replied_format(self):
        seen = []

        class Response:
            def __init__(self, payload):
                self.payload = payload

            def json(self):
                return self.payload

        def post(url, *, json, timeout):
            method = url.rsplit("/", 1)[-1]
            seen.append((method, json, timeout))
            if method == "getStickerSet":
                return Response({"ok": False, "description": "Bad Request: STICKERSET_INVALID"})
            return Response({"ok": True, "result": True})

        with patch("videl.utils.stickers.requests.post", side_effect=post), \
             patch("videl.utils.stickers.config.BOT_TOKEN", "test-token"), \
             patch("videl.utils.stickers.config.BOT_USERNAME", "Videl0Bot"):
            name, created = add_to_personal_pack(12345, "sticker-file-id", "🐈", "video")

        self.assertTrue(created)
        self.assertEqual(name, "videl0bot_12345_video_by_videl0bot")
        self.assertEqual([row[0] for row in seen], ["getStickerSet", "createNewStickerSet"])
        self.assertEqual(seen[-1][1]["stickers"][0]["sticker"], "sticker-file-id")
        self.assertEqual(seen[-1][1]["sticker_format"], "video")

    def test_kang_adds_to_an_existing_pack(self):
        methods = []

        class Response:
            def __init__(self, method):
                self.method = method

            def json(self):
                return {"ok": True, "result": {"name": "existing"}}

        def post(url, **_kwargs):
            method = url.rsplit("/", 1)[-1]
            methods.append(method)
            return Response(method)

        with patch("videl.utils.stickers.requests.post", side_effect=post), \
             patch("videl.utils.stickers.config.BOT_TOKEN", "test-token"), \
             patch("videl.utils.stickers.config.BOT_USERNAME", "Videl0Bot"):
            name, created = add_to_personal_pack(12345, "file", "🙂", "static")

        self.assertFalse(created)
        self.assertEqual(methods, ["getStickerSet", "addStickerToSet"])
        self.assertEqual(name, "videl0bot_12345_static_by_videl0bot")
