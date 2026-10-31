import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import mongomock
from pyrogram.enums import ChatMemberStatus, ChatType

from videl.plugins import notes


class FilterInlineManagementTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.chat_id = -93001
        self.db = mongomock.MongoClient().db
        self.store = self.db.mgmt_filters
        self.store.insert_many([
            {"chat_id": self.chat_id, "keyword": f"key{i:02d}", "reply": f"answer{i}"}
            for i in range(10)
        ])
        self.store.insert_one({"chat_id": self.chat_id + 1, "keyword": "key00", "reply": "other group"})
        self.client = NS(get_chat_member=AsyncMock(return_value=NS(status=ChatMemberStatus.ADMINISTRATOR)))
        self.message = NS(
            chat=NS(id=self.chat_id, type=ChatType.SUPERGROUP),
            id=81,
        )

    async def _first_delete_button(self):
        ctx = NS(message=self.message, user=NS(id=901), client=self.client)
        with patch.object(notes, "_filters", return_value=self.store):
            screen = await notes.list_filters(ctx)
        return next(
            button.callback_data
            for row in screen.keyboard.inline_keyboard
            for button in row
            if button.callback_data.startswith("mgmt_filter:delete:")
        )

    async def test_filter_list_shows_paged_inline_remove_buttons_to_live_admin(self):
        ctx = NS(
            message=self.message,
            user=NS(id=901),
            client=self.client,
        )
        with patch.object(notes, "_filters", return_value=self.store):
            screen = await notes.list_filters(ctx)

        self.assertIn("page 1/2", screen.html)
        buttons = [button for row in screen.keyboard.inline_keyboard for button in row]
        self.assertEqual(sum(button.callback_data.startswith("mgmt_filter:delete:") for button in buttons), 8)
        self.assertIn("mgmt_filter:page:1", [button.callback_data for button in buttons])

    async def test_filter_list_is_read_only_when_viewer_is_not_admin(self):
        self.client.get_chat_member.return_value = NS(status=ChatMemberStatus.MEMBER)
        ctx = NS(message=self.message, user=NS(id=902), client=self.client)
        with patch.object(notes, "_filters", return_value=self.store):
            screen = await notes.list_filters(ctx)

        buttons = [button for row in screen.keyboard.inline_keyboard for button in row]
        self.assertFalse(any(button.callback_data.startswith("mgmt_filter:delete:") for button in buttons))
        self.assertIn("Only a current group admin", screen.html)

    async def test_inline_delete_rechecks_live_admin_and_deletes_the_selected_filter_only(self):
        data = await self._first_delete_button()
        # A newly inserted filter changes row positions, but the button token
        # still points to the exact keyword that the admin originally selected.
        self.store.insert_one({"chat_id": self.chat_id, "keyword": "aaa", "reply": "new filter"})
        query = NS(
            data=data,
            message=self.message,
            from_user=NS(id=903),
            answer=AsyncMock(),
        )
        with patch.object(notes, "_filters", return_value=self.store), \
             patch.object(notes, "rich_edit", new=AsyncMock()) as edit, \
             patch.object(notes, "record_bot"):
            await notes.filter_management_callback(self.client, query)

        self.assertIsNone(self.store.find_one({"chat_id": self.chat_id, "keyword": "key00"}))
        self.assertIsNotNone(self.store.find_one({"chat_id": self.chat_id, "keyword": "aaa"}))
        self.assertIsNotNone(self.store.find_one({"chat_id": self.chat_id + 1, "keyword": "key00"}))
        query.answer.assert_awaited_once_with("Filter removed")
        edit.assert_awaited_once()

    async def test_inline_delete_denies_demoted_or_non_admin_actor(self):
        data = await self._first_delete_button()
        self.client.get_chat_member.return_value = NS(status=ChatMemberStatus.MEMBER)
        query = NS(
            data=data,
            message=self.message,
            from_user=NS(id=904),
            answer=AsyncMock(),
        )
        with patch.object(notes, "_filters", return_value=self.store), \
             patch.object(notes, "rich_edit", new=AsyncMock()) as edit:
            await notes.filter_management_callback(self.client, query)

        self.assertIsNotNone(self.store.find_one({"chat_id": self.chat_id, "keyword": "key00"}))
        query.answer.assert_awaited_once()
        self.assertTrue(query.answer.call_args.kwargs["show_alert"])
        edit.assert_not_awaited()

if __name__ == "__main__":
    unittest.main()
