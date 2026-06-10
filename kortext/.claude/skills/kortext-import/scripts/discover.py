"""List the user's Kortext library.

Helpful to find the content-id of a new book. Once you have the id, run
scrape.py with that id + a local slug.

Usage:
    .venv/bin/python .claude/skills/kortext-import/scripts/discover.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.kortext.api import KortextClient  # noqa: E402


def main() -> int:
    with KortextClient() as client:
        try:
            library = client.list_books()
        except Exception as e:
            print(f"library endpoint failed: {e}", file=sys.stderr)
            print("(if scrape.py works with a known book id, this is non-fatal)", file=sys.stderr)
            return 1

        # Library response shape varies — dump pretty for inspection, then try
        # to extract a useful summary.
        print(json.dumps(library, indent=2)[:4000])

        # Heuristic: look for common shapes (data.books, results, items).
        candidates = []
        if isinstance(library, dict):
            for key in ("data", "books", "items", "results"):
                v = library.get(key)
                if isinstance(v, list):
                    candidates = v
                    break
        elif isinstance(library, list):
            candidates = library

        if candidates:
            print(f"\n--- {len(candidates)} books ---")
            for b in candidates:
                if not isinstance(b, dict):
                    continue
                bid = b.get("id") or b.get("contentId") or b.get("bookId")
                title = b.get("title") or b.get("name") or "?"
                print(f"  {bid}  {title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
