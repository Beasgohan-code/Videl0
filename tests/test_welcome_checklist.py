import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "welcome_checklist", Path(__file__).parents[1] / "videl/utils/welcome_checklist.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class WelcomeChecklistTests(unittest.TestCase):
    def test_accepts_short_https_links(self):
        self.assertEqual(module.validate("Start here | https://example.com/start"),
                         [{"label": "Start here", "url": "https://example.com/start"}])

    def test_rejects_http_credentials_invalid_and_overlong_checklists(self):
        for raw in ("Start | http://example.com", "Start | https://user:pass@example.com",
                    "Start | https://example.com/has space", " | https://example.com", "x" * 33 + " | https://example.com"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                module.validate(raw)
        with self.assertRaises(ValueError):
            module.validate("\n".join(f"Link{i} | https://example.com/{i}" for i in range(5)))

    def test_stored_values_are_revalidated_before_keyboard_creation(self):
        self.assertEqual(module.safe_stored([
            {"label": "Good", "url": "https://example.com"},
            {"label": "Bad", "url": "javascript:alert(1)"},
        ]), [{"label": "Good", "url": "https://example.com"}])
