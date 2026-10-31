import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.plugins.group import COMMANDS, tagall


class TagallTests(unittest.IsolatedAsyncioTestCase):
    async def test_mentions_all_human_members_one_per_message_with_five_second_spacing(self):
        users = [SimpleNamespace(
            id=i, first_name=f"Member <{i}>", last_name="", is_bot=(i == 3)
        ) for i in range(1, 62)]

        class FakeClient:
            def __init__(self):
                self.sent = []
                self.iterated = False

            async def get_chat_members(self, chat_id):
                self.iterated = True
                for user in users:
                    yield SimpleNamespace(user=user)

            async def send_message(self, *args, **kwargs):
                self.sent.append((args, kwargs))
                return True

        client = FakeClient()
        ctx = SimpleNamespace(
            client=client,
            message=SimpleNamespace(chat=SimpleNamespace(id=-1001001), message_thread_id=77),
            command=SimpleNamespace(arguments="hello <everyone>"),
        )
        with patch("videl.plugins.group.asyncio.sleep", new=AsyncMock()) as sleep:
            result = await tagall(ctx)

        self.assertIsNone(result)
        self.assertTrue(client.iterated)
        self.assertEqual(len(client.sent), 60, "all 60 human members are included, not capped at 50")
        self.assertEqual(sleep.await_count, 59, "wait before every mention after the first")
        sleep.assert_awaited_with(5)
        first_args, first_kwargs = client.sent[0]
        self.assertEqual(first_args[0], -1001001)
        self.assertIn("hello &lt;everyone&gt;", first_args[1])
        self.assertIn('href="tg://user?id=1"', first_args[1])
        self.assertIn("Member &lt;1&gt;", first_args[1])
        self.assertEqual(first_kwargs["parse_mode"], "html")
        self.assertEqual(first_kwargs["message_thread_id"], 77)
        self.assertNotIn('href="tg://user?id=3"', "".join(call[0][1] for call in client.sent))

    async def test_requires_admin_policy_and_describes_unlimited_paced_behavior(self):
        command = next(entry for entry in COMMANDS if entry.name == "tagall")
        self.assertEqual(command.policy, "admin")
        self.assertIn("all accessible human members", command.summary)
        self.assertIn("every 5 seconds", command.summary)
        self.assertIn("/tagall stop", command.summary)

    async def test_rejects_oversized_announcement_without_sending(self):
        client = SimpleNamespace(send_message=AsyncMock())
        ctx = SimpleNamespace(
            client=client,
            message=SimpleNamespace(chat=SimpleNamespace(id=-1001)),
            command=SimpleNamespace(arguments="x" * 181),
        )
        with self.assertRaises(ValueError):
            await tagall(ctx)
        client.send_message.assert_not_awaited()

    async def test_tagall_stop_cancels_run_without_touching_messages_already_sent(self):
        users = [SimpleNamespace(id=i, first_name=f"Member {i}", is_bot=False) for i in range(1, 4)]
        sent = []
        client = SimpleNamespace(
            get_chat_members=lambda _chat_id: _members(users),
            send_message=AsyncMock(side_effect=lambda *args, **kwargs: sent.append(args[1])),
        )
        message = SimpleNamespace(chat=SimpleNamespace(id=-1001003), message_thread_id=None)
        run_ctx = SimpleNamespace(client=client, message=message, command=SimpleNamespace(arguments="update"))
        stop_ctx = SimpleNamespace(client=client, message=message, command=SimpleNamespace(arguments="stop"))
        sleeper = asyncio.Event()

        async def paused_sleep(seconds):
            self.assertEqual(seconds, 5)
            sleeper.set()
            await asyncio.Future()

        with patch("videl.plugins.group.asyncio.sleep", side_effect=paused_sleep):
            run = asyncio.create_task(tagall(run_ctx))
            await sleeper.wait()
            stopped = await tagall(stop_ctx)
            self.assertIn("No more mentions will be sent", stopped.html)
            with self.assertRaises(asyncio.CancelledError):
                await run
        self.assertEqual(len(sent), 1)

    async def test_stops_and_reports_partial_delivery_when_send_fails(self):
        users = [SimpleNamespace(id=i, first_name=f"Member {i}", is_bot=False) for i in range(1, 4)]
        client = SimpleNamespace(
            get_chat_members=lambda _chat_id: _members(users),
            send_message=AsyncMock(side_effect=[True, RuntimeError("Telegram unavailable")]),
        )
        ctx = SimpleNamespace(
            client=client,
            message=SimpleNamespace(chat=SimpleNamespace(id=-1001002), message_thread_id=None),
            command=SimpleNamespace(arguments="update"),
        )
        with patch("videl.plugins.group.asyncio.sleep", new=AsyncMock()):
            with self.assertRaisesRegex(ValueError, "stopped after 1 members"):
                await tagall(ctx)
        self.assertEqual(client.send_message.await_count, 2)


async def _members(users):
    for user in users:
        yield SimpleNamespace(user=user)


if __name__ == "__main__":
    unittest.main()
