# slides — pptx → markdown converter

Converts `.pptx` lecture slide decks into markdown, so lecture content can sit alongside textbook notes in [Obsidian](https://obsidian.md) (handy for spotting what the slides cover that the textbook doesn't, and vice versa).

The chapter number is auto-detected from the filename (it understands `ch3`, `chapter3`, `PP3`, `week3`, `lec3`, `module3`, and more).

> If the filename has no chapter-style keyword but does carry a stray number — a course number (`PSYC 1100`) or a year (`2024`) — detection can latch onto the wrong one. It ignores 3+ digit runs to avoid the worst of this, but when in doubt pass `--chapter NN` to set it explicitly.

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
- **Mac:** the built-in Python is old — install a current one with [Homebrew](https://brew.sh): `brew install python`.
- **Windows:** install from [python.org/downloads](https://www.python.org/downloads/) — and **tick "Add python.exe to PATH"** in the installer.
- **Linux:** your package manager (`sudo apt install python3` or equivalent).

Then, from inside this `slides/` folder (`cd` into it — e.g. `cd student-tools/slides`), create an isolated environment and install the one dependency:

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

That's it — nothing is installed system-wide, and the install creates a ready-to-run `convert-slides` command inside `.venv`.

---

## Usage

From inside the `slides/` folder:

```bash
# Mac / Linux — auto-detect the chapter number from the filename
.venv/bin/convert-slides ~/Downloads/Chapter\ 3\ Slides.pptx
# → writes ch03.md

# Override the chapter number if detection gets it wrong
.venv/bin/convert-slides ~/Downloads/slides.pptx --chapter 04

# Override the output path entirely
.venv/bin/convert-slides ~/Downloads/slides.pptx --out ~/Desktop/ch04.md
```

```powershell
# Windows — same flags, just the .venv\Scripts\ prefix
.venv\Scripts\convert-slides "$HOME\Downloads\Chapter 3 Slides.pptx"
.venv\Scripts\convert-slides "$HOME\Downloads\slides.pptx" --chapter 04
.venv\Scripts\convert-slides "$HOME\Downloads\slides.pptx" --out "$HOME\Desktop\ch04.md"
```

**Optional / advanced (Mac & Linux only):** to run `convert-slides` from any folder without the `.venv/bin/` prefix, symlink the wrapper onto your PATH:

```bash
ln -s "$(pwd)/convert-slides" ~/.local/bin/convert-slides
```

(This requires `~/.local/bin` to be on your PATH; if you don't know what that means, skip this — the `.venv/bin/convert-slides` form works fine.)

---

## Where output goes

By default, converted files land in `~/textbook-slides/chNN.md`.

To send them somewhere else (like an Obsidian vault folder), set the `SLIDES_DIR` environment variable:

```bash
# Mac / Linux — add to ~/.zshrc (or ~/.bashrc) to make it stick
export SLIDES_DIR="$HOME/Documents/Obsidian Vault/school/slides"
```

```powershell
# Windows — current PowerShell window only:
$env:SLIDES_DIR = "$HOME\Documents\Obsidian Vault\school\slides"
# …or permanently (takes effect in NEW terminal windows):
setx SLIDES_DIR "$HOME\Documents\Obsidian Vault\school\slides"
```

The `--out` flag always wins over `SLIDES_DIR` for a single run.

---

## Project layout

```
slides/
├── src/slides/
│   ├── convert.py        # CLI entry point
│   └── render.py         # pptx → markdown renderer
├── convert-slides        # shell wrapper (optional PATH convenience)
└── pyproject.toml
```
