"""A group admin's manager can do their job and nothing else.

The dangerous version of this feature reuses the owner's GroupView unchanged:
every action is then performed and recorded as the owner, and `backup_import`
is one request away. These tests pin the actor and the scope.
"""
import unittest
from unittest.mock import patch

import mongomock

from videl.utils import chat_admins, manager
from videl.utils.group_view import GroupView, ViewError

CHAT = -1001234567890
OTHER = -1009876543210
OWNER = 6265999542
ADMIN = 501
MEMBER = 502
BOT = 900


def member(user, status, **rights):
    payload = {"user": {"id": user, "is_bot": user == BOT, "first_name": f"u{user}"},
               "status": status}
    payload.update({key: bool(value) for key, value in rights.items()})
    return payload


class FakeTelegram:
    """Just enough Bot API for GroupView, with the permission facts we need."""

    def __init__(self):
        self.calls = []
        self.demoted = set()

    def __call__(self, method, payload):
        self.calls.append((method, dict(payload)))
        if method == "getMe":
            return 200, {"ok": True, "result": {"id": BOT, "is_bot": True, "username": "videlbot"}}
        if method == "getChat":
            chat = payload.get("chat_id")
            return 200, {"ok": True, "result": {
                "id": chat, "title": "Group A" if chat == CHAT else "Group B",
                "type": "supergroup", "member_count": 42,
                "permissions": {"can_send_messages": True}}}
        if method == "getChatMemberCount":
            return 200, {"ok": True, "result": 42}
        if method == "getChatMember":
            chat, user = int(payload.get("chat_id")), int(payload.get("user_id"))
            if user == OWNER:
                return 200, {"ok": True, "result": member(user, "creator")}
            if user == BOT:
                return 200, {"ok": True, "result": member(
                    user, "administrator", can_delete_messages=True,
                    can_restrict_members=True, can_invite_users=True,
                    can_pin_messages=True, can_manage_video_chats=True)}
            if chat == CHAT and user == ADMIN and user not in self.demoted:
                return 200, {"ok": True, "result": member(
                    user, "administrator", can_delete_messages=True,
                    can_restrict_members=True, can_invite_users=True,
                    can_pin_messages=True, can_manage_video_chats=False)}
            return 200, {"ok": True, "result": member(user, "member")}
        if method == "getChatAdministrators":
            return 200, {"ok": True, "result": [
                member(ADMIN, "administrator", can_delete_messages=True,
                       can_restrict_members=True, can_invite_users=True,
                       can_pin_messages=True),
                member(OWNER, "creator")]}
        return 200, {"ok": True, "result": True}


class ManagerAccessTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["served_chats"].insert_many([{"_id": CHAT}, {"_id": OTHER}])
        self.db["mgmt_chat_info"].insert_many([
            {"_id": CHAT, "title": "Group A", "type": "supergroup", "members": 42},
            {"_id": OTHER, "title": "Group B", "type": "supergroup", "members": 9},
        ])
        self.api = FakeTelegram()
        self.get_db = patch("videl.utils.db.get_db", lambda: self.db)
        self.get_db.start()
        self.addCleanup(self.get_db.stop)

    def test_an_admin_sees_their_group_with_the_admin_scope(self):
        payload = manager.describe(self.db, self.api, CHAT, ADMIN)
        self.assertEqual(payload["scope"], "admin")
        self.assertEqual(payload["chat"]["title"], "Group A")
        self.assertEqual(payload["actor"], ADMIN)
        self.assertTrue(payload["rights"]["can_delete_messages"])

    def test_a_member_of_the_group_is_not_an_admin(self):
        with self.assertRaises(ViewError) as caught:
            manager.describe(self.db, self.api, CHAT, MEMBER)
        self.assertEqual(caught.exception.status, 403)

    def test_an_admin_of_one_group_cannot_open_another(self):
        with self.assertRaises(ViewError) as caught:
            manager.describe(self.db, self.api, OTHER, ADMIN)
        self.assertEqual(caught.exception.status, 403)

    def test_an_admin_can_change_their_own_group_and_is_named_in_history(self):
        result = manager.act(self.db, self.api, CHAT, ADMIN,
                             {"action": "warn_limit", "limit": 4})
        self.assertTrue(result["ok"])
        stored = self.db["mgmt_chat_settings"].find_one({"chat_id": CHAT})
        self.assertEqual(stored["warn_threshold"], 4)
        row = self.db["mgmt_audit"].find_one({"chat_id": CHAT, "action": "warn_limit"})
        self.assertIsNotNone(row, "a change without a history row is a change nobody can review")
        self.assertEqual(row["actor"], ADMIN, "the admin must not be recorded as the owner")
        self.assertEqual(row["source"], "web")

    def test_owner_only_actions_are_refused_before_anything_is_written(self):
        for body in ({"action": "backup_import", "backup": {"format": "x"}},
                     {"action": "backup_restore", "backup_id": "1"},
                     {"action": "recording", "enabled": True, "retention_days": 7},
                     {"action": "purge_history"}):
            with self.subTest(action=body["action"]):
                with self.assertRaises(ViewError) as caught:
                    manager.act(self.db, self.api, CHAT, ADMIN, body)
                self.assertEqual(caught.exception.status, 403)
                self.assertIn("owner", str(caught.exception).lower())
        self.assertIsNone(self.db["group_view_settings"].find_one({"_id": CHAT}))

    def test_the_owner_path_is_unchanged(self):
        payload = GroupView(self.db, self.api).describe(CHAT)
        self.assertEqual(payload["scope"], "owner")
        recording = GroupView(self.db, self.api).act(
            {"chat_id": CHAT, "action": "recording", "enabled": False, "retention_days": 7})
        self.assertTrue(recording["ok"])

    def test_the_admin_cache_is_used_instead_of_asking_telegram_every_time(self):
        first = chat_admins.check(self.db, self.api, CHAT, ADMIN)
        calls = len(self.api.calls)
        second = chat_admins.check(self.db, self.api, CHAT, ADMIN)
        self.assertTrue(first["admin"] and second["admin"])
        self.assertEqual(len(self.api.calls), calls, "a second read must hit the cache")

    def test_my_groups_lists_only_groups_where_the_person_administers(self):
        groups = chat_admins.my_groups(self.db, self.api, ADMIN, refresh=True)
        self.assertEqual([group["id"] for group in groups], [CHAT])
        self.assertEqual(groups[0]["title"], "Group A")
        self.assertEqual(chat_admins.my_groups(self.db, self.api, MEMBER, refresh=True), [])

    def test_a_demoted_admin_is_refused_on_the_next_write(self):
        manager.describe(self.db, self.api, CHAT, ADMIN)
        # Telegram now says this person is an ordinary member. The cache still
        # says admin, which is exactly the window a live rights check must close.
        self.api.demoted.add(ADMIN)
        with self.assertRaises(ViewError) as caught:
            manager.act(self.db, self.api, CHAT, ADMIN, {"action": "warn_limit", "limit": 5})
        self.assertEqual(caught.exception.status, 403)


if __name__ == "__main__":
    unittest.main()
