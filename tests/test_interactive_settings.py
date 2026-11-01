import asyncio
import unittest

from videl.utils.interactive_settings import InteractionEngine, InputError, Step


class InteractionEngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = 100.0
        self.engine = InteractionEngine(clock=lambda: self.now)

    async def begin(self, **kwargs):
        defaults = dict(chat_id=-100, actor_id=7, target_chat_id=-100,
                        workflow="test", steps=(Step("value", "Send a value"),))
        defaults.update(kwargs)
        return await self.engine.begin(**defaults)

    async def test_sessions_are_isolated_by_actor_and_target(self):
        first = await self.begin()
        second = await self.begin(actor_id=8)
        third = await self.begin(chat_id=8, target_chat_id=-200)
        self.assertNotEqual(first.token, second.token)
        self.assertNotEqual(first.token, third.token)
        with self.assertRaises(RuntimeError):
            await self.begin()
        self.assertIsNone(await self.engine.get(first.token, chat_id=-100, actor_id=8))
        self.assertIsNone(await self.engine.get(first.token, chat_id=-101, actor_id=7))

    async def test_capture_requires_bound_prompt_and_matching_scope(self):
        session = await self.begin()
        await self.engine.bind_prompt(session.token, chat_id=-100, actor_id=7, message_id=50)
        self.assertEqual((await self.engine.capture(session.token, chat_id=-100, actor_id=7,
                         target_chat_id=-200, reply_to_message_id=50, value="ok")).status, "unauthorized")
        self.assertEqual((await self.engine.capture(session.token, chat_id=-100, actor_id=7,
                         target_chat_id=-100, reply_to_message_id=49, value="ok")).status, "stale")
        result = await self.engine.capture(session.token, chat_id=-100, actor_id=7,
                    target_chat_id=-100, reply_to_message_id=50, value="  hello  ")
        self.assertEqual(result.status, "preview")
        self.assertEqual(result.session.values, {"value": "hello"})

    async def test_validation_supports_text_media_url_number_duration_selection_and_buttons(self):
        self.assertEqual(Step("x", "", "text", max_length=3).validate(" abc "), "abc")
        self.assertEqual(Step("x", "", "media").validate({"type": "photo", "file_id": "f1"}),
                         {"type": "photo", "file_id": "f1"})
        self.assertIsNone(Step("x", "", "media", required=False).validate(None))
        self.assertEqual(Step("x", "", "url").validate("https://example.org/path"), "https://example.org/path")
        self.assertEqual(Step("x", "", "number", minimum=1, maximum=10).validate("5"), 5)
        self.assertEqual(Step("x", "", "duration", maximum=3600).validate("30m"), 1800)
        self.assertEqual(Step("x", "", "selection", choices=("yes", "no")).validate("yes"), "yes")
        self.assertEqual(Step("x", "", "buttons").validate("Docs | https://example.org"),
                         [{"label": "Docs", "target": "https://example.org"}])
        with self.assertRaises(InputError):
            Step("x", "", "media").validate({"type": "unknown", "file_id": "f1"})
        with self.assertRaises(InputError):
            Step("x", "", "url").validate("http://example.org")
        with self.assertRaises(InputError):
            Step("x", "", "buttons").validate("Admin | callback:promote")

    async def test_wizard_preview_edit_and_cancel(self):
        session = await self.begin(steps=(Step("name", "Name"), Step("count", "Count", "number", minimum=1)))
        await self.engine.bind_prompt(session.token, chat_id=-100, actor_id=7, message_id=1)
        first = await self.engine.capture(session.token, chat_id=-100, actor_id=7, target_chat_id=-100,
                                         reply_to_message_id=1, value="Rule")
        self.assertEqual(first.status, "accepted")
        await self.engine.bind_prompt(session.token, chat_id=-100, actor_id=7, message_id=2)
        invalid = await self.engine.capture(session.token, chat_id=-100, actor_id=7, target_chat_id=-100,
                                            reply_to_message_id=2, value="not a number")
        self.assertEqual(invalid.status, "invalid")
        self.assertEqual(invalid.session.index, 1)
        final = await self.engine.capture(session.token, chat_id=-100, actor_id=7, target_chat_id=-100,
                                          reply_to_message_id=2, value="3")
        self.assertEqual(final.status, "preview")
        await self.engine.bind_prompt(session.token, chat_id=-100, actor_id=7, message_id=3)
        edited = await self.engine.edit_again(session.token, chat_id=-100, actor_id=7, message_id=3)
        self.assertEqual(edited.phase, "input")
        self.assertEqual(edited.index, 0)
        self.assertEqual(edited.values, {})
        self.assertTrue(await self.engine.cancel(session.token, chat_id=-100, actor_id=7))

    async def test_confirm_rechecks_permission_and_failed_save_keeps_preview(self):
        session = await self.begin()
        await self.engine.bind_prompt(session.token, chat_id=-100, actor_id=7, message_id=1)
        await self.engine.capture(session.token, chat_id=-100, actor_id=7, target_chat_id=-100,
                                  reply_to_message_id=1, value="new")
        await self.engine.bind_prompt(session.token, chat_id=-100, actor_id=7, message_id=2)
        checks = []
        async def authorize(chat, actor):
            checks.append((chat, actor))
            return True
        async def failed_save(snapshot):
            self.assertEqual(snapshot.values["value"], "new")
            return False
        outcome, retained = await self.engine.commit(session.token, chat_id=-100, actor_id=7,
                    target_chat_id=-100, message_id=2, authorize=authorize, save=failed_save)
        self.assertEqual(outcome, "save_failed")
        self.assertEqual(retained.phase, "preview")
        self.assertEqual(checks, [(-100, 7)])
        async def save(snapshot): return True
        outcome, retained = await self.engine.commit(session.token, chat_id=-100, actor_id=7,
                    target_chat_id=-100, message_id=2, authorize=authorize, save=save)
        self.assertEqual(outcome, "saved")
        self.assertIsNone(retained)

    async def test_timeout_and_restart_semantics(self):
        session = await self.begin(timeout_seconds=3)
        self.now += 3
        self.assertIsNone(await self.engine.get(session.token, chat_id=-100, actor_id=7))
        # A newly-created engine models a process restart: no draft is recoverable.
        session = await self.begin()
        restarted = InteractionEngine(clock=lambda: self.now)
        self.assertIsNone(await restarted.get(session.token, chat_id=-100, actor_id=7))

    async def test_concurrent_confirm_is_claimed_once(self):
        session = await self.begin()
        await self.engine.bind_prompt(session.token, chat_id=-100, actor_id=7, message_id=1)
        await self.engine.capture(session.token, chat_id=-100, actor_id=7, target_chat_id=-100,
                                  reply_to_message_id=1, value="new")
        await self.engine.bind_prompt(session.token, chat_id=-100, actor_id=7, message_id=2)
        entered = asyncio.Event()
        release = asyncio.Event()
        async def authorize(chat, actor):
            entered.set()
            await release.wait()
            return True
        async def save(snapshot): return True
        pending = asyncio.create_task(self.engine.commit(session.token, chat_id=-100, actor_id=7,
                    target_chat_id=-100, message_id=2, authorize=authorize, save=save))
        await entered.wait()
        duplicate = await self.engine.commit(session.token, chat_id=-100, actor_id=7,
                    target_chat_id=-100, message_id=2, authorize=authorize, save=save)
        self.assertEqual(duplicate[0], "stale")
        release.set()
        self.assertEqual((await pending)[0], "saved")


if __name__ == "__main__":
    unittest.main()
