import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location("music_presets",Path(__file__).parents[1]/"videl/utils/music_presets.py")
presets=importlib.util.module_from_spec(spec); spec.loader.exec_module(presets)

class MusicPresetTests(unittest.TestCase):
    def test_add_normalize_apply_lookup_and_remove(self):
        saved=presets.add([]," Friday ",{"loop":"all","shuffle":True,"requests":False,"approval":True})
        self.assertEqual(saved,[{"name":"Friday","loop":"all","shuffle":True,"requests":False,"approval":True}])
        self.assertEqual(presets.get(saved,1)["loop"],"all")
        self.assertEqual(presets.remove(saved,1),[])
        self.assertEqual(presets.normalize([None,{"name":"ok","loop":"invalid","shuffle":1}]),
                         [{"name":"ok","loop":"off","shuffle":False,"requests":True,"approval":False}])

    def test_names_and_count_are_bounded(self):
        with self.assertRaises(ValueError): presets.add([]," ",{})
        with self.assertRaises(ValueError): presets.add([],"n"*(presets.MAX_NAME+1),{})
        saved=[]
        for index in range(presets.MAX_PRESETS): saved=presets.add(saved,f"Preset {index}",{})
        with self.assertRaises(ValueError): presets.add(saved,"Extra",{})
        with self.assertRaises(ValueError): presets.add(saved,"PRESET 0",{})
        self.assertIsNone(presets.get(saved,999))
