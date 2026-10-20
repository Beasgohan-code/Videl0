"""Offline behavioral tests for the active handler; no Telegram token or Mongo needed."""
import ast
import asyncio
from collections import OrderedDict, deque
from pathlib import Path
from types import SimpleNamespace
import logging
import re
import time
import unittest
from videl.utils.moderation import locked_message_reason


class ProtectionTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path("videl/modules/management_core.py").read_text())
        handler = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "mgmt_content_checker")
        handler.decorator_list = []
        self.settings = {}
        async def is_admin(*args): return False
        self.ns = dict(is_approved=lambda *args: False, locked_message_reason=locked_message_reason, Message=object, is_admin=is_admin, get_chat_setting=lambda cid, key, default=None: self.settings.get(key, default), time=time, deque=deque, _FLOOD_WINDOWS=OrderedDict(), _URL_RE=re.compile(r"https?://\S+"), logger=logging.getLogger(__name__))
        exec(compile(ast.Module(body=[handler], type_ignores=[]), "handler", "exec"), self.ns)
        self.deleted = 0
        async def delete(): self.deleted += 1
        self.message = SimpleNamespace(chat=SimpleNamespace(id=-100123, type="supergroup"), from_user=SimpleNamespace(id=123), text="hello", caption=None, entities=[], photo=None, video=None, audio=None, document=None, animation=None, voice=None, video_note=None, sticker=None, poll=None, forward_date=None, forward_from=None, forward_from_chat=None, delete=delete)

    def run_handler(self):
        asyncio.run(self.ns["mgmt_content_checker"](None, self.message))

    def test_antispam_enforces_only_after_six_messages(self):
        self.settings["antispam"] = True
        for _ in range(6): self.run_handler()
        self.assertEqual(self.deleted, 0)
        self.run_handler()
        self.assertEqual(self.deleted, 1)

    def test_antispam_disabled_does_not_delete(self):
        for _ in range(10): self.run_handler()
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
        async def is_admin(*args): return True
        self.ns["is_admin"] = is_admin
        self.settings["lock_forwards"] = True
        self.message.forward_date = 123
        self.run_handler()
        self.assertEqual(self.deleted, 0)


if __name__ == "__main__": unittest.main()
