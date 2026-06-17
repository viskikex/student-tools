"""Scrape one Kortext book into corpus/<slug>/raw/.

Architecture (post-recon):
  - Auth is a JWT minted from /account/token using saved cookies.
  - All chapter content is plain XHTML behind that JWT.
  - One book = ~17 GET requests (manifest + ncx + spine items).

This script is idempotent: it skips chapters already present in
corpus/<slug>/raw/ unless --force is passed.

Usage:
    .venv/bin/python .claude/skills/kortext-import/scripts/scrape.py \\
        --book-id <BOOK_ID> --slug <slug>

Optional:
    --force                   # re-fetch chapters even if present
    --only-chapter <number>   # fetch just that chapter (e.g. 1)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.kortext.api import KortextClient, SpineItem  # noqa: E402

CORPUS_DIR = PROJECT_ROOT / "corpus"

_CHAPTER_NUM_RE = re.compile(r"_(\d+)_Chapter\.xhtml$")


def chapter_number(href: str) -> int | None:
    """Best-effort: extract a chapter number from a Springer-style href.

    'html/539576_3_En_2_Chapter.xhtml' → 2
    Returns None for non-chapter spine items (Cover, Part_1, frontmatter, etc.).
    """
    m = _CHAPTER_NUM_RE.search(href)
    return int(m.group(1)) if m else None


def safe_filename(href: str) -> str:
    """Map an OEBPS href to a safe local filename.

    The href comes from package.opf, so it's untrusted (a hostile/MITM'd manifest
    could carry `..` or backslashes to escape raw/). Replace path separators, strip
    control chars, and collapse `..` — mirrors canvas-grabber's safeName(). Output
    is unchanged for legit Springer hrefs, so existing corpus files still resolve.
    build_markdown.py keeps an identical copy; keep the two in sync."""
    name = re.sub(r"[\\/]+", "__", href)   # path separators -> __
    name = re.sub(r"[\x00-\x1f]", "", name)  # strip control chars
    name = re.sub(r"\.{2,}", ".", name)    # collapse .. so it can't traverse
    name = name.strip().lstrip(".")
    return name or "file"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", required=True, help="Kortext content id (the number in the reader URL)")
    parser.add_argument("--slug", required=True, help="local slug for corpus directory")
    parser.add_argument("--force", action="store_true", help="re-fetch even if present")
    parser.add_argument("--only-chapter", type=int, help="fetch only this chapter number")
    args = parser.parse_args(argv)

    book_dir = CORPUS_DIR / args.slug
    raw_dir = book_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    with KortextClient() as client:
        info = client.token_info()
        print(f"token: {info['user']} <{info['email']}>, exp in {info['seconds_remaining']}s")

        print(f"fetching manifest for book {args.book_id}…")
        manifest = client.get_manifest(args.book_id)
        print(f"  title: {manifest.title}")
        if manifest.subtitle:
            print(f"  subtitle: {manifest.subtitle}")
        print(f"  authors: {', '.join(manifest.authors)}")
        print(f"  spine items: {len(manifest.spine)}")

        # Write _meta.json with the parsed manifest.
        meta = {
            "book_id": manifest.book_id,
            "title": manifest.title,
            "subtitle": manifest.subtitle,
            "authors": manifest.authors,
            "isbn": manifest.isbn,
            "publisher": manifest.publisher,
            "spine": [
                {
                    "idref": s.idref,
                    "href": s.href,
                    "media_type": s.media_type,
                    "linear": s.linear,
                    "chapter_number": chapter_number(s.href),
                }
                for s in manifest.spine
            ],
            "nav": manifest.nav,
            "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        (book_dir / "_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        print(f"  wrote _meta.json")

        fetched = 0
        skipped = 0
        for item in manifest.spine:
            ch_num = chapter_number(item.href)
            if args.only_chapter is not None and ch_num != args.only_chapter:
                continue
            if item.media_type != "application/xhtml+xml":
                continue
            out_path = raw_dir / safe_filename(item.href)
            if out_path.exists() and not args.force:
                skipped += 1
                continue
            label = f"chapter {ch_num}" if ch_num is not None else item.href
            print(f"  fetching {label}…")
            xhtml = client.get_chapter_xhtml(args.book_id, item.href)
            out_path.write_bytes(xhtml)
            fetched += 1

        print(f"\ndone: fetched {fetched}, skipped {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
