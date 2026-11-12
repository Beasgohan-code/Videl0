import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mongomock
from videl.plugins import settings
from videl.utils.interactive_settings import engine


class ConnectedEscalationEditorTests(unittest.IsolatedAsyncioTestCase):
    CHAT, USER, OTHER_USER, BOT = -100844, 844, 845, 999

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["mgmt_chat_settings"].insert_one({"chat_id": self.CHAT, "revision": 0,
            "automation": {"escalation": {"enabled": True, "action": "ban", "mute_hours": 6,
                "decay_days": 0, "ladder": [], "review_severe": False}, "quiet_hours": {"enabled": False},
                "protection": {"enabled": False}}})
        self.serial = 100
        async def send(*args, **kwargs):
            self.serial += 1
            return SimpleNamespace(id=self.serial)
        async def get_member(chat_id, user_id):
            if user_id == self.BOT:
                return SimpleNamespace(status="administrator", can_restrict_members=True)
            return SimpleNamespace(status="administrator")
        self.client = SimpleNamespace(me=SimpleNamespace(id=self.BOT), send_message=AsyncMock(side_effect=send),
            get_chat_member=AsyncMock(side_effect=get_member))

    async def asyncTearDown(self):
        for actor in (self.USER, self.OTHER_USER):
            await engine.cancel_owner(chat_id=actor, actor_id=actor, target_chat_id=self.CHAT)
            await engine.cancel_owner(chat_id=self.CHAT, actor_id=actor, target_chat_id=self.CHAT)

    def _query(self, *, actor=None, group=False, token=None, action=None, message_id=12):
        actor = self.USER if actor is None else actor
        chat_id = self.CHAT if group else actor
        if token is None:
            data = f"settings:{self.CHAT}:warn_escalation:edit:v0"
        else:
            data = f"warn_escalation_edit:{token}:{action}"
        return SimpleNamespace(data=data, message=SimpleNamespace(chat=SimpleNamespace(
            id=chat_id, type="group" if group else "private"), id=message_id),
            from_user=SimpleNamespace(id=actor), answer=AsyncMock())

    async def _start(self, *, actor=None, group=False):
        actor = self.USER if actor is None else actor
        query = self._query(actor=actor, group=group)
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
            new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.settings_callback(self.client, query)
        session = await engine.for_owner(chat_id=(self.CHAT if group else actor), actor_id=actor,
                                         target_chat_id=self.CHAT)
        self.assertEqual(session.workflow, "warning_escalation")
        return session

    async def _reply(self, session, value):
        message = SimpleNamespace(chat=SimpleNamespace(id=session.chat_id),
            from_user=SimpleNamespace(id=session.actor_id), text=value,
            reply_to_message=SimpleNamespace(id=session.expected_message_id))
        with patch("videl.utils.db._db", self.db):
            await settings.connected_escalation_reply(self.client, message)
        return await engine.get(session.token, chat_id=session.chat_id, actor_id=session.actor_id)

    async def _complete(self, session, *, enabled="on", ladder="mute-kick-ban", action="mute",
                        mute_hours="12", decay_days="30", review="on"):
        for value in (enabled, ladder, action, mute_hours, decay_days, review):
            session = await self._reply(session, value)
        return session

    def _callback(self, session, action, *, actor=None, group=False):
        actor = session.actor_id if actor is None else actor
        return self._query(actor=actor, group=group, token=session.token, action=action,
                           message_id=session.expected_message_id)

    async def _save(self, session, *, resolver=None):
        query = self._callback(session, "save", group=session.chat_id == self.CHAT)
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target",
            new=resolver or AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.connected_escalation_callback(self.client, query)
        return query

    async def test_private_editor_previews_and_saves_existing_automation_schema(self):
        session = await self._complete(await self._start())
        self.assertEqual(session.phase, "preview")
        preview = self.client.send_message.await_args_list[-1].args[1]
        self.assertIn(f"Target group: <code>{self.CHAT}</code>", preview)
        self.assertIn("No settings have changed yet", preview)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["automation"]["escalation"]["action"], "ban")
        query = await self._save(session)
        stored = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})
        escalation = stored["automation"]["escalation"]
        self.assertEqual(escalation["ladder"], ["mute", "kick", "ban"])
        self.assertEqual(escalation["mute_hours"], 12)
        self.assertEqual(escalation["decay_days"], 30)
        self.assertTrue(escalation["review_severe"])
        self.assertEqual(query.answer.call_args.args[0], "Warning-escalation settings saved.")
        self.assertFalse(stored["automation"]["quiet_hours"]["enabled"])
        self.assertFalse(stored["automation"]["protection"]["enabled"])

    async def test_cancel_invalid_values_and_timeout_do_not_write(self):
        session = await self._start()
        session = await self._reply(session, "yes")
        self.assertEqual(session.index, 0)
        self.assertIsNone(session.values.get("enabled"))
        for value in ("off", "single", "none", "0", "0", "off"):
            session = await self._reply(session, value)
        cancel = self._callback(session, "cancel")
        with patch("videl.utils.db._db", self.db):
            await settings.connected_escalation_callback(self.client, cancel)
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)

        session = await self._complete(await self._start())
        clock = engine._clock
        try:
            engine._clock = lambda: 10**12
            expired = self._callback(session, "save")
            with patch("videl.utils.db._db", self.db):
                await settings.connected_escalation_callback(self.client, expired)
        finally:
            engine._clock = clock
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)

    async def test_connection_revocation_lost_admin_and_missing_bot_right_prevent_save(self):
        session = await self._complete(await self._start())
        denied = await self._save(session, resolver=AsyncMock(return_value=(None, "admin role revoked")))
        self.assertIn("permission changed", denied.answer.call_args.args[0])
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)

        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        session = await self._complete(await self._start())
        async def no_restrict(chat_id, user_id):
            return SimpleNamespace(status="administrator", can_restrict_members=False)
        self.client.get_chat_member.side_effect = no_restrict
        denied = await self._save(session)
        self.assertIn("Restrict Members", denied.answer.call_args.args[0])
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)

    async def test_storage_failure_does_not_claim_success(self):
        session = await self._complete(await self._start())
        query = self._callback(session, "save")
        with patch("videl.utils.db.get_db", return_value=None), patch("videl.app.connections.connected_target",
            new=AsyncMock(return_value=(SimpleNamespace(id=self.CHAT), None))):
            await settings.connected_escalation_callback(self.client, query)
        self.assertIn("No success was reported", query.answer.call_args.args[0])
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 0)

    async def test_stale_revision_and_repeated_confirmation_are_safe(self):
        session = await self._complete(await self._start())
        self.db["mgmt_chat_settings"].update_one({"chat_id": self.CHAT}, {"$set": {"revision": 1}})
        stale = await self._save(session)
        self.assertIn("changed since", stale.answer.call_args.args[0])
        stale_escalation = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["automation"]["escalation"]
        self.assertEqual(stale_escalation["ladder"], [])
        self.assertEqual(stale_escalation["action"], "ban")

        await engine.cancel_owner(chat_id=self.USER, actor_id=self.USER, target_chat_id=self.CHAT)
        self.db["mgmt_chat_settings"].update_one({"chat_id": self.CHAT}, {"$set": {"revision": 0}})
        session = await self._complete(await self._start())
        first, second = self._callback(session, "save"), self._callback(session, "save")
        async def slow_resolver(*args, **kwargs):
            await asyncio.sleep(0.02)
            return SimpleNamespace(id=self.CHAT), None
        with patch("videl.utils.db._db", self.db), patch("videl.app.connections.connected_target", new=slow_resolver):
            await asyncio.gather(settings.connected_escalation_callback(self.client, first),
                                 settings.connected_escalation_callback(self.client, second))
        self.assertEqual(self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["revision"], 1)
        self.assertEqual(sum(q.answer.call_args.args[0] == "Warning-escalation settings saved." for q in (first, second)), 1)

    async def test_group_context_prompt_and_confirmation_remain_group_scoped(self):
        session = await self._complete(await self._start(group=True), enabled="off", ladder="single",
            action="none", mute_hours="6", decay_days="0", review="off")
        query = self._callback(session, "save", group=True)
        with patch("videl.utils.db._db", self.db):
            await settings.connected_escalation_callback(self.client, query)
        saved = self.db["mgmt_chat_settings"].find_one({"chat_id": self.CHAT})["automation"]["escalation"]
        self.assertFalse(saved["enabled"])
        self.assertEqual(saved["action"], "none")
        self.assertEqual(query.answer.call_args.args[0], "Warning-escalation settings saved.")


if __name__ == "__main__":
    unittest.main()
