"""Portable group backup contract.

A backup can be made for one group and applied to another, so the tests focus
on the two things that hurt when they fail: refusing foreign or malformed files,
and never applying a change before the owner has seen the diff.
"""
import unittest
from unittest.mock import Mock, patch

import mongomock

from videl.utils import audit
from videl.utils import group_view as view

CID = -1001234567
OTHER = -1007654321


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["served_chats"].insert_many([{"_id": CID}, {"_id": OTHER}])
        self.db["mgmt_chat_settings"].insert_one({
            "chat_id": CID,
            "lock_links": True,
            "antispam": True,
            "warn_threshold": 4,
            "welcome_message": "Welcome",
            "automation": {},
        })
        self.db["blacklist"].insert_many([
            {"chat": CID, "trigger": "spam", "mode": "del"},
            {"chat": CID, "trigger": "scam*", "mode": "warn"},
        ])
        self.db["disabled_cmds"].insert_one({"chat": CID, "cmd": "music"})
        self.db["mgmt_warnings"].insert_one({"chat_id": CID, "user_id": 5, "count": 2})
        self.view = view.GroupView(self.db, Mock(return_value=(500, {"ok": False})))
        self.patch_db = patch("videl.utils.db.get_db", return_value=self.db)
        self.patch_db.start()
        self.patch_global = patch("videl.utils.db._db", self.db)
        self.patch_global.start()

    def tearDown(self):
        self.patch_global.stop()
        self.patch_db.stop()

    def export(self, chat_id=CID):
        return self.view.export_group(chat_id)["backup"]

    def test_export_carries_configuration_and_no_member_data(self):
        backup = self.export()
        self.assertEqual(backup["format"], "videl-group-backup")
        self.assertEqual(backup["version"], 1)
        self.assertTrue(backup["settings"]["lock_links"])
        self.assertEqual(backup["settings"]["warn_threshold"], 4)
        self.assertEqual({row["trigger"] for row in backup["blacklist"]}, {"spam", "scam*"})
        self.assertEqual(backup["commands_disabled"], ["music"])
        serialised = str(backup)
        self.assertNotIn("mgmt_warnings", serialised)
        self.assertNotIn("count", serialised, "warnings are member data, not configuration")

    def test_import_is_a_dry_run_until_confirmed(self):
        document = self.export()
        document["settings"]["lock_links"] = False
        document["settings"]["lock_photos"] = True
        document["blacklist"] = [{"trigger": "spam", "mode": "del"}]
        document["commands_disabled"] = []
        preview = self.view.import_group(CID, 1, {"document": document})
        self.assertTrue(preview["dry_run"])
        self.assertFalse(preview["empty"])
        changes = preview["changes"]
        self.assertEqual(changes["settings"]["after"], {"lock_links": False, "lock_photos": True})
        self.assertEqual(changes["settings"]["before"]["lock_links"], True)
        self.assertEqual(changes["blacklist"], {"add": [], "remove": ["scam*"]})
        self.assertEqual(changes["commands"], {"disable": [], "enable": ["music"]})
        # Nothing was written yet.
        self.assertTrue(self.db["mgmt_chat_settings"].find_one({"chat_id": CID})["lock_links"])
        self.assertEqual(self.db["disabled_cmds"].count_documents({"chat": CID}), 1)

    def test_confirm_applies_and_saves_a_snapshot_for_undo(self):
        document = self.export(OTHER)  # a fresh group's empty config
        result = self.view.import_group(CID, 1, {"document": document, "dry_run": False})
        self.assertEqual(result["dry_run"], False) if "dry_run" in result else None
        self.assertIsNotNone(result["backup_id"])
        settings = self.db["mgmt_chat_settings"].find_one({"chat_id": CID})
        self.assertFalse(settings["lock_links"])
        self.assertEqual(self.db["blacklist"].count_documents({"chat": CID}), 0)
        self.assertEqual(self.db["disabled_cmds"].count_documents({"chat": CID}), 0)
        self.assertEqual(len(audit.recent(self.db, CID, kind="backup")), 1)
        # The saved snapshot still holds the state from before the import.
        from videl.utils.db import get_backup
        saved = get_backup(result["backup_id"])
        self.assertEqual(saved["chat"], CID)
        self.assertTrue(saved["data"]["settings"]["lock_links"])

    def test_restore_undoes_an_import(self):
        before = self.export()
        self.view.import_group(CID, 1, {"document": self.export(OTHER), "dry_run": False})
        self.assertFalse(self.db["mgmt_chat_settings"].find_one({"chat_id": CID})["lock_links"])
        restored = self.view.import_group(CID, 1, {"document": before, "dry_run": False})
        self.assertTrue(restored["ok"])
        settings = self.db["mgmt_chat_settings"].find_one({"chat_id": CID})
        self.assertTrue(settings["lock_links"])
        self.assertEqual(settings["warn_threshold"], 4)
        self.assertEqual({row["trigger"] for row in self.db["blacklist"].find({"chat": CID})},
                         {"spam", "scam*"})

    def test_restore_rejects_a_snapshot_belonging_to_another_group(self):
        from videl.utils.db import save_backup
        other_snapshot = save_backup(OTHER, self.export())
        with self.assertRaises(view.ViewError) as raised:
            self.view.restore_saved(CID, 1, {"backup_id": other_snapshot})
        self.assertEqual(raised.exception.status, 404)

    def test_foreign_and_malformed_files_are_refused(self):
        for document in ({"format": "something-else"}, {"format": "videl-group-backup", "version": 99},
                         {"format": "videl-group-backup", "version": 1},
                         {"format": "videl-group-backup", "version": 1, "settings": {}}):
            with self.assertRaises(view.ViewError):
                self.view.import_group(CID, 1, {"document": document})
        with self.assertRaises(view.ViewError):
            self.view.import_group(12345, 1, {"document": self.export()})

    def test_unknown_keys_are_ignored_rather_than_written(self):
        document = self.export()
        document["settings"]["not_a_setting"] = True
        document["settings"]["warn_threshold"] = 999
        document["settings"]["welcome_message"] = "x" * 5000
        document["blacklist"] = [{"trigger": "abuse", "mode": "not_a_mode"}]
        result = self.view.import_group(CID, 1, {"document": document, "dry_run": False})
        settings = self.db["mgmt_chat_settings"].find_one({"chat_id": CID})
        self.assertNotIn("not_a_setting", settings)
        self.assertEqual(settings["warn_threshold"], 10, "clamped to the supported range")
        self.assertEqual(len(settings["welcome_message"]), 1000, "truncated to the field limit")
        self.assertEqual(settings["welcome_message"], "x" * 1000)
        self.assertTrue(result["ok"])
        self.assertEqual(self.db["blacklist"].find_one({"chat": CID, "trigger": "abuse"})["mode"], "del")

    def test_an_identical_backup_reports_nothing_to_do(self):
        result = self.view.import_group(CID, 1, {"document": self.export(), "dry_run": False})
        self.assertTrue(result["empty"])
        self.assertIsNone(result["backup_id"])
        self.assertEqual(audit.recent(self.db, CID, kind="backup"), [])


class BackupRouteTests(unittest.TestCase):
    def setUp(self):
        import config
        from videl import __main__ as backend
        self.backend = backend
        self.previous = config.WEBAPP_SECRET
        config.WEBAPP_SECRET = "test-secret"
        self.db = mongomock.MongoClient().videl
        self.db["served_chats"].insert_one({"_id": CID})
        self.patch_db = patch("videl.utils.db.get_db", return_value=self.db)
        self.patch_db.start()
        self.patch_global = patch("videl.utils.db._db", self.db)
        self.patch_global.start()
        self.patch_api = patch.object(backend, "_bot_api", Mock(return_value=(500, {"ok": False})))
        self.patch_api.start()
        self.client = backend._flask.test_client()

    def tearDown(self):
        import config
        config.WEBAPP_SECRET = self.previous
        self.patch_api.stop()
        self.patch_global.stop()
        self.patch_db.stop()

    def test_export_requires_the_internal_secret(self):
        self.assertEqual(self.client.get(f"/internal/chat/{CID}/backup").status_code, 403)
        response = self.client.get(f"/internal/chat/{CID}/backup", headers={"X-Videl-Internal": "test-secret"})
        self.assertTrue(response.get_json()["ok"])

    def test_unknown_group_is_a_404(self):
        response = self.client.get(f"/internal/chat/{OTHER}/backup", headers={"X-Videl-Internal": "test-secret"})
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
