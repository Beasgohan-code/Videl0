import logging
import unittest
from unittest.mock import patch

import config
from videl.utils.redaction import RedactingFilter, redact_secrets
from videl.utils.url_logger import _mask_url


class SecretRedactionTests(unittest.TestCase):
    def test_configured_credentials_and_common_header_url_secrets_are_removed(self):
        values = {
            "BOT_TOKEN": "123456:offline-token-secret-value",
            "WEBAPP_SECRET": "offline-webapp-signing-secret",
            "MONGO_DB_URL": "mongodb+srv://private-user:private-password@cluster.invalid/db",
            "STRING_SESSION": "offline-assistant-session-value",
            "ELDIAN_API_KEY": "offline-provider-key-value",
            "INTERNAL_SECRET": "offline-internal-key-value",
            "API_HASH": "offline-api-hash-value",
        }
        with patch.dict(config.__dict__, values):
            result = redact_secrets(
                " ".join(values.values())
                + " Authorization: Bearer bearer-credential-value"
                + " https://service.invalid/?api_key=query-key-value"
            )
            for secret in values.values():
                self.assertNotIn(secret, result)
            self.assertNotIn("bearer-credential-value", result)
            self.assertNotIn("query-key-value", result)
            self.assertIn("<redacted>", result)

    def test_redacting_logging_filter_sanitizes_formatted_messages(self):
        with patch.object(config, "BOT_TOKEN", "123456:offline-token-secret-value"):
            record = logging.LogRecord(
                "test", logging.ERROR, __file__, 1, "request failed: %s", (config.BOT_TOKEN,), None
            )
            self.assertTrue(RedactingFilter().filter(record))
            self.assertNotIn(config.BOT_TOKEN, record.getMessage())
            self.assertEqual(record.args, ())

    def test_url_logger_masks_full_connection_strings_and_bot_tokens(self):
        with patch.multiple(
            config,
            BOT_TOKEN="123456:offline-token-secret-value",
            MONGO_DB_URL="mongodb+srv://private-user:private-password@cluster.invalid/db",
        ):
            safe = _mask_url(
                "https://api.telegram.org/bot123456:offline-token-secret-value/sendMessage"
                "?db=mongodb+srv://private-user:private-password@cluster.invalid/db"
            )
            self.assertNotIn("offline-token-secret-value", safe)
            self.assertNotIn("private-password", safe)
            self.assertNotIn("private-user", safe)


if __name__ == "__main__":
    unittest.main()
