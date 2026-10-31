"""Automation, audit, health, inbox and federation contracts.

No live Telegram, no live database: mongomock plus a mocked Bot API callable.
Every test asserts something the running bot actually does — if a rule here
stops holding, the panel is lying to the owner.
"""
import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import quote

import mongomock

from videl.utils import audit, automation, group_health
from videl.utils import group_view as view
from videl.modules import protection_windows

CID = -1001234567
UTC = timezone.utc


class AutomationWindowTests(unittest.TestCase):
    def test_window_inside_one_day(self):
        quiet = {"enabled": True, "start": "09:00", "end": "17:00", "tz_offset": 0}
        self.assertTrue(automation.in_quiet_hours(quiet, datetime(2026, 5, 1, 12, tzinfo=UTC)))
        self.assertFalse(automation.in_quiet_hours(quiet, datetime(2026, 5, 1, 18, tzinfo=UTC)))
        self.assertFalse(automation.in_quiet_hours(quiet, datetime(2026, 5, 1, 8, 59, tzinfo=UTC)))

    def test_window_wraps_midnight(self):
        quiet = {"enabled": True, "start": "22:00", "end": "07:00", "tz_offset": 0}
        self.assertTrue(automation.in_quiet_hours(quiet, datetime(2026, 5, 1, 23, tzinfo=UTC)))
        self.assertTrue(automation.in_quiet_hours(quiet, datetime(2026, 5, 1, 3, tzinfo=UTC)))
        self.assertFalse(automation.in_quiet_hours(quiet, datetime(2026, 5, 1, 12, tzinfo=UTC)))

    def test_offset_is_applied_in_minutes(self):
        quiet = {"enabled": True, "start": "22:00", "end": "07:00", "tz_offset": 330}
        # 17:00 UTC is 22:30 in IST, so the window has just opened.
        self.assertTrue(automation.in_quiet_hours(quiet, datetime(2026, 5, 1, 17, 0, tzinfo=UTC)))
        self.assertFalse(automation.in_quiet_hours(quiet, datetime(2026, 5, 1, 14, 0, tzinfo=UTC)))

    def test_equal_bounds_are_off_not_all_day(self):
        quiet = {"enabled": True, "start": "22:00", "end": "22:00", "tz_offset": 0}
        self.assertFalse(automation.in_quiet_hours(quiet, datetime(2026, 5, 1, 22, 30, tzinfo=UTC)))

    def test_disabled_never_matches(self):
        quiet = {"enabled": False, "start": "00:00", "end": "23:59", "tz_offset": 0}
        self.assertFalse(automation.in_quiet_hours(quiet, datetime(2026, 5, 1, 12, tzinfo=UTC)))

    def test_normalisation_clamps_unsafe_values(self):
        quiet = automation.normalize_quiet({"enabled": "yes", "start": "99:99", "end": "6:5", "tz_offset": 9999})
        self.assertIs(quiet["enabled"], False)
        self.assertEqual(quiet["start"], "22:00", "an invalid start falls back to the default")
        self.assertEqual(quiet["end"], "06:05")
        self.assertEqual(quiet["tz_offset"], 840)

    def test_escalation_defaults_keep_the_historic_ban(self):
        config = automation.normalize_escalation({})
        self.assertIs(config["enabled"], True)
        self.assertEqual(config["action"], "ban")
        self.assertEqual(config["mute_hours"], 6)
        self.assertIs(config["review_severe"], False)
        self.assertIs(automation.normalize_escalation({"review_severe": True})["review_severe"], True)
        self.assertIs(automation.normalize_escalation({"review_severe": "yes"})["review_severe"], False)
        bad = automation.normalize_escalation({"action": "explode", "mute_hours": 9999})
        self.assertEqual(bad["action"], "ban")
        self.assertEqual(bad["mute_hours"], 168)

    def test_description_names_the_window_and_zone(self):
        text = automation.describe_quiet({"enabled": True, "start": "22:00", "end": "07:00", "tz_offset": 330})
        self.assertIn("22:00", text)
        self.assertIn("UTC+05:30", text)


class HealthTests(unittest.TestCase):
    def test_unreachable_group_needs_attention(self):
        health = group_health.evaluate({"available": False, "settings": {}})
        self.assertTrue(health["attention"])
        self.assertLess(health["score"], 50)
        self.assertIn("unreachable", [issue["code"] for issue in health["issues"]])

    def test_bot_without_admin_is_flagged(self):
        health = group_health.evaluate({"available": True, "bot_admin": False, "settings": {"lock_links": True}})
        self.assertIn("not_admin", [issue["code"] for issue in health["issues"]])

    def test_defaults_do_not_count_as_protection(self):
        health = group_health.evaluate({"available": True,
                                        "settings": {"welcome_enabled": True},
                                        "explicit": {}})
        self.assertIn("no_protection", [issue["code"] for issue in health["issues"]])

    def test_pending_join_requests_reach_the_health_reasons(self):
        health = group_health.evaluate({"available": True, "bot_admin": True,
                                        "settings": {"lock_links": True, "antispam": True},
                                        "counts": {"pending_joins": 3},
                                        "automation": {"quiet_hours": {"enabled": True}}})
        codes = [issue["code"] for issue in health["issues"]]
        self.assertIn("pending_joins", codes)
        self.assertIn("3 join requests", health["issues"][-1]["message"])
        self.assertTrue(health["attention"], "waiting work must reach the queue even when the score is high")

    def test_a_configured_group_is_healthy(self):
        settings = {"lock_links": True, "lock_media": True, "antispam": True, "captcha_enabled": True}
        health = group_health.evaluate({"available": True, "bot_admin": True, "settings": settings, "members": 900})
        self.assertFalse(health["attention"])
        self.assertGreaterEqual(health["score"], 70)

    def test_summary_counts_are_derived_not_invented(self):
        rows = [
            {"available": True, "settings": {"lock_links": True}, "health": {"attention": False, "score": 90}},
            {"available": False, "settings": {}, "health": {"attention": True, "score": 30}},
        ]
        summary = group_health.summarize(rows)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["attention"], 1)
        self.assertEqual(summary["protected"], 1)
        self.assertEqual(summary["average"], 60)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl

    def test_bot_writes_are_attributed_to_the_bot_surface(self):
        with patch("videl.utils.db.get_db", return_value=self.db):
            self.assertTrue(audit.record_bot(CID, "warn", action="warn",
                                            detail="member 5: spam", actor=9))
            self.assertFalse(audit.record_bot(CID, "not_a_kind", detail="x"))
        row = self.db["mgmt_audit"].find_one({"kind": "warn"})
        self.assertEqual(row["source"], "bot")
        self.assertEqual(row["actor"], 9)
        self.assertEqual(row["detail"], "member 5: spam")

    def test_record_and_read_newest_first(self):
        audit.record(self.db, CID, "settings", action="settings", detail="on: lock_links", actor=1)
        audit.record(self.db, CID, "preset", action="preset", detail="preset: strict", actor=1)
        rows = audit.recent(self.db, CID)
        self.assertEqual([row["kind"] for row in rows], ["preset", "settings"])
        self.assertEqual(rows[1]["detail"], "on: lock_links")

    def test_kind_filter_and_limit(self):
        for index in range(5):
            audit.record(self.db, CID, "settings" if index % 2 else "preset", action="x")
        self.assertEqual(len(audit.recent(self.db, CID, kind="settings")), 2)
        self.assertEqual(len(audit.recent(self.db, CID, limit=3)), 3)

    def test_unknown_kind_is_refused(self):
        self.assertFalse(audit.record(self.db, CID, "made_up", action="x"))
        self.assertEqual(audit.recent(self.db, CID), [])

    def test_detail_is_one_clean_line(self):
        audit.record(self.db, CID, "settings", action="x", detail="line\nbreak\x00 with\x07control")
        self.assertEqual(audit.recent(self.db, CID)[0]["detail"], "line break with control")

    def test_other_chats_are_not_mixed(self):
        audit.record(self.db, CID, "settings", action="x")
        self.assertEqual(audit.recent(self.db, -100999), [])


class GroupAutomationTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["served_chats"].insert_one({"_id": CID})
        self.member = {"status": "administrator", "can_delete_messages": True,
                       "can_restrict_members": True, "can_invite_users": True}
        self.api = Mock(side_effect=self.telegram)
        self.service = view.GroupView(self.db, self.api)
        self.patch_global = patch("videl.utils.db._db", self.db)
        self.patch_global.start()

    def tearDown(self):
        self.patch_global.stop()

    def telegram(self, method, payload):
        if method == "getMe":
            result = {"id": 777, "first_name": "Videl", "username": "ExampleBot"}
        elif method == "getChatMember":
            result = self.member
        elif method == "getChat":
            result = {"id": CID, "title": "Test group", "type": "supergroup"}
        elif method == "getChatMemberCount":
            result = 42
        else:
            result = True
        return 200, {"ok": True, "result": result}

    def act(self, **body):
        return self.service.act({"chat_id": CID, **body})

    def test_quiet_hours_are_saved_normalised_and_audited(self):
        payload = self.act(action="automation", quiet_hours={"enabled": True, "start": "22:00", "end": "07:00", "tz_offset": 330})
        self.assertTrue(payload["automation"]["quiet_hours"]["enabled"])
        self.assertEqual(payload["automation"]["quiet_hours"]["tz_offset"], 330)
        stored = self.db["mgmt_chat_settings"].find_one({"chat_id": CID})["automation"]
        self.assertEqual(stored["quiet_hours"]["start"], "22:00")
        events = audit.recent(self.db, CID, kind="automation")
        self.assertEqual(len(events), 1)

    def test_quiet_hours_reject_bad_values(self):
        for body in ({"start": "25:00"}, {"start": "22:00", "end": "22:00"}, {"tz_offset": 5000}):
            with self.assertRaises(view.ViewError):
                self.act(action="automation", quiet_hours=body)

    def test_escalation_accepts_only_known_actions(self):
        with self.assertRaises(view.ViewError):
            self.act(action="automation", escalation={"action": "nuke"})
        payload = self.act(action="automation", escalation={"action": "mute", "mute_hours": 12})
        self.assertEqual(payload["automation"]["escalation"]["action"], "mute")
        self.assertEqual(payload["automation"]["escalation"]["mute_hours"], 12)

    def test_protection_window_is_saved_normalised_and_audited(self):
        payload = self.act(action="automation", protection={
            "enabled": True, "start": "23:00", "end": "06:00", "locks": ["lock_links", "lock_media"]})
        protection = payload["automation"]["protection"]
        self.assertTrue(protection["enabled"])
        self.assertEqual(protection["locks"], ["lock_links", "lock_media"])
        self.assertEqual(protection["start"], "23:00")
        stored = self.db["mgmt_chat_settings"].find_one({"chat_id": CID})["automation"]["protection"]
        self.assertEqual(stored["end"], "06:00")
        self.assertIn("protection", self.service.describe(CID)["automation"])

    def test_protection_window_rejects_unsafe_settings(self):
        for body in ({"locks": ["lock_evil"]}, {"enabled": True, "locks": []},
                     {"start": "22:00", "end": "22:00"}, {"enabled": "yes"}, {"locks": "lock_links"}):
            with self.assertRaises(view.ViewError):
                self.act(action="automation", protection=body)

    def test_automation_requires_a_body(self):
        with self.assertRaises(view.ViewError):
            self.act(action="automation")

    def test_commands_can_be_disabled_and_read_back(self):
        payload = self.act(action="command_disable", command="play")
        self.assertIn("play", payload["disabled_commands"])
        self.assertIn("play", self.service.describe(CID)["community"]["disabled_commands"])
        again = self.act(action="command_enable", command="play")
        self.assertNotIn("play", again["disabled_commands"])

    def test_command_switch_is_visible_immediately_not_after_a_cache_expiry(self):
        from videl.utils.db import disable_cmd, enable_cmd, is_disabled

        self.assertFalse(is_disabled(CID, "play"))
        disable_cmd(CID, "play")
        self.assertTrue(is_disabled(CID, "play"))
        enable_cmd(CID, "play")
        self.assertFalse(is_disabled(CID, "play"))

    def test_unknown_command_is_rejected(self):
        with self.assertRaises(view.ViewError):
            self.act(action="command_disable", command="not_a_real_command")

    def test_join_request_approval_calls_telegram_and_updates_the_row(self):
        self.db["mgmt_join_requests"].insert_one({"chat_id": CID, "user": 55, "status": "pending", "name": "Ada"})
        payload = self.act(action="join_request", user_id=55, decision="approve")
        self.assertEqual(payload["status"], "approved")
        row = self.db["mgmt_join_requests"].find_one({"chat_id": CID, "user": 55})
        self.assertEqual(row["status"], "approved")
        methods = [call.args[0] for call in self.api.call_args_list]
        self.assertIn("approveChatJoinRequest", methods)

    def test_join_request_must_be_pending(self):
        with self.assertRaises(view.ViewError) as error:
            self.act(action="join_request", user_id=55, decision="approve")
        self.assertEqual(error.exception.status, 404)

    def test_report_can_be_resolved_and_is_removed_from_the_open_inbox(self):
        insert = self.db["mgmt_reports"].insert_one({"chat_id": CID, "reporter": 5, "target": 6,
                                                    "message_id": 9, "text": "spam", "status": "open"})
        inbox = self.service.describe(CID)["inbox"]
        self.assertEqual(len(inbox["reports"]), 1)
        payload = self.act(action="report_update", id=str(insert.inserted_id), status="resolved")
        self.assertEqual(payload["status"], "resolved")
        self.assertEqual(self.service.describe(CID)["inbox"]["reports"], [])

    def test_report_warn_adds_a_warning_and_closes_the_row(self):
        insert = self.db["mgmt_reports"].insert_one({"chat_id": CID, "reporter": 5, "target": 77,
                                                    "message_id": 9, "text": "spam", "status": "open"})
        payload = self.act(action="report_update", id=str(insert.inserted_id), decision="warn")
        self.assertEqual(payload["status"], "resolved")
        self.assertIn("1/3", payload["note"])
        self.assertEqual(self.db["mgmt_warnings"].find_one({"chat_id": CID, "user_id": 77})["count"], 1)
        self.assertEqual(self.db["mgmt_reports"].find_one({"_id": insert.inserted_id})["decision"], "warn")
        self.assertEqual(payload["inbox"]["reports"], [])
        self.assertEqual(audit.recent(self.db, CID, kind="report")[0]["action"], "report_update")

    def test_report_ban_calls_telegram_and_refuses_a_second_action(self):
        insert = self.db["mgmt_reports"].insert_one({"chat_id": CID, "reporter": 5, "target": 78,
                                                    "message_id": 9, "text": "spam", "status": "open"})
        payload = self.act(action="report_update", id=str(insert.inserted_id), decision="ban")
        self.assertEqual(payload["note"], "member banned")
        methods = [call.args[0] for call in self.api.call_args_list]
        self.assertIn("banChatMember", methods)
        with self.assertRaises(view.ViewError) as error:
            self.act(action="report_update", id=str(insert.inserted_id), decision="ban")
        self.assertEqual(error.exception.status, 409)

    def test_report_action_rejects_unknown_decisions(self):
        insert = self.db["mgmt_reports"].insert_one({"chat_id": CID, "reporter": 5, "target": 79,
                                                    "status": "open"})
        with self.assertRaises(view.ViewError):
            self.act(action="report_update", id=str(insert.inserted_id), decision="explode")

    def test_describe_carries_automation_and_inbox(self):
        payload = self.service.describe(CID)
        self.assertIn("quiet_hours", payload["automation"])
        self.assertIn("join_requests", payload["inbox"])
        self.assertIn("reports", payload["inbox"])

    def test_audit_history_is_group_only_and_readable(self):
        self.act(action="preset", preset="balanced")
        history = self.service.events(CID)
        self.assertEqual(history["events"][0]["kind"], "preset")
        self.assertIn("settings", history["kinds"])


class ProtectionWindowTests(unittest.TestCase):
    """A window may only turn off the locks it turned on itself."""

    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["served_chats"].insert_one({"_id": CID})
        self.db["mgmt_chat_settings"].insert_one({
            "chat_id": CID,
            "lock_media": True,
            "automation": {
                "quiet_hours": {"tz_offset": 0},
                "protection": {"enabled": True, "start": "22:00", "end": "07:00",
                               "locks": ["lock_links", "lock_media"]},
            },
        })
        self.patch_db = patch("videl.utils.db.get_db", return_value=self.db)
        self.patch_db.start()
        self.patch_global = patch("videl.utils.db._db", self.db)
        self.patch_global.start()
        self.document = self.db["mgmt_chat_settings"].find_one({"chat_id": CID})
        self.inside = datetime(2026, 5, 1, 23, tzinfo=UTC)
        self.outside = datetime(2026, 5, 1, 12, tzinfo=UTC)

    def tearDown(self):
        self.patch_global.stop()
        self.patch_db.stop()

    def test_normalisation_keeps_only_real_locks(self):
        config = automation.normalize_protection({"enabled": True, "locks": ["lock_links", "lock_links", "lock_nope", 7]})
        self.assertEqual(config["locks"], ["lock_links"])
        self.assertFalse(config["state"]["active"])

    def test_plan_turns_on_missing_locks_and_leaves_manual_ones_alone(self):
        changes, state = protection_windows.plan(
            self.document["automation"]["protection"], self.document, now=self.inside)
        self.assertEqual(changes, {"lock_links": True}, "media was already on, so only links is applied")
        self.assertTrue(state["active"])
        self.assertEqual(state["applied"], ["lock_links"], "only the lock the window set is recorded")

    def test_plan_releases_only_recorded_locks_at_the_end(self):
        _, state = protection_windows.plan(
            self.document["automation"]["protection"], self.document, now=self.inside)
        document = {**self.document, "lock_links": True}
        changes, closed = protection_windows.plan(
            {**self.document["automation"]["protection"], "state": state},
            document,
            now=self.outside,
        )
        self.assertEqual(changes, {"lock_links": False})
        self.assertFalse(closed["active"])
        self.assertEqual(closed["applied"], [])

    def test_removing_a_lock_mid_window_releases_it(self):
        state = {"active": True, "applied": ["lock_links", "lock_media"], "since": "2026-05-01T23:00:00+00:00"}
        protection = {"enabled": True, "start": "22:00", "end": "07:00",
                      "locks": ["lock_links"], "state": state}
        changes, new_state = protection_windows.plan(
            protection, {"lock_links": True, "lock_media": True}, now=self.inside)
        self.assertEqual(changes, {"lock_media": False})
        self.assertEqual(new_state["applied"], ["lock_links"])

    def test_disabled_window_releases_its_locks_but_keeps_manual_ones(self):
        protection = {"enabled": False, "start": "22:00", "end": "07:00", "locks": ["lock_links"],
                      "state": {"active": True, "applied": ["lock_links"], "since": None}}
        changes, state = protection_windows.plan(protection,
                                                 {"lock_links": True, "lock_media": True}, now=self.inside)
        self.assertEqual(changes, {"lock_links": False})
        self.assertFalse(state["active"])

    def test_run_once_applies_and_audits_then_is_idempotent(self):
        first = protection_windows.run_once(self.db, now=self.inside)
        self.assertEqual(first["applied"], 1)
        stored = self.db["mgmt_chat_settings"].find_one({"chat_id": CID})
        self.assertIs(stored["lock_links"], True)
        events = audit.recent(self.db, CID, kind="automation")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "protection_window")
        self.assertEqual(events[0]["source"], "system")
        again = protection_windows.run_once(self.db, now=self.inside)
        self.assertEqual(again["applied"], 0)
        self.assertEqual(len(audit.recent(self.db, CID, kind="automation")), 1, "a tick with no change writes no row")

    def test_run_once_releases_after_the_window_and_keeps_a_manual_lock(self):
        protection_windows.run_once(self.db, now=self.inside)
        self.db["mgmt_chat_settings"].update_one({"chat_id": CID}, {"$set": {"lock_stickers": True}})
        outcome = protection_windows.run_once(self.db, now=self.outside)
        self.assertEqual(outcome["released"], 1)
        stored = self.db["mgmt_chat_settings"].find_one({"chat_id": CID})
        self.assertIs(stored["lock_links"], False)
        self.assertIs(stored["lock_media"], True, "media was on before the window and must stay on")
        self.assertIs(stored["lock_stickers"], True, "a lock set by hand during the window stays on")

    def test_run_once_reports_a_missing_database_without_raising(self):
        with patch("videl.utils.db.get_db", return_value=None):
            outcome = protection_windows.run_once(now=self.inside)
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["error"], "MongoDB is not connected")


class EscalationTests(unittest.TestCase):
    """The warning ladder must call the API Telegram actually exposes."""

    def ctx(self):
        ctx = Mock()
        ctx.client = Mock()
        ctx.client.ban_chat_member = AsyncMock()
        ctx.client.unban_chat_member = AsyncMock()
        return ctx

    def test_mute_is_a_temporary_ban_with_a_finite_end(self):
        from videl.plugins.moderation import _apply_action

        ctx = self.ctx()
        phrase = asyncio.run(_apply_action(ctx, CID, 55, "mute", {"mute_hours": 3}))
        self.assertIn("muted for 3 hours", phrase)
        kwargs = ctx.client.ban_chat_member.await_args.kwargs
        self.assertIn("until_date", kwargs)
        remaining = kwargs["until_date"] - datetime.now(UTC)
        self.assertGreater(remaining.total_seconds(), 2 * 3600)

    def test_kick_bans_then_unbans(self):
        from videl.plugins.moderation import _apply_action

        ctx = self.ctx()
        asyncio.run(_apply_action(ctx, CID, 55, "kick", {"mute_hours": 1}))
        ctx.client.ban_chat_member.assert_awaited_once()
        ctx.client.unban_chat_member.assert_awaited_once()

    def test_ban_is_permanent(self):
        from videl.plugins.moderation import _apply_action

        ctx = self.ctx()
        asyncio.run(_apply_action(ctx, CID, 55, "ban", {}))
        self.assertNotIn("until_date", ctx.client.ban_chat_member.await_args.kwargs)

    def test_default_ladder_keeps_banning_when_storage_is_absent(self):
        from videl.plugins.moderation import _escalation

        with patch("videl.utils.db.get_escalation", side_effect=RuntimeError("no db")):
            self.assertEqual(_escalation(CID)["action"], "ban")


class QuietWindowTests(unittest.TestCase):
    def test_watcher_reads_the_stored_window_once_per_minute(self):
        from videl.plugins import locks

        db = mongomock.MongoClient().videl
        db["mgmt_chat_settings"].insert_one({"chat_id": CID, "automation": {
            "quiet_hours": {"enabled": True, "start": "00:00", "end": "23:59", "tz_offset": 0},
        }})
        locks._QUIET_CACHE.clear()
        with patch("videl.utils.db._db", db):
            self.assertTrue(locks._quiet_window(CID)["enabled"])
            self.assertIn(CID, locks._QUIET_CACHE)
        locks._QUIET_CACHE.clear()


class ScheduledRetryTests(unittest.TestCase):
    """A rejected post may be resent; an accepted one never may."""

    def collection(self):
        self.db = mongomock.MongoClient().videl
        return self.db["scheduled_posts"]

    def setUp(self):
        from videl.utils import scheduled_posts
        self.module = scheduled_posts
        self.store = self.collection()
        self.patch = patch.object(scheduled_posts, "_collection", lambda: self.store)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def job(self, status="failed"):
        from datetime import timedelta
        self.store.insert_one({
            "_id": "11111111-1111-4111-8111-111111111111",
            "owner_id": self.module.OWNER_ID,
            "status": status,
            "method": "sendMessage",
            "payload": {"chat_id": "@x", "text": "hi"},
            "due_at": datetime.now(UTC) - timedelta(minutes=5),
            "created_at": datetime.now(UTC),
        })
        return "11111111-1111-4111-8111-111111111111"

    def test_failed_job_is_requeued_one_minute_ahead(self):
        identifier = self.job("failed")
        outcome = self.module.retry_job(identifier)
        self.assertEqual(outcome["status"], "pending")
        row = self.store.find_one({"_id": identifier})
        self.assertEqual(row["status"], "pending")
        due = row["due_at"] if row["due_at"].tzinfo else row["due_at"].replace(tzinfo=UTC)
        self.assertGreater(due, datetime.now(UTC))

    def test_delivered_or_unknown_jobs_are_never_resent(self):
        for status in ("sent", "sending", "unconfirmed", "missed", "cancelled", "pending"):
            identifier = self.job(status)
            with self.assertRaises(ValueError):
                self.module.retry_job(identifier)
            self.store.delete_many({})

    def test_missing_job_is_refused(self):
        with self.assertRaises(ValueError):
            self.module.retry_job("22222222-2222-4222-8222-222222222222")

    def test_job_list_reports_the_failure_reason(self):
        self.job("failed")
        self.store.update_one({}, {"$set": {"error": "Bad Request: chat not found"}})
        rows = self.module.list_jobs()
        self.assertEqual(rows[0]["error"], "Bad Request: chat not found")


class DisabledCommandRouterTests(unittest.TestCase):
    def test_disabled_group_command_does_not_run_the_handler(self):
        from videl.app.router import Router, parse

        handler = AsyncMock(return_value=None)

        async def run():
            from videl.app.router import Command
            router = Router([Command("ping", handler, "Ping", policy="group")])
            message = Mock()
            message.text = "/ping"
            message.chat.id = CID
            message.chat.type = "supergroup"
            message.id = 1
            message.from_user.id = 5
            client = Mock()
            client.me.username = "ExampleBot"
            with patch("videl.utils.db.is_disabled", return_value=True), \
                 patch("videl.app.router.rich_reply", AsyncMock()) as reply:
                handled = await router.dispatch(client, message)
            handler.assert_not_awaited()
            self.assertTrue(handled)
            self.assertIn("turned this command off", reply.await_args.args[1])

        asyncio.run(run())

    def test_enabled_command_still_runs(self):
        from videl.app.router import Command, Router

        handler = AsyncMock(return_value=None)

        async def run():
            router = Router([Command("ping", handler, "Ping", policy="group")])
            message = Mock()
            message.text = "/ping"
            message.chat.id = CID
            message.chat.type = "supergroup"
            message.id = 2
            message.from_user.id = 5
            client = Mock()
            client.me.username = "ExampleBot"
            with patch("videl.utils.db.is_disabled", return_value=False), \
                 patch("videl.app.router.rich_reply", AsyncMock()):
                await router.dispatch(client, message)
            handler.assert_awaited_once()

        asyncio.run(run())


class CommandGateTests(unittest.TestCase):
    """The gate must stop lower handler groups, not just answer politely."""

    def message(self, text="/play song", admin=False):
        from unittest.mock import AsyncMock

        message = Mock()
        message.text = text
        message.chat.id = CID
        message.from_user.id = 5
        message.from_user.is_bot = False
        return message

    def run_gate(self, message, blocked=True):
        from pyrogram import StopPropagation
        from videl.modules import command_gate

        async def run():
            with patch("videl.utils.db.is_disabled", return_value=blocked), \
                 patch.object(command_gate, "is_admin", AsyncMock(return_value=False)), \
                 patch.object(command_gate, "rich_reply", AsyncMock()) as reply:
                with self.assertRaises(StopPropagation):
                    await command_gate.disabled_command_gate(None, message)
                return reply

        return asyncio.run(run())

    def test_disabled_command_is_stopped_before_other_handlers(self):
        reply = self.run_gate(self.message("/play"))
        self.assertIn("/play", reply.await_args.args[1])

    def test_enabled_command_passes_through(self):
        from videl.modules import command_gate

        async def run():
            with patch("videl.utils.db.is_disabled", return_value=False):
                return await command_gate.disabled_command_gate(None, self.message("/play"))

        self.assertIsNone(asyncio.run(run()))

    def test_owner_is_never_blocked(self):
        from videl.modules import command_gate
        from videl.app.router import OWNER_ID

        message = self.message("/play")
        message.from_user.id = OWNER_ID

        async def run():
            with patch("videl.utils.db.is_disabled", return_value=True):
                return await command_gate.disabled_command_gate(None, message)

        self.assertIsNone(asyncio.run(run()))

    def test_admin_is_never_blocked(self):
        from unittest.mock import AsyncMock
        from videl.modules import command_gate

        async def run():
            with patch("videl.utils.db.is_disabled", return_value=True), \
                 patch.object(command_gate, "is_admin", AsyncMock(return_value=True)):
                return await command_gate.disabled_command_gate(None, self.message("/play"))

        self.assertIsNone(asyncio.run(run()))

    def test_plain_text_is_ignored(self):
        from videl.modules import command_gate

        async def run():
            return await command_gate.disabled_command_gate(None, self.message("hello there"))

        self.assertIsNone(asyncio.run(run()))


class InternalRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().videl
        self.db["served_chats"].insert_one({"_id": CID})
        self.db["served_chats"].insert_one({"_id": -100999})
        self.db["mgmt_chat_settings"].insert_one({"chat_id": CID, "lock_links": True})
        self.db["feds"].insert_one({"_id": "fed1", "name": "North", "owner": 1, "created": 1})
        self.db["fed_chats"].insert_one({"fed": "fed1", "chat": CID})
        self.db["fed_bans"].insert_one({"fed": "fed1", "user": 9, "reason": "spam", "banner": 1, "time": 1})

        import config
        import videl.__main__ as backend
        self.backend = backend
        self.previous = getattr(config, "WEBAPP_SECRET", "")
        self.previous_token = getattr(config, "BOT_TOKEN", "")
        config.WEBAPP_SECRET = "test-secret"
        config.BOT_TOKEN = "123:offline-fixture"
        self.patch_db = patch("videl.utils.db.get_db", return_value=self.db)
        self.patch_db.start()
        self.patch_global = patch("videl.utils.db._db", self.db)
        self.patch_global.start()
        self.api = Mock(side_effect=self.telegram)
        self.patch_api = patch.object(backend, "_bot_api", self.api)
        self.patch_api.start()
        self.client = backend._flask.test_client()

    def tearDown(self):
        import config
        config.WEBAPP_SECRET = self.previous
        config.BOT_TOKEN = self.previous_token
        self.patch_api.stop()
        self.patch_global.stop()
        self.patch_db.stop()

    def telegram(self, method, payload):
        if method == "getMe":
            result = {"id": 777, "first_name": "Videl", "username": "ExampleBot"}
        elif method == "getChatMember":
            result = {"status": "administrator", "can_delete_messages": True, "can_invite_users": True}
        elif method == "getChat":
            result = {"id": payload["chat_id"], "title": "Test group", "type": "supergroup"}
        elif method == "getChatMemberCount":
            result = 42
        else:
            result = True
        return 200, {"ok": True, "result": result}

    def headers(self):
        return {"X-Videl-Internal": "test-secret"}

    def test_chat_list_reports_health_automation_and_summary(self):
        self.db["mgmt_join_requests"].insert_one({"chat_id": CID, "user": 55, "status": "pending"})
        self.db["mgmt_join_requests"].insert_one({"chat_id": CID, "user": 56, "status": "approved"})
        self.db["mgmt_reports"].insert_one({"chat_id": CID, "status": "open", "target": 5})
        self.db["mgmt_reports"].insert_one({"chat_id": CID, "status": "resolved", "target": 6})
        response = self.client.get("/internal/chats", headers=self.headers())
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        row = next(item for item in payload["chats"] if item["id"] == CID)
        self.assertIn("health", row)
        self.assertIn("quiet_hours", row["automation"])
        self.assertEqual(row["counts"]["pending_joins"], 1, "answered requests are not waiting work")
        self.assertEqual(row["counts"]["reports"], 1, "resolved reports are history, not a queue")
        self.assertIn("pending_joins", [issue["code"] for issue in row["health"]["issues"]])
        self.assertEqual(payload["summary"]["total"], 2)
        self.assertIn("attention", payload["summary"])

    def test_chat_list_exposes_the_revision_a_panel_must_send_back(self):
        # The Automation screen edits from list rows, so the token has to be
        # there too — 0 for a group whose document predates revisions.
        self.assertEqual(next(row for row in self.client.get("/internal/chats", headers=self.headers()).get_json()["chats"] if row["id"] == CID)["revision"], 0)
        self.db["mgmt_chat_settings"].update_one({"chat_id": CID}, {"$set": {"revision": 4}}, upsert=True)
        row = next(row for row in self.client.get("/internal/chats", headers=self.headers()).get_json()["chats"] if row["id"] == CID)
        self.assertEqual(row["revision"], 4)

    def test_audit_endpoint_requires_secret_and_filters(self):
        self.assertEqual(self.client.get(f"/internal/chat/{CID}/audit").status_code, 403)
        # One save can write several rows in the same millisecond; the cursor
        # must page through that tie group, not skip it.
        stamp = datetime.now(UTC)
        self.db["mgmt_audit"].insert_many([
            {"chat_id": CID, "kind": "preset", "action": "preset",
             "detail": "preset: strict", "ts": stamp},
            {"chat_id": CID, "kind": "settings", "action": "settings",
             "detail": "on: lock_links", "ts": stamp},
        ])
        payload = self.client.get(f"/internal/chat/{CID}/audit", headers=self.headers()).get_json()
        self.assertEqual(len(payload["events"]), 2)
        self.assertFalse(payload["has_more"])
        self.assertTrue(all(event["id"] for event in payload["events"]))
        first = self.client.get(f"/internal/chat/{CID}/audit?limit=1", headers=self.headers()).get_json()
        self.assertEqual(len(first["events"]), 1)
        self.assertTrue(first["has_more"], "one more row exists, so the panel can offer Load older")
        cursor = first["events"][0]
        older = self.client.get(
            f"/internal/chat/{CID}/audit?limit=1&before={quote(cursor['at'], safe='')}"
            f"&before_id={cursor['id']}",
            headers=self.headers()).get_json()
        self.assertEqual(len(older["events"]), 1, "the tied row is still reachable")
        self.assertNotEqual(older["events"][0]["id"], cursor["id"])
        filtered = self.client.get(f"/internal/chat/{CID}/audit?kind=preset", headers=self.headers()).get_json()
        self.assertEqual([event["kind"] for event in filtered["events"]], ["preset"])
        bad = self.client.get(f"/internal/chat/{CID}/audit?before_id=nope", headers=self.headers())
        self.assertEqual(bad.status_code, 400)
        # Search is a case-insensitive match over stored action and detail.
        found = self.client.get(f"/internal/chat/{CID}/audit?q=LOCK_LINKS", headers=self.headers()).get_json()
        self.assertEqual([event["kind"] for event in found["events"]], ["settings"])
        self.assertEqual(found["query"], "LOCK_LINKS")
        missing = self.client.get(f"/internal/chat/{CID}/audit?q=nothing-here", headers=self.headers()).get_json()
        self.assertEqual(missing["events"], [])
        # The actor filter narrows to one admin; a non-numeric value is refused.
        self.db["mgmt_audit"].update_many({}, {"$set": {"actor": 6265999542}})
        mine = self.client.get(f"/internal/chat/{CID}/audit?actor=6265999542", headers=self.headers()).get_json()
        self.assertEqual(len(mine["events"]), 2)
        other = self.client.get(f"/internal/chat/{CID}/audit?actor=42", headers=self.headers()).get_json()
        self.assertEqual(other["events"], [])
        self.assertEqual(self.client.get(f"/internal/chat/{CID}/audit?actor=abc", headers=self.headers()).status_code, 400)

    def test_federation_overview_and_detail(self):
        overview = self.client.get("/internal/federation", headers=self.headers()).get_json()
        self.assertEqual(overview["total"], 1)
        entry = overview["federations"][0]
        self.assertEqual(entry["chat_count"], 1)
        self.assertEqual(entry["bans"], 1)
        detail = self.client.get("/internal/federation/fed1", headers=self.headers()).get_json()
        self.assertEqual(detail["federation"]["bans"][0]["reason"], "spam")

    def test_federation_unban_removes_the_ban(self):
        response = self.client.post("/internal/federation/fed1", headers=self.headers(),
                                    json={"action": "unban", "user_id": 9})
        outcome = response.get_json()
        self.assertTrue(outcome["removed"])
        self.assertEqual(outcome["unbans"], [{"chat": CID, "ok": True}])
        self.assertIsNone(self.db["fed_bans"].find_one({"fed": "fed1", "user": 9}))
        bad = self.client.post("/internal/federation/fed1", headers=self.headers(), json={"action": "ban_all"})
        self.assertEqual(bad.status_code, 400)

    def test_health_reports_a_measured_api_latency_not_a_guess(self):
        self.client.get("/internal/chats", headers=self.headers())
        payload = self.client.get("/health").get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(payload["api"]["samples"], 1)
        self.assertGreaterEqual(payload["api"]["p95_ms"], 0.0)
        self.assertIn("running", payload["keepalive"])
        self.assertEqual(payload["keepalive"]["consecutive_failures"], 0)
        self.assertIn("running", payload["watchdog"])
        self.assertIn("checks", payload["watchdog"])
        providers = payload["media_downloaders"]
        self.assertEqual(providers["primary"], "shruti")
        self.assertIn(providers["shruti"]["state"], {"configured", "needs_api_key", "invalid_url"})
        self.assertEqual(providers["fallbacks"], ["eldian", "local_yt_dlp"])
        self.assertNotIn("YT_API_KEY", repr(providers))

    def test_health_times_the_database_separately(self):
        # One number cannot say whether the API or Mongo is slow.
        self.client.get("/health")
        payload = self.client.get("/health").get_json()
        self.assertIs(payload["db"]["connected"], True)
        self.assertGreaterEqual(payload["db"]["samples"], 1)
        self.assertGreaterEqual(payload["db"]["p95_ms"], 0.0)
        self.assertIn("bot_attempts", payload)

    def test_a_database_that_answers_nothing_is_not_reported_fast(self):
        from videl.utils import db as database
        backend = self.backend
        database._db = None
        try:
            payload = self.client.get("/health").get_json()
        finally:
            database._db = self.db
        self.assertIs(payload["db"]["connected"], False)
        self.assertIsNone(payload["db"]["p95_ms"])
        self.assertIn("MongoDB is disconnected", payload["degraded_reasons"])

    def test_the_fleet_list_pages_instead_of_stopping_silently(self):
        # 21 groups is more than one 20-group page, which is the whole point:
        # the old endpoint returned 200 and said nothing about the rest.
        for extra in range(19):
            self.db["served_chats"].insert_one({"_id": -200000 - extra})
        first = self.client.get("/internal/chats?limit=20", headers=self.headers()).get_json()
        self.assertEqual(first["total"], 21, "the count covers the fleet, not the page")
        self.assertEqual(first["returned"], 20)
        self.assertIs(first["has_more"], True)
        self.assertIs(first["truncated"], True, "older panels still get the hint")
        self.assertIsNotNone(first["next_cursor"])
        self.assertEqual(first["summary"]["scope"], "page")
        self.assertEqual(first["summary"]["total"], 20, "page totals stay honest about their scope")

        second = self.client.get(f"/internal/chats?limit=20&cursor={first['next_cursor']}",
                                 headers=self.headers()).get_json()
        self.assertEqual(second["returned"], 1)
        self.assertIs(second["has_more"], False)
        self.assertIsNone(second["next_cursor"])

    def test_paging_walks_every_group_exactly_once(self):
        for extra in range(30):
            self.db["served_chats"].insert_one({"_id": -300000 - extra})
        seen, cursor, pages = [], None, 0
        while True:
            url = "/internal/chats?limit=20" + (f"&cursor={cursor}" if cursor is not None else "")
            body = self.client.get(url, headers=self.headers()).get_json()
            pages += 1
            self.assertEqual(body["total"], 32)
            seen.extend(row["id"] for row in body["chats"])
            if not body["has_more"]:
                self.assertIsNone(body["next_cursor"])
                break
            cursor = body["next_cursor"]
            self.assertLess(pages, 10, "paging must terminate")
        self.assertEqual(len(seen), len(set(seen)), "no group is returned twice")
        self.assertEqual(set(seen), {-1001234567, -100999, *(-300000 - n for n in range(30))})
        self.assertGreater(pages, 1, "the fixture really did span pages")

    def test_a_bad_page_parameter_is_refused_rather_than_ignored(self):
        self.assertEqual(self.client.get("/internal/chats?limit=abc", headers=self.headers()).status_code, 400)
        self.assertEqual(self.client.get("/internal/chats?limit=5", headers=self.headers()).status_code, 400)
        self.assertEqual(self.client.get("/internal/chats?limit=10000", headers=self.headers()).status_code, 400)
        unknown = self.client.get("/internal/chats?cursor=42", headers=self.headers())
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(unknown.get_json()["total"], 2)

    def test_health_names_what_is_not_running(self):
        # The HTTP API answering is not the same as the bot working. Keep the
        # status "ok" for uptime monitors, but say which part is down.
        backend = self.backend
        previous = (backend._BOT_STATUS, backend._BOT_ERROR, backend._BOT_ONLINE_AT)
        try:
            backend._BOT_STATUS = "failed"
            backend._BOT_ERROR = "AUTH_KEY_UNRESTRICTED"
            backend._BOT_ONLINE_AT = None
            payload = self.client.get("/health").get_json()
            self.assertEqual(payload["status"], "ok")
            self.assertIs(payload["degraded"], True)
            self.assertIn("Telegram bot is failed", payload["degraded_reasons"])
            self.assertEqual(payload["bot_error"], "AUTH_KEY_UNRESTRICTED")

            backend._BOT_STATUS = "online"
            backend._BOT_ERROR = ""
            backend._BOT_ONLINE_AT = 1792500000
            payload = self.client.get("/health").get_json()
            # The test process runs no watchdog, so that reason stays; the bot
            # reason and the stale start error must be gone.
            self.assertNotIn("Telegram bot is failed", payload["degraded_reasons"])
            self.assertIsNone(payload["bot_error"])
            self.assertEqual(payload["bot_online_at"], 1792500000)
            with patch("videl.core.watcher.watchdog_status",
                       return_value={"running": True, "healthy": True, "last_tick": 1792500000}):
                healthy = self.client.get("/health").get_json()
            self.assertIs(healthy["degraded"], False)
            self.assertEqual(healthy["degraded_reasons"], [])
        finally:
            backend._BOT_STATUS, backend._BOT_ERROR, backend._BOT_ONLINE_AT = previous

    def test_a_start_error_is_published_without_the_bot_token(self):
        import config
        backend = self.backend
        try:
            text = f"Unauthorized: bot {config.BOT_TOKEN} was rejected; session abcdefghijklmnopqrstuvwxyz012345"
            published = backend._health_text(text)
            self.assertNotIn(config.BOT_TOKEN, published)
            self.assertNotIn("abcdefghijklmnopqrstuvwxyz012345", published)
            self.assertIn("Unauthorized", published)
            self.assertLessEqual(len(backend._health_text("x" * 900)), 240)
            self.assertEqual(backend._health_text(None), "")
        finally:
            pass

    def test_federation_unknown_id_is_404(self):
        self.assertEqual(self.client.get("/internal/federation/nope", headers=self.headers()).status_code, 404)


if __name__ == "__main__":
    unittest.main()
