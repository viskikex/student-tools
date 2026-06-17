"""Build markdown corpus from raw EPUB XHTMLs.

Reads corpus/<slug>/_meta.json + corpus/<slug>/raw/*.xhtml and writes:
  - corpus/<slug>/_index.md         (linked TOC)
  - corpus/<slug>/NN-<slugified>.md (one per chapter spine item)

Idempotent: rewrites markdown from raw on every run. Raw files are the
source of truth; markdown can always be regenerated.

Usage:
    .venv/bin/python .claude/skills/kortext-import/scripts/build_markdown.py \\
        --slug multicultural-psych

Optional:
    --only-chapter <number>   # rebuild just that chapter
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.kortext.render import render_chapter  # noqa: E402

CORPUS_DIR = PROJECT_ROOT / "corpus"


def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    return s[:60] or "chapter"


def safe_filename(href: str) -> str:
    """Map an OEBPS href to a safe local filename.

    The href comes from package.opf, so it's untrusted (a hostile/MITM'd manifest
    could carry `..` or backslashes to escape raw/). Replace path separators, strip
    control chars, and collapse `..` — mirrors canvas-grabber's safeName(). Output
    is unchanged for legit Springer hrefs, so existing corpus files still resolve.
    scrape.py keeps an identical copy; keep the two in sync."""
    name = re.sub(r"[\\/]+", "__", href)   # path separators -> __
    name = re.sub(r"[\x00-\x1f]", "", name)  # strip control chars
    name = re.sub(r"\.{2,}", ".", name)    # collapse .. so it can't traverse
    name = name.strip().lstrip(".")
    return name or "file"


def _to_roman(n: int) -> str:
    """Tiny int → lowercase roman numeral. Good enough for textbook Part counts (1-20)."""
    table = [
        (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
    ]
    out = []
    for value, sym in table:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--only-chapter", type=int)
    args = parser.parse_args(argv)

    book_dir = CORPUS_DIR / args.slug
    raw_dir = book_dir / "raw"
    meta_path = book_dir / "_meta.json"
    if not meta_path.exists():
        print(f"no _meta.json at {meta_path} — run scrape.py first", file=sys.stderr)
        return 2
    meta = json.loads(meta_path.read_text())

    # Decide which spine items become chapter markdown files.
    # We include any spine item with a real chapter number, plus front/back
    # matter as their own files so nothing important is dropped.
    today = date.today().isoformat()
    index_entries: list[tuple[int, str, str]] = []  # (order, label, md_filename)
    order = 0
    last_chapter = 0  # track last seen chapter number so Parts sort right after it

    for spine in meta["spine"]:
        href = spine["href"]
        ch_num = spine.get("chapter_number")
        if args.only_chapter is not None and ch_num != args.only_chapter:
            continue
        if spine["media_type"] != "application/xhtml+xml":
            continue
        raw_path = raw_dir / safe_filename(href)
        if not raw_path.exists():
            print(f"  skipping {href}: raw file not present (run scrape first)")
            continue

        order += 1
        xhtml = raw_path.read_bytes()
        rendered = render_chapter(xhtml)

        # Pick a filename prefix that makes Obsidian's file explorer sort right.
        # - Cover/frontmatter come first (00a, 00b)
        # - Chapters use their own number (NN)
        # - Part dividers sit between the chapter that precedes them and the next one
        #   by using `NNz-part-{roman}` — z sorts after any chapter-number prefix
        # - Backmatter sorts last (zz)
        skip_title_suffix = False
        if ch_num is not None:
            prefix = f"{ch_num:02d}"
            last_chapter = ch_num
        elif "Cover" in href:
            prefix = "00a-cover"
            skip_title_suffix = True
        elif "Frontmatter" in href:
            prefix = "00b-frontmatter"
            skip_title_suffix = True
        elif "Backmatter" in href:
            prefix = "zz-backmatter"
            skip_title_suffix = True
        elif href.startswith("html/Part_"):
            # Extract the part number from "html/Part_1.xhtml" → "1" → "i"
            part_digit = href.removeprefix("html/Part_").rstrip(".xhtml").rstrip("_")
            try:
                roman = _to_roman(int(part_digit))
            except ValueError:
                roman = part_digit.lower()
            prefix = f"{last_chapter:02d}z-part-{roman}"
            skip_title_suffix = True  # filename is self-explanatory; title can be long
        else:
            prefix = f"{order:02d}"

        if skip_title_suffix:
            md_filename = f"{prefix}.md"
        else:
            md_filename = f"{prefix}-{slugify(rendered.title_clean)}.md"
        md_path = book_dir / md_filename

        # Frontmatter block.
        fm = [
            "---",
            f"book: {json.dumps(meta['title'])}",
            f"authors: {', '.join(meta['authors'])}",
            f"course: {args.slug}",
            f"chapter: {ch_num if ch_num is not None else 'null'}",
            f"chapter_title: {json.dumps(rendered.title_clean)}",
            f"source: raw/{safe_filename(href)}",
            f"scraped_at: {today}",
            "---",
            "",
        ]
        body = [f"# {rendered.title}", "", rendered.markdown]
        md_path.write_text("\n".join(fm + body), encoding="utf-8")
        print(f"  wrote {md_filename}")

        index_entries.append((order, rendered.title, md_filename))

    # Build _index.md.
    if args.only_chapter is None:
        idx_lines = [
            f"# {meta['title']}",
            "",
        ]
        if meta.get("subtitle"):
            idx_lines += [f"*{meta['subtitle']}*", ""]
        idx_lines += [
            f"{', '.join(meta['authors'])}  ",
            f"{meta.get('publisher') or ''}  ",
            f"ISBN: {meta.get('isbn') or 'n/a'}",
            "",
            "## Chapters",
            "",
        ]
        for _, label, fname in index_entries:
            idx_lines.append(f"- [{label}]({fname})")
        (book_dir / "_index.md").write_text("\n".join(idx_lines) + "\n", encoding="utf-8")
        print(f"  wrote _index.md")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
