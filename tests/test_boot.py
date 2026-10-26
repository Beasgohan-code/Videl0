"""Retrying a failed bot start, and saying so once.

A failed start parks nothing and delivers nothing, so the only question is how
long to wait. These tests pin the policy: a blip retries in seconds, a session
conflict waits for the other instance to drain, a dead token is not pretended
to be a blip, and the owner is told once rather than every 15 seconds.
"""
import unittest
from unittest.mock import patch

from videl.utils import boot


class ClassifyTests(unittest.TestCase):
    def test_a_network_error_is_transient(self):
        self.assertEqual(boot.classify(OSError("Network is unreachable")), "transient")
        self.assertEqual(boot.classify(TimeoutError("timed out")), "transient")
        self.assertEqual(boot.classify("502 Bad Gateway"), "transient")

    def test_a_duplicated_session_is_a_conflict_not_a_blip(self):
        self.assertEqual(boot.classify("AUTH_KEY_DUPLICATED"), "conflict")
        self.assertEqual(boot.classify("Telegram says: [406 AUTH_KEY_DUPLICATED]"), "conflict")

    def test_a_rejected_credential_is_fatal(self):
        self.assertEqual(boot.classify("AUTH_KEY_UNREGISTERED"), "fatal")
        self.assertEqual(boot.classify("Unauthorized"), "fatal")
        self.assertEqual(boot.classify("API_ID_INVALID"), "fatal")

    def test_telegram_flood_wait_is_a_rate_limit_not_a_network_blip(self):
        error = 'Telegram says: [420 FLOOD_WAIT_X] - Please wait 619 seconds before repeating the action.'
        self.assertEqual(boot.classify(error), "rate_limit")
        self.assertEqual(boot.retry_after(error), 619)
        self.assertEqual(boot.retry_delay_for_error(1, error), 624)
        self.assertEqual(boot.retry_after("FLOOD_WAIT_123"), 123)

    def test_a_conflict_wins_over_the_generic_marker(self):
        # Both codes can appear in one message; the specific one decides.
        self.assertEqual(boot.classify("Unauthorized: AUTH_KEY_DUPLICATED"), "conflict")

    def test_nothing_is_guessed_from_an_empty_error(self):
        self.assertEqual(boot.classify(None), "transient")
        self.assertEqual(boot.classify(""), "transient")


class DelayTests(unittest.TestCase):
    def test_a_transient_failure_backs_off_then_settles(self):
        delays = [boot.retry_delay(attempt, "transient") for attempt in range(1, 8)]
        self.assertEqual(delays[:5], [15, 30, 60, 120, 240])
        self.assertEqual(delays[5:], [900, 900], "the slow cadence never gives up")

    def test_delays_never_shrink(self):
        for kind in ("transient", "conflict", "rate_limit", "fatal"):
            with self.subTest(kind=kind):
                delays = [boot.retry_delay(attempt, kind) for attempt in range(1, 12)]
                self.assertEqual(delays, sorted(delays))

    def test_a_conflict_waits_longer_than_a_blip(self):
        self.assertGreater(boot.retry_delay(1, "conflict"), boot.retry_delay(1, "transient"))
        self.assertGreaterEqual(boot.retry_delay(1, "fatal"), 1800)

    def test_bad_attempt_numbers_are_tolerated(self):
        for attempt in (0, -3, "x", None):
            with self.subTest(attempt=attempt):
                self.assertGreater(boot.retry_delay(attempt, "transient"), 0)
        self.assertEqual(boot.retry_delay(1, "nonsense"), boot.retry_delay(1, "transient"))


class AlertTests(unittest.TestCase):
    def test_the_first_failure_and_each_change_are_announced(self):
        self.assertTrue(boot.should_alert(1, "transient", None))
        self.assertFalse(boot.should_alert(2, "transient", "transient"))
        self.assertFalse(boot.should_alert(6, "transient", "transient"))
        self.assertTrue(boot.should_alert(3, "conflict", "transient"),
                        "a different failure is news even on a later attempt")

    def test_every_kind_explains_itself_in_words(self):
        for kind in ("transient", "conflict", "rate_limit", "fatal"):
            with self.subTest(kind=kind):
                text = boot.describe(kind)
                self.assertTrue(text)
                self.assertNotIn("_", text)


class NotifyTests(unittest.TestCase):
    def test_no_log_channel_is_not_an_error(self):
        import config
        previous = getattr(config, "LOG_CHANNEL_ID", 0)
        config.LOG_CHANNEL_ID = 0
        try:
            with patch("videl.utils.alerts.call_bot_api") as send:
                self.assertFalse(__import__("videl.utils.alerts", fromlist=["notify"]).notify("x"))
                send.assert_not_called()
        finally:
            config.LOG_CHANNEL_ID = previous

    def test_a_failed_alert_never_raises(self):
        import config
        previous = getattr(config, "LOG_CHANNEL_ID", 0)
        config.LOG_CHANNEL_ID = -1009
        try:
            from videl.utils import alerts
            with patch.object(alerts, "call_bot_api", side_effect=RuntimeError("blocked")):
                self.assertFalse(alerts.notify("x"))
            with patch.object(alerts, "call_bot_api", return_value=(200, {"ok": True})) as send:
                self.assertTrue(alerts.notify("<b>hi</b>", title="Test"))
            self.assertEqual(send.call_args.args[1]["chat_id"], -1009)
            self.assertEqual(send.call_args.args[1]["parse_mode"], "HTML")
        finally:
            config.LOG_CHANNEL_ID = previous

    def test_an_empty_message_is_not_sent(self):
        import config
        previous = getattr(config, "LOG_CHANNEL_ID", 0)
        config.LOG_CHANNEL_ID = -1009
        try:
            from videl.utils import alerts
            with patch.object(alerts, "call_bot_api") as send:
                self.assertFalse(alerts.notify(""))
                send.assert_not_called()
        finally:
            config.LOG_CHANNEL_ID = previous


if __name__ == "__main__":
    unittest.main()
