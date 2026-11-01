import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock
from videl.plugins import settings
from videl.utils.interactive_settings import engine
from videl.utils import listening_sessions


class ConnectedSessionScheduleTests(unittest.IsolatedAsyncioTestCase):
    CHAT, USER, BOT = -100912, 912, 999

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["mgmt_chat_settings"].insert_one({"chat_id": self.CHAT, "revision": 0})
        self.next_id = 200
        async def send(*args, **kwargs):
            self.next_id += 1
            return SimpleNamespace(id=self.next_id)
        self.client = SimpleNamespace(me=SimpleNamespace(id=self.BOT), send_message=AsyncMock(side_effect=send),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")))

    async def asyncTearDown(self):
        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    def _details(self, day_offset=2, title="Friday listening"):
        due = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=day_offset)
        return due.strftime("%Y-%m-%d %H:%M UTC") + " | " + title, due

    @staticmethod
    def _as_utc(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    async def _start(self):
        query = SimpleNamespace(data=f"settings:{self.CHAT}:session:schedule:v0",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=25),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
             new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.settings_callback(self.client, query)
        return await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    async def _reply(self, raw=None):
        session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        if raw is None: raw, _ = self._details()
        message = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
            text=raw, reply_to_message=SimpleNamespace(id=session.expected_message_id))
        with patch("videl.utils.db._db", self.db):
            await settings.connected_session_reply(self.client, message)
        return await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)

    def _query(self, action, session):
        return SimpleNamespace(data=f"listensession_{action}:{session.token}",
            message=SimpleNamespace(chat=SimpleNamespace(id=self.USER, type="private"), id=session.expected_message_id),
            from_user=SimpleNamespace(id=self.USER), answer=AsyncMock())

    async def _confirm(self, session, resolver=None):
        query = self._query("save", session)
        resolver = resolver or AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target", resolver):
            await settings.connected_session_callback(self.client, query)
        return query, resolver

    async def test_success_creates_scheduler_record_only_after_confirmation_and_utc(self):
        await self._start(); raw, due = self._details(title="Friday <listening>")
        session = await self._reply(raw)
        self.assertEqual(self.db["listening_sessions"].count_documents({}), 0)
        self.assertEqual(session.chat_id, self.USER)
        self.assertEqual(session.target_chat_id, self.CHAT)
        self.assertIn(due.strftime("%Y-%m-%d %H:%M UTC"), self.client.send_message.await_args_list[-1].args[1])
        self.assertIn("Friday &lt;listening&gt;", self.client.send_message.await_args_list[-1].args[1])
        query, resolver = await self._confirm(session)
        resolver.assert_awaited_once_with(self.client, self.USER, expected_chat_id=self.CHAT)
        row = self.db["listening_sessions"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["title"], "Friday <listening>")
        self.assertEqual(self._as_utc(row["due_at"]), due)
        self.assertEqual(row["status"], "scheduled")
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)
        self.assertEqual(query.answer.call_args.args[0], "Listening session scheduled.")

    async def test_edit_preview_then_schedules_revised_details(self):
        await self._start(); first, _ = self._details(title="Old title")
        session = await self._reply(first)
        edit = self._query("edit", session)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_session_callback(self.client, edit)
        self.assertEqual(self.db["listening_sessions"].count_documents({}), 0)
        raw, due = self._details(title="New title")
        revised = await self._reply(raw)
        await self._confirm(revised)
        row = self.db["listening_sessions"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["title"], "New title")
        self.assertEqual(self._as_utc(row["due_at"]), due)

    async def test_cancel_and_timeout_never_create_session(self):
        await self._start(); session = await self._reply()
        cancel = self._query("cancel", session)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_session_callback(self.client, cancel)
        self.assertEqual(self.db["listening_sessions"].count_documents({}), 0)

        await self._start(); session = await self._reply()
        clock = engine._clock
        try:
            engine._clock = lambda: 10**12
            query, _ = await self._confirm(session)
            self.assertIn("expired", query.answer.call_args.args[0].lower())
        finally:
            engine._clock = clock
        self.assertEqual(self.db["listening_sessions"].count_documents({}), 0)

    async def test_invalid_date_title_and_timezone_leave_input_active(self):
        await self._start()
        future, _ = self._details()
        future_time = future.split(" | ", 1)[0]
        for invalid in ("bad", "2020-01-01 10:00 UTC | Past", "2020-01-01 10:00 | Missing zone",
                        "2099-01-01 10:00 UTC | Too far", future_time + " | ",
                        future_time + " | " + "x" * 101):
            session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
            reply = SimpleNamespace(chat=SimpleNamespace(id=self.USER), from_user=SimpleNamespace(id=self.USER),
                text=invalid, reply_to_message=SimpleNamespace(id=session.expected_message_id))
            with patch("videl.utils.db._db", self.db):
                await settings.connected_session_reply(self.client, reply)
            self.assertEqual((await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)).phase, "input")
        self.assertEqual(self.db["listening_sessions"].count_documents({}), 0)

    async def test_connection_and_actor_permission_revocation_prevent_scheduling(self):
        await self._start(); session = await self._reply()
        query, _ = await self._confirm(session, AsyncMock(return_value=(None, "connection changed")))
        self.assertIn("connection", query.answer.call_args.args[0].lower())
        self.assertEqual(self.db["listening_sessions"].count_documents({}), 0)
        session = await engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        revoked, _ = await self._confirm(session, AsyncMock(return_value=(None, "no longer a current administrator")))
        self.assertIn("admin", revoked.answer.call_args.args[0].lower())
        self.assertEqual(self.db["listening_sessions"].count_documents({}), 0)

    async def test_bot_send_permission_loss_prevents_scheduling(self):
        await self._start(); session = await self._reply()
        with patch("videl.utils.db._db", self.db), patch("videl.plugins.settings._group_bot_can_announce", new=AsyncMock(return_value=False)):
            query = self._query("save", session)
            await settings.connected_session_callback(self.client, query)
        self.assertIn("permission changed", query.answer.call_args.args[0].lower())
        self.assertEqual(self.db["listening_sessions"].count_documents({}), 0)

    async def test_actor_and_target_isolation_reject_forged_callback(self):
        await self._start(); session = await self._reply()
        query = self._query("save", session)
        query.from_user = SimpleNamespace(id=self.USER + 1)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_session_callback(self.client, query)
        self.assertEqual(self.db["listening_sessions"].count_documents({}), 0)
        other = await engine.get(session.token, chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT - 1)
        self.assertIsNone(other)

    async def test_concurrent_confirmation_creates_exactly_one_record(self):
        await self._start(); session = await self._reply()
        first = self._query("save", session); second = self._query("save", session)
        async def delayed(*args, **kwargs):
            await asyncio.sleep(0.02)
            return SimpleNamespace(id=self.CHAT), None
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target", new=delayed):
            await asyncio.gather(settings.connected_session_callback(self.client, first),
                                 settings.connected_session_callback(self.client, second))
        self.assertEqual(self.db["listening_sessions"].count_documents({"chat_id": self.CHAT}), 1)

    async def test_scheduler_db_failure_and_ambiguous_insert_are_safe(self):
        await self._start(); session = await self._reply()
        with patch("videl.utils.db._db", self.db), patch("videl.utils.listening_sessions.schedule", return_value=None):
            query, _ = await self._confirm(session)
        self.assertIn("could not schedule", query.answer.call_args.args[0].lower())
        self.assertEqual(self.db["listening_sessions"].count_documents({}), 0)

        due = datetime.now(timezone.utc) + timedelta(days=2)
        collection = self.db["listening_sessions"]
        collection_type = type(collection)
        real_insert = collection_type.insert_one
        def insert_then_raise(instance, document, *args, **kwargs):
            real_insert(instance, document, *args, **kwargs)
            raise RuntimeError("write response lost")
        identifier = "retrytoken123"
        with patch.object(collection_type, "insert_one", new=insert_then_raise):
            saved = listening_sessions.schedule(self.db, self.CHAT, self.USER, due, "Title", identifier=identifier)
        self.assertEqual(saved, identifier)
        self.assertEqual(collection.count_documents({"_id": identifier}), 1)
        self.assertEqual(listening_sessions.schedule(self.db, self.CHAT, self.USER, due, "Title", identifier=identifier), identifier)
        self.assertEqual(collection.count_documents({"_id": identifier}), 1)

    async def test_existing_group_context_prompt_still_schedules(self):
        raw, due = self._details()
        prompt_message = SimpleNamespace(id=88)
        message = SimpleNamespace(chat=SimpleNamespace(id=self.CHAT, type="supergroup"),
            from_user=SimpleNamespace(id=self.USER), reply_to_message=prompt_message,
            text=raw, reply_text=AsyncMock())
        import time
        settings._PROMPTS[(self.CHAT, self.USER)] = (88, "session", time.monotonic() + 300, 0)
        with patch("videl.utils.db._db", self.db), \
             patch("videl.utils.settings_store.write"), \
             patch("videl.utils.listening_sessions.schedule", return_value="legacy-id") as schedule:
            await settings.blocklist_prompt_reply(self.client, message)
        schedule.assert_called_once()
        self.assertEqual(schedule.call_args.args[1:3], (self.CHAT, self.USER))
        self.assertEqual(schedule.call_args.args[3], due)
        message.reply_text.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
