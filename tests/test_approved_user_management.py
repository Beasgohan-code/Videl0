import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.modules import approve


class ApprovedUserPaginationTests(unittest.TestCase):
    def test_pages_are_bounded_ordered_and_clamped(self):
        users = list(range(1, 24)) + [0, -1, True, 2**80]
        all_users, page, index, pages = approve._approved_page(users, 1)
        self.assertEqual(all_users, list(range(1, 24)))
        self.assertEqual(page, list(range(11, 21)))
        self.assertEqual(index, 1)
        self.assertEqual(pages, 3)
        self.assertEqual(approve._approved_page(users, 999)[2], 2)

    def test_group_list_keyboard_has_navigation_and_only_current_page_remove_actions(self):
        users = list(range(100, 124))
        markup = approve._approved_keyboard(users, allow_clear=True, page=1)
        callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
        removals = [data for data in callbacks if data.startswith("approve:rm:")]
        self.assertEqual(removals, [f"approve:rm:{uid}" for uid in range(110, 120)])
        self.assertIn("approve:page:0", callbacks)
        self.assertIn("approve:page:2", callbacks)


class ApprovedUserGroupCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_approval_command_can_inspect_user_status_without_mutating(self):
        message = SimpleNamespace(chat=SimpleNamespace(id=-10011), command=["approval", "123"],
                                  reply_to_message=None)
        with patch.object(approve, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(approve, "_resolve_target", new=AsyncMock(return_value=(123, "Example"))), \
             patch.object(approve, "is_approved", return_value=True) as lookup, \
             patch.object(approve, "rich_send", new=AsyncMock()) as send:
            await approve.approval_info(None, message)
        lookup.assert_called_once_with(-10011, 123)
        self.assertIn("Approved", send.await_args.args[2])
        self.assertIn("123", send.await_args.args[2])

    async def test_approval_status_inspection_requires_fresh_admin_authorization(self):
        message = SimpleNamespace(chat=SimpleNamespace(id=-10011), command=["approval", "123"],
                                  reply_to_message=None)
        with patch.object(approve, "is_user_authorized", new=AsyncMock(return_value=False)), \
             patch.object(approve, "_resolve_target", new=AsyncMock()) as resolver, \
             patch.object(approve, "is_approved") as lookup:
            await approve.approval_info(None, message)
        resolver.assert_not_called()
        lookup.assert_not_called()

    def _query(self, data):
        return SimpleNamespace(data=data, message=SimpleNamespace(chat=SimpleNamespace(id=-10011)),
            from_user=SimpleNamespace(id=111), answer=AsyncMock())

    async def test_group_page_callback_uses_message_group_scope_and_renders_page(self):
        query = self._query("approve:page:2")
        with patch.object(approve, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(approve, "list_approved", return_value=list(range(1, 24))), \
             patch.object(approve, "rich_edit", new=AsyncMock()) as edit:
            await approve.approve_cbs(None, query)
        self.assertIn("Showing 21–23 of 23", edit.await_args.args[1])
        self.assertEqual(edit.await_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data,
                         "approve:rm:21")

    async def test_unauthorized_and_nonexistent_removal_do_not_mutate(self):
        unauthorized = self._query("approve:rm:101")
        with patch.object(approve, "is_user_authorized", new=AsyncMock(return_value=False)), \
             patch.object(approve, "disapprove_user") as remove:
            await approve.approve_cbs(None, unauthorized)
        remove.assert_not_called()

        missing = self._query("approve:rm:101")
        with patch.object(approve, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(approve, "is_approved", return_value=False), \
             patch.object(approve, "list_approved", return_value=[202]), \
             patch.object(approve, "rich_edit", new=AsyncMock()):
            await approve.approve_cbs(None, missing)
        self.assertIn("no longer approved", missing.answer.call_args.args[0].lower())

    async def test_malformed_or_out_of_range_user_callback_is_rejected(self):
        for data in ("approve:rm:0", "approve:rm:abc", "approve:rm:１２３", f"approve:rm:{2**80}"):
            query = self._query(data)
            with patch.object(approve, "is_user_authorized", new=AsyncMock(return_value=True)), \
                 patch.object(approve, "disapprove_user") as remove:
                await approve.approve_cbs(None, query)
            remove.assert_not_called()
            self.assertTrue(query.answer.await_args.kwargs.get("show_alert"))

    async def test_clear_opens_scoped_preview_without_mutating(self):
        from videl.utils.interactive_settings import engine
        query = self._query("approve:clear")
        query.message.id = 700
        users = [101, 202, 303]
        with patch.object(approve, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(approve, "list_approved", return_value=users), \
             patch.object(approve, "rich_edit", new=AsyncMock()) as edit, \
             patch("videl.utils.db.get_db") as get_db:
            await approve.approve_cbs(None, query)
            callback = edit.await_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data
            token = callback.rsplit(":", 1)[-1]
            session = await engine.get(token, chat_id=-10011, actor_id=111, target_chat_id=-10011)
            self.assertEqual(session.workflow, "approved_clear")
            self.assertEqual(session.values["users"], users)
            self.assertEqual(session.expected_message_id, 700)
            self.assertIn("3 currently approved", edit.await_args.args[1])
            get_db.assert_not_called()
        await engine.cancel(token, chat_id=-10011, actor_id=111)

    async def test_clear_confirmation_refuses_revoked_admin(self):
        from videl.utils.interactive_settings import engine
        session = await engine.begin_preview(chat_id=-10011, actor_id=111, target_chat_id=-10011,
            workflow="approved_clear", values={"users": [101, 202]})
        await engine.bind_prompt(session.token, chat_id=-10011, actor_id=111, message_id=700)
        query = self._query(f"approve:clear:confirm:{session.token}")
        query.message.id = 700
        with patch.object(approve, "is_user_authorized", new=AsyncMock(side_effect=[True, False])), \
             patch("videl.utils.db.get_db") as get_db:
            await approve.approve_cbs(None, query)
        get_db.assert_not_called()
        self.assertIn("permission could not be verified", query.answer.call_args.args[0].lower())
        await engine.cancel(session.token, chat_id=-10011, actor_id=111)

    async def test_clear_confirmation_refuses_a_changed_list_without_mutating(self):
        from videl.utils.interactive_settings import engine
        session = await engine.begin_preview(chat_id=-10011, actor_id=111, target_chat_id=-10011,
            workflow="approved_clear", values={"users": [101, 202]})
        await engine.bind_prompt(session.token, chat_id=-10011, actor_id=111, message_id=700)
        query = self._query(f"approve:clear:confirm:{session.token}")
        query.message.id = 700
        with patch.object(approve, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(approve, "list_approved", return_value=[101, 202, 303]), \
             patch("videl.utils.db.get_db") as get_db:
            await approve.approve_cbs(None, query)
        get_db.assert_not_called()
        self.assertIn("changed or storage", query.answer.call_args.args[0].lower())
        await engine.cancel(session.token, chat_id=-10011, actor_id=111)

    async def test_clear_confirmation_deletes_only_reviewed_ids_and_is_single_use(self):
        from videl.utils.interactive_settings import engine
        from unittest.mock import MagicMock
        session = await engine.begin_preview(chat_id=-10011, actor_id=111, target_chat_id=-10011,
            workflow="approved_clear", values={"users": [101, 202]})
        await engine.bind_prompt(session.token, chat_id=-10011, actor_id=111, message_id=700)
        collection = MagicMock()
        collection.count_documents.return_value = 0
        database = {"approved": collection}
        query = self._query(f"approve:clear:confirm:{session.token}")
        query.message.id = 700
        with patch.object(approve, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(approve, "list_approved", return_value=[101, 202]), \
             patch("videl.utils.db.get_db", return_value=database):
            await approve.approve_cbs(None, query)
            self.assertEqual(collection.delete_many.call_args.args[0],
                             {"chat": -10011, "user": {"$in": [101, 202]}})
            self.assertIn("cleared", query.answer.call_args.args[0].lower())
            retry = self._query(f"approve:clear:confirm:{session.token}")
            retry.message.id = 700
            await approve.approve_cbs(None, retry)
            self.assertEqual(collection.delete_many.call_count, 1)


if __name__ == "__main__":
    unittest.main()
