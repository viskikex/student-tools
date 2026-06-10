# student-tools

A small collection of personal tools for studying. Each one lives in its own folder with its own setup instructions and can be used independently.

| Tool | What it does |
|------|--------------|
| [**kortext/**](kortext/) | Extracts chapters from a [Kortext](https://kortext.com)-hosted eBook into a clean local markdown corpus, then generates chapter study notes. Works with [Claude Code](https://claude.com/claude-code). |
| [**slides/**](slides/) | Converts `.pptx` lecture slide decks into markdown. |

Both tools produce [Obsidian](https://obsidian.md)-friendly markdown, so a textbook corpus and lecture notes can live side by side in one vault.

## Getting started

Pick the tool you want and follow the README inside its folder:

- **Import a textbook →** [`kortext/README.md`](kortext/README.md)
- **Convert slides →** [`slides/README.md`](slides/README.md)

Each folder has its own Python virtual environment and dependencies, so you only install what the tool you're using actually needs.

## Requirements

- Python 3.11 or newer (`python3 --version` to check)
- macOS or Linux (the shell wrapper and paths assume a Unix-like system)

## A note on the Kortext tool

The `kortext` tool only works with eBooks you already have legitimate access to through your own Kortext account, and is intended for **personal study use only** — see [`kortext/README.md`](kortext/README.md#legal--terms-of-service) for the full disclaimer. The `slides` tool has no such caveats; it just reads files you give it.
