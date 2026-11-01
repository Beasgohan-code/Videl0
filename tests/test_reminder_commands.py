"""Reminder commands keep personal reminder text private and button actions real."""
from __future__ import annotations

import asyncio
import unittest
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pyrogram.enums import ChatType

from videl.app.router import CommandError
from videl.plugins import reminder


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def sort(self, *_args):
        return self

    def limit(self, _count):
        return self.rows


class Collection:
    def __init__(self, rows=(), deleted=0, fail=False, deleted_results=None):
        self.rows = list(rows)
        self.deleted = deleted
        self.deleted_results = list(deleted_results or [])
        self.fail = fail
        self.delete_calls = []

    def find(self, selector):
        self.selector = selector
        return Cursor(self.rows)

    def delete_many(self, selector):
        self.delete_calls.append(selector)
        if self.fail:
            raise RuntimeError("database unavailable")
        deleted = self.deleted_results.pop(0) if self.deleted_results else self.deleted
        return SimpleNamespace(deleted_count=deleted)


class ReminderCommandTests(unittest.IsolatedAsyncioTestCase):
    def context(self, *, private=True, arguments=""):
        user_id = 42
        chat = SimpleNamespace(
            id=user_id if private else -100123,
            type=ChatType.PRIVATE if private else ChatType.SUPERGROUP,
        )
        message = SimpleNamespace(chat=chat, message_thread_id=None, from_user=SimpleNamespace(id=user_id))
        return SimpleNamespace(
            message=message,
            user=SimpleNamespace(id=user_id),
            command=SimpleNamespace(arguments=arguments),
        )

    async def test_reminder_list_refuses_to_disclose_personal_text_in_group(self):
        with patch.object(reminder, "_store", return_value=Collection()):
            with self.assertRaisesRegex(CommandError, "private"):
                await reminder.reminders(self.context(private=False))

    async def test_private_list_has_a_real_clear_all_action(self):
        store = Collection([{"text": "private appointment", "due_at": None}])
        with patch.object(reminder, "_store", return_value=store):
            screen = await reminder.reminders(self.context())
        buttons = [button for row in screen.keyboard.inline_keyboard for button in row]
        clear = next(button for button in buttons if button.text == "Clear all")
        self.assertEqual(clear.callback_data, "reminders:clear")
        self.assertIn("private appointment", screen.html)

    async def test_clear_button_checks_private_actor_and_bot_message_before_deleting(self):
        store = Collection(deleted=2)
        actor = SimpleNamespace(id=42)
        message = SimpleNamespace(
            chat=SimpleNamespace(id=42, type=ChatType.PRIVATE),
            from_user=SimpleNamespace(id=900), id=71,
        )
        query = SimpleNamespace(
            data="reminders:clear", message=message, from_user=actor,
            answer=AsyncMock(),
        )
        client = SimpleNamespace(me=SimpleNamespace(id=900))
        with patch.object(reminder, "_store", return_value=store), \
             patch.object(reminder, "rich_edit", new=AsyncMock()) as edit:
            await reminder.reminders_callback(client, query)
        self.assertEqual(store.delete_calls, [{"user_id": 42, "status": "pending"}])
        query.answer.assert_awaited_once()
        edit.assert_awaited_once()

    async def test_replayed_clear_is_idempotent_and_reports_the_current_result(self):
        store = Collection(deleted_results=[2, 0])
        query = SimpleNamespace(
            data="reminders:clear",
            message=SimpleNamespace(chat=SimpleNamespace(id=42, type=ChatType.PRIVATE),
                                    from_user=SimpleNamespace(id=900), id=75),
            from_user=SimpleNamespace(id=42), answer=AsyncMock(),
        )
        client = SimpleNamespace(me=SimpleNamespace(id=900))
        with patch.object(reminder, "_store", return_value=store):
            with patch.object(reminder, "rich_edit", new=AsyncMock()):
                await reminder.reminders_callback(client, query)
                await reminder.reminders_callback(client, query)
        self.assertEqual(store.delete_calls, [
            {"user_id": 42, "status": "pending"},
            {"user_id": 42, "status": "pending"},
        ])
        self.assertEqual(query.answer.await_count, 2)
        self.assertIn("Cancelled 2", query.answer.await_args_list[0].args[0])
        self.assertIn("No pending", query.answer.await_args_list[1].args[0])

    async def test_forged_or_wrong_chat_button_never_mutates_storage(self):
        store = Collection(deleted=1)
        query = SimpleNamespace(
            data="reminders:clear",
            message=SimpleNamespace(chat=SimpleNamespace(id=-100123, type=ChatType.SUPERGROUP),
                                    from_user=SimpleNamespace(id=900), id=72),
            from_user=SimpleNamespace(id=42), answer=AsyncMock(),
        )
        client = SimpleNamespace(me=SimpleNamespace(id=900))
        with patch.object(reminder, "_store", return_value=store):
            await reminder.reminders_callback(client, query)
        self.assertEqual(store.delete_calls, [])
        query.answer.assert_awaited_once()

    async def test_database_failure_is_not_reported_as_a_successful_clear(self):
        store = Collection(fail=True)
        query = SimpleNamespace(
            data="reminders:clear",
            message=SimpleNamespace(chat=SimpleNamespace(id=42, type=ChatType.PRIVATE),
                                    from_user=SimpleNamespace(id=900), id=73),
            from_user=SimpleNamespace(id=42), answer=AsyncMock(),
        )
        client = SimpleNamespace(me=SimpleNamespace(id=900))
        with patch.object(reminder, "_store", return_value=store), \
             patch.object(reminder, "rich_edit", new=AsyncMock()) as edit:
            await reminder.reminders_callback(client, query)
        self.assertEqual(len(store.delete_calls), 1)
        edit.assert_not_awaited()
        query.answer.assert_awaited_once()
        self.assertTrue(query.answer.await_args.kwargs.get("show_alert"))

    async def test_other_users_cannot_use_a_private_clear_button(self):
        store = Collection(deleted=1)
        query = SimpleNamespace(
            data="reminders:clear",
            message=SimpleNamespace(chat=SimpleNamespace(id=42, type=ChatType.PRIVATE),
                                    from_user=SimpleNamespace(id=900), id=74),
            from_user=SimpleNamespace(id=99), answer=AsyncMock(),
        )
        client = SimpleNamespace(me=SimpleNamespace(id=900))
        with patch.object(reminder, "_store", return_value=store):
            await reminder.reminders_callback(client, query)
        self.assertEqual(store.delete_calls, [])
        query.answer.assert_awaited_once()


class ReminderWriter:
    def __init__(self, *, pending=0, count_error=None, insert_error=None, delete_error=None):
        self.pending = pending
        self.count_error = count_error
        self.insert_error = insert_error
        self.delete_error = delete_error
        self.inserted = []

    def count_documents(self, selector):
        if self.count_error:
            raise self.count_error
        self.count_selector = selector
        return self.pending

    def insert_one(self, document):
        if self.insert_error:
            raise self.insert_error
        self.inserted.append(document)
        return SimpleNamespace(inserted_id="reminder-1")

    def delete_many(self, selector):
        if self.delete_error:
            raise self.delete_error
        self.delete_selector = selector
        return SimpleNamespace(deleted_count=0)


class ReminderWriteTests(unittest.IsolatedAsyncioTestCase):
    def context(self, arguments):
        actor = SimpleNamespace(id=42, first_name="Ari")
        message = SimpleNamespace(
            from_user=actor,
            chat=SimpleNamespace(id=42, type=ChatType.PRIVATE),
            message_thread_id=None,
        )
        return SimpleNamespace(
            message=message, user=actor,
            command=SimpleNamespace(arguments=arguments),
        )

    async def test_invalid_duration_is_rejected_before_database_access(self):
        store = ReminderWriter()
        with patch.object(reminder, "_store", return_value=store):
            screen = await reminder.remind(self.context("5s too soon"))
        self.assertIn("10 seconds", screen.html)
        self.assertFalse(hasattr(store, "count_selector"))
        self.assertEqual(store.inserted, [])

    async def test_limit_boundary_does_not_insert_an_extra_reminder(self):
        store = ReminderWriter(pending=reminder.MAX_PENDING)
        with patch.object(reminder, "_store", return_value=store):
            screen = await reminder.remind(self.context("10m call"))
        self.assertIn("20 pending reminders", screen.html)
        self.assertEqual(store.count_selector, {"user_id": 42, "status": "pending"})
        self.assertEqual(store.inserted, [])

    async def test_count_database_error_has_safe_recovery_and_does_not_insert(self):
        store = ReminderWriter(count_error=RuntimeError("database unavailable"))
        with patch.object(reminder, "_store", return_value=store):
            with self.assertRaisesRegex(CommandError, "could not check"):
                await reminder.remind(self.context("10m call"))
        self.assertEqual(store.inserted, [])

    async def test_ambiguous_insert_failure_tells_user_to_check_before_retrying(self):
        store = ReminderWriter(insert_error=RuntimeError("write timeout"))
        with patch.object(reminder, "_store", return_value=store):
            with self.assertRaisesRegex(CommandError, "Check /reminders before retrying"):
                await reminder.remind(self.context("10m call"))
        self.assertEqual(store.inserted, [])

    async def test_reminder_list_read_error_is_actionable_not_a_raw_exception(self):
        class BrokenRead:
            def find(self, _selector):
                raise RuntimeError("database unavailable")

        with patch.object(reminder, "_store", return_value=BrokenRead()):
            with self.assertRaisesRegex(CommandError, "could not load"):
                await reminder.reminders(self.context(""))

    async def test_forget_write_error_does_not_claim_success_and_suggests_verification(self):
        store = ReminderWriter(delete_error=RuntimeError("write timeout"))
        with patch.object(reminder, "_store", return_value=store):
            with self.assertRaisesRegex(CommandError, "Check /reminders before retrying"):
                await reminder.forget(self.context("all"))


class ConcurrentReminderWriter:
    def __init__(self, pending):
        self.pending = pending
        self.lock = threading.Lock()
        self.inserted = []

    def count_documents(self, _selector):
        with self.lock:
            return self.pending

    def insert_one(self, document):
        with self.lock:
            self.pending += 1
            self.inserted.append(dict(document))
            return SimpleNamespace(inserted_id=f"reminder-{self.pending}")


class ReminderAdmissionConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_admissions_cannot_overshoot_limit_in_one_bot_process(self):
        store = ConcurrentReminderWriter(reminder.MAX_PENDING - 1)
        contexts = [ReminderWriteTests().context("10m call") for _ in range(2)]
        with patch.object(reminder, "_store", return_value=store), \
             patch.object(reminder, "_schedule"):
            screens = await asyncio.gather(*(reminder.remind(ctx) for ctx in contexts))
        self.assertEqual(len(store.inserted), 1)
        self.assertEqual(store.pending, reminder.MAX_PENDING)
        self.assertEqual(sum("I will message this chat when the time is up." in screen.html for screen in screens), 1)
        self.assertEqual(sum(f"{reminder.MAX_PENDING} pending reminders" in screen.html for screen in screens), 1)
