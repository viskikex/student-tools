# syllabus — drop a syllabus in, get markdown out

Converts a course syllabus (`.docx` from Word/Google Docs, or `.pdf` — including Canvas's "print syllabus" pages) into clean markdown, so it can live in [Obsidian](https://obsidian.md) next to your notes, slides, and Canvas data.

The output leads with a **Key dates table**: every date mentioned anywhere in the document, sorted chronologically, with the computed weekday and the sentence it came from. No AI involved — it's plain pattern-matching, which means it's fast, free, runs offline, and never invents a date that isn't in the document. The full converted syllabus follows below the table.

A nice side effect of the computed weekday: it catches professor typos. If the syllabus says "Friday, January 15" and the table says `Thu`, one of them is wrong — and it isn't the calendar.

Works on **macOS, Linux, and Windows**. The setup below shows both flavors — follow the one matching your machine.

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

If that prints 3.11 or newer, you're set. If not:
- **Mac:** the built-in Python is old — install a current one with [Homebrew](https://brew.sh): `brew install python`. (If the install step below still complains about the version, call the new one explicitly: `/opt/homebrew/bin/python3` instead of `python3`.)
- **Windows:** install from [python.org/downloads](https://www.python.org/downloads/) — and **tick "Add python.exe to PATH"** in the installer.
- **Linux:** your package manager (`sudo apt install python3` or equivalent).

**Then, from inside this `syllabus/` folder** (`cd` into it — e.g. `cd student-tools/syllabus`), create an isolated environment and install the two dependencies:

```bash
# Mac / Linux
python3 -m venv .venv
.venv/bin/pip install -e .
```

```powershell
# Windows (PowerShell)
py -m venv .venv
.venv\Scripts\pip install -e .
```

That's it. The install creates a ready-to-run `convert-syllabus` command inside `.venv` — nothing is installed system-wide, and deleting the folder removes everything.

---

## Usage

From inside the `syllabus/` folder:

```bash
# Mac / Linux
.venv/bin/convert-syllabus ~/Downloads/"SOC 101 Syllabus Spring 26.docx"
# → writes ~/syllabi/soc-101-syllabus-spring-26.md
```

```powershell
# Windows
.venv\Scripts\convert-syllabus "$HOME\Downloads\SOC 101 Syllabus Spring 26.docx"
# → writes <your home folder>\syllabi\soc-101-syllabus-spring-26.md
```

Options (same on every platform):

```bash
# Choose the output file yourself
.venv/bin/convert-syllabus syllabus.pdf --out ~/Desktop/psci210-syllabus.md

# Force the year used for dates that don't state one (auto-detected otherwise)
.venv/bin/convert-syllabus syllabus.docx --year 2026
```

**Optional / advanced (Mac & Linux only):** `./convert-syllabus` is a small wrapper that does the same thing; to run it from any folder, symlink it onto your PATH:

```bash
ln -s "$(pwd)/convert-syllabus" ~/.local/bin/convert-syllabus
```

(This requires `~/.local/bin` to be on your PATH; if you don't know what that means, skip this — the `.venv/bin/convert-syllabus` form works fine.)

---

## Where output goes

By default, converted files land in a `syllabi` folder in your home directory. To send them somewhere else (like your Obsidian vault), set the `SYLLABUS_DIR` environment variable:

```bash
# Mac / Linux — add to ~/.zshrc (or ~/.bashrc) to make it stick
export SYLLABUS_DIR="$HOME/Documents/Obsidian Vault/school/multicultural-psych"
```

```powershell
# Windows — current PowerShell window only:
$env:SYLLABUS_DIR = "$HOME\Documents\Obsidian Vault\school\multicultural-psych"
# …or permanently (takes effect in NEW terminal windows):
setx SYLLABUS_DIR "$HOME\Documents\Obsidian Vault\school\multicultural-psych"
```

The `--out` flag always wins over `SYLLABUS_DIR` for a single run.

---

## What it does and doesn't do

**Does:**
- `.docx`: preserves headings (including school-template styles like "SyllabusHeading1"), bulleted/numbered lists, and tables. Hand-bolded section labels ("Office Hours" in bold instead of a real heading style) are detected and promoted to headings.
- `.pdf`: extracts the text and repairs the broken ligatures Canvas's print-to-PDF produces (`Informa!on` → `Information`).
- Finds dates in most formats: `February 13`, `Feb. 13th, 2026`, `04/05`, `4/5/26`. Dates without a year get the year the document mentions most often.

**Doesn't:**
- Parse the schedule *structure*. Every professor lays out their schedule differently (week-by-week, module-based prose, tables, …) — a deterministic tool that pretended to understand all of them would be quietly wrong. The flat date table is the honest version: complete, sorted, with context, and you do the judging.
- Produce perfect PDF text. PDF extraction is inherently best-effort — spacing can be odd, and some ligature damage is ambiguous (the same broken glyph can mean "tt" or "ft"). The `.docx` path is much cleaner; prefer it when you have both.
- Old-style `.doc` files. Open them in Word/Pages/Google Docs, save as `.docx`, re-run.

---

## Project layout

```
syllabus/
├── src/syllabus/
│   ├── convert.py      # CLI entry point
│   ├── docx2md.py      # docx → markdown (headings, lists, tables)
│   ├── pdf2md.py       # pdf → text + ligature repair
│   └── dates.py        # date extraction for the key-dates table
├── convert-syllabus    # shell wrapper (Mac/Linux convenience)
└── pyproject.toml
```
