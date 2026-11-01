import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock

from videl.plugins import settings, welcome
from videl.utils.interactive_settings import InteractionEngine


class InteractiveWelcomeTelegramTests(unittest.IsolatedAsyncioTestCase):
    CHAT = -1001234567
    ADMIN = 345

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db_patch = patch("videl.utils.db._db", self.db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.engine_patch = patch.object(welcome, "_interaction_engine", InteractionEngine())
        self.engine_patch.start()
        self.addCleanup(self.engine_patch.stop)
        self.group = SimpleNamespace(id=self.CHAT, type="supergroup", title="Test Group")
        self.admin = SimpleNamespace(id=self.ADMIN)
        self.client = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")),
            send_message=AsyncMock(), me=SimpleNamespace(username="VidelBot"),
        )
        self.panel = SimpleNamespace(chat=self.group, id=100, edit_text=AsyncMock())
        self.query = SimpleNamespace(data="", message=self.panel, from_user=self.admin, answer=AsyncMock())
        self.prompt = SimpleNamespace(id=200)
        self.client.send_message.return_value = self.prompt

    def callback(self, action, revision=0):
        self.query.data = f"settings:{self.CHAT}:{action}:v{revision}"

    async def open_welcome_settings(self):
        screen = settings._screen(self.CHAT, "welcome")
        rows = screen.keyboard.inline_keyboard
        button_data = [button.callback_data for row in rows for button in row if button.callback_data]
        self.assertIn(f"settings:{self.CHAT}:welcome_text:edit:v0", button_data)
        self.assertIn("Welcome text", screen.html)
        self.assertIn("Welcome messages", screen.html)
        self.callback("welcome_text:edit")
        with patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
            await settings.settings_callback(self.client, self.query)
        self.assertIn("Reply to the welcome-text prompt", self.query.answer.call_args.args[0])
        self.assertIsNotNone(self.client.send_message.await_args.kwargs.get("reply_markup"))
        session = await welcome._interaction_engine.for_owner(
            chat_id=self.CHAT, actor_id=self.ADMIN, target_chat_id=self.CHAT)
        self.assertEqual(session.workflow, "welcome_text")
        return session

    async def submit_text(self, session, text, *, actor_id=None, chat_id=None, reply_id=None):
        message = SimpleNamespace(
            chat=SimpleNamespace(id=chat_id or self.CHAT, type="supergroup", title="Test Group"),
            from_user=SimpleNamespace(id=actor_id or self.ADMIN), text=text,
            reply_to_message=SimpleNamespace(id=reply_id if reply_id is not None else session.expected_message_id),
        )
        await welcome.welcome_edit_message(self.client, message)
        return message

    def callback_for_session(self, session, action):
        preview = SimpleNamespace(chat=self.group, id=session.expected_message_id, edit_text=AsyncMock())
        query = SimpleNamespace(data=f"welcome_edit:{session.token}:{action}", message=preview,
                                from_user=self.admin, answer=AsyncMock())
        return query

    async def test_actual_settings_callback_routes_to_reply_prompt_and_preview(self):
        session = await self.open_welcome_settings()
        await self.submit_text(session, "Welcome {name} to {title}!")
        self.assertEqual(self.client.send_message.await_count, 2)
        self.assertEqual(self.client.send_message.await_args.args[1], "Welcome Alex to Test Group!")
        self.assertEqual(self.client.send_message.await_args.kwargs["reply_markup"].inline_keyboard[0][1].text, "Save")
        current = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertIsNone(current)

    async def test_await_text_requires_the_actual_prompt_reply(self):
        session = await self.open_welcome_settings()
        await self.submit_text(session, "not a reply", reply_id=999)
        self.assertEqual(self.client.send_message.await_count, 1)
        self.assertEqual(session.phase, "input")
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))

    async def test_placeholder_validation_reprompts_and_does_not_consume_step(self):
        session = await self.open_welcome_settings()
        await self.submit_text(session, "Welcome {username}")
        active = await welcome._interaction_engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN, target_chat_id=self.CHAT)
        self.assertEqual(active.phase, "input")
        self.assertEqual(active.index, 0)
        self.assertIn("Unsupported placeholder", self.client.send_message.await_args.args[1])
        await self.submit_text(active, "Welcome {mention} to {title}!")
        self.assertEqual(self.client.send_message.await_args.args[1], 'Welcome <a href="tg://user?id=12345">Alex</a> to Test Group!')

    async def test_edit_again_and_cancel_are_actor_scoped_and_do_not_save(self):
        session = await self.open_welcome_settings()
        await self.submit_text(session, "Hello {name}")
        preview_session = await welcome._interaction_engine.get(session.token, chat_id=self.CHAT,
                                                                   actor_id=self.ADMIN, target_chat_id=self.CHAT)
        query = self.callback_for_session(preview_session, "edit")
        with patch.object(welcome, "rich_edit", new=AsyncMock()):
            await welcome.welcome_edit_callback(self.client, query)
        edited = await welcome._interaction_engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN, target_chat_id=self.CHAT)
        self.assertEqual(edited.phase, "input")
        self.assertEqual(edited.index, 0)
        query = self.callback_for_session(edited, "cancel")
        with patch.object(welcome, "rich_edit", new=AsyncMock()):
            await welcome.welcome_edit_callback(self.client, query)
        self.assertIsNone(await welcome._interaction_engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN, target_chat_id=self.CHAT))
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))

    async def test_successful_save_uses_cas_and_reports_success(self):
        session = await self.open_welcome_settings()
        await self.submit_text(session, "Welcome {name} to {title}!")
        preview_session = await welcome._interaction_engine.get(session.token, chat_id=self.CHAT,
                                                                   actor_id=self.ADMIN, target_chat_id=self.CHAT)
        query = self.callback_for_session(preview_session, "save")
        with patch.object(welcome, "rich_edit", new=AsyncMock()):
            await welcome.welcome_edit_callback(self.client, query)
        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(saved["welcome_message"], "Welcome {name} to {title}!")
        self.assertEqual(saved["revision"], 1)
        self.assertIn("saved", query.answer.call_args.args[0].lower())

    async def test_save_failure_is_not_reported_as_success_and_preview_remains_retryable(self):
        session = await self.open_welcome_settings()
        await self.submit_text(session, "Welcome {name}")
        preview_session = await welcome._interaction_engine.get(session.token, chat_id=self.CHAT,
                                                                   actor_id=self.ADMIN, target_chat_id=self.CHAT)
        query = self.callback_for_session(preview_session, "save")
        with patch("videl.utils.settings_store.write", side_effect=RuntimeError("offline")), \
             patch.object(welcome, "rich_edit", new=AsyncMock()):
            await welcome.welcome_edit_callback(self.client, query)
        self.assertIn("could not save", query.answer.call_args.args[0].lower())
        retained = await welcome._interaction_engine.get(session.token, chat_id=self.CHAT,
                                                           actor_id=self.ADMIN, target_chat_id=self.CHAT)
        self.assertEqual(retained.phase, "preview")
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))

    async def test_revision_conflict_refreshes_latest_and_discards_draft(self):
        session = await self.open_welcome_settings()
        await self.submit_text(session, "Welcome {name}")
        # Another editor commits a change after this workflow opened at revision 0.
        from videl.utils.settings_store import write
        write(self.CHAT, {"welcome_message": "Changed elsewhere"}, expected=0)
        preview_session = await welcome._interaction_engine.get(session.token, chat_id=self.CHAT,
                                                                   actor_id=self.ADMIN, target_chat_id=self.CHAT)
        query = self.callback_for_session(preview_session, "save")
        with patch.object(welcome, "rich_edit", new=AsyncMock()) as edit:
            await welcome.welcome_edit_callback(self.client, query)
        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(saved["welcome_message"], "Changed elsewhere")
        self.assertEqual(saved["revision"], 1)
        self.assertIn("changed elsewhere", query.answer.call_args.args[0].lower())
        edit.assert_awaited_once()
        self.assertIsNone(await welcome._interaction_engine.get(session.token, chat_id=self.CHAT,
                                                                actor_id=self.ADMIN, target_chat_id=self.CHAT))

    async def test_initial_and_save_time_permission_changes_fail_closed(self):
        self.client.get_chat_member.return_value = SimpleNamespace(status="member")
        self.callback("welcome_text:edit")
        with patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
            await settings.settings_callback(self.client, self.query)
        self.assertIn("current group admins", self.query.answer.call_args.args[0].lower())
        self.assertIsNone(await welcome._interaction_engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN, target_chat_id=self.CHAT))

        self.client.get_chat_member.side_effect = [SimpleNamespace(status="administrator"), SimpleNamespace(status="member")]
        self.client.get_chat_member.return_value = None
        self.query.answer.reset_mock()
        session = await self.open_welcome_settings()
        await self.submit_text(session, "Welcome {name}")
        preview_session = await welcome._interaction_engine.get(session.token, chat_id=self.CHAT,
                                                                   actor_id=self.ADMIN, target_chat_id=self.CHAT)
        query = self.callback_for_session(preview_session, "save")
        with patch.object(welcome, "rich_edit", new=AsyncMock()):
            await welcome.welcome_edit_callback(self.client, query)
        self.assertIn("permission could not be verified", query.answer.call_args.args[0].lower())
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))

    async def test_sessions_are_isolated_across_admins_and_groups(self):
        first = await welcome._interaction_engine.begin(chat_id=self.CHAT, actor_id=self.ADMIN,
                    target_chat_id=self.CHAT, workflow="welcome_text", revision=0,
                    steps=(welcome.Step("welcome_message", "Send text", max_length=1000),))
        other_admin = await welcome._interaction_engine.begin(chat_id=self.CHAT, actor_id=999,
                    target_chat_id=self.CHAT, workflow="welcome_text", revision=0,
                    steps=(welcome.Step("welcome_message", "Send text", max_length=1000),))
        other_group = await welcome._interaction_engine.begin(chat_id=-1007654321, actor_id=self.ADMIN,
                    target_chat_id=-1007654321, workflow="welcome_text", revision=0,
                    steps=(welcome.Step("welcome_message", "Send text", max_length=1000),))
        await welcome._interaction_engine.bind_prompt(first.token, chat_id=self.CHAT, actor_id=self.ADMIN, message_id=1)
        await welcome._interaction_engine.bind_prompt(other_admin.token, chat_id=self.CHAT, actor_id=999, message_id=2)
        result = await welcome._interaction_engine.capture(first.token, chat_id=self.CHAT, actor_id=999,
                    target_chat_id=self.CHAT, reply_to_message_id=1, value="bad actor")
        self.assertEqual(result.status, "unauthorized")
        self.assertIsNone(await welcome._interaction_engine.get(first.token, chat_id=-1007654321,
                                                                 actor_id=self.ADMIN, target_chat_id=-1007654321))
        self.assertIsNotNone(await welcome._interaction_engine.get(other_group.token, chat_id=-1007654321,
                                                                     actor_id=self.ADMIN, target_chat_id=-1007654321))

    async def test_cancel_message_clears_draft(self):
        session = await self.open_welcome_settings()
        message = SimpleNamespace(chat=self.group, from_user=self.admin, text="/cancel@VidelBot",
                                  reply_to_message=None)
        await welcome.welcome_edit_message(self.client, message)
        self.assertIsNone(await welcome._interaction_engine.get(session.token, chat_id=self.CHAT,
                                                                actor_id=self.ADMIN, target_chat_id=self.CHAT))
        self.assertIn("cancelled", self.client.send_message.await_args.args[1].lower())


if __name__ == "__main__":
    unittest.main()
