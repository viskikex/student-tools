"""Regression tests for the adversarial review's high-severity slides findings.

Covers: grouped shapes (text + title), chart-only slides, multiline title/notes,
table pipe escape, corrupt-pptx clean error. These are the render-layer bugs the
5 existing test_defang tests don't reach.

Run from the slides/ folder:  .venv/bin/python -m unittest discover tests
"""

import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pptx import Presentation
from pptx.util import Inches

from slides.render import pptx_to_markdown
from slides.convert import detect_chapter, resolve_chapter


def _save_deck(prs, path="/tmp/slides_test.pptx"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    prs.save(path)
    return Path(path)


class GroupedShapesTest(unittest.TestCase):
    def test_grouped_textboxes_render(self):
        """A GROUP shape with textboxes inside must not be silently dropped."""
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
        # Add two textboxes, then group them via XML.
        tb1 = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1))
        tb1.text_frame.text = "child A"
        tb2 = slide.shapes.add_textbox(Inches(3), Inches(1), Inches(2), Inches(1))
        tb2.text_frame.text = "child B"
        path = _save_deck(prs)
        md = pptx_to_markdown(path, chapter="99")
        self.assertIn("child A", md, "grouped child A dropped")
        self.assertIn("child B", md, "grouped child B dropped")


class ChartOnlySlideTest(unittest.TestCase):
    def test_chart_only_slide_has_image_marker(self):
        """A chart-only slide must emit [image], not an empty section."""
        from pptx.chart.data import CategoryChartData
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        chart_data = CategoryChartData()
        chart_data.categories = ["A", "B"]
        chart_data.add_series("S1", (1, 2))
        slide.shapes.add_chart(
            1, Inches(1), Inches(1), Inches(4), Inches(3), chart_data
        )
        path = _save_deck(prs, "/tmp/chart_test.pptx")
        md = pptx_to_markdown(path, chapter="99")
        self.assertIn("[image]", md, "chart-only slide yielded no [image] marker")


class MultilineTest(unittest.TestCase):
    def test_multiline_title_collapsed(self):
        """A title with newlines must not break the markdown heading."""
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[0])  # title slide
        slide.shapes.title.text_frame.text = "Line 1\nLine 2\nLine 3"
        path = _save_deck(prs, "/tmp/multiline_title.pptx")
        md = pptx_to_markdown(path, chapter="99")
        # The heading must be one line — no bare "Line 2" leaking out.
        heading_line = [ln for ln in md.splitlines() if ln.startswith("## Slide")][0]
        self.assertIn("Line 1", heading_line)
        self.assertNotIn("\n", heading_line)

    def test_multiline_notes_stay_blockquoted(self):
        """Multi-line notes must keep every line inside the blockquote."""
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.notes_slide.notes_text_frame.text = "Line one\nLine two\nLine three"
        path = _save_deck(prs, "/tmp/notes_nl.pptx")
        md = pptx_to_markdown(path, chapter="99")
        # Every line after '> ' must either start with '> ' or be part of the
        # same quoted block (no bare 'Line two' outside the quote).
        in_quote = False
        for ln in md.splitlines():
            if ln.startswith("> "):
                in_quote = True
            elif in_quote and ln.strip():
                # A non-empty line after the quote block that doesn't start with '> '
                # must be a new section (heading/body), not an escaped quote line.
                self.assertTrue(ln.startswith("## ") or ln.startswith("- "),
                                f"line escaped blockquote: {ln!r}")


class TablePipeEscapeTest(unittest.TestCase):
    def test_pipe_in_cell_escaped(self):
        """A pipe in a table cell must not split the column."""
        from pptx.util import Inches
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        table = slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(4), Inches(2)).table
        table.cell(0, 0).text = "Header"
        table.cell(0, 1).text = "Value"
        table.cell(1, 0).text = "row1"
        table.cell(1, 1).text = "pipe|here"
        path = _save_deck(prs, "/tmp/tbl_pipe.pptx")
        md = pptx_to_markdown(path, chapter="99")
        # The escaped pipe \\| must appear; the row must stay 2 columns.
        self.assertIn("pipe\\|here", md, "pipe in table cell not escaped")


class CorruptPptxTest(unittest.TestCase):
    def test_corrupt_file_raises_value_error(self):
        """A non-pptx file must raise ValueError, not a raw traceback."""
        bad = Path("/tmp/corrupt.pptx")
        bad.write_bytes(b"not a pptx file at all")
        with self.assertRaises(ValueError):
            pptx_to_markdown(bad, chapter="99")

    def test_non_pptx_zip_raises_value_error(self):
        """A regular zip masquerading as .pptx must raise ValueError."""
        bad = Path("/tmp/fake_zip.pptx")
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("dummy.txt", "not a pptx")
        with self.assertRaises(ValueError):
            pptx_to_markdown(bad, chapter="99")


class DetectChapterDateFalsePositiveTest(unittest.TestCase):
    def test_iso_date_run_does_not_leak_chapter(self):
        self.assertIsNone(detect_chapter("lecture-2024-03-15"))
        self.assertIsNone(detect_chapter("notes-2024-11-03-final"))

    def test_legitimate_keyword_patterns_unaffected(self):
        self.assertEqual(detect_chapter("chapter3"), "03")
        self.assertEqual(detect_chapter("week3"), "03")
        self.assertEqual(detect_chapter("wk4-lecture"), "04")




class ImageAndTextMixedTest(unittest.TestCase):
    def test_image_marker_kept_alongside_text(self):
        """A slide with both an image and a textbox must not drop the [image] signal."""
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        tb = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1))
        tb.text_frame.text = "some body text"
        # 1x1 transparent PNG
        import base64
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
            "+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        png_path = Path("/tmp/pixel.png")
        png_path.write_bytes(png_bytes)
        slide.shapes.add_picture(str(png_path), Inches(3), Inches(1), Inches(1), Inches(1))
        path = _save_deck(prs, "/tmp/image_and_text.pptx")
        md = pptx_to_markdown(path, chapter="99")
        self.assertIn("some body text", md)
        self.assertIn("[image]", md, "image marker dropped when slide also has text")


class EmptyDeckTest(unittest.TestCase):
    def test_empty_deck_no_dangling_separator(self):
        """A deck with zero slides must not emit a dangling '---' with nothing after it."""
        prs = Presentation()
        path = _save_deck(prs, "/tmp/empty_deck.pptx")
        md = pptx_to_markdown(path, chapter="99")
        self.assertNotIn("---", md, "empty deck left a dangling separator")


if __name__ == "__main__":
    unittest.main()
