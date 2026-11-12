import re
import unittest

from videl.plugins.settings import _nav
from videl.utils.premium_emojis import PREMIUM_IDS
from videl.utils.rich_ui import rich_button


class PremiumStaticUiTests(unittest.TestCase):
    def test_settings_navigation_uses_native_icons_without_unicode_badges(self):
        for section in ("home", "more"):
            with self.subTest(section=section):
                rows = _nav(-100123, section)
                buttons = [button for row in rows for button in row]
                self.assertTrue(buttons)
                for item in buttons:
                    self.assertNotRegex(item.text, r"[^\w\s]", item.text)
                    self.assertIn(item.icon_custom_emoji_id, PREMIUM_IDS.values())
                self.assertTrue(all(item.callback_data.startswith("settings:-100123:tab:") for item in buttons))

    def test_downloader_help_buttons_use_native_icons_and_keep_callbacks(self):
        expected = (
            ("Play in voice chat", "help_play"),
            ("Download video", "dl:video"),
            ("Download audio", "dl:song"),
            ("Audio help", "dl:song"),
            ("Video help", "dl:video"),
        )
        for label, callback in expected:
            with self.subTest(label=label):
                rendered = rich_button(label, callback_data=callback)
                match = re.search(r'icon_custom_emoji_id="([0-9]+)"', rendered)
                self.assertIsNotNone(match)
                self.assertIn(match.group(1), PREMIUM_IDS.values())
                self.assertIn(f'data="{callback}"', rendered)
                self.assertIn(f">{label}</tg-button>", rendered)


if __name__ == "__main__":
    unittest.main()
