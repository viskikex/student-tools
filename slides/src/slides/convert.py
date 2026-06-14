#!/usr/bin/env python3
r"""Convert a .pptx lecture slide deck to markdown for gap analysis.

Usage:
    convert-slides <input.pptx> [--chapter NN] [--out PATH]

Output lands at:
    $SLIDES_DIR/chNN.md   (defaults to ~/textbook-slides/chNN.md)

Set the SLIDES_DIR environment variable to point output wherever you like
(e.g. an Obsidian vault folder), or use --out to override per run.

Chapter number is auto-detected from the filename. Pass --chapter to override
if detection gets it wrong.

Examples:
    convert-slides ~/Downloads/Chapter\ 3\ Slides.pptx
    convert-slides ~/Downloads/wk4-lecture.pptx --chapter 04
    convert-slides ~/Downloads/slides.pptx --out ~/Desktop/custom.md
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Allow running as a script from any cwd
sys.path.insert(0, str(Path(__file__).parent.parent))

from slides.render import pptx_to_markdown

# Default output directory. Override with the SLIDES_DIR environment variable
# (e.g. point it at an Obsidian vault folder), or use --out per run.
SLIDES_DIR = Path(os.environ.get("SLIDES_DIR") or Path.home() / "textbook-slides")

# Patterns tried in order against the stem (case-insensitive).
# Each yields the raw digit string; we zero-pad to 2 digits.
_CHAPTER_PATTERNS = [
    r"ch(?:p|ap(?:ter)?)?[\s_-]*(\d+)",  # chapter3, chap3, chp3, ch3, ch-3
    r"pp[\s_-]*(\d+)",                  # PP2, pp 3
    r"week[\s_-]*(\d+)",               # week3, week-3
    r"wk[\s_-]*(\d+)",                 # wk3
    r"mod(?:ule)?[\s_-]*(\d+)",        # module3, mod3
    r"lec(?:ture)?[\s_-]*(\d+)",       # lecture3, lec3
    r"unit[\s_-]*(\d+)",               # unit3
    # Bare number at a word boundary, last resort. Capped at 1-2 digits so a
    # stray course number (1100) or year (2024) doesn't get read as a chapter;
    # 3+ digit runs are skipped. Ambiguous cases should use --chapter.
    r"(?:^|[\s_-])(\d{1,2})(?:[\s_-]|$)",
]


def detect_chapter(stem: str) -> str | None:
    """Try to extract a chapter number from a filename stem."""
    for pattern in _CHAPTER_PATTERNS:
        m = re.search(pattern, stem, re.IGNORECASE)
        if m:
            return m.group(1).zfill(2)
    return None


def resolve_chapter(explicit: str | None, input_path: Path) -> str | None:
    if explicit:
        return explicit.zfill(2)
    detected = detect_chapter(input_path.stem)
    return detected


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a .pptx slide deck to markdown for gap analysis."
    )
    parser.add_argument("input", type=Path, help="Path to the .pptx file")
    parser.add_argument(
        "--chapter", "-c",
        metavar="NN",
        help="Override chapter number (e.g. 02). Auto-detected from filename if omitted.",
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
    if input_path.suffix.lower() != ".pptx":
        print(f"error: expected a .pptx file, got: {input_path.suffix}", file=sys.stderr)
        sys.exit(1)

    chapter = resolve_chapter(args.chapter, input_path)

    if args.out:
        output_path = args.out.expanduser().resolve()
    elif chapter:
        SLIDES_DIR.mkdir(parents=True, exist_ok=True)
        output_path = SLIDES_DIR / f"ch{chapter}.md"
    else:
        # No chapter detected and no --out: drop alongside the input file
        print(
            f"warning: couldn't detect chapter number from '{input_path.stem}'. "
            "Writing alongside input. Use --chapter NN to set it explicitly.",
            file=sys.stderr,
        )
        output_path = input_path.with_suffix(".md")

    print(f"converting: {input_path.name}")
    if chapter:
        print(f"chapter:    {chapter}")
    md = pptx_to_markdown(input_path, chapter=chapter)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding="utf-8")
    print(f"written:    {output_path}")


if __name__ == "__main__":
    main()
