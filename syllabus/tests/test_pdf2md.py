"""Tests for pdf_to_markdown — the .pdf -> text converter.

Focus: scanned (image-only) PDFs warn instead of silently producing near-empty
output, and corrupt/encrypted PDFs raise ValueError (caught cleanly by the
CLI) instead of a raw pypdf traceback.

Run from the syllabus/ folder:  .venv/bin/python -m unittest discover tests
"""

import io
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pypdf import PdfWriter

from syllabus.pdf2md import pdf_to_markdown

TMP = Path("/tmp/syllabus_pdf2md_test")
TMP.mkdir(exist_ok=True)


class ScannedPdfTest(unittest.TestCase):
    def test_no_text_layer_warns_on_stderr(self):
        w = PdfWriter()
        w.add_blank_page(width=200, height=200)
        path = TMP / "scanned.pdf"
        with open(path, "wb") as f:
            w.write(f)

        buf = io.StringIO()
        with redirect_stderr(buf):
            md = pdf_to_markdown(path)
        self.assertIn("no extractable text layer", buf.getvalue())
        self.assertEqual(md, "\n")


class CorruptPdfTest(unittest.TestCase):
    def test_non_pdf_raises_value_error(self):
        bad = TMP / "notapdf.pdf"
        bad.write_bytes(b"%PDF-1.4\nnot really\n%%EOF\n")
        with self.assertRaises(ValueError):
            pdf_to_markdown(bad)

    def test_encrypted_pdf_raises_value_error(self):
        w = PdfWriter()
        w.add_blank_page(width=200, height=200)
        w.encrypt("secret")
        path = TMP / "encrypted.pdf"
        with open(path, "wb") as f:
            w.write(f)
        with self.assertRaises(ValueError):
            pdf_to_markdown(path)


if __name__ == "__main__":
    unittest.main()
