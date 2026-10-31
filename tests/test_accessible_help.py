import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "accessible_help", Path(__file__).parents[1] / "videl/utils/accessible_help.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class AccessibleHelpTests(unittest.TestCase):
    def test_linear_output_is_escaped_and_includes_examples(self):
        text = module.render([{"name": "play", "summary": "Play audio"},
                              {"name": "bad", "summary": "<script>unsafe</script>"}])
        self.assertIn("/play — Play audio", text)
        self.assertIn("Example:", text)
        self.assertNotIn("<script>", text)
        self.assertNotIn("<tg-emoji", text)
        self.assertNotIn("<table", text)

    def test_long_lists_are_bounded_and_direct_users_to_search(self):
        entries = [{"name": f"cmd{i}", "summary": "Example"} for i in range(60)]
        text = module.render(entries)
        self.assertIn("Showing 18 commands", text)
        self.assertNotIn("/cmd59", text)
