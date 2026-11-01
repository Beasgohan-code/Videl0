import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import mongomock
from pyrogram.enums import ChatType

from videl.plugins import notes
from videl.utils.interactive_settings import InteractionEngine


class ConnectedFilterCrudTests(unittest.IsolatedAsyncioTestCase):
    CHAT, USER = -1007788, 7788

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db_patch = patch("videl.utils.db._db", self.db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.engine = InteractionEngine()
        self.engine_patch = patch.object(notes, "engine", self.engine)
        self.engine_patch.start()
        self.addCleanup(self.engine_patch.stop)
        notes._CONNECTED_FILTER_ACTIONS.clear()
        self.group = NS(id=self.CHAT, type=ChatType.SUPERGROUP)
        self.user = NS(id=self.USER)
        self.resolver = AsyncMock(return_value=(self.group, None))
        self.serial = 100
        async def send(*args, **kwargs):
            self.serial += 1
            return NS(id=self.serial)
        self.client = NS(get_chat_member=AsyncMock(return_value=NS(status="administrator")),
                         send_message=AsyncMock(side_effect=send))
        self.rich = patch("videl.plugins.notes.rich_edit", new=AsyncMock())
        self.rich.start()
        self.addCleanup(self.rich.stop)
        self.panel = NS(chat=NS(id=self.USER, type=ChatType.PRIVATE), id=50)

    async def screen(self, page=0):
        with patch("videl.app.connections.connected_target", new=self.resolver):
            return await notes.connected_filter_screen(self.client, actor_id=self.USER,
                private_chat_id=self.USER, target_chat_id=self.CHAT, page=page, message_id=self.panel.id)

    def query(self, data, *, actor=None, message=None):
        return NS(data=data, message=message or self.panel, from_user=actor or self.user,
                  answer=AsyncMock())

    async def test_empty_and_bounded_paginated_group_scoped_lists(self):
        with patch("videl.app.connections.connected_target", new=self.resolver):
            empty = await self.screen()
        self.assertIn("No automatic filters", empty.html)
        self.assertEqual(len(empty.keyboard.inline_keyboard), 2)  # Add and Back
        self.db.mgmt_filters.insert_many([
            {"chat_id": self.CHAT, "keyword": f"kw{i:02}", "reply": f"reply{i}"}
            for i in range(19)
        ])
        self.db.mgmt_filters.insert_one({"chat_id": self.CHAT - 1, "keyword": "outside", "reply": "secret"})
        first = await self.screen()
        self.assertIn("page 1 of 3", first.html)
        self.assertEqual(sum("Edit ·" in b.text for row in first.keyboard.inline_keyboard for b in row), 8)
        page_button = next(b for row in first.keyboard.inline_keyboard for b in row
                           if b.callback_data and b.callback_data.startswith("connected_filter:page:"))
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, self.query(page_button.callback_data))
        self.assertEqual(self.rich.new.call_args.args[1].count("<code>"), 8)
        self.assertNotIn("secret", self.rich.new.call_args.args[1])

    async def test_edit_selected_filter_uses_preview_and_exact_snapshot(self):
        row = self.db.mgmt_filters.insert_one({"chat_id": self.CHAT, "keyword": "hello", "reply": "old"})
        screen = await self.screen()
        edit = next(b.callback_data for line in screen.keyboard.inline_keyboard for b in line
                    if b.callback_data and b.callback_data.startswith("connected_filter:edit:"))
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, self.query(edit))
        session = await self.engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        self.assertEqual(session.values["original"]["_id"], row.inserted_id)
        for value in ("hello", "new reply"):
            message = NS(chat=NS(id=self.USER, type=ChatType.PRIVATE), from_user=self.user, text=value,
                         reply_to_message=NS(id=session.expected_message_id))
            with patch("videl.app.connections.connected_target", new=self.resolver):
                await notes.filter_editor_message(self.client, message)
            session = await self.engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        self.assertEqual(session.phase, "preview")
        self.assertEqual(session.values["original"]["reply"], "old")
        confirm = self.query(f"filter_edit:{session.token}:save", message=NS(chat=self.panel.chat, id=session.expected_message_id))
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.filter_editor_callback(self.client, confirm)
        saved = self.db.mgmt_filters.find_one({"_id": row.inserted_id})
        self.assertEqual(saved["reply"], "new reply")

    async def test_delete_requires_exact_preview_confirmation_and_rejects_replay(self):
        row = self.db.mgmt_filters.insert_one({"chat_id": self.CHAT, "keyword": "remove-me", "reply": "goodbye"})
        screen = await self.screen()
        delete = next(b.callback_data for line in screen.keyboard.inline_keyboard for b in line
                      if b.callback_data and b.callback_data.startswith("connected_filter:delete:"))
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, self.query(delete))
        session = await self.engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        self.assertEqual(session.workflow, "filter_delete")
        self.assertIsNotNone(self.db.mgmt_filters.find_one({"_id": row.inserted_id}))
        confirm = self.query(f"connected_filter:confirm:{session.token}")
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, confirm)
        self.assertIsNone(self.db.mgmt_filters.find_one({"_id": row.inserted_id}))
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, confirm)
        self.assertIn("expired", confirm.answer.call_args.args[0].lower())

    async def test_delete_storage_failure_is_not_reported_as_success(self):
        row = self.db.mgmt_filters.insert_one({"chat_id": self.CHAT, "keyword": "safe", "reply": "unchanged"})
        screen = await self.screen()
        delete = next(b.callback_data for line in screen.keyboard.inline_keyboard for b in line
                      if b.callback_data and b.callback_data.startswith("connected_filter:delete:"))
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, self.query(delete))
        session = await self.engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        confirm = self.query(f"connected_filter:confirm:{session.token}")
        from videl.utils import filter_store
        with patch("videl.app.connections.connected_target", new=self.resolver), \
             patch.object(filter_store, "delete_filter_by_id", side_effect=filter_store.FilterStoreError("offline")):
            await notes.connected_filter_callback(self.client, confirm)
        self.assertIsNotNone(self.db.mgmt_filters.find_one({"_id": row.inserted_id}))
        self.assertNotIn("deleted", confirm.answer.call_args.args[0].lower())

    async def test_cancelled_delete_preview_never_writes(self):
        row = self.db.mgmt_filters.insert_one({"chat_id": self.CHAT, "keyword": "keep-me", "reply": "still here"})
        screen = await self.screen()
        delete = next(b.callback_data for line in screen.keyboard.inline_keyboard for b in line
                      if b.callback_data and b.callback_data.startswith("connected_filter:delete:"))
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, self.query(delete))
        session = await self.engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        cancel = self.query(f"connected_filter:cancel:{session.token}")
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, cancel)
        self.assertIsNotNone(self.db.mgmt_filters.find_one({"_id": row.inserted_id}))
        self.assertIsNone(await self.engine.get(session.token, chat_id=self.USER, actor_id=self.USER))

    async def test_delete_confirmation_rechecks_admin_and_rejects_stale_snapshot(self):
        row = self.db.mgmt_filters.insert_one({"chat_id": self.CHAT, "keyword": "hold", "reply": "original"})
        screen = await self.screen()
        delete = next(b.callback_data for line in screen.keyboard.inline_keyboard for b in line
                      if b.callback_data and b.callback_data.startswith("connected_filter:delete:"))
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, self.query(delete))
        session = await self.engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        self.db.mgmt_filters.update_one({"_id": row.inserted_id}, {"$set": {"reply": "changed elsewhere"}})
        confirm = self.query(f"connected_filter:confirm:{session.token}")
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, confirm)
        self.assertIsNotNone(self.db.mgmt_filters.find_one({"_id": row.inserted_id}))
        self.assertIn("not completed", confirm.answer.call_args.args[0].lower())

        # A second preview must not commit once Telegram no longer reports admin.
        self.client.get_chat_member.side_effect = None
        self.client.get_chat_member.return_value = NS(status="administrator")
        screen = await self.screen()
        delete = next(b.callback_data for line in screen.keyboard.inline_keyboard for b in line
                      if b.callback_data and b.callback_data.startswith("connected_filter:delete:"))
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, self.query(delete))
        session = await self.engine.for_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        self.client.get_chat_member.side_effect = RuntimeError("Telegram unavailable")
        confirm = self.query(f"connected_filter:confirm:{session.token}")
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, confirm)
        self.assertIsNotNone(self.db.mgmt_filters.find_one({"_id": row.inserted_id}))

    async def test_connected_mapping_cannot_redirect_to_another_group(self):
        self.db.mgmt_filters.insert_one({"chat_id": self.CHAT - 1, "keyword": "private", "reply": "other"})
        redirected = AsyncMock(return_value=(NS(id=self.CHAT - 1, type=ChatType.SUPERGROUP), None))
        with patch("videl.app.connections.connected_target", new=redirected):
            with self.assertRaises(PermissionError):
                await notes.connected_filter_screen(self.client, actor_id=self.USER,
                    private_chat_id=self.USER, target_chat_id=self.CHAT, page=0, message_id=self.panel.id)
        self.assertEqual(self.db.mgmt_filters.count_documents({"chat_id": self.CHAT}), 0)

    async def test_cancel_stale_actor_and_revoked_connection_do_not_mutate(self):
        row = self.db.mgmt_filters.insert_one({"chat_id": self.CHAT, "keyword": "keep", "reply": "yes"})
        screen = await self.screen()
        delete = next(b.callback_data for line in screen.keyboard.inline_keyboard for b in line
                      if b.callback_data and b.callback_data.startswith("connected_filter:delete:"))
        with patch("videl.app.connections.connected_target", new=self.resolver):
            await notes.connected_filter_callback(self.client, self.query(delete, actor=NS(id=self.USER + 1),
                message=NS(chat=NS(id=self.USER + 1, type=ChatType.PRIVATE), id=self.panel.id)))
        self.assertIsNotNone(self.db.mgmt_filters.find_one({"_id": row.inserted_id}))
        with patch("videl.app.connections.connected_target", new=AsyncMock(return_value=(None, "revoked"))):
            denied = self.query(delete)
            await notes.connected_filter_callback(self.client, denied)
        self.assertIsNotNone(self.db.mgmt_filters.find_one({"_id": row.inserted_id}))


if __name__ == "__main__":
    unittest.main()
