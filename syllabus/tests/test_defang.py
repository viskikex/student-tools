"""The [[ defang is a security boundary (see student-tools CLAUDE.md): no syllabus
text should leave a live ``[[`` in the MARKDOWN output, including runs of 3+
brackets that a naive ``str.replace("[[", ...)`` would let through.

Defang is applied at markdown-render time (render_table), NOT in the data path
(``_normalize_context`` / JSON ``title`` / ``_date_id``) — so the vault-safety
assertions target render_table's output, where it matters. The data path keeps
clean text so consumers can string-search/dedup without ZWSP/escape artifacts
(ZWSP-in-title, truncated-context-id-collision).

Run from the syllabus/ folder:  .venv/bin/python -m unittest discover tests
"""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from syllabus.dates import _normalize_context, defang, render_table

PAYLOADS = [
    "[[note]]",
    "[[[note]]",
    "[[[[note]]",
    "x[[[y]]",
    "![[embed]]",
    "![[[embed]]",
    "[[[[[deep]]",
]

# Markdown images auto-load remote URLs in Obsidian's reading view, so an
# untrusted ![](url) is a tracking beacon. The defang must break the `![` trigger.
IMAGE_PAYLOADS = [
    "![](https://attacker.example/track.png)",
    "![alt](https://attacker.example/track.png)",
    "![[embed]]",
]


class DefangTest(unittest.TestCase):
    def test_no_live_wikilink_survives_defang(self):
        for p in PAYLOADS:
            self.assertNotIn("[[", defang(p), f"live [[ survived defang({p!r})")

    def test_no_live_wikilink_survives_render_table(self):
        # render_table is the markdown path — defang is applied here, not in the
        # data path. A syllabus line containing [[note]] must not leave a live
        # wikilink in the rendered key-dates table.
        for p in PAYLOADS:
            rendered = render_table([(date(2026, 2, 13), _normalize_context(p))])
            self.assertNotIn("[[", rendered, f"live [[ survived render_table({p!r})")

    def test_no_live_image_trigger_survives_defang(self):
        for p in IMAGE_PAYLOADS:
            self.assertNotIn("![", defang(p), f"live ![ survived defang({p!r})")

    def test_no_live_image_trigger_survives_render_table(self):
        for p in IMAGE_PAYLOADS:
            rendered = render_table([(date(2026, 2, 13), _normalize_context(p))])
            self.assertNotIn("![", rendered, f"live ![ survived render_table({p!r})")

    def test_render_table_escapes_pipes_in_context(self):
        # Pipe in a context line must be escaped so it doesn't split the table cell.
        rendered = render_table([(date(2026, 2, 13), _normalize_context("a | b"))])
        self.assertIn("\\|", rendered)

    def test_normalize_context_keeps_clean_text(self):
        # Data path: no ZWSP, no pipe-escape, no markdown artifacts. Consumers
        # string-search/dedup on this value (ZWSP-in-title, truncated-context-id-collision).
        for p in PAYLOADS:
            ctx = _normalize_context(p)
            self.assertNotIn("\u200b", ctx, f"ZWSP leaked into _normalize_context({p!r})")
            self.assertNotIn("\\|", ctx, f"pipe-escape leaked into _normalize_context({p!r})")

    def test_plain_text_untouched(self):
        self.assertEqual(defang("Week 1: read chapter"), "Week 1: read chapter")
        self.assertEqual(defang("[single]"), "[single]")
        self.assertEqual(defang("Quiz due, no excuses!"), "Quiz due, no excuses!")

    def test_idempotent(self):
        for p in PAYLOADS + IMAGE_PAYLOADS:
            once = defang(p)
            self.assertEqual(defang(once), once)


if __name__ == "__main__":
    unittest.main()
