import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "member_faq", Path(__file__).parents[1] / "videl/utils/member_faq.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class MemberFAQTests(unittest.TestCase):
    def test_add_update_and_remove_are_bounded_and_case_insensitive(self):
        items = module.add([], "How do I get help?", "Ask an admin or read the rules.")
        items = module.add(items, "HOW DO I GET HELP?", "Use /help.")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["answer"], "Use /help.")
        items = module.add(items, "Where are rules?", "Use /rules.")
        self.assertEqual(module.remove(items, 1), [{"question": "Where are rules?", "answer": "Use /rules."}])

    def test_item_count_and_text_lengths_are_enforced(self):
        items = []
        for i in range(module.MAX_ITEMS):
            items = module.add(items, f"Question {i}", "Answer")
        with self.assertRaises(ValueError): module.add(items, "One more", "Answer")
        with self.assertRaises(ValueError): module.add([], "q" * (module.MAX_QUESTION + 1), "Answer")
        with self.assertRaises(ValueError): module.add([], "Question", "a" * (module.MAX_ANSWER + 1))

    def test_malformed_persisted_data_is_ignored(self):
        self.assertEqual(module.normalize([None, {"question": "Bad", "answer": ""},
                                           {"question": "Good?", "answer": "Yes."}]),
                         [{"question": "Good?", "answer": "Yes."}])
