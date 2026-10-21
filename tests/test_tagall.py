import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from videl.plugins.group import COMMANDS, tagall


class TagallTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_one_bounded_escaped_announcement_without_duplicate_reply(self):
        users = [SimpleNamespace(
            id=i, first_name=f"Member <{i}>", last_name="", is_bot=(i == 3)
        ) for i in range(1, 62)]

        class FakeClient:
            def __init__(self):
                self.sent = []

            async def get_chat_members(self, chat_id, limit):
                self.requested_limit = limit
                for user in users:
                    yield SimpleNamespace(user=user)

            async def send_message(self, *args, **kwargs):
                self.sent.append((args, kwargs))

        client = FakeClient()
        ctx = SimpleNamespace(
            client=client,
            message=SimpleNamespace(chat=SimpleNamespace(id=-1001), message_thread_id=None),
            command=SimpleNamespace(arguments="hello <everyone>"),
        )
        result = await tagall(ctx)
        self.assertIsNone(result)
        self.assertEqual(len(client.sent), 1)
        text, = client.sent[0][0][1:]
        self.assertIn("Announcement · 50 members", text)
        self.assertIn("hello &lt;everyone&gt;", text)
        self.assertIn("tg://user?id=1", text)
        self.assertIn("Member &lt;1&gt;", text)
        self.assertNotIn('href="tg://user?id=3"', text)
        self.assertLessEqual(len(text), 3900)
        self.assertEqual(client.sent[0][1]["parse_mode"], "html")

    async def test_requires_admin_policy_and_is_in_command_manifest(self):
        command = next(entry for entry in COMMANDS if entry.name == "tagall")
        self.assertEqual(command.policy, "admin")
        self.assertIn("50", command.summary)

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
