"""Away-status browsing is bounded, paginated and group-context aware."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pyrogram.enums import ChatType

from videl.app.router import CommandError
from videl.plugins import afk


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.offset = 0
        self.limit_count = len(self.rows)

    def sort(self, *_args):
        return self

    def skip(self, count):
        self.offset = count
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def __iter__(self):
        return iter(self.rows[self.offset:self.offset + self.limit_count])


class Store:
    def __init__(self, rows, fail=False):
        self.rows = list(rows)
        self.fail = fail
        self.find_calls = []

    def count_documents(self, selector):
        if self.fail:
            raise RuntimeError("database unavailable")
        return len(self.rows)

    def find(self, selector):
        self.find_calls.append(selector)
        if self.fail:
            raise RuntimeError("database unavailable")
        return Cursor(self.rows)


class AfkListTests(unittest.IsolatedAsyncioTestCase):
    def context(self, argument=""):
        return SimpleNamespace(
            message=SimpleNamespace(
                chat=SimpleNamespace(id=-100123, type=ChatType.SUPERGROUP),
                from_user=SimpleNamespace(id=42),
            ),
            command=SimpleNamespace(arguments=argument),
        )

    def rows(self, count):
        return [{"name": f"User {index}", "reason": "Away", "since": None}
                for index in range(1, count + 1)]

    async def test_lists_are_paginated_and_report_total_and_bot_wide_scope(self):
        store = Store(self.rows(12))
        with patch.object(afk, "_store", return_value=store):
            first = await afk.afk_list(self.context("1"))
            second = await afk.afk_list(self.context("2"))
        self.assertIn("User 1", first.html)
        self.assertIn("User 10", first.html)
        self.assertNotIn("User 11", first.html)
        self.assertIn("User 11", second.html)
        self.assertIn("User 12", second.html)
        self.assertIn("12", second.html)
        self.assertIn("across chats", second.html.casefold())
        first_callbacks = [button.callback_data for row in first.keyboard.inline_keyboard for button in row]
        second_callbacks = [button.callback_data for row in second.keyboard.inline_keyboard for button in row]
        self.assertIn("afklist:1", first_callbacks)
        self.assertIn("afklist:0", second_callbacks)

    async def test_invalid_page_is_rejected_without_database_access(self):
        store = Store(self.rows(1))
        with patch.object(afk, "_store", return_value=store):
            for argument in ("0", "-1", "next", "1 2"):
                with self.subTest(argument=argument):
                    screen = await afk.afk_list(self.context(argument))
                    self.assertIn("/afklist [page]", screen.html)
        self.assertEqual(store.find_calls, [])

    async def test_page_beyond_end_clamps_to_last_page(self):
        store = Store(self.rows(12))
        with patch.object(afk, "_store", return_value=store):
            screen = await afk.afk_list(self.context("999"))
        self.assertIn("User 12", screen.html)
        self.assertNotIn("User 1</td>", screen.html)

    async def test_database_failure_returns_recovery_guidance(self):
        with patch.object(afk, "_store", return_value=Store(self.rows(1), fail=True)):
            with self.assertRaisesRegex(CommandError, "temporarily unavailable"):
                await afk.afk_list(self.context())

    async def test_pagination_callback_is_group_only_and_requires_videl_message(self):
        store = Store(self.rows(12))
        actor = SimpleNamespace(id=42)
        query = SimpleNamespace(
            data="afklist:1",
            message=SimpleNamespace(
                chat=SimpleNamespace(id=-100123, type=ChatType.SUPERGROUP),
                from_user=SimpleNamespace(id=900), id=7,
            ),
            from_user=actor,
            answer=AsyncMock(),
        )
        client = SimpleNamespace(me=SimpleNamespace(id=900))
        with patch.object(afk, "_store", return_value=store), \
             patch.object(afk, "rich_edit", new=AsyncMock()) as edit:
            await afk.afk_list_callback(client, query)
        query.answer.assert_awaited_once()
        edit.assert_awaited_once()
        self.assertIn("User 11", edit.await_args.args[1])

        query.message.chat = SimpleNamespace(id=42, type=ChatType.PRIVATE)
        store.find_calls.clear()
        with patch.object(afk, "_store", return_value=store):
            await afk.afk_list_callback(client, query)
        self.assertEqual(store.find_calls, [])
        self.assertTrue(query.answer.await_args.kwargs.get("show_alert"))
