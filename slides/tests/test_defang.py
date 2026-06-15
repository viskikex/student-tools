"""The [[ defang is a security boundary (see student-tools CLAUDE.md): no slide
text should leave a live ``[[`` in the output, including runs of 3+ brackets that
a naive ``str.replace("[[", ...)`` would let through.

Run from the slides/ folder:  .venv/bin/python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from slides.render import _clean, _defang

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
            self.assertNotIn("[[", _defang(p), f"live [[ survived _defang({p!r})")

    def test_clean_also_defangs(self):
        for p in PAYLOADS:
            self.assertNotIn("[[", _clean(p))

    def test_plain_text_untouched(self):
        self.assertEqual(_defang("a normal slide title"), "a normal slide title")
        self.assertEqual(_defang("[single]"), "[single]")

    def test_idempotent(self):
        for p in PAYLOADS:
            once = _defang(p)
            self.assertEqual(_defang(once), once)


if __name__ == "__main__":
    unittest.main()
