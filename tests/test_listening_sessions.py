import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location("listening_sessions",Path(__file__).parents[1]/"videl/utils/listening_sessions.py")
sessions=importlib.util.module_from_spec(spec); spec.loader.exec_module(sessions)

class ListeningSessionTests(unittest.TestCase):
    def test_parse_utc_time_and_title(self):
        now=datetime(2026,10,31,12,0,tzinfo=timezone.utc)
        due,title=sessions.parse_schedule("2026-11-01 18:30 UTC | Friday mix",now=now)
        self.assertEqual(due,datetime(2026,11,1,18,30,tzinfo=timezone.utc))
        self.assertEqual(title,"Friday mix")

    def test_reject_bad_past_and_overlong_schedules(self):
        now=datetime(2026,10,31,12,0,tzinfo=timezone.utc)
        for text in ("bad", "2026-10-31 12:00 UTC | Soon", "2026-12-15 12:00 UTC | Too far", "2026-11-01 12:00 | "):
            with self.assertRaises(ValueError): sessions.parse_schedule(text,now=now)
        with self.assertRaises(ValueError): sessions.parse_schedule("2026-11-01 12:00 UTC | "+"x"*(sessions.MAX_TITLE+1),now=now)
