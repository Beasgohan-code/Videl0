import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import mongomock
from pyrogram.enums import ChatType

from videl.plugins import sudo
from videl.modules import block
from videl.utils import db

OWNER_ID = 6265999542


class SudoDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.database = mongomock.MongoClient().videl
        self.db_patch = patch.object(db, "_db", self.database)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def test_sudo_roster_is_unique_and_revocable(self):
        self.assertEqual(db.add_sudo_user(701, OWNER_ID), "added")
        self.assertEqual(db.add_sudo_user(701, OWNER_ID), "exists")
        self.assertTrue(db.is_sudo_user(701))
        self.assertEqual([row["_id"] for row in db.get_sudo_users()], [701])
        self.database.blocked_users.insert_one({"_id": 701})
        self.assertFalse(db.is_sudo_user(701), "a blocked account must not retain operator access")
        self.database.blocked_users.delete_one({"_id": 701})
        self.assertTrue(db.remove_sudo_user(701))
        self.assertFalse(db.is_sudo_user(701))
        self.assertFalse(db.remove_sudo_user(701))

    def test_sudo_membership_fails_closed_when_database_is_unavailable(self):
        with patch.object(db, "_db", None):
            self.assertFalse(db.is_sudo_user(701))
            self.assertIsNone(db.get_sudo_users())
            self.assertIsNone(db.add_sudo_user(701, OWNER_ID))


class SudoScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_keeps_original_access_but_sudo_is_private_only(self):
        owner = NS(from_user=NS(id=OWNER_ID), chat=NS(type=ChatType.GROUP))
        operator_private = NS(from_user=NS(id=701), chat=NS(type=ChatType.PRIVATE))
        operator_group = NS(from_user=NS(id=701), chat=NS(type=ChatType.SUPERGROUP))
        member_private = NS(from_user=NS(id=702), chat=NS(type=ChatType.PRIVATE))
        with patch.object(block, "is_sudo_user", side_effect=lambda uid: uid == 701):
            self.assertTrue(await block._owner_or_sudo(None, None, owner))
            self.assertTrue(await block._owner_or_sudo(None, None, operator_private))
            self.assertFalse(await block._owner_or_sudo(None, None, operator_group))
            self.assertFalse(await block._owner_or_sudo(None, None, member_private))

    def test_only_owner_private_commands_manage_sudo(self):
        self.assertEqual({command.name for command in sudo.COMMANDS}, {"addsudo", "delsudo", "rmsudo", "sudolist", "sudohelp"})
        self.assertTrue(all(command.policy == "owner" for command in sudo.COMMANDS if command.name != "sudohelp"))
        self.assertTrue(all(command.category == "owner" for command in sudo.COMMANDS if command.name != "sudohelp"))
        from videl.utils.command_catalog import visible_commands
        public = {item["name"] for item in visible_commands()}
        private_owner = {item["name"] for item in visible_commands(owner=True)}
        self.assertTrue({"addsudo", "delsudo", "rmsudo", "sudolist", "gblock", "gunblock", "ublock", "uunblock", "blocklist"}.isdisjoint(public))
        self.assertTrue({"addsudo", "delsudo", "rmsudo", "sudolist", "gblock", "gunblock", "ublock", "uunblock", "blocklist"}.issubset(private_owner))

    async def test_owner_can_add_a_single_numeric_user_and_scope_is_explicit(self):
        ctx = NS(
            command=NS(arguments="701", name="addsudo"),
            message=NS(reply_to_message=None),
            client=NS(get_users=AsyncMock()),
            user=NS(id=OWNER_ID),
        )
        with patch.object(sudo, "get_sudo_users", return_value=[]), \
             patch.object(sudo, "add_sudo_user", return_value="added") as add, \
             patch.object(sudo, "record_bot"):
            screen = await sudo.add_sudo(ctx)
        add.assert_called_once_with(701, OWNER_ID)
        self.assertIn("/gblock", screen.html)
        self.assertIn("does not grant Telegram administrator rights", screen.html)

    async def test_inline_remove_requires_owner_private_and_bot_authored_panel(self):
        message = NS(
            chat=NS(id=OWNER_ID, type=ChatType.PRIVATE),
            from_user=NS(id=9000, is_bot=True),
        )
        query = NS(
            message=message,
            from_user=NS(id=OWNER_ID),
            data="sudoadmin:remove:701",
            answer=AsyncMock(),
        )
        client = NS(me=NS(id=9000), get_me=AsyncMock())
        with patch.object(sudo, "remove_sudo_user", return_value=True), \
             patch.object(sudo, "get_sudo_users", return_value=[]), \
             patch.object(sudo, "record_bot"), \
             patch.object(sudo, "rich_edit", new=AsyncMock()) as edit:
            await sudo.sudo_inline_callback(client, query)
        query.answer.assert_awaited_once_with("Sudo access removed")
        edit.assert_awaited_once()

    async def test_inline_remove_refuses_group_and_non_owner_callbacks(self):
        message = NS(chat=NS(type=ChatType.SUPERGROUP), from_user=NS(id=9000, is_bot=True))
        query = NS(message=message, from_user=NS(id=701), data="sudoadmin:remove:702", answer=AsyncMock())
        with patch.object(sudo, "remove_sudo_user") as remove:
            await sudo.sudo_inline_callback(NS(me=NS(id=9000)), query)
        remove.assert_not_called()
        self.assertTrue(query.answer.call_args.kwargs["show_alert"])


if __name__ == "__main__":
    unittest.main()
