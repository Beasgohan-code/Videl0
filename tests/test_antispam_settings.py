import unittest
from types import SimpleNamespace
from unittest.mock import patch

from videl.app.router import CommandError
from videl.plugins import locks


class AntiSpamSettingsTests(unittest.IsolatedAsyncioTestCase):
    CHAT = -100987

    def setUp(self):
        locks._ANTISPAM_CACHE.clear()

    async def test_thresholds_default_and_clamp_to_safe_bounds(self):
        values = {"antispam_limit": 999, "antispam_window": 1}
        with patch.object(locks.base, "get_setting", side_effect=lambda chat, key, default=None: values.get(key, default)):
            self.assertEqual(locks.antispam_config(self.CHAT), (30, 3))
        locks.invalidate_antispam_config(self.CHAT)
        values["antispam_limit"] = "bad"
        with patch.object(locks.base, "get_setting", side_effect=lambda chat, key, default=None: values.get(key, default)):
            self.assertEqual(locks.antispam_config(self.CHAT), (locks.FLOOD_LIMIT, locks.FLOOD_WINDOW))

    async def test_admin_command_persists_config_and_invalidates_cache(self):
        ctx = SimpleNamespace(
            message=SimpleNamespace(chat=SimpleNamespace(id=self.CHAT), from_user=SimpleNamespace(id=123)),
            command=SimpleNamespace(arguments="on 12 15"),
        )
        locks._ANTISPAM_CACHE[self.CHAT] = (0.0, 7, 8)
        with patch.object(locks.base, "get_setting", side_effect=lambda chat, key, default=None: {
                 "antispam": True, "antispam_limit": 12, "antispam_window": 15,
             }.get(key, default)), \
             patch.object(locks.base, "set_settings", return_value=True) as save, \
             patch.object(locks, "_record") as audit:
            result = await locks.antispam(ctx)
        save.assert_called_once_with(self.CHAT, {
            "antispam": True, "antispam_limit": 12, "antispam_window": 15,
        })
        self.assertEqual(locks.antispam_config(self.CHAT), (12, 15))
        audit.assert_awaited_once()
        self.assertIn("12 messages", result.html)
        self.assertIn("15 seconds", result.html)

    async def test_invalid_thresholds_fail_without_writing(self):
        ctx = SimpleNamespace(
            message=SimpleNamespace(chat=SimpleNamespace(id=self.CHAT), from_user=SimpleNamespace(id=123)),
            command=SimpleNamespace(arguments="on 2 90"),
        )
        with patch.object(locks.base, "get_setting", return_value=7), \
             patch.object(locks.base, "set_settings") as save:
            with self.assertRaises(CommandError):
                await locks.antispam(ctx)
        save.assert_not_called()

    async def test_off_preserves_threshold_configuration(self):
        ctx = SimpleNamespace(
            message=SimpleNamespace(chat=SimpleNamespace(id=self.CHAT), from_user=SimpleNamespace(id=123)),
            command=SimpleNamespace(arguments="off"),
        )
        with patch.object(locks.base, "get_setting", side_effect=lambda chat, key, default=None: {
            "antispam": True, "antispam_limit": 11, "antispam_window": 20,
        }.get(key, default)), \
             patch.object(locks.base, "set_settings", return_value=True) as save, \
             patch.object(locks, "_record"):
            await locks.antispam(ctx)
        save.assert_called_once_with(self.CHAT, {"antispam": False})

    async def test_admin_command_lists_status_without_changing_settings(self):
        ctx = SimpleNamespace(
            message=SimpleNamespace(chat=SimpleNamespace(id=self.CHAT), from_user=SimpleNamespace(id=123)),
            command=SimpleNamespace(arguments="status"),
        )
        with patch.object(locks.base, "get_setting", side_effect=lambda chat, key, default=None: {
            "antispam": True, "antispam_limit": 9, "antispam_window": 14,
        }.get(key, default)), patch.object(locks.base, "set_settings") as save:
            result = await locks.antispam(ctx)
        save.assert_not_called()
        self.assertIn("9 messages", result.html)
        self.assertIn("14 seconds", result.html)


if __name__ == "__main__":
    unittest.main()
