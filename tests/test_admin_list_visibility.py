import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from videl.modules import approve, blocklist


class AdminListVisibilityTests(unittest.IsolatedAsyncioTestCase):
    def _message(self):
        return SimpleNamespace(chat=SimpleNamespace(id=-10011), from_user=SimpleNamespace(id=111))

    async def test_approved_roster_is_not_disclosed_to_non_admin(self):
        with patch.object(approve, "is_user_authorized", new=AsyncMock(return_value=False)), \
             patch.object(approve, "_approved_list_view") as render, \
             patch.object(approve, "rich_send", new=AsyncMock()) as send:
            await approve.approved_list(None, self._message())
        render.assert_not_called()
        send.assert_not_awaited()

    async def test_blacklist_configuration_and_sticker_ids_are_admin_only(self):
        for handler, storage_name in ((blocklist.listbl_cmd, "get_blacklist"),
                                      (blocklist.list_bl_stickers_cmd, "list_bl_stickers")):
            with self.subTest(handler=handler.__name__), \
                 patch.object(blocklist, "is_user_authorized", new=AsyncMock(return_value=False)), \
                 patch.object(blocklist, storage_name) as read, \
                 patch.object(blocklist, "rich_send", new=AsyncMock()) as send:
                await handler(None, self._message())
                read.assert_not_called()
                send.assert_not_awaited()


class BlacklistClearConfirmationTests(unittest.IsolatedAsyncioTestCase):
    def _query(self, data):
        return SimpleNamespace(data=data, message=SimpleNamespace(id=700, chat=SimpleNamespace(id=-10011)),
            from_user=SimpleNamespace(id=111), answer=AsyncMock())

    async def test_clear_previews_without_mutation_and_confirmation_clears_only_reviewed_group(self):
        from videl.utils.interactive_settings import engine
        rows = [{"chat": -10011, "trigger": "spam"}, {"chat": -10011, "trigger": "scam"}]
        query = self._query("bl:clear")
        with patch.object(blocklist, "is_user_authorized", new=AsyncMock(return_value=True)), \
             patch.object(blocklist, "get_blacklist", return_value=rows), \
             patch.object(blocklist, "rich_edit", new=AsyncMock()) as edit, \
             patch("videl.utils.db.get_db") as get_db:
            await blocklist.bl_cbs(None, query)
            callback = edit.await_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data
            token = callback.rsplit(":", 1)[-1]
            session = await engine.get(token, chat_id=-10011, actor_id=111, target_chat_id=-10011)
            self.assertEqual(session.workflow, "blacklist_clear")
            self.assertEqual(session.values["triggers"], ["scam", "spam"])
            self.assertIn("2 current blacklist entries", edit.await_args.args[1])
            get_db.assert_not_called()

            collection = MagicMock()
            collection.count_documents.return_value = 0
            database = {"blacklist": collection}
            confirm = self._query(f"bl:clear:confirm:{token}")
            with patch("videl.utils.db.get_db", return_value=database):
                await blocklist.bl_cbs(None, confirm)
            self.assertEqual(collection.delete_many.call_args.args[0],
                {"chat": -10011, "trigger": {"$in": ["scam", "spam"]}})
            self.assertIn("cleared", confirm.answer.call_args.args[0].lower())
            retry = self._query(f"bl:clear:confirm:{token}")
            with patch("videl.utils.db.get_db", return_value=database):
                await blocklist.bl_cbs(None, retry)
            self.assertEqual(collection.delete_many.call_count, 1)
        await engine.cancel(token, chat_id=-10011, actor_id=111)

    async def test_clear_confirmation_rechecks_role_and_rejects_changed_snapshot(self):
        from videl.utils.interactive_settings import engine
        for authorized, rows in ((False, None), (True, [{"trigger": "spam"}, {"trigger": "scam"}, {"trigger": "new"}])):
            session = await engine.begin_preview(chat_id=-10011, actor_id=111, target_chat_id=-10011,
                workflow="blacklist_clear", values={"triggers": ["scam", "spam"]})
            await engine.bind_prompt(session.token, chat_id=-10011, actor_id=111, message_id=700)
            query = self._query(f"bl:clear:confirm:{session.token}")
            auth = AsyncMock(side_effect=[True, authorized])
            with patch.object(blocklist, "is_user_authorized", new=auth), \
                 patch.object(blocklist, "get_blacklist", return_value=rows or []), \
                 patch("videl.utils.db.get_db") as get_db:
                await blocklist.bl_cbs(None, query)
            get_db.assert_not_called()
            if not authorized:
                self.assertIn("permission could not be verified", query.answer.call_args.args[0].lower())
            else:
                self.assertIn("changed", query.answer.call_args.args[0].lower())
            await engine.cancel(session.token, chat_id=-10011, actor_id=111)


if __name__ == "__main__":
    unittest.main()
