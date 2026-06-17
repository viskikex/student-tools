"""Console entrypoints for the kortext import pipeline.

These exist so the manual (no-Claude-Code) path is a clean
`kortext-scrape --book-id X --slug Y` instead of a long path into a hidden
`.claude/skills/...` folder. They're thin wrappers: the actual logic lives in
the skill scripts, which Claude Code also runs directly. Nothing is duplicated.

Wired up in pyproject.toml under [project.scripts]; available after
`pip install -e .`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# src/kortext/cli.py → parents[2] is the kortext project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / ".claude" / "skills" / "kortext-import" / "scripts"


def _load(filename: str):
    """Load a skill script as a module (not as __main__, so its main() runs
    only when we call it)."""
    path = SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(f"kortext_script_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def auth() -> None:
    raise SystemExit(_load("auth.py").main())


def discover() -> None:
    raise SystemExit(_load("discover.py").main())


def scrape() -> None:
    raise SystemExit(_load("scrape.py").main(sys.argv[1:]))


def build() -> None:
    raise SystemExit(_load("build_markdown.py").main(sys.argv[1:]))
