#!/usr/bin/env python3
r"""Convert a course syllabus (.docx or .pdf) to markdown.

Usage:
    convert-syllabus <syllabus.docx|syllabus.pdf> [--year YYYY] [--out PATH]

Output lands at:
    $SYLLABUS_DIR/<slug>.md   (defaults to ~/syllabi/<slug>.md)

The output starts with a "Key dates" table: every date-looking string in the
document, sorted chronologically, with the line it appeared on. Below that is
the full converted document. Dates without an explicit year get the year the
document mentions most often; pass --year to override.

Set the SYLLABUS_DIR environment variable to point output somewhere permanent
(e.g. an Obsidian vault folder), or use --out per run.

Examples:
    convert-syllabus ~/Downloads/SOC\ 101\ Syllabus\ Spring\ 26.docx
    convert-syllabus syllabus.pdf --out ~/Desktop/psci210-syllabus.md
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

# Allow running as a script from any cwd
sys.path.insert(0, str(Path(__file__).parent.parent))

# defang() lives in dates.py (the single copy for this tool) — applied to the
# converted body + the filename-stem heading below so a syllabus can't pull other
# vault notes into the output. Safe on converter output, which never emits real
# wikilinks.
from syllabus.dates import defang, extract_dates, infer_year, render_table

SYLLABUS_DIR = Path(os.environ.get("SYLLABUS_DIR") or Path.home() / "syllabi")


def slugify(stem: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return slug or "syllabus"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a .docx or .pdf syllabus to markdown with a key-dates table."
    )
    parser.add_argument("input", type=Path, help="Path to the .docx or .pdf syllabus")
    parser.add_argument(
        "--year", "-y",
        type=int,
        metavar="YYYY",
        help="Year for dates that don't state one. Auto-inferred from the document if omitted.",
    )
    parser.add_argument(
        "--out", "-o",
        type=Path,
        metavar="PATH",
        help="Override output file path entirely.",
    )
    args = parser.parse_args()

    input_path: Path = args.input.expanduser().resolve()
    if not input_path.exists():
        print(f"error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    suffix = input_path.suffix.lower()
    if suffix == ".docx":
        from syllabus.docx2md import docx_to_markdown
        body = docx_to_markdown(input_path)
    elif suffix == ".pdf":
        from syllabus.pdf2md import pdf_to_markdown
        body = pdf_to_markdown(input_path)
    elif suffix == ".doc":
        print(
            "error: old-style .doc isn't supported. Open it in Word/Pages/Google Docs "
            "and save as .docx, then re-run.",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print(f"error: expected a .docx or .pdf file, got: {suffix or '(no extension)'}", file=sys.stderr)
        sys.exit(1)

    year = args.year or infer_year(body) or date.today().year
    entries = extract_dates(body, default_year=year)

    if args.out:
        output_path = args.out.expanduser().resolve()
    else:
        SYLLABUS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = SYLLABUS_DIR / f"{slugify(input_path.stem)}.md"

    md = "\n".join([
        f"# {defang(input_path.stem)}",
        "",
        f"> Converted from `{input_path.name}` on {date.today():%Y-%m-%d}. "
        f"The key dates below are auto-extracted (assumed year: {year}) — "
        "syllabi drift, so verify anything load-bearing against Canvas.",
        "",
        "## Key dates (auto-extracted)",
        "",
        render_table(entries),
        "",
        "---",
        "",
        defang(body),
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding="utf-8")
    print(f"converted:  {input_path.name}")
    print(f"key dates:  {len(entries)} found (assumed year {year})")
    print(f"written:    {output_path}")


if __name__ == "__main__":
    main()
