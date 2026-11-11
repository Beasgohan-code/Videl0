import unittest

from videl.plugins.preferences import _preferences_screen


class PreferencesUiTests(unittest.TestCase):
    def test_screen_exposes_only_existing_personal_preferences(self):
        screen = _preferences_screen(42, {
            "notifications_enabled": False,
            "quiet_hours": {"enabled": True, "start": "22:00", "end": "07:00", "utc_offset_minutes": 330},
            "language": "ml",
        })
        self.assertIn("UTC+5.5", screen.html)
        callbacks = [button.callback_data for row in screen.keyboard.inline_keyboard
                     for button in row if button.callback_data]
        self.assertIn("preferences:42:notifications:on", callbacks)
        self.assertIn("preferences:42:notifications:off", callbacks)
        self.assertIn("preferences:42:language:ml", callbacks)
        self.assertIn("preferences:42:quiet:off", callbacks)
        self.assertIn("preferences:42:quiet:help", callbacks)
        self.assertTrue(all(value.startswith("preferences:42:") for value in callbacks))


if __name__ == "__main__":
    unittest.main()
