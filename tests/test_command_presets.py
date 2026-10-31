import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "command_presets", Path(__file__).parents[1] / "videl/utils/command_presets.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class CommandPresetPlanTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"name": "ban", "category": "manage", "context": "group", "owner": False},
            {"name": "play", "category": "music", "context": "group", "owner": False},
            {"name": "lyrics", "category": "music", "context": "group", "owner": False},
            {"name": "ping", "category": "tools", "context": "chat", "owner": False},
            {"name": "restart", "category": "owner", "context": "private", "owner": True},
        ]

    def test_moderation_profile_keeps_core_and_moderation_commands(self):
        result = module.plan(self.entries, [], "moderation")
        self.assertEqual(result["disable"], ["lyrics", "play"])
        self.assertNotIn("ping", result["disable"])
        self.assertNotIn("ban", result["disable"])
        self.assertNotIn("restart", result["result"])

    def test_community_to_music_profile_restores_music_commands(self):
        community = module.plan(self.entries, [], "community")
        music = module.plan(self.entries, community["result"], "music")
        self.assertEqual(music["enable"], ["lyrics", "play"])
        self.assertEqual(music["disable"], [])

    def test_unknown_profiles_are_rejected(self):
        with self.assertRaises(ValueError):
            module.plan(self.entries, [], "owner")
