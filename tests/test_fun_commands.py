import asyncio
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from videl.app.routes import COMMANDS
from videl.app.router import Command, Router, Screen
from videl.plugins import fun
from videl.utils.stickers import add_to_personal_pack
from videl.utils.bot_commands import command_menu


class AnimationDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_animation_reply_keeps_chat_thread_and_reply_context(self):
        async def handler(_ctx):
            return Screen("<b>Animated hello</b>", animation=b"GIF89a-test")

        router = Router((Command("wave", handler, "Animated hello"),))
        client = SimpleNamespace(
            me=SimpleNamespace(username="VidelBot"),
            send_animation=AsyncMock(),
        )
        message = SimpleNamespace(
            text="/wave", id=7, message_thread_id=22,
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
        self.assertEqual(options["caption"], "<b>Animated hello</b>")
        callbacks = {button.callback_data for row in options["reply_markup"].inline_keyboard for button in row}
        self.assertTrue({"help:home", "cmds:all:0"}.issubset(callbacks))


class FeatureCommandTests(TestCase):
    def test_requested_commands_are_in_the_dispatch_registry(self):
        names = {command.name for command in COMMANDS}
        self.assertTrue({"kang", "font", "hug", "kiss", "like", "wave", "highfive", "dance"}.issubset(names))
        menu = {item["command"] for item in command_menu()}
        self.assertTrue({"kang", "font", "hug", "kiss", "like", "wave", "highfive", "dance"}.issubset(menu))

    def test_font_command_maps_unicode_and_escapes_markup(self):
        context = SimpleNamespace(command=SimpleNamespace(arguments="bold A&B 42"))
        screen = asyncio.run(fun.font(context))
        self.assertIn("𝐀&amp;𝐁", screen.html)
        self.assertIn("𝟒𝟐", screen.html)

    def test_font_command_rejects_unknown_style(self):
        context = SimpleNamespace(command=SimpleNamespace(arguments="comic hello"))
        with self.assertRaises(ValueError):
            asyncio.run(fun.font(context))

    def test_hug_falls_back_to_the_local_animation_with_a_friendly_caption(self):
        context = SimpleNamespace(
            command=SimpleNamespace(arguments=""),
            message=SimpleNamespace(reply_to_message=None),
            user=SimpleNamespace(id=42, first_name="Listener"),
        )
        with patch("videl.utils.fun_animation.fetch_reaction", new=AsyncMock(return_value=None)), \
             patch("videl.utils.fun_animation.render", return_value=b"GIF89a-test"):
            screen = asyncio.run(fun.hug(context))
        self.assertEqual(screen.animation, b"GIF89a-test")
        self.assertIn("friendly hug", screen.html)
        self.assertIn("<b>", screen.html)
        self.assertIn("Videl original animation", screen.html)

    def test_like_caption_credits_api_art_safely(self):
        from videl.utils.fun_animation import ReactionAsset
        context = SimpleNamespace(
            command=SimpleNamespace(arguments=""),
            message=SimpleNamespace(reply_to_message=None),
            user=SimpleNamespace(id=42, first_name="Listener"),
        )
        fetch = AsyncMock(return_value=ReactionAsset(
            b"GIF89a-test", "Series", "Artist & <Name>",
            "https://artist.example/profile", "https://artist.example/artwork",
        ))
        with patch("videl.utils.fun_animation.fetch_reaction", fetch):
            screen = asyncio.run(fun.like(context))
        self.assertEqual(screen.animation, b"GIF89a-test")
        self.assertIn("Artist &amp; &lt;Name&gt;", screen.html)
        self.assertIn("https://artist.example/artwork", screen.html)
        self.assertIn("Nekos.best GIF", screen.html)
        fetch.assert_awaited_once_with("like")

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
