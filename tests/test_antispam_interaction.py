import re
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock

from videl.plugins import settings
from videl.utils.interactive_settings import InteractionEngine


class AntiSpamInteractionTests(unittest.IsolatedAsyncioTestCase):
    CHAT = -100444
    ADMIN = 55
    BOT = 999

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db_patch = patch("videl.utils.db._db", self.db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.engine_patch = patch.object(settings, "engine", InteractionEngine())
        self.engine_patch.start()
        self.addCleanup(self.engine_patch.stop)
        self.group = SimpleNamespace(id=self.CHAT, type="supergroup", title="Flood Test")
        self.admin = SimpleNamespace(id=self.ADMIN)
        self.panel = SimpleNamespace(chat=self.group, id=10, edit_text=AsyncMock())
        self.query = SimpleNamespace(data="", message=self.panel, from_user=self.admin, answer=AsyncMock())
        self.can_delete = True
        async def get_member(chat_id, user_id):
            if int(user_id) == self.ADMIN:
                return SimpleNamespace(status="administrator")
            privileges = SimpleNamespace(can_delete_messages=self.can_delete)
            return SimpleNamespace(status="administrator", privileges=privileges)
        self.client = SimpleNamespace(
            get_chat_member=AsyncMock(side_effect=get_member),
            send_message=AsyncMock(return_value=SimpleNamespace(id=100)),
            me=SimpleNamespace(id=self.BOT),
        )

    async def open_editor(self):
        screen = settings._screen(self.CHAT, "safety")
        callbacks = [b.callback_data for row in screen.keyboard.inline_keyboard for b in row if b.callback_data]
        callback_data = f"settings:{self.CHAT}:antispam:edit:v0"
        self.assertIn(callback_data, callbacks)
        self.assertIsNotNone(re.match(settings._PATTERN, callback_data))
        self.assertFalse(any(f"settings:{self.CHAT}:antispam:{state}:v0" in callbacks for state in ("on", "off")))
        self.query.data = f"settings:{self.CHAT}:antispam:edit:v0"
        with patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
            await settings.settings_callback(self.client, self.query)
        session = await settings.engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN, target_chat_id=self.CHAT)
        self.assertEqual(session.workflow, "antispam")
        return session

    async def send_value(self, session, value, *, actor_id=None):
        message = SimpleNamespace(
            chat=self.group,
            from_user=SimpleNamespace(id=actor_id or self.ADMIN),
            text=value,
            reply_to_message=SimpleNamespace(id=session.expected_message_id),
        )
        await settings.antispam_settings_message(self.client, message)

    async def test_settings_route_wizard_preview_and_cas_save(self):
        session = await self.open_editor()
        await self.send_value(session, "ON")
        self.assertEqual(session.current_step.key, "limit")
        await self.send_value(session, "7")
        self.assertEqual(session.current_step.key, "window")
        await self.send_value(session, "12")
        self.assertEqual(session.phase, "preview")
        self.assertIn("Burst limit", self.client.send_message.await_args.args[1])
        query = SimpleNamespace(
            data=f"antispam_edit:{session.token}:save",
            message=SimpleNamespace(chat=self.group, id=session.expected_message_id, edit_text=AsyncMock()),
            from_user=self.admin, answer=AsyncMock(),
        )
        with (
            patch.object(settings, "rich_edit", new=AsyncMock()),
            patch("videl.plugins.locks.invalidate_antispam_config") as invalidate,
        ):
            await settings.antispam_settings_callback(self.client, query)
        invalidate.assert_called_once_with(self.CHAT)
        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertTrue(saved["antispam"])
        self.assertEqual(saved["antispam_limit"], 7)
        self.assertEqual(saved["antispam_window"], 12)
        self.assertEqual(saved["revision"], 1)
        self.assertIn("saved", query.answer.call_args.args[0].lower())

    async def test_invalid_number_reprompts_and_cancel_does_not_save(self):
        session = await self.open_editor()
        await self.send_value(session, "on")
        await self.send_value(session, "31")
        self.assertEqual(session.index, 1)
        self.assertEqual(session.phase, "input")
        self.assertIn("outside the allowed range", self.client.send_message.await_args.args[1])
        query = SimpleNamespace(
            data=f"antispam_edit:{session.token}:cancel",
            message=SimpleNamespace(chat=self.group, id=100, edit_text=AsyncMock()),
            from_user=self.admin, answer=AsyncMock(),
        )
        with patch.object(settings, "rich_edit", new=AsyncMock()):
            await settings.antispam_settings_callback(self.client, query)
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))
        self.assertIsNone(await settings.engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN, target_chat_id=self.CHAT))

    async def test_missing_bot_delete_right_only_offered_as_safe_choice(self):
        self.can_delete = False
        session = await self.open_editor()
        self.assertEqual(session.steps[0].choices, ("off",))
        await self.send_value(session, "on")
        self.assertEqual(session.index, 0)
        await self.send_value(session, "off")
        await self.send_value(session, "7")
        await self.send_value(session, "8")
        self.assertEqual(session.phase, "preview")
        self.assertIn("only Off is available", self.client.send_message.await_args_list[0].args[1])

    async def test_bot_permission_loss_before_save_prevents_enable(self):
        session = await self.open_editor()
        await self.send_value(session, "on")
        await self.send_value(session, "7")
        await self.send_value(session, "8")
        self.can_delete = False
        query = SimpleNamespace(
            data=f"antispam_edit:{session.token}:save",
            message=SimpleNamespace(chat=self.group, id=session.expected_message_id, edit_text=AsyncMock()),
            from_user=self.admin, answer=AsyncMock(),
        )
        with patch.object(settings, "rich_edit", new=AsyncMock()):
            await settings.antispam_settings_callback(self.client, query)
        self.assertIn("Delete Messages permission", query.answer.call_args.args[0])
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))

    async def test_revision_conflict_and_storage_failure_are_not_success(self):
        session = await self.open_editor()
        await self.send_value(session, "on")
        await self.send_value(session, "7")
        await self.send_value(session, "8")
        from videl.utils.settings_store import write
        write(self.CHAT, {"other": "changed"}, expected=0)
        query = SimpleNamespace(
            data=f"antispam_edit:{session.token}:save",
            message=SimpleNamespace(chat=self.group, id=session.expected_message_id, edit_text=AsyncMock()),
            from_user=self.admin, answer=AsyncMock(),
        )
        with patch.object(settings, "rich_edit", new=AsyncMock()):
            await settings.antispam_settings_callback(self.client, query)
        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        self.assertNotIn("antispam", saved)
        self.assertIn("changed elsewhere", query.answer.call_args.args[0].lower())

        # A separate fresh session exercises a transient writer failure.
        self.db["mgmt_chat_settings"].delete_many({"chat_id": self.CHAT})
        await settings.engine.cancel_owner(chat_id=self.CHAT, actor_id=self.ADMIN)
        session = await self.open_editor()
        await self.send_value(session, "off")
        await self.send_value(session, "7")
        await self.send_value(session, "8")
        query = SimpleNamespace(
            data=f"antispam_edit:{session.token}:save",
            message=SimpleNamespace(chat=self.group, id=session.expected_message_id, edit_text=AsyncMock()),
            from_user=self.admin, answer=AsyncMock(),
        )
        with (
            patch("videl.utils.settings_store.write", side_effect=RuntimeError("offline")),
            patch.object(settings, "rich_edit", new=AsyncMock()),
        ):
            await settings.antispam_settings_callback(self.client, query)
        self.assertIn("could not save", query.answer.call_args.args[0].lower())
        retained = await settings.engine.get(session.token, chat_id=self.CHAT, actor_id=self.ADMIN,
                                              target_chat_id=self.CHAT)
        self.assertEqual(retained.phase, "preview")
        self.assertIsNone(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT}))

    async def test_non_admin_cannot_open_editor(self):
        async def denied(chat_id, user_id):
            return SimpleNamespace(status="member")
        self.client.get_chat_member.side_effect = denied
        self.query.data = f"settings:{self.CHAT}:antispam:edit:v0"
        with patch("videl.plugins.settings.rich_edit", new=AsyncMock()):
            await settings.settings_callback(self.client, self.query)
        self.assertIn("Only current group admins", self.query.answer.call_args.args[0])
        self.assertIsNone(await settings.engine.for_owner(chat_id=self.CHAT, actor_id=self.ADMIN, target_chat_id=self.CHAT))


if __name__ == "__main__":
    unittest.main()
