import asyncio
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import mongomock
from pyrogram.enums import ChatMemberStatus, ChatType

from videl.plugins import notes, settings
from videl.utils import filter_store
from videl.utils.interactive_settings import InteractionEngine


class InteractiveFilterTests(unittest.IsolatedAsyncioTestCase):
    CHAT = -1003456001
    OTHER_CHAT = -1003456002
    ADMIN = 501
    SECOND_ADMIN = 502

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db_patch = patch("videl.utils.db._db", self.db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.engine = InteractionEngine()
        self.notes_engine_patch = patch.object(notes, "engine", self.engine)
        self.settings_engine_patch = patch.object(settings, "engine", self.engine)
        self.notes_engine_patch.start()
        self.settings_engine_patch.start()
        self.addCleanup(self.notes_engine_patch.stop)
        self.addCleanup(self.settings_engine_patch.stop)
        notes._FILTER_ACTIONS.clear()
        self.group = NS(id=self.CHAT, type=ChatType.SUPERGROUP, title="Filter group")
        self.admin = NS(id=self.ADMIN)
        self.panel = NS(chat=self.group, id=100, edit_text=AsyncMock())
        self.client = NS(
            get_chat_member=AsyncMock(return_value=NS(status=ChatMemberStatus.ADMINISTRATOR)),
            send_message=AsyncMock(),
        )
        self.sent_id = [200]
        async def send_message(*_args, **_kwargs):
            self.sent_id[0] += 1
            return NS(id=self.sent_id[0])
        self.client.send_message.side_effect = send_message
        self.rich_edit_patch = patch("videl.plugins.notes.rich_edit", new=AsyncMock())
        self.rich_edit_patch.start()
        self.settings_edit_patch = patch("videl.plugins.settings.rich_edit", new=AsyncMock())
        self.settings_edit_patch.start()
        self.addCleanup(self.rich_edit_patch.stop)
        self.addCleanup(self.settings_edit_patch.stop)

    async def start(self, *, mode="add", original=None, chat_id=None, actor_id=None):
        chat_id = self.CHAT if chat_id is None else chat_id
        actor_id = self.ADMIN if actor_id is None else actor_id
        panel = self.panel if chat_id == self.CHAT else NS(chat=NS(id=chat_id, type=ChatType.SUPERGROUP), id=100)
        await notes.start_filter_editor(self.client, panel, chat_id, actor_id,
                                        mode=mode, original=original)
        session = await self.engine.for_owner(chat_id=chat_id, actor_id=actor_id,
                                              target_chat_id=chat_id)
        self.assertIsNotNone(session)
        return session

    async def submit(self, session, text, *, actor_id=None, chat_id=None, reply_id=None):
        actor_id = session.actor_id if actor_id is None else actor_id
        chat_id = session.chat_id if chat_id is None else chat_id
        message = NS(
            chat=NS(id=chat_id, type=ChatType.SUPERGROUP),
            from_user=NS(id=actor_id, is_bot=False),
            text=text,
            reply_to_message=NS(id=session.expected_message_id if reply_id is None else reply_id),
        )
        await notes.filter_editor_message(self.client, message)
        return message

    def preview_query(self, session, action, *, actor=None, chat=None):
        panel = NS(chat=chat or NS(id=session.chat_id, type=ChatType.SUPERGROUP),
                   id=session.expected_message_id, edit_text=AsyncMock())
        return NS(data=f"filter_edit:{session.token}:{action}", message=panel,
                  from_user=actor or NS(id=session.actor_id), answer=AsyncMock())

    async def click(self, session, action, *, actor=None, chat=None):
        query = self.preview_query(session, action, actor=actor, chat=chat)
        await notes.filter_editor_callback(self.client, query)
        return query

    async def reach_preview(self, session, keyword="Hello", reply="Welcome back"):
        await self.submit(session, keyword)
        current = await self.engine.get(session.token, chat_id=session.chat_id,
                                        actor_id=session.actor_id, target_chat_id=session.chat_id)
        await self.submit(current, reply)
        return await self.engine.get(session.token, chat_id=session.chat_id,
                                     actor_id=session.actor_id, target_chat_id=session.chat_id)

    async def test_settings_automations_tab_routes_to_add_filter(self):
        screen = settings._screen(self.CHAT, "automations")
        self.assertIn("Automatic filters", screen.html)
        callbacks = [button.callback_data for row in screen.keyboard.inline_keyboard
                     for button in row if button.callback_data]
        self.assertIn(f"settings:{self.CHAT}:filters:add:v0", callbacks)
        self.assertIn(f"settings:{self.CHAT}:filters:manage:v0", callbacks)
        query = NS(data=f"settings:{self.CHAT}:filters:add:v0", message=self.panel,
                   from_user=self.admin, answer=AsyncMock())
        await settings.settings_callback(self.client, query)
        session = await self.engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN,
                                              target_chat_id=self.CHAT)
        self.assertEqual(session.workflow, "filter_add")
        self.assertIn("nothing is saved", query.answer.call_args.args[0].lower())

    async def test_non_admin_cannot_start_the_settings_filter_editor(self):
        self.client.get_chat_member.return_value = NS(status=ChatMemberStatus.MEMBER)
        query = NS(data=f"settings:{self.CHAT}:filters:add:v0", message=self.panel,
                   from_user=self.admin, answer=AsyncMock())
        await settings.settings_callback(self.client, query)
        self.assertIn("Only current group admins", query.answer.call_args.args[0])
        self.assertIsNone(await self.engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN,
                                                      target_chat_id=self.CHAT))

    async def test_valid_add_normalizes_keyword_previews_plain_text_and_audits(self):
        session = await self.start()
        await self.submit(session, "  HeLLo There  ")
        session = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        self.assertEqual(session.values["keyword"], "hello there")
        await self.submit(session, "  <b>Welcome</b> back!  ")
        preview = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        self.assertEqual(preview.phase, "preview")
        self.assertEqual(preview.values["reply"], "<b>Welcome</b> back!")
        self.assertIsNone(self.db["mgmt_filters"].find_one({"chat_id": self.CHAT}))
        preview_html, keyboard = notes._filter_preview(preview)
        self.assertIn("&lt;b&gt;Welcome&lt;/b&gt;", preview_html)
        self.assertEqual([button.text for row in keyboard.inline_keyboard for button in row][:2],
                         ["Save", "Edit Again"])
        result = await self.click(preview, "save")
        saved = self.db["mgmt_filters"].find_one({"chat_id": self.CHAT})
        self.assertEqual((saved["keyword"], saved["reply"]), ("hello there", "<b>Welcome</b> back!"))
        audit = self.db["mgmt_audit"].find_one({"chat_id": self.CHAT, "kind": "filter"})
        self.assertEqual(audit["detail"], "text filter added")
        self.assertNotIn("Welcome", audit["detail"])
        self.assertIn("saved", result.answer.call_args.args[0].lower())

    async def test_empty_oversized_and_invalid_keywords_are_reprompted(self):
        session = await self.start()
        for value, expected in (("   ", "cannot be empty"), ("k" * 65, "64 characters")):
            await self.submit(session, value)
            current = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                            target_chat_id=self.CHAT)
            self.assertEqual(current.phase, "input")
            self.assertEqual(current.index, 0)
            self.assertEqual(current.values, {})
            self.assertIn(expected, self.client.send_message.await_args.args[1])
            session = current
        await self.submit(session, "  HELLO  ")
        current = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        self.assertEqual(current.values["keyword"], "hello")

    async def test_media_reply_is_rejected_with_plain_text_guidance(self):
        session = await self.start()
        message = NS(chat=NS(id=self.CHAT, type=ChatType.SUPERGROUP),
                     from_user=NS(id=self.ADMIN, is_bot=False), text=None,
                     photo=NS(file_id="photo"),
                     reply_to_message=NS(id=session.expected_message_id))
        await notes.filter_editor_message(self.client, message)
        self.assertIn("Only plain-text", self.client.send_message.await_args.args[1])
        current = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        self.assertEqual(current.index, 0)
        self.assertEqual(current.values, {})

    async def test_empty_and_oversized_responses_are_rejected(self):
        session = await self.start()
        await self.submit(session, "hey")
        session = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        for value, expected in (("  ", "cannot be empty"), ("x" * 401, "400 characters")):
            await self.submit(session, value)
            current = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                            target_chat_id=self.CHAT)
            self.assertEqual(current.phase, "input")
            self.assertEqual(current.index, 1)
            self.assertIn(expected, self.client.send_message.await_args.args[1])
            session = current
        self.assertIsNone(self.db["mgmt_filters"].find_one({"chat_id": self.CHAT}))

    async def test_cancel_and_timeout_leave_no_filter(self):
        session = await self.start()
        await self.reach_preview(session)
        session = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        await self.click(session, "cancel")
        self.assertIsNone(await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                                target_chat_id=self.CHAT))
        self.assertIsNone(self.db["mgmt_filters"].find_one({"chat_id": self.CHAT}))

        now = [100.0]
        self.engine._clock = lambda: now[0]
        timed = await self.start(chat_id=self.OTHER_CHAT)
        now[0] += 601
        expired = await self.engine.get(timed.token, chat_id=self.OTHER_CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.OTHER_CHAT)
        self.assertIsNone(expired)
        self.assertIsNone(self.db["mgmt_filters"].find_one({"chat_id": self.OTHER_CHAT}))

    async def test_edit_existing_filter_cas_updates_same_record(self):
        original = self.db["mgmt_filters"].insert_one({"chat_id": self.CHAT, "keyword": "hello", "reply": "old"})
        row = self.db["mgmt_filters"].find_one({"_id": original.inserted_id})
        session = await self.start(mode="edit", original=row)
        preview = await self.reach_preview(session, " Hi ", "New response")
        self.assertEqual(preview.values["keyword"], "hi")
        await self.click(preview, "save")
        rows = list(self.db["mgmt_filters"].find({"chat_id": self.CHAT}))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["_id"], original.inserted_id)
        self.assertEqual((rows[0]["keyword"], rows[0]["reply"]), ("hi", "New response"))

    async def test_edit_again_restores_original_snapshot_and_cancel_discards_draft(self):
        inserted = self.db["mgmt_filters"].insert_one({"chat_id": self.CHAT, "keyword": "hello", "reply": "old"})
        original = self.db["mgmt_filters"].find_one({"_id": inserted.inserted_id})
        session = await self.start(mode="edit", original=original)
        preview = await self.reach_preview(session, "new", "new response")
        await self.click(preview, "edit")
        edited = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                       target_chat_id=self.CHAT)
        self.assertEqual(edited.workflow, "filter_edit")
        self.assertEqual(edited.values["original"]["_id"], inserted.inserted_id)
        self.assertEqual(edited.index, 0)
        await self.click(edited, "cancel")
        current = self.db["mgmt_filters"].find_one({"_id": inserted.inserted_id})
        self.assertEqual((current["keyword"], current["reply"]), ("hello", "old"))

    async def test_add_duplicate_and_legacy_duplicates_are_never_overwritten_or_merged(self):
        self.db["mgmt_filters"].insert_one({"chat_id": self.CHAT, "keyword": "Hello", "reply": "first"})
        session = await self.start()
        preview = await self.reach_preview(session, " hello ", "replacement")
        result = await self.click(preview, "save")
        rows = list(self.db["mgmt_filters"].find({"chat_id": self.CHAT}))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["reply"], "first")
        self.assertIn("already has a filter", result.answer.call_args.args[0])

        self.db["mgmt_filters"].insert_one({"chat_id": self.CHAT, "keyword": "HELLO ", "reply": "second"})
        with self.assertRaises(filter_store.FilterStoreConflict):
            filter_store.put_filter(self.db, self.CHAT, "hello", "third", mode="upsert")
        self.assertEqual(self.db["mgmt_filters"].count_documents({"chat_id": self.CHAT}), 2)

    async def test_conflicting_edit_snapshot_preserves_concurrent_change(self):
        inserted = self.db["mgmt_filters"].insert_one({"chat_id": self.CHAT, "keyword": "old", "reply": "original"})
        original = self.db["mgmt_filters"].find_one({"_id": inserted.inserted_id})
        session = await self.start(mode="edit", original=original)
        preview = await self.reach_preview(session, "new", "my draft")
        self.db["mgmt_filters"].update_one({"_id": inserted.inserted_id}, {"$set": {"reply": "changed elsewhere"}})
        result = await self.click(preview, "save")
        current = self.db["mgmt_filters"].find_one({"_id": inserted.inserted_id})
        self.assertEqual((current["keyword"], current["reply"]), ("old", "changed elsewhere"))
        self.assertIn("changed or was removed", result.answer.call_args.args[0])

    async def test_duplicate_normalized_records_block_edit_without_deleting_either(self):
        first = self.db["mgmt_filters"].insert_one({"chat_id": self.CHAT, "keyword": "hello", "reply": "one"})
        self.db["mgmt_filters"].insert_one({"chat_id": self.CHAT, "keyword": " HELLO ", "reply": "two"})
        original = self.db["mgmt_filters"].find_one({"_id": first.inserted_id})
        with self.assertRaisesRegex(filter_store.FilterStoreConflict, "Duplicate filters"):
            filter_store.edit_filter(self.db, self.CHAT, original, "new", "response")
        self.assertEqual(self.db["mgmt_filters"].count_documents({"chat_id": self.CHAT}), 2)

    async def test_permission_loss_before_commit_prevents_mutation(self):
        session = await self.start()
        preview = await self.reach_preview(session)
        self.client.get_chat_member.return_value = NS(status=ChatMemberStatus.MEMBER)
        result = await self.click(preview, "save")
        self.assertIn("could not be verified", result.answer.call_args.args[0])
        self.assertIsNone(self.db["mgmt_filters"].find_one({"chat_id": self.CHAT}))

    async def test_database_failure_is_not_success_and_preview_is_retryable(self):
        session = await self.start()
        preview = await self.reach_preview(session)
        with patch.object(filter_store, "put_filter", side_effect=filter_store.FilterStoreError("offline")):
            result = await self.click(preview, "save")
        self.assertIn("could not save", result.answer.call_args.args[0].lower())
        current = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        self.assertEqual(current.phase, "preview")
        self.assertIsNone(self.db["mgmt_filters"].find_one({"chat_id": self.CHAT}))

    async def test_concurrent_adds_for_same_normalized_keyword_only_create_one_row(self):
        def attempt(reply):
            try:
                return filter_store.put_filter(self.db, self.CHAT, " HELLO ", reply, mode="create")[1]
            except filter_store.FilterStoreConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, ("first", "second")))
        self.assertCountEqual(outcomes, ["created", "conflict"])
        self.assertEqual(self.db["mgmt_filters"].count_documents({"chat_id": self.CHAT}), 1)

    async def test_concurrent_edits_use_snapshot_cas_and_do_not_lose_both_writes(self):
        inserted = self.db["mgmt_filters"].insert_one({"chat_id": self.CHAT, "keyword": "hello", "reply": "old"})
        original = self.db["mgmt_filters"].find_one({"_id": inserted.inserted_id})
        def attempt(reply):
            try:
                filter_store.edit_filter(self.db, self.CHAT, original, "hello", reply)
                return "saved"
            except filter_store.FilterStoreConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, ("one", "two")))
        self.assertCountEqual(outcomes, ["saved", "conflict"])
        self.assertIn(self.db["mgmt_filters"].find_one({"_id": inserted.inserted_id})["reply"], {"one", "two"})
        self.assertEqual(self.db["mgmt_filters"].count_documents({"chat_id": self.CHAT}), 1)

    async def test_busy_group_lease_refuses_second_writer(self):
        with filter_store._group_lease(self.db["mgmt_filters"], self.CHAT):
            with self.assertRaises(filter_store.FilterStoreConflict):
                filter_store.put_filter(self.db, self.CHAT, "hello", "response")
        self.assertEqual(self.db["mgmt_filters"].count_documents({"chat_id": self.CHAT}), 0)

    async def test_cross_group_filters_are_isolated(self):
        filter_store.put_filter(self.db, self.CHAT, "hello", "here", mode="create")
        filter_store.put_filter(self.db, self.OTHER_CHAT, "hello", "there", mode="create")
        self.assertEqual(self.db["mgmt_filters"].find_one({"chat_id": self.CHAT})["reply"], "here")
        self.assertEqual(self.db["mgmt_filters"].find_one({"chat_id": self.OTHER_CHAT})["reply"], "there")

    async def test_filter_list_edit_buttons_recheck_admin_and_delete_exact_record(self):
        one = self.db["mgmt_filters"].insert_one({"chat_id": self.CHAT, "keyword": "hello", "reply": "one"})
        two = self.db["mgmt_filters"].insert_one({"chat_id": self.CHAT, "keyword": "hello ", "reply": "two"})
        ctx = NS(message=self.panel, user=self.admin, client=self.client)
        screen = await notes.list_filters(ctx)
        actions = [button.callback_data for row in screen.keyboard.inline_keyboard
                   for button in row if button.callback_data and button.callback_data.startswith("mgmt_filter:")]
        self.assertTrue(any(value.startswith("mgmt_filter:edit:") for value in actions))
        self.assertEqual(sum(value.startswith("mgmt_filter:delete:") for value in actions), 2)
        token = next(value.rsplit(":", 1)[-1] for value in actions if value.startswith("mgmt_filter:delete:"))
        query = NS(data=f"mgmt_filter:delete:{token}", message=self.panel,
                   from_user=self.admin, answer=AsyncMock())
        await notes.filter_management_callback(self.client, query)
        remaining = list(self.db["mgmt_filters"].find({"chat_id": self.CHAT}))
        self.assertEqual(len(remaining), 1)
        self.assertIn(remaining[0]["_id"], {one.inserted_id, two.inserted_id})

    async def test_existing_filter_edit_button_starts_scoped_editor_and_requires_live_admin(self):
        inserted = self.db["mgmt_filters"].insert_one({"chat_id": self.CHAT, "keyword": "hello", "reply": "answer"})
        screen = await notes.list_filters(NS(message=self.panel, user=self.admin, client=self.client))
        edit_data = next(button.callback_data for row in screen.keyboard.inline_keyboard
                         for button in row if button.callback_data.startswith("mgmt_filter:edit:"))
        token = edit_data.rsplit(":", 1)[-1]
        query = NS(data=edit_data, message=self.panel, from_user=self.admin, answer=AsyncMock())
        await notes.filter_management_callback(self.client, query)
        session = await self.engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN,
                                              target_chat_id=self.CHAT)
        self.assertEqual(session.workflow, "filter_edit")
        self.assertEqual(session.values["original"]["_id"], inserted.inserted_id)

        # A second token is refused if Telegram no longer considers its caller an admin.
        await self.engine.cancel(session.token, chat_id=self.CHAT, actor_id=self.ADMIN)
        notes._FILTER_ACTIONS.clear()
        screen = await notes.list_filters(NS(message=self.panel, user=self.admin, client=self.client))
        edit_data = next(button.callback_data for row in screen.keyboard.inline_keyboard
                         for button in row if button.callback_data.startswith("mgmt_filter:edit:"))
        self.client.get_chat_member.return_value = NS(status=ChatMemberStatus.MEMBER)
        denied = NS(data=edit_data, message=self.panel, from_user=self.admin, answer=AsyncMock())
        await notes.filter_management_callback(self.client, denied)
        self.assertIn("current group admin", denied.answer.call_args.args[0].lower())
        self.assertIsNone(await self.engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN,
                                                      target_chat_id=self.CHAT))

    async def test_sessions_are_isolated_by_group_and_user(self):
        current = await self.start()
        other_group = await self.start(chat_id=self.OTHER_CHAT)
        other_admin = await self.start(chat_id=self.CHAT, actor_id=self.SECOND_ADMIN)
        wrong_user = await self.click(current, "save", actor=NS(id=self.SECOND_ADMIN))
        self.assertIn("expired or belongs", wrong_user.answer.call_args.args[0])
        self.assertIsNotNone(await self.engine.get(other_group.token, chat_id=self.OTHER_CHAT,
                                                   actor_id=self.ADMIN, target_chat_id=self.OTHER_CHAT))
        self.assertIsNotNone(await self.engine.get(other_admin.token, chat_id=self.CHAT,
                                                   actor_id=self.SECOND_ADMIN, target_chat_id=self.CHAT))
        self.assertIsNotNone(await self.engine.get(current.token, chat_id=self.CHAT,
                                                   actor_id=self.ADMIN, target_chat_id=self.CHAT))

    async def test_existing_filter_commands_keep_upsert_and_delete_behavior(self):
        ctx = NS(message=NS(chat=NS(id=self.CHAT), from_user=self.admin, reply_to_message=None),
                 command=NS(arguments="HELLO First response"))
        first = await notes.add_filter(ctx)
        self.assertIn("Filter saved", notes.base.plain(first.html))
        ctx.command.arguments = "hello Replaced response"
        await notes.add_filter(ctx)
        self.assertEqual(self.db["mgmt_filters"].count_documents({"chat_id": self.CHAT}), 1)
        self.assertEqual(self.db["mgmt_filters"].find_one({"chat_id": self.CHAT})["reply"], "Replaced response")
        ctx.command.arguments = "HELLO"
        removed = await notes.remove_filter(ctx)
        self.assertIn("Filter removed", notes.base.plain(removed.html))
        self.assertEqual(self.db["mgmt_filters"].count_documents({"chat_id": self.CHAT}), 0)

    async def test_existing_longest_casefolded_substring_matcher_is_unchanged(self):
        self.db["mgmt_filters"].insert_many([
            {"chat_id": self.CHAT, "keyword": "hello", "reply": "generic"},
            {"chat_id": self.CHAT, "keyword": "hello there", "reply": "specific"},
        ])
        message = NS(text="Well, HELLO THERE friend", from_user=NS(id=90, is_bot=False),
                     chat=NS(id=self.CHAT), reply_text=AsyncMock())
        with patch.object(notes, "_filters", return_value=self.db["mgmt_filters"]):
            await notes.filter_watcher(None, message)
        message.reply_text.assert_awaited_once_with("specific", parse_mode=None)


if __name__ == "__main__":
    unittest.main()
