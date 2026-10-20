"""Offline checks: Telegram/network requests and command effects are mocked."""

import asyncio
import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import requests
from pyrogram.errors import BadRequest
from pyrogram.enums import ButtonStyle
from videl.utils.poll_options import build_poll
from videl.utils.bot_ui import button, plain_keyboard, visual_call
from pyrogram.types import InlineKeyboardMarkup
from videl.utils import bot_api as transport

# Import handlers without scheduling Pyrogram dispatcher tasks on test event loops.
from videl import bot as test_bot

with patch.object(test_bot, "add_handler"):
    api_tools_module = importlib.import_module("videl.modules.api_tools")
    management_module = importlib.import_module("videl.modules.management_core")
    start_module = importlib.import_module("videl.modules.start")


class PollTests(unittest.TestCase):
    def test_poll_flags_and_plain_text_options(self):
        result = build_poll(
            "--multiple --public --shuffle --add-options --hide-results Pick <one> | A | B"
        )
        self.assertEqual(result["options"], [{"text": "A"}, {"text": "B"}])
        self.assertTrue(result["allows_multiple_answers"])
        self.assertFalse(result["is_anonymous"])
        self.assertTrue(result["shuffle_options"])
        self.assertTrue(result["hide_results_until_closes"])
        self.assertTrue(result["allow_adding_options"])
        self.assertEqual(result["question"], "Pick <one>")

    def test_quiz_has_valid_zero_based_correct_answers(self):
        result = build_poll("Which? | *One | Two | *Three", quiz=True)
        self.assertEqual(result["correct_option_ids"], [0, 2])
        self.assertTrue(result["allows_multiple_answers"])
        self.assertFalse(result["allows_revoting"])
        self.assertTrue(result["is_anonymous"])

    def test_invalid_polls_never_reach_telegram(self):
        for text, quiz in [
            ("Q | One", False),
            ("Q | A | a", False),
            ("--paid Q | A | B", False),
            ("Q | A | B", True),
            ("--add-options Q | *A | B", True),
            ("Q | " + "a" * 101 + " | B", False),
            ("😀" * 151 + " | A | B", False),
        ]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    build_poll(text, quiz=quiz)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.token = patch.object(
            transport.config, "BOT_TOKEN", "offline-secret-never-log"
        )
        self.token.start()
        self.addCleanup(self.token.stop)

    def test_rejected_visuals_fall_back_without_changing_delivery(self):
        original = {
            "chat_id": -1001,
            "message_thread_id": 22,
            "protect_content": True,
            "text": '<tg-emoji emoji-id="123">🎵</tg-emoji> Hello',
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {
                            "text": "Open",
                            "url": "https://example.com",
                            "style": "primary",
                            "icon_custom_emoji_id": "123",
                        }
                    ]
                ]
            },
        }
        rejected = Mock(status_code=400)
        rejected.json.return_value = {
            "ok": False,
            "description": "CUSTOM_EMOJI_INVALID",
        }
        accepted = Mock(status_code=200)
        accepted.json.return_value = {"ok": True, "result": {"message_id": 9}}
        with patch.object(
            transport.requests, "post", side_effect=[rejected, accepted]
        ) as send:
            status, data = transport.call_bot_api("sendMessage", original)
        self.assertEqual(status, 200)
        fallback = send.call_args_list[1].kwargs["json"]
        self.assertEqual(fallback["message_thread_id"], 22)
        self.assertTrue(fallback["protect_content"])
        self.assertEqual(fallback["text"], "🎵 Hello")
        self.assertEqual(
            fallback["reply_markup"]["inline_keyboard"][0][0],
            {"text": "Open", "url": "https://example.com"},
        )
        self.assertIn(
            "icon_custom_emoji_id", original["reply_markup"]["inline_keyboard"][0][0]
        )

    def test_timeouts_are_not_retried_and_token_is_not_logged(self):
        with patch.object(
            transport.requests,
            "post",
            side_effect=requests.Timeout(
                "https://api.telegram.org/botoffline-secret-never-log/sendMessage"
            ),
        ) as send:
            with self.assertLogs(transport.log, level="WARNING") as logs:
                status, data = transport.call_bot_api(
                    "sendMessage", {"chat_id": 1, "text": "Hello"}
                )
        send.assert_called_once()
        self.assertIsNone(status)
        self.assertNotIn("offline-secret-never-log", " ".join(logs.output))
        self.assertNotIn("offline-secret-never-log", data["description"])

    def test_rate_limit_is_not_automatically_retried(self):
        response = Mock(status_code=429)
        response.json.return_value = {"ok": False, "parameters": {"retry_after": 20}}
        with patch.object(transport.requests, "post", return_value=response) as send:
            status, result = transport.call_bot_api(
                "sendMessage", {"chat_id": 1, "text": "Hi"}
            )
        send.assert_called_once()
        self.assertEqual(status, 429)
        self.assertEqual(result["parameters"]["retry_after"], 20)


class KeyboardTests(unittest.TestCase):
    def test_semantic_styles_keep_actions(self):
        self.assertEqual(
            button("Open Videl Studio", url="https://example.com").style,
            ButtonStyle.PRIMARY,
        )
        self.assertEqual(
            button("Stop playback", callback_data="stop").style, ButtonStyle.DANGER
        )
        self.assertEqual(
            button("Resume", callback_data="resume").style, ButtonStyle.SUCCESS
        )
        item = button("Previous", callback_data="page_1")
        markup = InlineKeyboardMarkup([[item]])
        basic = plain_keyboard(markup)
        self.assertEqual(basic.inline_keyboard[0][0].callback_data, "page_1")
        self.assertIsNone(basic.inline_keyboard[0][0].icon_custom_emoji_id)
        self.assertIsNot(basic.inline_keyboard[0][0], item)

    def test_emoji_ids_and_fallback_text_are_safe(self):
        from videl.utils.premium_emojis import tg_emoji

        self.assertEqual(tg_emoji('1" onclick="bad', "<unsafe>"), "&lt;unsafe&gt;")
        self.assertEqual(tg_emoji("9999999999999999999", "Hi"), "Hi")

    def test_start_uses_signed_mini_app_launch_buttons_in_private(self):
        from videl.modules.start import _start_kb

        private = _start_kb(True).inline_keyboard
        group = _start_kb(False).inline_keyboard
        self.assertIsNotNone(private[0][0].web_app)
        self.assertIsNotNone(private[2][0].web_app)
        self.assertIsNotNone(group[0][0].url)

    def test_missing_database_is_not_displayed_as_zero(self):
        from videl.modules.start import _studio_private_caption

        with patch(
            "videl.utils.db.read_live_totals", side_effect=RuntimeError("offline")
        ):
            self.assertIn("Unavailable", _studio_private_caption(1, "Owner"))


class AsyncBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_visual_fallback_preserves_actions(self):
        markup = InlineKeyboardMarkup(
            [[button("Stop", callback_data="stop", icon="cross")]]
        )
        send = AsyncMock(side_effect=[BadRequest("CUSTOM_EMOJI_INVALID"), "accepted"])
        result = await visual_call(
            send,
            1,
            caption='<tg-emoji emoji-id="123">🎵</tg-emoji> Track',
            reply_markup=markup,
        )
        self.assertEqual(result, "accepted")
        self.assertEqual(send.call_args.kwargs["caption"], "🎵 Track")
        self.assertEqual(
            send.call_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data,
            "stop",
        )

    async def test_native_network_error_does_not_send_twice(self):
        send = AsyncMock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError):
            await visual_call(send, 1, text="Hello")
        send.assert_awaited_once()

    async def test_rich_timeout_does_not_fall_through_to_a_second_send(self):
        from vendor.richgram.richgram.rich_ui import rich_send

        client = SimpleNamespace(
            send_rich_message=AsyncMock(side_effect=TimeoutError()),
            send_message=AsyncMock(),
        )
        await rich_send(client, 1, "<h2>Hello</h2>")
        client.send_message.assert_not_awaited()

    async def test_reaction_requires_authorization(self):
        module = importlib.import_module("videl.modules.api_tools")
        with patch.object(
            module, "is_user_authorized", AsyncMock(return_value=False)
        ), patch.object(module, "bot_api", AsyncMock()) as call, patch.object(
            module, "rich_reply", AsyncMock()
        ):
            await module.react_command(None, SimpleNamespace())
        call.assert_not_awaited()

    async def test_topic_actions_require_a_forum(self):
        module = importlib.import_module("videl.modules.api_tools")
        message = SimpleNamespace(chat=SimpleNamespace(is_forum=False))
        with patch.object(module, "bot_api", AsyncMock()) as call, patch.object(
            module, "rich_reply", AsyncMock()
        ):
            await module.topic_command(None, message)
        call.assert_not_awaited()

    async def test_poll_keeps_topic_routing(self):
        module = importlib.import_module("videl.modules.management_core")
        message = SimpleNamespace(
            chat=SimpleNamespace(id=-100),
            command=["quiz", "Question", "|", "*A", "|", "B"],
            message_thread_id=33,
        )
        with patch(
            "videl.utils.bot_api.bot_api", AsyncMock(return_value=(200, {"ok": True}))
        ) as call:
            await module.poll_cmd(None, message)
        self.assertEqual(call.call_args.args[0], "sendPoll")
        self.assertEqual(call.call_args.args[1]["message_thread_id"], 33)
        self.assertEqual(call.call_args.args[1]["correct_option_ids"], [0])

    async def test_rich_edit_rejection_strips_icons_but_keeps_callbacks(self):
        from vendor.richgram.richgram.rich_ui import _rich_edit_via_client

        client = SimpleNamespace(
            edit_message_text=AsyncMock(
                side_effect=[BadRequest("CUSTOM_EMOJI_INVALID"), "edited"]
            )
        )
        markup = InlineKeyboardMarkup(
            [[button("Stop", callback_data="stop", icon="cross")]]
        )
        result = await _rich_edit_via_client(
            client,
            1,
            2,
            '<tg-emoji emoji-id="123">🎵</tg-emoji> Track',
            reply_markup=markup,
        )
        self.assertEqual(result, "edited")
        fallback = client.edit_message_text.call_args.kwargs
        self.assertEqual(fallback["text"], "🎵 Track")
        self.assertEqual(
            fallback["reply_markup"].inline_keyboard[0][0].callback_data, "stop"
        )
        self.assertIsNone(
            fallback["reply_markup"].inline_keyboard[0][0].icon_custom_emoji_id
        )

    async def test_rich_edit_timeout_is_not_retried(self):
        from vendor.richgram.richgram.rich_ui import _rich_edit_via_client

        client = SimpleNamespace(
            edit_message_text=AsyncMock(side_effect=TimeoutError())
        )
        self.assertIsNone(
            await _rich_edit_via_client(
                client, 1, 2, "<h2>Update</h2>", reply_markup=None
            )
        )
        client.edit_message_text.assert_awaited_once()

    async def test_plugin_photo_timeout_does_not_duplicate_as_text(self):
        with patch.object(test_bot, "add_handler"):
            runtime = importlib.import_module("videl.plugins.runtime")
        message = SimpleNamespace(chat=SimpleNamespace(id=1))
        with patch.object(
            runtime.bot, "send_photo", AsyncMock(side_effect=TimeoutError())
        ) as photo, patch.object(runtime, "rich_reply", AsyncMock()) as reply:
            await runtime._send(
                message, "Cover", "Description", photo="https://example.com/cover.jpg"
            )
        photo.assert_awaited_once()
        self.assertNotIn("<h2>", photo.call_args.kwargs["caption"])
        reply.assert_not_awaited()

    async def test_plugin_photo_definite_rejection_can_fall_back(self):
        with patch.object(test_bot, "add_handler"):
            runtime = importlib.import_module("videl.plugins.runtime")
        message = SimpleNamespace(chat=SimpleNamespace(id=1))
        with patch.object(
            runtime.bot,
            "send_photo",
            AsyncMock(side_effect=BadRequest("PHOTO_INVALID")),
        ), patch.object(runtime, "rich_reply", AsyncMock()) as reply:
            await runtime._send(
                message, "Cover", "Description", photo="https://example.com/cover.jpg"
            )
        reply.assert_awaited_once()
