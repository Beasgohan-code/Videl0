"""Settings never report a fictional successful Telegram connection."""
import importlib
import unittest
from unittest.mock import patch


class BotSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = importlib.import_module("videl.__main__")
        cls.client = cls.api._flask.test_client()

    def test_failed_identity_query_is_an_error_not_fallback_success(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(self.api, "_bot_api", return_value=(False, {"ok": False})):
            response = self.client.get("/internal/bot-settings", headers={"X-Videl-Internal": "offline-test-only"})
            self.assertEqual(response.status_code, 502)
            self.assertFalse(response.json["ok"])
            self.assertNotIn("bot", response.json)

    def test_partial_settings_are_explicitly_unverified(self):
        results = [(True, {"ok": True, "result": {"username": "offline_bot"}}), (False, {"ok": False}), (False, {"ok": False})]
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(self.api, "_bot_api", side_effect=results):
            response = self.client.get("/internal/bot-settings", headers={"X-Videl-Internal": "offline-test-only"})
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json["commands"])
            self.assertIsNone(response.json["menu_button"])
            self.assertEqual(len(response.json["warnings"]), 2)

    def test_settings_require_authorization(self):
        with patch.object(self.api.config, "WEBAPP_SECRET", "offline-test-only"), patch.object(self.api, "_bot_api") as telegram:
            response = self.client.get("/internal/bot-settings")
            self.assertEqual(response.status_code, 403)
            telegram.assert_not_called()
