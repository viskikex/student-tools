# kortext — textbook importer + summarizer

Extracts chapter content from a [Kortext](https://kortext.com)-hosted eBook into a clean local markdown corpus, then (optionally) generates chapter-level study notes.

The import itself (steps 1–4 below) is plain Python and needs nothing else. The **study-notes part is optional** and uses [Claude Code](https://claude.com/claude-code) — a separate, free-to-install AI coding tool from Anthropic that you download and sign into on its own ([install instructions](https://claude.com/claude-code)). If you just want your textbook as markdown, you never need it.

It works because Kortext serves its eBooks as structured XHTML through a normal web API — so instead of screen-scraping page images, this tool just downloads the chapter text directly and converts it to tidy markdown. One book is about 17 small requests.

> **Heads up:** this only works on books you already have access to through your own Kortext account, and it's for personal study only. See [Legal / Terms of Service](#legal--terms-of-service) at the bottom before you use it.

---

## What you get

For each book, a folder under `corpus/<slug>/` containing:

- `NN-<chapter-title>.md` — one clean markdown file per chapter, with section numbering, citations, and emphasis preserved
- `NN-<chapter-title>.notes.md` — study notes (created on demand by the summarizer)
- `_index.md` — a clickable table of contents
- `_meta.json` — the book's parsed metadata
- `raw/` — the original downloaded files (kept as a source of truth so markdown can always be regenerated)

> **What it doesn't carry over:** tables and figures aren't converted — they're left as `[Table omitted in markdown]` / `[Figure — caption]` placeholders. Prose, section numbering, citations, and emphasis come through; if you need an original table or figure, it's in that chapter's `raw/` XHTML.

It all opens cleanly in [Obsidian](https://obsidian.md).

---

## Setup (one time)

You need **Python 3.11 or newer**.

**First, open a terminal:**
- **Mac:** press `Cmd+Space`, type "Terminal", hit Enter.
- **Windows:** press the Windows key, type "PowerShell", hit Enter.
- **Linux:** you know where it is.

**Check your Python:**

```bash
python3 --version        # Mac / Linux
py --version             # Windows
```

If that prints 3.11 or newer, you're set. If not, grab a current Python from [python.org/downloads](https://www.python.org/downloads/) (on Windows, **tick "Add python.exe to PATH"** in the installer; on Mac, `brew install python` via [Homebrew](https://brew.sh) also works).

**Then, from inside this `kortext/` folder** (`cd` into it — e.g. `cd student-tools/kortext`), create an isolated environment and install the tool plus the headless browser Playwright uses for login:

```bash
# Mac / Linux
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/playwright install chromium
```

```powershell
# Windows (PowerShell)
py -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\playwright install chromium
```

That's it. You won't need to repeat this unless you move the folder.

---

## Using it — step by step

There are three steps to import a book — **log in → download → build** — plus an optional one (between log-in and download) to find a book's ID. All commands are run from inside this `kortext/` folder.

> **Using Claude Code? You can skip the commands.** If you've installed Claude Code (the optional tool described above), just open this folder in it and ask in plain language — *"import my textbook"* — and it'll walk the whole pipeline below for you, asking for the book ID and slug as it goes. The commands here are the manual path for people who'd rather not use it (or don't want to install it just to import). Either way, **no AI is required to import** — the commands are plain Python.

> **On Windows:** in every command below, replace the `.venv/bin/` prefix with `.venv\Scripts\` — everything after it is the same.

### Step 1 — Log in (one time, or whenever your login expires)

```bash
.venv/bin/kortext-auth
```

This opens a real browser window. Log into Kortext like you normally would, then come back to the terminal and press **Enter**. Your login is saved to `auth-state.json` so the next steps can run on their own.

> 🔒 **Treat `auth-state.json` like a password.** It's a live session — anyone who gets the file can reach your Kortext account without logging in. It's gitignored and written owner-only (`chmod 600`); don't commit, share, or sync it. If it leaks, log out of Kortext in your browser to invalidate the session, then re-run this step.

> If a later step fails with an "unauthorized" or "401" error, your saved login has expired — just run this step again.

### Optional — Find the book's ID

```bash
.venv/bin/kortext-discover
```

This *tries* to list the books in your library with their IDs — but Kortext's library endpoint isn't always reachable and its response shape varies, so the script may just print raw JSON without a tidy book list. **The dependable way to get an ID is straight from the reader URL:** open the book in Kortext and it's the number in the address bar. Treat `discover.py` as a convenience, the reader URL as the fallback that always works.

You'll also pick a **slug** — a short, hyphenated name for the folder this book gets saved in (for example `intro-psych` or `social-work-200`).

### Step 2 — Download the book

```bash
.venv/bin/kortext-scrape --book-id <BOOK_ID> --slug <slug>
```

Downloads every chapter into `corpus/<slug>/raw/`. Safe to re-run — it skips anything already downloaded, so if your connection drops partway, just run it again.

> Two optional flags: **`--force`** re-downloads even files already present (use it if a chapter came down corrupt or truncated), and **`--only-chapter N`** fetches just chapter `N` instead of the whole book.

### Step 3 — Build the markdown

```bash
.venv/bin/kortext-build --slug <slug>
```

Turns the downloaded files into clean, readable markdown chapters in `corpus/<slug>/`. Open `corpus/<slug>/_index.md` in Obsidian to browse the result.

---

## Making study notes (optional — needs Claude Code)

This part needs [Claude Code](https://claude.com/claude-code), which is **separate software**: an AI assistant that runs in your terminal, installed and signed into independently of this tool (it has free and paid plans — see [claude.com/claude-code](https://claude.com/claude-code) for setup). Everything above this section works without it.

Once you have it, open this folder in Claude Code and ask in plain language, e.g.:

> summarize chapter 3

Claude reads the chapter and writes a `NN-...notes.md` file next to it with core ideas, key terms, cross-chapter connections, and self-test questions. Notes cite **section numbers** (like `§2.2`) rather than page numbers, because the source carries stable section numbering instead of print pages.

The two skills that power this live in `.claude/skills/` and load automatically when you open the folder in Claude Code:

- **kortext-import** — runs the import pipeline above from natural-language requests ("import my textbook")
- **textbook-summarize** — writes the chapter notes ("summarize chapter 3")

---

## Troubleshooting

| Problem | What it means | Fix |
|---------|---------------|-----|
| `unauthorized` / `401` error during scrape | Your saved login expired | Re-run Step 1 (`kortext-auth`) |
| `No module named 'playwright'` | Dependencies aren't installed | Re-run the Setup steps inside this folder |
| A chapter's markdown comes out mostly empty | That chapter's source had an unusual structure — or the raw download was incomplete | Open the matching file in `corpus/<slug>/raw/` to inspect. If the raw XHTML itself looks truncated, re-pull just that chapter (`kortext-scrape --book-id <id> --slug <slug> --force --only-chapter N`) then rebuild it (`kortext-build --slug <slug> --only-chapter N`). If the raw looks fine, the renderer lives in `src/kortext/render.py` |
| Login window never appears | Playwright's browser isn't installed | Run `.venv/bin/playwright install chromium` |

If Kortext changes their website and the tool stops working, the diagnostic scripts in [`recon/`](recon/) exist to help figure out what changed. See `recon/README.md`.

---

## Project layout

```
kortext/
├── src/kortext/
│   ├── api.py            # Kortext API client (login + content fetching)
│   └── render.py         # XHTML → markdown renderer
├── .claude/skills/
│   ├── kortext-import/   # the import pipeline (with scripts/)
│   └── textbook-summarize/
├── recon/                # diagnostic scripts (only needed if the API changes)
├── corpus/               # your imported books land here (not committed to git)
├── CLAUDE.md             # architecture notes for Claude Code / contributors
└── pyproject.toml
```

---

## Legal / Terms of Service

Kortext's terms of service generally prohibit scraping. This tool only requests content through the same path Kortext's own web reader uses, and only for books your account already has legitimate access to. It is intended for **personal study use only** — do not redistribute extracted content.

Using this tool is your responsibility. Respect Kortext's terms and applicable copyright law. If you're not comfortable with that, don't use it.
