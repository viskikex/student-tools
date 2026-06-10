---
name: kortext-import
description: Use when the user wants to import, scrape, download, or extract a Kortext eBook/textbook into the local corpus. Handles authentication, fetching the EPUB manifest, downloading chapter XHTML via Kortext's API, and conversion to Obsidian-flavored markdown. Trigger phrases include "import my textbook", "scrape this book", "pull chapter X from Kortext", "add book to corpus".
---

# kortext-import

End-to-end pipeline for getting a Kortext book into the local markdown corpus. Each stage is idempotent so re-running is safe.

## Architecture (one-line version)

Kortext serves Springer EPUB3 chapters as XHTML through a REST API. We mint a JWT from `/account/token` using saved session cookies, then fetch every chapter and build markdown locally. ~17 GET requests per book.

## Stages

### 1. `scripts/auth.py` — first-time / refresh login

Run when:
- `auth-state.json` doesn't exist yet, OR
- `scrape.py` fails with an "Unauthorized" / "401" / "token endpoint returned" error (cookies went stale).

```bash
.venv/bin/python .claude/skills/kortext-import/scripts/auth.py
```

Opens headed Chromium. User logs in manually. When they press Enter, the script saves `storageState` to `auth-state.json` and closes the browser.

### 2. `scripts/discover.py` — list the user's library

Optional. Useful for finding a new book's content id.

```bash
.venv/bin/python .claude/skills/kortext-import/scripts/discover.py
```

Once you have a `book_id`, pick a `slug` for it (kebab-case, e.g. `multicultural-psych`, `social-work-200`). The slug becomes the corpus directory name.

### 3. `scripts/scrape.py` — fetch manifest + chapter XHTMLs

```bash
.venv/bin/python .claude/skills/kortext-import/scripts/scrape.py \
    --book-id <BOOK_ID> --slug <slug>
```

What it does:
- Mints a JWT from `/account/token` using saved cookies.
- Fetches `OEBPS/package.opf` (spine + metadata) and `OEBPS/toc.ncx` (navigation).
- Writes `corpus/<slug>/_meta.json` with parsed metadata.
- For each spine item that's an `application/xhtml+xml`: fetches it to `corpus/<slug>/raw/<safe-filename>.xhtml`. Skips files that already exist.

Flags:
- `--force` re-fetch even if present
- `--only-chapter N` fetch just chapter N (useful for testing)

If a chapter fails partway through (network blip), just re-run — already-present chapters are skipped.

### 4. `scripts/build_markdown.py` — XHTML → markdown corpus

```bash
.venv/bin/python .claude/skills/kortext-import/scripts/build_markdown.py \
    --slug multicultural-psych
```

What it does:
- Reads `corpus/<slug>/_meta.json` + `corpus/<slug>/raw/*.xhtml`.
- For each spine item: parses the XHTML and writes `corpus/<slug>/NN-<slugified-title>.md` with frontmatter pointing back at the source.
- Writes `corpus/<slug>/_index.md` (linked TOC for Obsidian).

Idempotent — rewrites markdown from raw on every run. Raw files are the source of truth; markdown can always be regenerated.

Flags:
- `--only-chapter N` rebuild just that chapter (also skips writing `_index.md`).

## Verification after a run

1. `ls corpus/<slug>/` shows numbered chapter files + `_index.md` + `_meta.json` + `raw/`.
2. Open `corpus/<slug>/01-*.md` in Obsidian. Section headings should match the printed book; inline citations like `(Smith, 2020)` should be intact; the chapter frontmatter should have the right title and author.
3. If something looks off, the fix is almost always in `src/kortext/render.py` — re-render is free (no network).

## When something fails

| Error | Meaning | Fix |
|-------|---------|-----|
| `token endpoint returned 401` | Session cookies expired | re-run `auth.py` |
| `RuntimeError: 401 ... /api/content/...` | JWT didn't carry — same root cause | re-run `auth.py` |
| `No module named 'src'` | Script path resolution bug | check `PROJECT_ROOT = parents[4]` |
| Chapter file is mostly empty | XHTML structure unusual | open `raw/*.xhtml` for that chapter and inspect; tweak `render.py` |

## Don't

- Don't scrape books the user hasn't been assigned or doesn't own access to.
- Don't redistribute the corpus. Personal study use only.
