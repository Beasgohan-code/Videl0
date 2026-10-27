from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from bson import ObjectId

from videl.app.router import Command, CommandError, Context, Parsed, Router
from videl.plugins.reports import report, reports
from pyrogram.enums import ChatMemberStatus


class Collection:
    def __init__(self):
        self.documents = []

    def count_documents(self, query):
        return 0

    def insert_one(self, document):
        self.documents.append(document)
        return SimpleNamespace(inserted_id=ObjectId())


class ReportCommandTests(IsolatedAsyncioTestCase):
    async def test_report_stores_ids_reason_and_status_without_copying_message_text(self):
        collection = Collection()
        reported = SimpleNamespace(id=22, from_user=SimpleNamespace(id=91), text="sensitive original text")
        message = SimpleNamespace(
            chat=SimpleNamespace(id=-100321, type="supergroup"),
            from_user=SimpleNamespace(id=42),
            reply_to_message=reported,
        )
        ctx = Context(SimpleNamespace(), message, Parsed("report", "spam link"))
        with patch("videl.plugins.reports._reports_collection", return_value=collection):
            screen = await report(ctx)
        saved = collection.documents[0]
        self.assertEqual(saved["chat_id"], -100321)
        self.assertEqual(saved["message_id"], 22)
        self.assertEqual(saved["reporter"], 42)
        self.assertEqual(saved["target"], 91)
        self.assertEqual(saved["reason"], "spam link")
        self.assertEqual(saved["status"], "open")
        self.assertNotIn("text", saved)
        self.assertNotIn("sensitive original text", repr(saved))
        self.assertNotIn("sensitive original text", screen.html)

    async def test_report_queue_never_renders_into_group_chat(self):
        message = SimpleNamespace(chat=SimpleNamespace(id=-100321, type="supergroup"))
        ctx = Context(SimpleNamespace(), message, Parsed("reports", ""), actor=SimpleNamespace(id=42))
        with self.assertRaises(CommandError) as caught:
            await reports(ctx)
        self.assertIn("private chat", str(caught.exception))

    async def test_connected_admin_reviews_reports_in_private_chat(self):
        class Cursor:
            def sort(self, *_args):
                return self

            def limit(self, *_args):
                return self

            def __iter__(self):
                return iter([])

        class ReportCollection:
            def find(self, *_args):
                return Cursor()

        from unittest.mock import AsyncMock
        from videl.app.router import Screen

        private = SimpleNamespace(
            id=5,
            text="/reports",
            chat=SimpleNamespace(id=42, type="private"),
            from_user=SimpleNamespace(id=42),
            reply_to_message=None,
            message_thread_id=None,
        )
        group = SimpleNamespace(id=-100321, title="Test Group", type="supergroup")
        member = SimpleNamespace(status=ChatMemberStatus.ADMINISTRATOR, privileges=None)
        client = SimpleNamespace(
            me=SimpleNamespace(username="testbot"),
            get_chat=AsyncMock(return_value=group),
            get_chat_member=AsyncMock(return_value=member),
        )
        router = Router([Command("reports", reports, "Review reports", policy="admin")])
        with (
            patch("videl.utils.db.get_connected_chat", return_value=-100321),
            patch("videl.plugins.reports._reports_collection", return_value=ReportCollection()),
            patch("videl.app.router.rich_reply", new_callable=AsyncMock) as reply,
        ):
            await router.dispatch(client, private)
        reply.assert_awaited_once()
        self.assertIs(reply.await_args.args[0], private)
