# kortext (textbook importer)

CC-native pipeline for extracting Kortext EPUBs into a permanent local markdown corpus, then generating chapter-level study notes via skills. The corpus and notes are written so they open cleanly in Obsidian.

This file is the architecture reference for both humans and Claude Code. Read it before changing the pipeline. (This is one tool in the `student-tools` repo; the sibling `slides/` tool is independent and has its own README.)

## Architecture overview

Kortext serves Springer-formatted EPUB3 chapters as plain XHTML through a REST API — no DOM scraping or per-page Playwright selectors needed. The diagnostic scripts in `recon/` are what revealed this; re-run them if Kortext changes their reader and the scraper breaks.

- The reader fetches chapter content via `https://read.na1.kortext.com/api/content/v1/epub/epub-page/<book_id>/OEBPS/html/<chapter>.xhtml`
- Auth is a JWT obtained from `https://app.na1.kortext.com/account/token` using session cookies
- One book = ~17 GET requests for the whole thing
- The XHTML is Springer's high-quality structured output with proper section numbering, citations, and emphasis

```
auth-state.json (session cookies)  →  /account/token  →  JWT
JWT + cookies                       →  REST chapter XHTML
chapter XHTML                       →  parse with BeautifulSoup  →  markdown
```

Files:
- `src/kortext/api.py` — `KortextClient` (token + manifest + chapter fetch)
- `src/kortext/render.py` — Springer XHTML → Obsidian-flavored markdown
- `src/kortext/cli.py` — thin console entrypoints (`kortext-auth/discover/scrape/build`, registered in `pyproject.toml`) that load and run the skill scripts below. Keeps the manual user-facing path off the hidden `.claude/skills/...` path.
- `.claude/skills/kortext-import/scripts/auth.py` — one-time login
- `.claude/skills/kortext-import/scripts/discover.py` — list the user's library
- `.claude/skills/kortext-import/scripts/scrape.py` — fetch manifest + chapter XHTMLs into `corpus/<slug>/raw/`
- `.claude/skills/kortext-import/scripts/build_markdown.py` — `raw/*.xhtml` → `corpus/<slug>/NN-*.md`
- `recon/` — diagnostic scripts to re-run if Kortext changes their API (`sniff_network.py` logs every reader request to a fresh `network_log.txt`; `check_token.py` validates the JWT path + a chapter fetch). Generated logs contain live tokens and are gitignored — regenerate one when needed rather than keeping a sample around.

`corpus/<slug>/` layout:
```
<slug>/
├── _meta.json                 # parsed package.opf + toc.ncx
├── _index.md                  # human-readable TOC
├── 00a-cover.md
├── 01-introduction.md
├── 02-<chapter-title>.md
├── ...
├── NN-<chapter-title>.notes.md   # study notes (written by textbook-summarize)
└── raw/                       # original XHTMLs from Kortext, source of truth
    └── html__<...>_Chapter.xhtml
```

## Skills

- **`kortext-import`** — auth → discover → scrape → build markdown. Each stage idempotent.
- **`textbook-summarize`** — reads `corpus/<slug>/NN-*.md`, writes parallel `.notes.md`. No script, pure prompt.

Both at `.claude/skills/<name>/SKILL.md`.

## Pipeline (canonical commands)

Console entrypoints (after `pip install -e .`); each wraps the like-named `scripts/*.py`:

```bash
# one-time: log in to Kortext, save cookies
.venv/bin/kortext-auth

# (optional) list books in your library
.venv/bin/kortext-discover

# fetch the whole book (skips already-downloaded)
.venv/bin/kortext-scrape --book-id <BOOK_ID> --slug <slug>

# build markdown from raw XHTMLs
.venv/bin/kortext-build --slug <slug>

# then point CC at corpus/<slug>/ and ask
# "summarize chapter 1" → triggers textbook-summarize
```

## Citation strategy in summaries

The Springer XHTML doesn't embed EPUB pagebreaks, so we don't have inline print-page markers. Instead, chapters carry explicit section numbering (`2.1`, `2.2.2`, …) which the markdown preserves as `## 2.1 ...`, `### 2.2.2 ...`. The `textbook-summarize` skill cites by section: `(§2.2.2)` rather than `(p. 47)`. Section numbers are stable across editions and arguably more useful for study.

If we ever need print-page mapping, `/api/content/v1/metadata/pages?contentId=<book_id>` returned 200 during recon — that's likely a chapter↔page-range mapping we can fold in later.

## Quality notes for summaries

- Don't smooth over mechanism-level detail to be concise — exam questions live in specifics.
- Flag contested stances as contested, not as fact.
- Preserve the source chapter's own framing of identity, culture, and group categories rather than substituting generic language. (Especially relevant for social-science texts, where summarization most often flattens nuance.)
- Cite section numbers using the `## N.M ...` headings in the source.

## Scope notes

- Working > elegant. This is a study tool, not production software — don't gold-plate.
- Tables and figures are placeholdered (`[Table omitted in markdown]`, `[Figure — caption]`). Acceptable.

## Ethics / Terms of Service

Kortext's terms generally prohibit scraping. This tool only uses the content path Kortext deliberately exposes to its own reader UI, applied to books the user already has legitimate access to. It is for **personal study use only** — do not redistribute extracted content. Using it is your responsibility; respect Kortext's terms and applicable copyright.

## Known minor issues

- Nested numbered lists render as `1. 1.` doubles (Springer wraps OL-in-OL for some lists). Not blocking.
- Tables and figures are placeholdered. Acceptable.
