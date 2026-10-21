"""Concurrent group edits: a stale panel save is refused, not silently applied.

Two panels open on the same group used to be last-write-wins: the second save
quietly undid the first, and the switch that flipped back had no explanation.
These tests pin the revision contract that replaced that.
"""
import importlib
import unittest
from unittest.mock import Mock, patch

import mongomock

from videl.plugins import base as plugin_base
from videl.utils import group_view as view
from videl.utils import settings_store

CID = -1001234567


class SettingsRevisionTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["served_chats"].insert_one({"_id": CID})
        self.api = Mock(side_effect=self.telegram)
        self.service = view.GroupView(self.db, self.api)
        # The automation helpers read the module-level connection, not a
        # parameter, so point that at the test database too.
        self.connection = patch("videl.utils.db._db", self.db)
        self.connection.start()

    def tearDown(self):
        self.connection.stop()

    def telegram(self, method, payload):
        if method == "getMe":
            return 200, {"ok": True, "result": {"id": 777, "first_name": "Videl", "username": "ExampleBot"}}
        if method == "getChatMember":
            return 200, {"ok": True, "result": {
                "status": "administrator", "can_delete_messages": True,
                "can_restrict_members": True, "can_pin_messages": True, "can_manage_chat": True}}
        if method == "getChat":
            return 200, {"ok": True, "result": {
                "id": CID, "title": "Test group", "type": "supergroup",
                "permissions": {"can_send_messages": True}}}
        if method == "getChatMemberCount":
            return 200, {"ok": True, "result": 42}
        return 200, {"ok": True, "result": True}

    def act(self, **body):
        return self.service.act({"chat_id": CID, **body})

    # ── the token itself ────────────────────────────────────────────────────
    def test_a_group_that_was_never_saved_reads_revision_zero(self):
        self.assertEqual(self.service.describe(CID)["revision"], 0)
        self.assertEqual(self.service.read(CID)["revision"], 0)

    def test_a_save_returns_the_revision_the_panel_must_send_next(self):
        result = self.act(action="settings", revision=0, settings={"lock_links": True})
        self.assertTrue(result["ok"])
        self.assertEqual(result["revision"], 1)
        self.assertEqual(self.service.describe(CID)["revision"], 1)
        self.assertTrue(self.service.snapshot(CID)["lock_links"])

    def test_a_stale_save_is_refused_and_the_winner_survives(self):
        self.act(action="settings", revision=0, settings={"lock_links": True})
        with self.assertRaises(view.ViewError) as caught:
            self.act(action="settings", revision=0, settings={"lock_links": False})
        error = caught.exception
        self.assertEqual(error.status, 409)
        self.assertTrue(getattr(error, "conflict", False))
        self.assertEqual(error.revision, 1)
        self.assertTrue(self.service.snapshot(CID)["lock_links"],
                        "the refused write must not reach MongoDB")

    def test_the_panel_can_retry_from_the_revision_it_was_told(self):
        self.act(action="settings", revision=0, settings={"lock_links": True})
        with self.assertRaises(view.ViewError) as caught:
            self.act(action="settings", revision=0, settings={"lock_links": False})
        retry = self.act(action="settings", revision=caught.exception.revision,
                         settings={"lock_links": False})
        self.assertTrue(retry["ok"])
        self.assertEqual(retry["revision"], 2)
        self.assertFalse(self.service.snapshot(CID)["lock_links"])

    def test_a_revision_must_be_a_non_negative_integer(self):
        for value in ("3", -1, True, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(view.ViewError) as caught:
                    self.act(action="settings", revision=value, settings={"lock_links": True})
                self.assertEqual(caught.exception.status, 400)

    # ── every writer shares the counter ─────────────────────────────────────
    def test_locks_presets_and_limits_share_one_counter(self):
        self.act(action="preset", revision=0, preset="strict")
        with self.assertRaises(view.ViewError) as caught:
            self.act(action="warn_limit", revision=0, limit=4)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.act(action="warn_limit", revision=1, limit=4)["revision"], 2)

    def test_protection_toggles_are_guarded_too(self):
        first = self.act(action="protect", revision=0, settings={"lock_stickers": True})
        self.assertEqual(first["revision"], 1)
        with self.assertRaises(view.ViewError) as caught:
            self.act(action="protect", revision=0, settings={"lock_stickers": False})
        self.assertEqual(caught.exception.status, 409)
        self.assertTrue(self.service.snapshot(CID)["lock_stickers"])

    def test_automation_writes_are_guarded_and_reported(self):
        first = self.act(action="automation", revision=0,
                         quiet_hours={"enabled": True, "start": "22:00", "end": "07:00"})
        self.assertTrue(first["automation"]["quiet_hours"]["enabled"])
        self.assertEqual(first["revision"], 1)
        with self.assertRaises(view.ViewError) as caught:
            self.act(action="automation", revision=0, escalation={"action": "mute"})
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(caught.exception.revision, 1)

    def test_a_change_made_from_telegram_makes_an_open_panel_stale(self):
        self.act(action="settings", revision=0, settings={"lock_links": True})
        # /warnlimit and the other commands write through the plugin helper.
        with patch("videl.plugins.base.get_db", return_value=self.db):
            self.assertTrue(plugin_base.set_settings(CID, {"warn_threshold": 6}))
        with self.assertRaises(view.ViewError) as caught:
            self.act(action="warn_limit", revision=1, limit=4)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(caught.exception.revision, 2)
        self.assertEqual(self.service.snapshot(CID)["warn_threshold"], 6)

    def test_a_scheduler_tick_does_not_invalidate_a_panel_edit(self):
        self.act(action="settings", revision=0, settings={"lock_links": True})
        from videl.utils import db as db_module

        db_module.set_protection_state(CID, {"active": True, "applied": ["lock_links"]})
        db_module.set_protection_state(CID, {"active": False})
        self.assertEqual(settings_store.revision(CID, self.db), 1,
                         "runtime state is not an owner edit")
        self.assertEqual(self.act(action="settings", revision=1,
                                  settings={"lock_links": False})["revision"], 2)

    # ── backups ─────────────────────────────────────────────────────────────
    def test_an_import_is_refused_when_the_group_moved_on(self):
        self.act(action="settings", revision=0, settings={"lock_links": True})
        backup = self.service.export_group(CID)["backup"]
        self.act(action="settings", revision=1, settings={"lock_links": False})
        with self.assertRaises(view.ViewError) as caught:
            self.service.import_group(CID, view.OWNER_ID,
                                      {"document": backup, "dry_run": False, "revision": 1})
        self.assertEqual(caught.exception.status, 409)
        self.assertFalse(self.service.snapshot(CID)["lock_links"],
                         "a refused import applies nothing")
        applied = self.service.import_group(CID, view.OWNER_ID,
                                            {"document": backup, "dry_run": False, "revision": 2})
        self.assertTrue(applied["ok"])
        self.assertTrue(self.service.snapshot(CID)["lock_links"])

    def test_an_import_without_a_revision_still_works(self):
        self.act(action="settings", revision=0, settings={"lock_links": True})
        backup = self.service.export_group(CID)["backup"]
        backup["settings"]["lock_links"] = False
        applied = self.service.import_group(CID, view.OWNER_ID, {"document": backup, "dry_run": False})
        self.assertTrue(applied["ok"])
        self.assertFalse(self.service.snapshot(CID)["lock_links"])
        self.assertGreaterEqual(settings_store.revision(CID, self.db), 2)


class RevisionRouteTests(unittest.TestCase):
    """The 409 has to reach the panel with the revision it should reload from."""

    @classmethod
    def setUpClass(cls):
        cls.api = importlib.import_module("videl.__main__")
        cls.client = cls.api._flask.test_client()

    def telegram(self, method, payload):
        if method == "getMe":
            return 200, {"ok": True, "result": {"id": 777, "first_name": "Videl", "username": "ExampleBot"}}
        if method == "getChatMember":
            return 200, {"ok": True, "result": {"status": "administrator", "can_delete_messages": True,
                                               "can_restrict_members": True, "can_manage_chat": True}}
        return 200, {"ok": True, "result": True}

    def test_a_conflict_reaches_the_panel_as_409_with_the_current_revision(self):
        db = mongomock.MongoClient().videl
        db["served_chats"].insert_one({"_id": CID})
        db["mgmt_chat_settings"].insert_one({"chat_id": CID, "lock_links": True, "revision": 3})
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), \
                patch.object(self.api, "_bot_api", side_effect=self.telegram), \
                patch("videl.utils.db._db", db):
            response = self.client.post(
                f"/internal/chat/{CID}",
                json={"action": "settings", "revision": 2, "settings": {"lock_links": False}},
                headers={"X-Videl-Internal": "offline-test-only"},
            )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json["ok"])
        self.assertTrue(response.json["conflict"])
        self.assertEqual(response.json["revision"], 3)
        self.assertTrue(db["mgmt_chat_settings"].find_one({"chat_id": CID})["lock_links"])
