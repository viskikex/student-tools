"""Tests for extract_dates / infer_year / render_table — the headline regex.

The key-dates table is the syllabus tool's whole reason for existing, yet these
functions had zero direct coverage before this file. Cases below exercise the
edges the adversarial review surfaced (cross-year ranges, day-first numerics,
two-digit years, multi-date lines, dedup, sorting, render branches).

Run from the syllabus/ folder:  .venv/bin/python -m unittest discover tests
"""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from syllabus.dates import extract_dates, infer_year, key_date_items, render_table, schedule_feed


def _dates(entries):
    return [d for d, _ in entries]


class ExtractDatesTest(unittest.TestCase):
    def test_named_month_with_explicit_year(self):
        self.assertEqual(_dates(extract_dates("Midterm Feb 13, 2026", 2027)), [date(2026, 2, 13)])

    def test_named_month_inherits_default_year(self):
        self.assertEqual(_dates(extract_dates("Midterm Feb 13", 2026)), [date(2026, 2, 13)])

    def test_abbreviated_month(self):
        self.assertEqual(_dates(extract_dates("Quiz Sep. 5th", 2026)), [date(2026, 9, 5)])

    def test_numeric_month_first(self):
        self.assertEqual(_dates(extract_dates("Due 4/5/2026", 2027)), [date(2026, 4, 5)])

    def test_two_digit_year_maps_to_2000s(self):
        self.assertEqual(_dates(extract_dates("Due 4/5/26", 2027)), [date(2026, 4, 5)])

    def test_unambiguous_day_first_numeric(self):
        # 31/12: first number can't be a month -> day-first.
        self.assertEqual(_dates(extract_dates("Exam 31/12", 2026)), [date(2026, 12, 31)])

    def test_day_first_with_year(self):
        self.assertEqual(_dates(extract_dates("Exam 13/5/2026", 2027)), [date(2026, 5, 13)])

    def test_cross_year_named_range_rolls_january(self):
        # Dec 15 - Jan 10 with default 2027: Jan 10 rolls to 2028.
        self.assertEqual(
            _dates(extract_dates("Finals Dec 15 - Jan 10", 2027)),
            [date(2027, 12, 15), date(2028, 1, 10)],
        )

    def test_cross_year_numeric_named_mixed(self):
        # 12/15 - Jan 10: numeric Dec, named Jan -> Jan rolls to next year.
        self.assertEqual(
            _dates(extract_dates("12/15 - Jan 10", 2027)),
            [date(2027, 12, 15), date(2028, 1, 10)],
        )

    def test_cross_year_named_numeric_mixed(self):
        # Dec 15 - 01/10: named Dec, numeric Jan -> Jan rolls to next year.
        self.assertEqual(
            _dates(extract_dates("Dec 15 - 01/10", 2027)),
            [date(2027, 12, 15), date(2028, 1, 10)],
        )

    def test_two_digit_year_pivot(self):
        # 0-49 -> 20xx, 50-99 -> 19xx (Y2K convention), not unconditional +2000.
        self.assertEqual(_dates(extract_dates("4/5/99", 2026)), [date(1999, 4, 5)])
        self.assertEqual(_dates(extract_dates("4/5/50", 2026)), [date(1950, 4, 5)])
        self.assertEqual(_dates(extract_dates("4/5/26", 2026)), [date(2026, 4, 5)])
        self.assertEqual(_dates(extract_dates("4/5/00", 2026)), [date(2000, 4, 5)])

    def test_same_year_range_no_roll(self):
        self.assertEqual(
            _dates(extract_dates("Feb 3 - Mar 10", 2026)),
            [date(2026, 2, 3), date(2026, 3, 10)],
        )

    def test_explicit_year_not_rolled(self):
        # Both years explicit -> honored as written, no roll.
        self.assertEqual(
            _dates(extract_dates("Dec 15 2026 - Jan 10 2027", 2028)),
            [date(2026, 12, 15), date(2027, 1, 10)],
        )

    def test_three_dates_on_one_line(self):
        self.assertEqual(
            _dates(extract_dates("Sep 5, Dec 15 - Jan 10", 2027)),
            [date(2027, 9, 5), date(2027, 12, 15), date(2028, 1, 10)],
        )

    def test_dedup_same_date_and_context(self):
        entries = extract_dates("Feb 13 and Feb 13 again", 2026)
        self.assertEqual(len(entries), 1)

    def test_sorted_chronologically(self):
        entries = extract_dates("Mar 10\nFeb 13\nJan 7", 2026)
        self.assertEqual(_dates(entries), [date(2026, 1, 7), date(2026, 2, 13), date(2026, 3, 10)])

    def test_invalid_day_rejected(self):
        self.assertEqual(_dates(extract_dates("Feb 30", 2026)), [])

    def test_leap_day_accepted(self):
        self.assertEqual(_dates(extract_dates("Feb 29, 2024", 2026)), [date(2024, 2, 29)])

    def test_leap_day_rejected_non_leap(self):
        self.assertEqual(_dates(extract_dates("Feb 29, 2025", 2026)), [])

    def test_no_dates(self):
        self.assertEqual(extract_dates("No dates here at all", 2026), [])

    def test_url_fragment_not_matched(self):
        # 2026/27 looks like a year range, not a date — the numeric guard rejects it.
        self.assertEqual(extract_dates("see https://example.com/2026/27", 2026), [])

    def test_distinct_long_lines_dont_collide_on_truncated_context(self):
        # Two lines sharing the first 107 chars but differing afterward must
        # produce two entries with two distinct ids (regression for truncated-context id collision).
        prefix = "A" * 200
        entries = extract_dates(prefix + " unique1 Feb 13\n" + prefix + " unique2 Feb 13", 2026)
        self.assertEqual(len(entries), 2, "distinct lines collapsed by truncated dedupe key")
        items = key_date_items(entries, "syl.docx")
        ids = [i["id"] for i in items]
        self.assertEqual(len(set(ids)), 2, "distinct lines got colliding schedule ids")
        # Title is the display-truncated form, not the full 200+ char context.
        self.assertTrue(all(len(i["title"]) <= 110 for i in items))

    def test_title_does_not_carry_defang_zero_width_space(self):
        # ZWSP-in-title: a [[ in the source line must not leave a ZWSP in the JSON title.
        items = key_date_items(extract_dates("Feb 13 [[secret]] exam", 2026), "syl.docx")
        self.assertNotIn("\u200b", items[0]["title"])


class InferYearTest(unittest.TestCase):
    def test_most_common_year(self):
        self.assertEqual(infer_year("2026 2026 2027"), 2026)

    def test_no_year_returns_none(self):
        self.assertIsNone(infer_year("no year here"))

    def test_tie_is_deterministic_smaller_wins(self):
        # Equal counts of 2026 and 2027 — must not depend on text order.
        self.assertEqual(infer_year("2026 2027"), infer_year("2027 2026"))


class RenderTableTest(unittest.TestCase):
    def test_empty_renders_placeholder(self):
        self.assertIn("No dates found", render_table([]))

    def test_populated_has_header_and_rows(self):
        entries = [(date(2026, 2, 13), "Midterm Feb 13")]
        rendered = render_table(entries)
        self.assertIn("| Date | Day |", rendered)
        self.assertIn("2026-02-13", rendered)




class ScheduleFeedNaiveNowTest(unittest.TestCase):
    def test_naive_now_coerced_to_utc(self):
        from datetime import datetime
        naive = datetime(2026, 3, 1, 12, 0, 0)
        feed = schedule_feed([], "x.docx", now=naive)
        self.assertEqual(feed["generated_at"], "2026-03-01T12:00:00Z")

    def test_aware_now_unaffected(self):
        from datetime import datetime, timezone
        aware = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        feed = schedule_feed([], "x.docx", now=aware)
        self.assertEqual(feed["generated_at"], "2026-03-01T12:00:00Z")
if __name__ == "__main__":
    unittest.main()
