# recon/

Diagnostic scripts that revealed Kortext's API architecture. Not part of the
normal pipeline — kept here for re-running if Kortext changes their reader and
the scraper breaks.

## Files

- **`sniff_network.py`** — opens the reader with saved auth, logs every
  request/response to a fresh `probe_out/network_log.txt`. Prints localStorage
  and sessionStorage at the end. Run this first if a scrape suddenly 401s and
  re-auth doesn't fix it. ⚠️ The generated log contains **live auth tokens,
  session cookies, and account ids** — it is gitignored; never commit or share
  one. (What the capture *shows* — the JWT-Bearer scheme and the
  `/api/content/v1/epub/epub-page/...` URL shape — is written up in the project
  `CLAUDE.md`.)
- **`check_token.py`** — minimal health check. Hits `/account/token`,
  decodes the JWT, prints expiry, then tries to fetch a chapter XHTML. If both
  succeed the architecture is still working.

## Hardcoded values

Both scripts have a `BOOK_ID` constant and reference a reader URL with a
session hash. Edit those if you're recon-ing against a different book; the hash
in `sniff_network.py` may already be stale (it's session-scoped) but the script
falls back gracefully.

## What recon found

The whole story is in the project `CLAUDE.md`. Short version: Kortext serves
Springer EPUB3 chapter XHTMLs directly through their content API, gated by a
short-lived JWT minted from `/account/token`. No DOM scraping needed.
