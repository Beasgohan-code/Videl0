"""Offline behavioral tests for lock and anti-flood enforcement."""
import asyncio
import re
import time
import unittest
from collections import OrderedDict, deque
from types import SimpleNamespace
from unittest.mock import patch

from videl.plugins import locks


class ProtectionTests(unittest.TestCase):
    def setUp(self):
        self.settings = {}
        self.deleted = 0
        self.admin = False

        async def is_admin(*args):
            return self.admin

        async def delete():
            self.deleted += 1

        self.message = SimpleNamespace(
            chat=SimpleNamespace(id=-100123, type="supergroup"),
            from_user=SimpleNamespace(id=123),
            text="hello",
            caption=None,
            entities=[],
            caption_entities=[],
            photo=None,
            video=None,
            audio=None,
            document=None,
            animation=None,
            voice=None,
            video_note=None,
            sticker=None,
            poll=None,
            forward_date=None,
            forward_from=None,
            forward_from_chat=None,
            delete=delete,
        )
        self.patches = [
            patch.object(locks.base, "is_admin", is_admin),
            patch.object(locks.base, "get_setting", lambda chat_id, key, default=None: self.settings.get(key, default)),
            patch.object(locks, "is_approved", lambda *args: False),
        ]
        for item in self.patches:
            item.start()
        locks._FLOOD_WINDOWS.clear()

    def tearDown(self):
        for item in self.patches:
            item.stop()

    def run_handler(self):
        asyncio.run(locks.mgmt_content_checker(None, self.message))

    def test_antispam_enforces_only_after_the_configured_burst(self):
        self.settings["antispam"] = True
        for _ in range(locks.FLOOD_LIMIT):
            self.run_handler()
        self.assertEqual(self.deleted, 0)
        self.run_handler()
        self.assertEqual(self.deleted, 1)

    def test_antispam_disabled_does_not_delete(self):
        for _ in range(10):
            self.run_handler()
        self.assertEqual(self.deleted, 0)

    def test_forward_lock_and_legacy_key(self):
        self.message.forward_date = 123
        for key in ("lock_forward", "lock_forwards"):
            self.settings = {key: True}
            self.run_handler()
        self.assertEqual(self.deleted, 2)

    def test_poll_lock(self):
        self.settings["lock_polls"] = True
        self.message.poll = object()
        self.run_handler()
        self.assertEqual(self.deleted, 1)

    def test_admin_bypasses_protections(self):
        self.admin = True
        self.settings["lock_forwards"] = True
        self.message.forward_date = 123
        self.run_handler()
        self.assertEqual(self.deleted, 0)

    def test_private_chat_is_ignored(self):
        self.settings["lock_links"] = True
        self.message.chat.type = "private"
        self.message.text = "https://example.com"
        self.run_handler()
        self.assertEqual(self.deleted, 0)
