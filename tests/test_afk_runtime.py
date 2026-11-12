"""AFK notices are rate-limited atomically across concurrent message handlers."""
from __future__ import annotations

import asyncio
import copy
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from videl.plugins import afk


class AtomicAfkStore:
    def __init__(self, *, fail=False):
        self.document = {
            "user_id": 99,
            "reason": "at lunch",
            "since": None,
            "last_notice": {},
        }
        self.lock = threading.Lock()
        self.fail = fail
        self.queries = []

    def find_one_and_delete(self, _selector):
        return None

    def find_one_and_update(self, selector, update, *, return_document):
        self.queries.append((selector, update, return_document))
        if self.fail:
            raise RuntimeError("database unavailable")
        with self.lock:
            if selector.get("user_id") != 99:
                return None
            path, value = next(iter(update["$set"].items()))
            chat_id = path.split(".", 1)[1]
            previous = self.document["last_notice"].get(chat_id)
            allowed = previous is None or previous <= time.time() - afk.NOTICE_COOLDOWN
            if not allowed:
                return None
            old = copy.deepcopy(self.document)
            self.document["last_notice"][chat_id] = value
            return old


class AfkRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def message(self):
        return SimpleNamespace(
            from_user=SimpleNamespace(id=42, is_bot=False, first_name="Alice"),
            chat=SimpleNamespace(id=-10088),
            id=5,
            text="I will be back soon",
            caption=None,
            entities=[SimpleNamespace(user=SimpleNamespace(id=99))],
            caption_entities=[],
            reply_to_message=None,
        )

    async def test_simultaneous_mentions_send_only_one_away_notice_per_chat(self):
        store = AtomicAfkStore()
        reply = AsyncMock()
        with patch.object(afk, "_store", return_value=store), \
             patch.object(afk, "rich_reply", new=reply):
            await asyncio.gather(
                afk._afk_presence(None, self.message()),
                afk._afk_presence(None, self.message()),
            )
        self.assertEqual(reply.await_count, 1)
        self.assertEqual(len(store.queries), 2)
        selector, update, _return_document = store.queries[0]
        self.assertEqual(selector["user_id"], 99)
        self.assertTrue(any(f"last_notice.-10088" in condition for condition in selector["$or"]))
        self.assertIn("last_notice.-10088", update["$set"])

    async def test_database_failure_suppresses_notice_without_revealing_stale_data(self):
        store = AtomicAfkStore(fail=True)
        reply = AsyncMock()
        with patch.object(afk, "_store", return_value=store), \
             patch.object(afk, "rich_reply", new=reply):
            await afk._afk_presence(None, self.message())
        reply.assert_not_awaited()
        self.assertEqual(len(store.queries), 1)
