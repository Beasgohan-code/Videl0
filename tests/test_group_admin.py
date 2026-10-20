"""Group manager contract: typed settings, presets and the internal endpoints.

No live Telegram, no live database — mongomock plus a mocked Bot API callable.
"""
import unittest
from unittest.mock import Mock, patch

import mongomock

from videl.utils import group_view as view

CID = -1001234567


class GroupAdminTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["served_chats"].insert_one({"_id": CID})
        self.owner = {"status": "administrator", "can_delete_messages": True, "can_restrict_members": True}
        self.api = Mock(side_effect=self.telegram)
        self.service = view.GroupView(self.db, self.api)

    def telegram(self, method, payload):
        if method == "getMe":
            result = {"id": 777, "first_name": "Videl", "username": "ExampleBot"}
        elif method == "getChatMember":
            result = self.owner if payload["user_id"] == view.OWNER_ID else self.owner
        elif method == "getChat":
            result = {"id": CID, "title": "Test group", "type": "supergroup", "permissions": {"can_send_messages": True}}
        elif method == "getChatMemberCount":
            result = 42
        else:
            result = True
        return 200, {"ok": True, "result": result}

    def act(self, **body):
        return self.service.act({"chat_id": CID, **body})

    # ── reads ───────────────────────────────────────────────────────────────
    def test_snapshot_covers_every_enforced_lock(self):
        snapshot = self.service.snapshot(CID)
        for key in view.LOCK_KEYS:
            self.assertIn(key, snapshot)
        self.assertEqual(len(view.BOOL_SETTINGS), 21)
        self.assertIs(snapshot["welcome_enabled"], True, "the bot greets new members unless told otherwise")
        self.assertEqual(snapshot["warn_threshold"], 3)
        self.assertEqual(snapshot["blacklist_mode"], "del")

    def test_describe_returns_settings_community_and_presets(self):
        self.db["mgmt_notes"].insert_one({"chat_id": CID, "name": "rules", "type": "text", "content": "hi"})
        self.db["mgmt_filters"].insert_one({"chat_id": CID, "keyword": "hello", "reply": "hey"})
        self.db["blacklist"].insert_one({"chat": CID, "trigger": "spam", "mode": "del"})
        self.db["approved"].insert_one({"chat": CID, "user": 5})
        payload = self.service.describe(CID)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["chat"]["title"], "Test group")
        self.assertEqual([item["name"] for item in payload["community"]["notes"]], ["rules"])
        self.assertEqual([item["keyword"] for item in payload["community"]["filters"]], ["hello"])
        self.assertEqual([item["trigger"] for item in payload["community"]["blacklist"]], ["spam"])
        self.assertEqual(payload["community"]["approved"], [5])
        self.assertEqual(set(payload["presets"]), {"relaxed", "balanced", "strict", "lockdown"})
        self.assertEqual(payload["problems"], [])

    def test_describe_rejects_unserved_and_private_chats(self):
        with self.assertRaises(view.ViewError) as error:
            self.service.describe(-100999)
        self.assertEqual(error.exception.status, 404)
        with self.assertRaises(view.ViewError):
            self.service.describe(42)

    # ── writes ──────────────────────────────────────────────────────────────
    def test_preset_writes_only_supported_booleans(self):
        outcome = self.act(action="preset", preset="strict")
        document = self.db["mgmt_chat_settings"].find_one({"chat_id": CID})
        self.assertTrue(document["lock_media"])
        self.assertTrue(document["captcha_enabled"])
        self.assertFalse(document["lock_locations"])
        self.assertEqual(outcome["preset"], "strict")
        self.assertEqual(outcome["settings"], self.service.snapshot(CID))
        with self.assertRaises(view.ViewError):
            self.act(action="preset", preset="everything")

    def test_warn_limit_is_bounded_and_persisted_where_the_bot_reads_it(self):
        self.assertEqual(self.act(action="warn_limit", limit=5)["settings"]["warn_threshold"], 5)
        for bad in (0, 11, -1):
            with self.assertRaises(view.ViewError):
                self.act(action="warn_limit", limit=bad)

    def test_unknown_protection_key_is_rejected(self):
        with self.assertRaises(view.ViewError):
            self.act(action="protect", settings={"nonsense": True})
        with self.assertRaises(view.ViewError):
            self.act(action="protect", settings={"lock_links": "yes"})

    def test_welcome_text_and_toggle(self):
        outcome = self.act(action="welcome", text="Welcome {name}", enabled=False)
        self.assertEqual(outcome["settings"]["welcome_message"], "Welcome {name}")
        self.assertFalse(outcome["settings"]["welcome_enabled"])
        with self.assertRaises(view.ViewError):
            self.act(action="welcome", text="x" * 1001)

    def test_blacklist_adds_removes_and_sets_mode(self):
        self.act(action="blacklist_add", trigger="  Spam  ")
        self.assertEqual([item["trigger"] for item in self.db["blacklist"].find({"chat": CID})], ["spam"])
        self.act(action="blacklist_mode", mode="mute")
        self.assertEqual(self.service.snapshot(CID)["blacklist_mode"], "mute")
        with self.assertRaises(view.ViewError):
            self.act(action="blacklist_mode", mode="nuke")
        self.act(action="blacklist_remove", trigger="spam")
        self.assertEqual(self.db["blacklist"].count_documents({"chat": CID}), 0)

    def test_note_filter_and_approval_removal(self):
        self.db["mgmt_notes"].insert_one({"chat_id": CID, "name": "rules", "type": "text"})
        self.db["mgmt_filters"].insert_one({"chat_id": CID, "keyword": "hi", "reply": "hello"})
        self.db["approved"].insert_one({"chat": CID, "user": 9})
        self.db["mgmt_warnings"].insert_one({"chat_id": CID, "user_id": 9, "count": 2, "reasons": []})
        self.act(action="note_delete", name="RULES")
        self.act(action="filter_delete", keyword="HI")
        self.act(action="approved_remove", user_id=9)
        self.act(action="warn_reset", user_id=9)
        for name, query in (("mgmt_notes", {"chat_id": CID}), ("mgmt_filters", {"chat_id": CID}),
                            ("approved", {"chat": CID}), ("mgmt_warnings", {"chat_id": CID})):
            self.assertEqual(self.db[name].count_documents(query), 0, name)

    def test_settings_are_rechecked_against_telegram_permissions(self):
        self.owner = {"status": "member"}
        with self.assertRaises(view.ViewError) as error:
            self.act(action="preset", preset="strict")
        self.assertEqual(error.exception.status, 403)


class InternalRoutesTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["served_chats"].insert_one({"_id": CID})
        self.db["mgmt_chat_settings"].insert_one({"chat_id": CID, "lock_links": True, "warn_threshold": 4})
        self.db["served_chats"].insert_one({"_id": -100999})
        import config
        import videl.__main__ as backend
        self.backend = backend
        self.previous = getattr(config, "WEBAPP_SECRET", "")
        self.previous_token = getattr(config, "BOT_TOKEN", "")
        config.WEBAPP_SECRET = "test-secret"
        config.BOT_TOKEN = "123:offline-fixture"
        self.patch_db = patch("videl.utils.db.get_db", return_value=self.db)
        self.patch_db.start()
        self.api = Mock(side_effect=self.telegram)
        self.patch_api = patch.object(backend, "_bot_api", self.api)
        self.patch_api.start()
        self.client = backend._flask.test_client()

    def tearDown(self):
        import config
        config.WEBAPP_SECRET = self.previous
        config.BOT_TOKEN = self.previous_token
        self.patch_api.stop()
        self.patch_db.stop()

    def telegram(self, method, payload):
        if method == "getMe":
            result = {"id": 777, "first_name": "Videl", "username": "ExampleBot"}
        elif method == "getChatMember":
            result = {"status": "administrator", "can_delete_messages": True}
        elif method == "getChat":
            result = {"id": payload["chat_id"], "title": "Test group", "type": "supergroup"}
        elif method == "getChatMemberCount":
            result = 7
        else:
            result = True
        return 200, {"ok": True, "result": result}

    def headers(self, secret="test-secret"):
        return {"X-Videl-Internal": secret}

    def test_chat_list_requires_the_shared_secret(self):
        self.assertEqual(self.client.get("/internal/chats").status_code, 403)
        self.assertEqual(self.client.get("/internal/chats", headers=self.headers("wrong")).status_code, 403)

    def test_chat_list_returns_typed_settings_and_counts(self):
        response = self.client.get("/internal/chats", headers=self.headers())
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        row = payload["chats"][0]
        self.assertEqual(row["id"], CID)
        self.assertIs(row["settings"]["lock_links"], True)
        self.assertEqual(row["settings"]["warn_threshold"], 4)
        self.assertEqual(row["warn_limit"], 4)
        self.assertEqual(row["counts"]["warns"], 0)
        self.assertIs(row["available"], True)

    def test_detail_and_action_endpoints(self):
        detail = self.client.get(f"/internal/chat/{CID}", headers=self.headers())
        self.assertEqual(detail.status_code, 200)
        self.assertIn("community", detail.get_json())
        update = self.client.post(f"/internal/chat/{CID}", headers=self.headers(),
                                  json={"action": "warn_limit", "limit": 6})
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.get_json()["settings"]["warn_threshold"], 6)
        missing = self.client.get("/internal/chat/-100999", headers=self.headers())
        self.assertEqual(missing.status_code, 200)

    def test_bulk_preset_updates_each_group_and_reports_failures(self):
        response = self.client.post("/internal/chats/bulk", headers=self.headers(),
                                    json={"chat_ids": [CID, -100999], "action": "preset", "preset": "balanced"})
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["updated"], 2)
        self.assertTrue(all(item["ok"] for item in payload["results"]))
        self.assertTrue(self.db["mgmt_chat_settings"].find_one({"chat_id": -100999})["lock_links"])

    def test_bulk_settings_patch_is_validated(self):
        ok = self.client.post("/internal/chats/bulk", headers=self.headers(),
                              json={"chat_ids": [CID], "action": "settings", "settings": {"lock_media": True}})
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(self.db["mgmt_chat_settings"].find_one({"chat_id": CID})["lock_media"])
        bad = self.client.post("/internal/chats/bulk", headers=self.headers(),
                               json={"chat_ids": [CID], "action": "settings", "settings": {"made_up": True}})
        self.assertEqual(bad.status_code, 200)
        self.assertFalse(bad.get_json()["results"][0]["ok"])

    def test_bulk_rejects_empty_or_oversized_selection(self):
        for body in ({"chat_ids": [], "action": "preset", "preset": "balanced"},
                     {"chat_ids": list(range(16)), "action": "preset", "preset": "balanced"},
                     {"chat_ids": [CID], "action": "delete_everything"}):
            self.assertEqual(self.client.post("/internal/chats/bulk", headers=self.headers(), json=body).status_code, 400)
