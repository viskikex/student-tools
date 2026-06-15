"""The [[ defang is a security boundary (see student-tools CLAUDE.md): no syllabus
text should leave a live ``[[`` in the output, including runs of 3+ brackets that
a naive ``str.replace("[[", ...)`` would let through. ``defang`` lives in dates.py
and is shared by convert.py, so this is the syllabus tool's one copy.

Run from the syllabus/ folder:  .venv/bin/python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from syllabus.dates import _clean_context, defang

PAYLOADS = [
    "[[note]]",
    "[[[note]]",
    "[[[[note]]",
    "x[[[y]]",
    "![[embed]]",
    "![[[embed]]",
    "[[[[[deep]]",
]


class DefangTest(unittest.TestCase):
    def test_no_live_wikilink_survives(self):
        for p in PAYLOADS:
            self.assertNotIn("[[", defang(p), f"live [[ survived defang({p!r})")

    def test_clean_context_defangs_and_escapes_pipes(self):
        for p in PAYLOADS:
            self.assertNotIn("[[", _clean_context(p))
        self.assertIn("\\|", _clean_context("a | b"))

    def test_plain_text_untouched(self):
        self.assertEqual(defang("Week 1: read chapter"), "Week 1: read chapter")
        self.assertEqual(defang("[single]"), "[single]")

    def test_idempotent(self):
        for p in PAYLOADS:
            once = defang(p)
            self.assertEqual(defang(once), once)


if __name__ == "__main__":
    unittest.main()
