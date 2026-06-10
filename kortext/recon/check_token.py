"""Test whether /account/token gives us the JWT directly with saved cookies.

If yes: scraping architecture is
  recon.py (one-time login) → save cookies → token endpoint → JWT → fetch
  every chapter XHTML directly. No headed browser per scrape.

If no (e.g. needs CSRF or in-page state): we'll capture the JWT from a
live reader session instead.
"""

from __future__ import annotations

import json
import base64
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent
AUTH_STATE_PATH = PROJECT_ROOT / "auth-state.json"
OUT_DIR = PROJECT_ROOT / "probe_out"


def decode_jwt_payload(token: str) -> dict:
    """Decode a JWT payload without verifying signature — for inspection only."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    # JWT base64 is url-safe and unpadded.
    padded = payload + "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def main() -> None:
    with sync_playwright() as p:
        # No browser needed if /account/token works with just cookies.
        # But we'll use a Playwright context to load storage_state cleanly.
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(AUTH_STATE_PATH))

        # Variant 1: bare GET with cookies only.
        resp = context.request.get("https://app.na1.kortext.com/account/token")
        print(f"GET /account/token  →  status={resp.status}  ct={resp.headers.get('content-type')}  len={len(resp.body())}")
        body = resp.text()
        print(f"body[:500]:\n{body[:500]}")
        (OUT_DIR / "token_response.txt").write_text(body, encoding="utf-8")

        # If the body looks like a JWT (three dot-separated chunks of base64),
        # decode and show its payload.
        stripped = body.strip().strip('"')
        if stripped.count(".") == 2 and all(c.isalnum() or c in "-_." for c in stripped):
            try:
                payload = decode_jwt_payload(stripped)
                exp = payload.get("exp")
                if exp:
                    exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
                    delta = exp_dt - datetime.now(tz=timezone.utc)
                    print(f"\nJWT decoded — exp in {delta} (UTC {exp_dt.isoformat()})")
                print(f"payload: {json.dumps(payload, indent=2)[:600]}")

                # Try fetching chapter 2 with this token to confirm it works.
                token = stripped
                resp2 = context.request.get(
                    "https://read.na1.kortext.com/api/content/v1/epub/epub-page/<BOOK_ID>/OEBPS/html/<PKG_ID>_3_En_2_Chapter.xhtml",
                    headers={"Authorization": f"Bearer {token}"},
                )
                print(f"\nGET chapter 2 XHTML with bearer  →  status={resp2.status}  len={len(resp2.body())}")
                if 200 <= resp2.status < 300:
                    (OUT_DIR / "chapter_2.xhtml").write_bytes(resp2.body())
                    print("saved to probe_out/chapter_2.xhtml")
            except Exception as e:
                print(f"JWT decode/test failed: {e}")
        else:
            print("\n(body doesn't look like a bare JWT — may be HTML-wrapped)")

        browser.close()


if __name__ == "__main__":
    main()
