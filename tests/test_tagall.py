import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.app.router import parse
from videl.plugins import group
from videl.plugins.group import COMMANDS, tagall
from videl.plugins.start import member_caption

CHAT = -1001001
BOT_ID = 999


def admin(user_id, *, bot=False, status="administrator"):
    return {"status": status, "user": {"id": user_id, "first_name": f"Member <{user_id}>", "is_bot": bot}}


class FakeClient:
    def __init__(self):
        self.sent = []
        self.progress = SimpleNamespace(id=50, edit_text=AsyncMock())

    async def send_message(self, *args, **kwargs):
        self.sent.append((args, kwargs))
        return self.progress if len(self.sent) == 1 else SimpleNamespace(id=50 + len(self.sent))


class TagallTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = FakeClient()
        self.ctx = SimpleNamespace(
            client=self.client,
            message=SimpleNamespace(chat=SimpleNamespace(id=CHAT), id=77, message_thread_id=77),
            command=SimpleNamespace(arguments="hello <everyone>"),
        )

    def api(self, rows):
        async def call(method, payload):
            if method == "getMe":
                return {"id": BOT_ID, "username": "Videlapp", "is_bot": True}
            if method == "getChatMember":
                self.assertEqual(payload, {"chat_id": CHAT, "user_id": BOT_ID})
                return {"status": "administrator", "can_send_messages": True}
            if method == "getChatAdministrators":
                return rows
            raise AssertionError(method)
        return call

    async def test_batches_unique_human_admins_returned_by_bot_api_and_reports_scope(self):
        rows = [admin(i, bot=(i == 3)) for i in range(1, 62)]
        rows.append(admin(1))  # Duplicate Telegram rows must not duplicate a mention.
        with patch("videl.plugins.group._telegram_bot_api", side_effect=self.api(rows)) as api, \
             patch("videl.plugins.group.asyncio.sleep", new=AsyncMock()) as sleep:
            result = await tagall(self.ctx)

        self.assertIn("not all group members", result.html.lower())
        api.assert_any_await("getChatAdministrators", {"chat_id": CHAT})
        self.assertEqual(len(self.client.sent), 13)  # progress plus 12 batches
        batches = self.client.sent[1:]
        self.assertEqual(len(batches), 12)
        self.assertEqual(sleep.await_count, 11)
        mentions = [call[0][1] for call in batches]
        self.assertTrue(all(call[1]["parse_mode"] == "html" for call in batches))
        self.assertTrue(all(call[1]["message_thread_id"] == 77 for call in batches))
        self.assertTrue(all(text.count("tg://user?id=") <= 5 for text in mentions))
        self.assertTrue(all(len(text) <= 3500 for text in mentions))
        all_text = "".join(mentions)
        self.assertEqual(all_text.count("tg://user?id="), 60)
        self.assertNotIn('href="tg://user?id=3"', all_text)
        self.assertIn("Member &lt;1&gt;", mentions[0])
        self.client.progress.edit_text.assert_awaited()
        self.assertIn("Tag-all complete", self.client.progress.edit_text.await_args.args[0])

    async def test_start_guide_discloses_the_admin_only_member_list_boundary(self):
        group_guide = member_caption("there", private=False)
        plain = group.base.plain(group_guide).lower()
        self.assertIn("telegram-visible admins", plain)
        self.assertIn("not every member", plain)
        self.assertIn("/reload", plain)

    async def test_command_policy_and_help_are_honest_about_api_scope(self):
        command = next(entry for entry in COMMANDS if entry.name == "tagall")
        self.assertEqual(command.policy, "admin")
        self.assertIn("Bot API cannot list all members", command.summary)
        self.assertIn("/tagall stop", command.summary)
        self.assertEqual(parse("/tagall@Videlapp hello", "videlapp").name, "tagall")
        self.assertIsNone(parse("/tagall@anotherbot hello", "videlapp"))

    async def test_oversized_announcement_is_rejected_without_api_or_send(self):
        self.ctx.command.arguments = "x" * 181
        with patch("videl.plugins.group._telegram_bot_api", new=AsyncMock()) as api:
            with self.assertRaisesRegex(ValueError, "under 180"):
                await tagall(self.ctx)
        api.assert_not_awaited()
        self.assertFalse(self.client.sent)

    async def test_bot_not_admin_is_reported_before_sending(self):
        async def unavailable(method, payload):
            if method == "getMe":
                return {"id": BOT_ID}
            return {"status": "member"}
        with patch("videl.plugins.group._telegram_bot_api", side_effect=unavailable):
            with self.assertRaisesRegex(ValueError, "missing permission: Administrator"):
                await tagall(self.ctx)
        self.assertFalse(self.client.sent)

    async def test_roster_api_error_is_actionable_and_sends_no_mentions(self):
        async def unavailable(method, payload):
            if method == "getMe":
                return {"id": BOT_ID}
            if method == "getChatMember":
                return {"status": "administrator"}
            raise RuntimeError("Telegram unavailable")
        with patch("videl.plugins.group._telegram_bot_api", side_effect=unavailable):
            with self.assertRaisesRegex(ValueError, "cannot retrieve a complete member directory"):
                await tagall(self.ctx)
        self.assertFalse(self.client.sent)

    async def test_stop_cancels_a_run_without_recalling_delivered_batches(self):
        rows = [admin(i) for i in range(1, 7)]
        sleeper = asyncio.Event()
        async def paused_sleep(seconds):
            self.assertEqual(seconds, 5)
            sleeper.set()
            await asyncio.Future()
        with patch("videl.plugins.group._telegram_bot_api", side_effect=self.api(rows)), \
             patch("videl.plugins.group.asyncio.sleep", side_effect=paused_sleep):
            run = asyncio.create_task(tagall(self.ctx))
            await sleeper.wait()
            with self.assertRaisesRegex(ValueError, "already active"):
                await tagall(self.ctx)
            stop_ctx = SimpleNamespace(client=self.client, message=self.ctx.message,
                                       command=SimpleNamespace(arguments="stop"))
            stopped = await tagall(stop_ctx)
            self.assertIn("No more mentions", stopped.html)
            result = await run
        self.assertIn("tag-all stopped", group.base.plain(result.html).lower())
        self.assertEqual(len(self.client.sent), 2)  # progress and first five-admin batch
        self.assertEqual(self.client.sent[1][0][1].count("tg://user?id="), 5)

    async def test_partial_batch_failure_reports_count_and_permission_guidance(self):
        rows = [admin(i) for i in range(1, 7)]
        client = FakeClient()
        client.send_message = AsyncMock(side_effect=[client.progress, True, RuntimeError("forbidden")])
        ctx = SimpleNamespace(client=client, message=self.ctx.message, command=self.ctx.command)
        with patch("videl.plugins.group._telegram_bot_api", side_effect=self.api(rows)), \
             patch("videl.plugins.group.asyncio.sleep", new=AsyncMock()):
            with self.assertRaisesRegex(ValueError, "stopped after 5 of 6") as caught:
                await tagall(ctx)
        self.assertIn("Earlier batches were sent", str(caught.exception))
        self.assertIn("check the group before retrying", str(caught.exception))
        self.assertIn("stopped after 5 of 6", client.progress.edit_text.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
