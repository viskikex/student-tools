"""Wide network sniff: log every kortext.com request the reader makes.

Probe 03 saw zero matching requests, which suggests one of:
  - chapter XHTML is service-worker-cached, no network fire on re-load
  - the request URL doesn't match my guess
  - the reader fetches content via a different endpoint shape

Strategy: log EVERY request to *.kortext.com, sorted by content-type and
url pattern, with full request headers for anything that looks auth-y.
Then do a fresh-context load (no storage state) and a real load, so we
can see what the bootstrap actually does.

Also: navigate to a different chapter URL after first load to force a
content fetch (in case the initial open uses cached data).
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent
AUTH_STATE_PATH = PROJECT_ROOT / "auth-state.json"
OUT_DIR = PROJECT_ROOT / "probe_out"
BASE = "https://read.na1.kortext.com"
BOOK_ID = "REPLACE_WITH_YOUR_BOOK_ID"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    log_path = OUT_DIR / "network_log.txt"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            storage_state=str(AUTH_STATE_PATH),
            viewport={"width": 1400, "height": 900},
            # Disable cache to force fresh requests.
            bypass_csp=True,
        )

        # Disable service worker to force network requests through where we can see them.
        context.add_init_script("delete navigator.serviceWorker;")

        events: list[str] = []
        start = time.time()

        def stamp() -> str:
            return f"[{time.time() - start:6.2f}s]"

        def on_request(req):
            if "kortext.com" not in req.url:
                return
            line = f"{stamp()} REQ  {req.method:5s} {req.url}"
            events.append(line)
            # Capture auth-looking headers for content endpoints.
            if "/api/content/" in req.url or "/api/" in req.url:
                hdrs = dict(req.headers)
                interesting = {
                    k: v for k, v in hdrs.items()
                    if k.lower() in {"authorization", "cookie", "x-auth-token",
                                     "x-kortext-token", "x-access-token",
                                     "x-api-key", "referer"}
                    or k.lower().startswith("x-")
                }
                for k, v in interesting.items():
                    shown = v if len(v) < 250 else v[:250] + f"...[+{len(v)-250}]"
                    events.append(f"          hdr  {k}: {shown}")

        def on_response(resp):
            if "kortext.com" not in resp.url:
                return
            ct = resp.headers.get("content-type", "")[:40]
            events.append(f"{stamp()} RESP {resp.status} {ct:40s} {resp.url}")

        context.on("request", on_request)
        context.on("response", on_response)

        page = context.new_page()
        page.goto(f"{BASE}/reader/epub/{BOOK_ID}?hash=REPLACE_WITH_SESSION_HASH", wait_until="domcontentloaded")
        page.wait_for_timeout(8000)  # let it bootstrap fully

        # Try clicking the next-page arrow a couple of times to force fetches
        # if the first chapter is just cached. Best-effort — selector unknown.
        try:
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(1500)
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(1500)
        except Exception as e:
            events.append(f"  (arrow key press failed: {e})")

        # Also try evaluating localStorage for token-shaped values.
        try:
            ls = page.evaluate(
                "() => Object.fromEntries(Object.entries(localStorage))"
            )
            events.append("\n--- localStorage ---")
            for k, v in ls.items():
                shown = v if len(v) < 250 else v[:250] + f"...[+{len(v)-250}]"
                events.append(f"  {k}: {shown}")
        except Exception as e:
            events.append(f"  (localStorage read failed: {e})")

        try:
            ss = page.evaluate(
                "() => Object.fromEntries(Object.entries(sessionStorage))"
            )
            events.append("\n--- sessionStorage ---")
            for k, v in ss.items():
                shown = v if len(v) < 250 else v[:250] + f"...[+{len(v)-250}]"
                events.append(f"  {k}: {shown}")
        except Exception as e:
            events.append(f"  (sessionStorage read failed: {e})")

        log_path.write_text("\n".join(events), encoding="utf-8")

        # Print a summary to stdout, full log saved to file.
        print(f"\ntotal events: {len(events)}")
        print(f"full log → {log_path}")
        print("\n--- last 40 events ---")
        for line in events[-40:]:
            print(line)

        browser.close()


if __name__ == "__main__":
    main()
