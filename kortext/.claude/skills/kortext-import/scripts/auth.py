"""One-time / refresh auth flow for Kortext.

Launches a headed Chromium, lets you log into Kortext manually, then saves
storageState to auth-state.json at the project root. After this, scrape.py
can run headlessly using those cookies (plus a JWT it mints from
`https://app.na1.kortext.com/account/token`).

Re-run me if scrape.py fails with an unauthorized error (cookies went stale).

Usage:
    .venv/bin/python .claude/skills/kortext-import/scripts/auth.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[4]
AUTH_STATE_PATH = PROJECT_ROOT / "auth-state.json"
KORTEXT_URL = "https://app.kortext.com/"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.goto(KORTEXT_URL)

        print()
        print("=" * 60)
        print("Log into Kortext in the browser window that just opened.")
        print("When you're logged in and can see your library, come back")
        print("here and press Enter.")
        print("=" * 60)
        input("press Enter when logged in > ")

        context.storage_state(path=str(AUTH_STATE_PATH))
        # This file holds a live session (account access without re-login), so
        # restrict it to the owner. On Windows chmod is a near-no-op but harmless.
        AUTH_STATE_PATH.chmod(0o600)
        print(f"saved auth state → {AUTH_STATE_PATH.relative_to(PROJECT_ROOT)}")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
