import importlib.util
from pathlib import Path
import unittest


_spec = importlib.util.spec_from_file_location(
    "reason_templates", Path(__file__).parents[1] / "videl/utils/reason_templates.py"
)
_templates = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_templates)


class ReasonTemplateTests(unittest.TestCase):
    def test_defaults_are_safe_and_complete(self):
        values = _templates.normalize(None)
        self.assertEqual(set(values), set(_templates.ACTIONS))
        self.assertTrue(all(value for value in values.values()))

    def test_custom_template_expands_only_member_and_is_bounded(self):
        self.assertEqual(_templates.render("Please stop, {member}.", "Mina"), "Please stop, Mina.")
        self.assertEqual(_templates.render("{unknown}", "Mina"), "{unknown}")
        self.assertEqual(len(_templates.normalize({"ban": "x" * 500})["ban"]), 240)

    def test_template_opt_in_preserves_freeform_reasons(self):
        values = _templates.normalize({"warn": "Rule reminder for {member}"})
        self.assertEqual(_templates.select_reason(["template"], "warn", values, "Mina", "fallback"),
                         "Rule reminder for Mina")
        self.assertEqual(_templates.select_reason(["Flooding", "links"], "warn", values, "Mina", "fallback"),
                         "Flooding links")
        self.assertEqual(_templates.select_reason([], "warn", values, "Mina", "fallback"), "fallback")
