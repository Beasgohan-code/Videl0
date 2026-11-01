import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "maintenance", Path(__file__).parents[1] / "videl/utils/maintenance.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class Collection:
    def __init__(self): self.row = None
    def find_one(self, query, projection=None):
        return {"maintenance": self.row["maintenance"]} if self.row else None
    def update_one(self, query, update, upsert=False):
        self.row = update["$set"]


class MaintenanceTests(unittest.TestCase):
    def setUp(self): self.db={"mgmt_chat_settings":Collection()}

    def test_scope_is_grouped_and_feature_specific(self):
        self.assertEqual(module.save(self.db,-1001,enabled=True,features={"onboarding"}),
                         {"enabled":True,"features":["onboarding"]})
        self.assertTrue(module.is_paused(self.db,-1001,"onboarding"))
        self.assertFalse(module.is_paused(self.db,-1001,"protection"))
        self.assertFalse(module.is_paused(self.db,-1001,"unknown"))

    def test_disable_clears_features_and_invalid_empty_pause_is_rejected(self):
        self.assertIsNone(module.save(self.db,-1001,enabled=True,features=[]))
        self.assertEqual(module.save(self.db,-1001,enabled=False,features=["protection"]),
                         {"enabled":False,"features":[]})
        self.assertFalse(module.is_paused(self.db,-1001,"protection"))
