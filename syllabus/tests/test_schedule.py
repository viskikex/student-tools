"""Tests for the schedule.json slice (key_date_items/schedule_feed in dates.py).

The slice is what an agent/script acts on, so the invariants that matter: it
carries the canvas slice's shared core keys (source/title/type/due_at), due_at
stays date-only (no invented time), ids are stable across runs, and `past` is
computed against `today`.

Run from the syllabus/ folder:  .venv/bin/python -m unittest discover tests
"""

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from syllabus.dates import key_date_items, schedule_feed

ENTRIES = [
    (date(2026, 2, 13), "Midterm exam, Friday February 13"),
    (date(2026, 4, 5), "Final project due 4/5"),
]
TODAY = date(2026, 3, 1)


class KeyDateItemsTest(unittest.TestCase):
    def test_shared_core_keys_present(self):
        item = key_date_items(ENTRIES, "syl.docx", today=TODAY)[0]
        for k in ("source", "title", "type", "due_at"):
            self.assertIn(k, item)
        self.assertEqual(item["source"], "syllabus")
        self.assertEqual(item["type"], "key-date")

    def test_due_at_is_date_only(self):
        for item in key_date_items(ENTRIES, "syl.docx", today=TODAY):
            # date-only ISO, no time component
            self.assertRegex(item["due_at"], r"^\d{4}-\d{2}-\d{2}$")

    def test_weekday_is_computed(self):
        # 2026-02-13 is a Friday — the computed weekday is the typo-catch.
        item = key_date_items(ENTRIES, "syl.docx", today=TODAY)[0]
        self.assertEqual(item["weekday"], "Fri")

    def test_past_flag_against_today(self):
        items = key_date_items(ENTRIES, "syl.docx", today=TODAY)
        self.assertTrue(items[0]["past"])   # Feb 13 < Mar 1
        self.assertFalse(items[1]["past"])  # Apr 5 > Mar 1

    def test_ids_stable_and_unique(self):
        a = key_date_items(ENTRIES, "syl.docx", today=TODAY)
        b = key_date_items(ENTRIES, "syl.docx", today=TODAY)
        self.assertEqual([i["id"] for i in a], [i["id"] for i in b])  # deterministic
        self.assertEqual(len({i["id"] for i in a}), len(a))           # unique


class ScheduleFeedTest(unittest.TestCase):
    def test_envelope_shape(self):
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        feed = schedule_feed(ENTRIES, "syl.docx", now=now, today=TODAY)
        self.assertEqual(feed["source"], "syllabus")
        self.assertIsNone(feed["timezone"])
        self.assertEqual(feed["count"], 2)
        self.assertEqual(feed["generated_at"], "2026-03-01T12:00:00Z")
        self.assertEqual(len(feed["items"]), 2)

    def test_empty_entries(self):
        feed = schedule_feed([], "syl.docx", today=TODAY)
        self.assertEqual(feed["count"], 0)
        self.assertEqual(feed["items"], [])


if __name__ == "__main__":
    unittest.main()
