import asyncio
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from videl.app.routes import COMMANDS
from videl.plugins import fun
from videl.utils.stickers import add_to_personal_pack
from videl.utils.bot_commands import command_menu


class FeatureCommandTests(TestCase):
    def test_requested_commands_are_in_the_dispatch_registry(self):
        names = {command.name for command in COMMANDS}
        self.assertTrue({"kang", "font", "hug", "kiss"}.issubset(names))
        menu = {item["command"] for item in command_menu()}
        self.assertTrue({"kang", "font", "hug", "kiss"}.issubset(menu))

    def test_font_command_maps_unicode_and_escapes_markup(self):
        context = SimpleNamespace(command=SimpleNamespace(arguments="bold A&B 42"))
        screen = asyncio.run(fun.font(context))
        self.assertIn("𝐀&amp;𝐁", screen.html)
        self.assertIn("𝟒𝟐", screen.html)

    def test_font_command_rejects_unknown_style(self):
        context = SimpleNamespace(command=SimpleNamespace(arguments="comic hello"))
        with self.assertRaises(ValueError):
            asyncio.run(fun.font(context))

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
