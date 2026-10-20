import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("post_format", Path("videl/utils/post_format.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PostFormatTests(unittest.TestCase):
    def test_markup_does_not_consume_caption_limit(self):
        self.assertEqual(module.post_text_length("<b>" + "a" * 1024 + "</b>"), 1024)

    def test_entities_count_as_displayed_characters(self):
        self.assertEqual(module.post_text_length("<b>A &amp; B</b>"), 5)

    def test_telegram_counts_utf16(self):
        self.assertEqual(module.post_text_length("😀"), 2)

    def test_literal_angle_brackets_are_preserved(self):
        self.assertEqual(module.post_text_length("&lt;test&gt;"), 6)

    def test_plain_text_does_not_strip_markup(self):
        self.assertEqual(module.post_text_length("<b>Hello</b>", "Markdown"), 12)


if __name__ == "__main__":
    unittest.main()
