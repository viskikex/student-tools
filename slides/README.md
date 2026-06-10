# slides — pptx → markdown converter

Converts `.pptx` lecture slide decks into markdown, so lecture content can sit alongside textbook notes in [Obsidian](https://obsidian.md) (handy for spotting what the slides cover that the textbook doesn't, and vice versa).

The chapter number is auto-detected from the filename (it understands `ch3`, `chapter3`, `PP3`, `week3`, `lec3`, `module3`, and more).

---

## Setup (one time)

You need **Python 3.11+**. Check with `python3 --version`.

From inside this `slides/` folder:

```bash
# Create an isolated environment and install the one dependency
python3 -m venv .venv
.venv/bin/pip install -e .
```

To run `convert-slides` from anywhere, symlink the wrapper onto your PATH:

```bash
ln -s "$(pwd)/convert-slides" ~/.local/bin/convert-slides
```

(Make sure `~/.local/bin` is on your `PATH`. If `convert-slides` isn't found after this, that's usually why.)

---

## Usage

```bash
# Auto-detect the chapter number from the filename
convert-slides ~/Downloads/Chapter\ 3\ Slides.pptx
# → writes ch03.md

# Override the chapter number if detection gets it wrong
convert-slides ~/Downloads/slides.pptx --chapter 04

# Override the output path entirely
convert-slides ~/Downloads/slides.pptx --out ~/Desktop/ch04.md
```

If you didn't symlink it, run it directly instead:

```bash
.venv/bin/python src/slides/convert.py ~/Downloads/slides.pptx
```

---

## Where output goes

By default, converted files land in `~/textbook-slides/chNN.md`.

To send them somewhere else (like an Obsidian vault folder), set the `SLIDES_DIR` environment variable:

```bash
export SLIDES_DIR="$HOME/Documents/Obsidian Vault/school/slides"
convert-slides ~/Downloads/Chapter\ 3\ Slides.pptx
# → writes to that folder instead
```

Add the `export` line to your `~/.zshrc` (or `~/.bashrc`) to make it stick. The `--out` flag always wins over `SLIDES_DIR` for a single run.

---

## Project layout

```
slides/
├── src/slides/
│   ├── convert.py        # CLI entry point
│   └── render.py         # pptx → markdown renderer
├── convert-slides        # shell wrapper (symlink this onto your PATH)
└── pyproject.toml
```
