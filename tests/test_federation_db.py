"""Federation storage must fail closed and never replace a same-ID federation."""
import unittest
from unittest.mock import patch

import mongomock

from videl.utils import db
from videl.modules import federation


class FederationStorageTests(unittest.TestCase):
    def setUp(self):
        self.mongo = mongomock.MongoClient()
        self.database = self.mongo.videl
        self.patch_db = patch.object(db, "_db", self.database)
        self.patch_db.start()

    def tearDown(self):
        self.patch_db.stop()
        self.mongo.close()

    def test_create_does_not_overwrite_an_existing_federation(self):
        self.database.feds.insert_one({"_id": "videl_elite", "name": "Original", "owner": 41})

        self.assertFalse(db.create_fed("videl_elite", "Replacement", 99))
        self.assertEqual(self.database.feds.find_one({"_id": "videl_elite"})["name"], "Original")
        self.assertEqual(self.database.feds.find_one({"_id": "videl_elite"})["owner"], 41)

    def test_create_stores_a_new_owner_and_membership_sentinel(self):
        self.assertTrue(db.create_fed("videl_elite", "Videl Elite", 41))
        self.assertEqual(self.database.feds.find_one({"_id": "videl_elite"})["owner"], 41)
        self.assertIsNotNone(self.database.fed_chats.find_one({"fed": "videl_elite", "chat": -1}))


class FederationPermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_and_admin_are_live_telegram_roles_only(self):
        class Client:
            async def get_chat_member(self, chat_id, user_id):
                return type("Member", (), {"status": "administrator"})()

        self.assertTrue(await federation._is_telegram_admin(Client(), -1001, 8))

        class RegularMember:
            async def get_chat_member(self, chat_id, user_id):
                return type("Member", (), {"status": "member"})()

        self.assertFalse(await federation._is_telegram_admin(RegularMember(), -1001, 8))
        self.assertFalse(await federation._is_telegram_admin(Client(), -1001, None))

    async def test_bot_must_have_restrict_members_to_join_a_federation(self):
        class Client:
            async def get_me(self):
                return type("Me", (), {"id": 777})()

            async def get_chat_member(self, chat_id, user_id):
                return type("Member", (), {"status": "administrator", "can_restrict_members": False})()

        self.assertFalse(await federation._bot_can_ban(Client(), -1001))

        class EnforcingBot(Client):
            async def get_chat_member(self, chat_id, user_id):
                return type("Member", (), {"status": "administrator", "can_restrict_members": True})()

        self.assertTrue(await federation._bot_can_ban(EnforcingBot(), -1001))


if __name__ == "__main__":
    unittest.main()
