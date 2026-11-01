import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock

from videl.plugins import moderation, settings
from videl.utils.interactive_settings import InteractionEngine


class WarningThresholdEditorTests(unittest.IsolatedAsyncioTestCase):
    CHAT = -1001234567
    ADMIN = 345
    OTHER = 346

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db_patch = patch("videl.utils.db._db", self.db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.engine = InteractionEngine()
        self.engine_patch = patch.object(settings, "engine", self.engine)
        self.engine_patch.start()
        self.addCleanup(self.engine_patch.stop)
        self.group = SimpleNamespace(id=self.CHAT, type="supergroup", title="Test group")
        self.admin = SimpleNamespace(id=self.ADMIN)
        self.panel = SimpleNamespace(chat=self.group, id=100, edit_text=AsyncMock())
        self.client = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")),
        )
        self.query = SimpleNamespace(data="", message=self.panel, from_user=self.admin, answer=AsyncMock())
        self.rich_edit = patch("videl.plugins.settings.rich_edit", new=AsyncMock())
        self.rich_edit.start()
        self.addCleanup(self.rich_edit.stop)

    async def open_editor(self, *, revision=None, initial=None):
        if revision is None:
            revision = settings._revision(self.CHAT)
        self.query.data = f"settings:{self.CHAT}:warn_threshold:{'edit' if initial is None else initial}:v{revision}"
        await settings.settings_callback(self.client, self.query)
        session = await self.engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN, target_chat_id=self.CHAT)
        self.assertIsNotNone(session)
        self.assertEqual(session.workflow, "warn_threshold")
        return session

    def editor_query(self, session, action, *, actor=None, chat=None, message_id=None):
        group = chat or self.group
        panel = SimpleNamespace(chat=group, id=message_id or session.expected_message_id, edit_text=AsyncMock())
        return SimpleNamespace(data=f"warn_threshold_edit:{session.token}:{action}", message=panel,
                               from_user=actor or self.admin, answer=AsyncMock())

    async def click(self, session, action, **kwargs):
        query = self.editor_query(session, action, **kwargs)
        await settings.warn_threshold_editor_callback(self.client, query)
        return query

    async def choose(self, session, value):
        query = await self.click(session, f"pick:{value}")
        return query

    async def test_moderation_screen_displays_saved_value_and_all_valid_choices(self):
        self.db["mgmt_chat_settings"].insert_one({"chat_id": self.CHAT, "warn_threshold": 6, "revision": 1})
        screen = settings._screen(self.CHAT, "moderation")
        self.assertIn("Warning threshold", screen.html)
        self.assertIn("6", screen.html)
        editor_button = [b for row in screen.keyboard.inline_keyboard for b in row
                         if b.callback_data and ":warn_threshold:edit:" in b.callback_data]
        self.assertEqual(len(editor_button), 1)
        session = await self.open_editor(revision=1)
        self.assertIn("Currently saved: <b>6</b>", settings._warn_threshold_selection_screen(session).html)
        values = [b.callback_data.rsplit(":", 1)[-1]
                  for row in settings._warn_threshold_selection(session).inline_keyboard
                  for b in row if ":pick:" in (b.callback_data or "")]
        self.assertEqual(values, [str(number) for number in range(1, 11)])

    async def test_valid_values_preview_then_save_with_shared_cas_and_audit(self):
        for value in (1, 10):
            session = await self.open_editor()
            await self.choose(session, value)
            preview = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                            target_chat_id=self.CHAT)
            self.assertEqual(preview.phase, "preview")
            self.assertEqual(preview.values["warn_threshold"], str(value))
            self.assertIn(f"{value} active warnings", settings._warn_threshold_preview(preview).html)
            before_save = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
            if value == 1:
                self.assertIsNone(before_save)
            else:
                self.assertEqual(before_save["warn_threshold"], 1)
            with patch("videl.utils.audit.record_bot") as audit:
                saved = await self.click(preview, "save")
            document = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
            self.assertEqual(document["warn_threshold"], value)
            self.assertEqual(document["revision"], value if value == 1 else 2)
            self.assertIn("saved", saved.answer.call_args.args[0].lower())
            audit.assert_called_once()
            self.assertEqual(audit.call_args.kwargs["action"], "warn_threshold_interactive_saved")
            self.assertEqual(audit.call_args.kwargs["detail"], f"warn_threshold={value}")

    async def test_threshold_is_shown_as_unavailable_when_settings_store_cannot_be_read(self):
        with patch.object(settings.base, "collection", return_value=None):
            screen = settings._screen(self.CHAT, "moderation")
        self.assertIn("Unavailable", screen.html)

    async def test_save_records_only_the_setting_change_in_the_audit_event(self):
        session = await self.open_editor()
        await self.choose(session, 6)
        preview = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        await self.click(preview, "save")
        row = self.db["mgmt_audit"].find_one({"chat_id": self.CHAT})
        self.assertEqual(row["kind"], "settings")
        self.assertEqual(row["action"], "warn_threshold_interactive_saved")
        self.assertEqual(row["detail"], "warn_threshold=6")
        self.assertEqual(row["actor"], self.ADMIN)
        self.assertNotIn("message", row["detail"])

    async def test_legacy_threshold_buttons_open_a_confirmable_preview(self):
        session = await self.open_editor(initial=5)
        self.assertEqual(session.phase, "preview")
        self.assertEqual(session.values["warn_threshold"], "5")
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))
        preview = settings._warn_threshold_preview(session)
        labels = [b.text for row in preview.keyboard.inline_keyboard for b in row]
        self.assertIn("Save", labels)

    async def test_invalid_threshold_value_is_rejected_without_changing_the_session(self):
        session = await self.open_editor()
        invalid = await self.click(session, "pick:11")
        self.assertIn("from 1 to 10", invalid.answer.call_args.args[0])
        current = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        self.assertEqual(current.phase, "input")
        self.assertNotIn("warn_threshold", current.values)
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))

    async def test_edit_again_cancel_and_back_do_not_save(self):
        session = await self.open_editor()
        await self.choose(session, 4)
        preview = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        await self.click(preview, "edit")
        edited = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                       target_chat_id=self.CHAT)
        self.assertEqual(edited.phase, "input")
        self.assertEqual(edited.values, {"saved_value": 3})
        await self.choose(edited, 8)
        preview = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        await self.click(preview, "cancel")
        self.assertIsNone(await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                                target_chat_id=self.CHAT))
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))
        self.assertIn("moderation", settings.base.plain(self.rich_edit.new.call_args.args[1]).lower())

        session = await self.open_editor()
        await self.click(session, "back")
        self.assertIsNone(await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                                target_chat_id=self.CHAT))
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))

    async def test_unauthorized_user_cannot_open_editor(self):
        self.client.get_chat_member.return_value = SimpleNamespace(status="member")
        self.query.data = f"settings:{self.CHAT}:warn_threshold:edit:v0"
        await settings.settings_callback(self.client, self.query)
        self.assertIn("Only current group admins", self.query.answer.call_args.args[0])
        self.assertIsNone(await self.engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN,
                                                      target_chat_id=self.CHAT))

    async def test_admin_permission_loss_immediately_before_save_prevents_write(self):
        session = await self.open_editor()
        await self.choose(session, 7)
        preview = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        self.client.get_chat_member.return_value = SimpleNamespace(status="member")
        result = await self.click(preview, "save")
        self.assertIn("could not be verified", result.answer.call_args.args[0])
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))
        self.assertIsNone(await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                                target_chat_id=self.CHAT))

    async def test_revision_conflict_refreshes_latest_without_overwriting(self):
        self.db["mgmt_chat_settings"].insert_one({"chat_id": self.CHAT, "warn_threshold": 3, "revision": 1})
        session = await self.open_editor(revision=1)
        await self.choose(session, 9)
        from videl.utils.settings_store import write
        write(self.CHAT, {"warn_threshold": 4}, expected=1)
        preview = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        result = await self.click(preview, "save")
        document = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(document["warn_threshold"], 4)
        self.assertEqual(document["revision"], 2)
        self.assertIn("changed elsewhere", result.answer.call_args.args[0])
        self.assertIsNone(await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                                target_chat_id=self.CHAT))

    async def test_timeout_expires_the_editor_without_writing(self):
        now = [100.0]
        self.engine._clock = lambda: now[0]
        session = await self.open_editor()
        now[0] += 601
        expired = await self.click(session, "pick:5")
        self.assertIn("expired or belongs", expired.answer.call_args.args[0])
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))

    async def test_database_failure_is_not_reported_as_success_and_preview_can_retry(self):
        session = await self.open_editor()
        await self.choose(session, 6)
        preview = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        with patch("videl.utils.settings_store.write", side_effect=RuntimeError("database unavailable")):
            result = await self.click(preview, "save")
        self.assertIn("could not save", result.answer.call_args.args[0].lower())
        current = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        self.assertEqual(current.phase, "preview")
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))

    async def test_duplicate_selection_and_save_callbacks_do_not_commit_twice(self):
        session = await self.open_editor()
        first = await self.choose(session, 5)
        duplicate_pick = await self.click(session, "pick:5")
        self.assertIn("no longer active", duplicate_pick.answer.call_args.args[0])
        preview = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        await self.click(preview, "save")
        duplicate_save = await self.click(preview, "save")
        document = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(document["warn_threshold"], 5)
        self.assertEqual(document["revision"], 1)
        self.assertIn("expired or belongs", duplicate_save.answer.call_args.args[0])

    async def test_concurrent_save_callbacks_are_single_flight(self):
        session = await self.open_editor()
        await self.choose(session, 3)
        preview = await self.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                        target_chat_id=self.CHAT)
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.client.get_chat_member
        async def delayed(chat_id, user_id):
            entered.set()
            await release.wait()
            return await original(chat_id, user_id)
        self.client.get_chat_member = delayed
        first_query = self.editor_query(preview, "save")
        second_query = self.editor_query(preview, "save")
        first = asyncio.create_task(settings.warn_threshold_editor_callback(self.client, first_query))
        await entered.wait()
        await settings.warn_threshold_editor_callback(self.client, second_query)
        self.assertIn("no longer active", second_query.answer.call_args.args[0])
        release.set()
        await first
        document = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertEqual(document["warn_threshold"], 3)
        self.assertEqual(document["revision"], 1)

    async def test_sessions_are_isolated_by_group_and_user(self):
        first = await self.open_editor()
        user_session = await self.engine.begin(chat_id=self.CHAT, actor_id=self.OTHER, target_chat_id=self.CHAT,
                                               workflow="warn_threshold", steps=(settings.Step(
                                                   "warn_threshold", "", "selection", choices=settings._WARN_THRESHOLD_VALUES),))
        other_group = await self.engine.begin(chat_id=-1007654321, actor_id=self.ADMIN, target_chat_id=-1007654321,
                                               workflow="warn_threshold", steps=(settings.Step(
                                                   "warn_threshold", "", "selection", choices=settings._WARN_THRESHOLD_VALUES),))
        wrong_user = await self.click(first, "pick:4", actor=SimpleNamespace(id=self.OTHER))
        self.assertIn("expired or belongs", wrong_user.answer.call_args.args[0])
        self.assertIsNotNone(await self.engine.get(user_session.token, chat_id=self.CHAT, actor_id=self.OTHER,
                                                   target_chat_id=self.CHAT))
        self.assertIsNotNone(await self.engine.get(other_group.token, chat_id=-1007654321,
                                                   actor_id=self.ADMIN, target_chat_id=-1007654321))

    async def test_setwarnlimit_command_remains_compatible(self):
        ctx = SimpleNamespace(message=SimpleNamespace(), command=SimpleNamespace(arguments="8"))
        with patch("videl.plugins.moderation._names", return_value=(self.CHAT, "Admin")):
            result = await moderation.set_warn_limit(ctx)
        self.assertIn("8", result.html)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["warn_threshold"], 8)
        ctx.command.arguments = "11"
        invalid = await moderation.set_warn_limit(ctx)
        self.assertIn("1 and 10", invalid.html)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["warn_threshold"], 8)


if __name__ == "__main__":
    unittest.main()
