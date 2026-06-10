# recon/

Diagnostic scripts and the original network capture that revealed Kortext's API
architecture. Not part of the normal pipeline — kept here for re-running if
Kortext changes their reader and the scraper breaks.

## Files

- **`sniff_network.py`** — opens the reader with saved auth, logs every
  request/response to a fresh `network_log.txt`. Prints localStorage and
  sessionStorage at the end. Run this first if a scrape suddenly 401s and
  re-auth doesn't fix it — compare the new requests against the old log.
- **`check_token.py`** — minimal health check. Hits `/account/token`,
  decodes the JWT, prints expiry, then tries to fetch a chapter XHTML. If both
  succeed the architecture is still working.
- **`network_log.txt`** — the original capture that revealed the JWT-Bearer
  auth scheme + the `/api/content/v1/epub/epub-page/...` URL shape. Useful as a
  diff baseline. **Auth tokens and session ids in it have been redacted**
  (`<REDACTED>`) — regenerate a fresh log with `sniff_network.py` if you need
  real values for debugging.

## Hardcoded values

Both scripts have a `BOOK_ID` constant and reference a reader URL with a
session hash. Edit those if you're recon-ing against a different book; the hash
in `sniff_network.py` may already be stale (it's session-scoped) but the script
falls back gracefully.

## What recon found

The whole story is in the project `CLAUDE.md`. Short version: Kortext serves
Springer EPUB3 chapter XHTMLs directly through their content API, gated by a
short-lived JWT minted from `/account/token`. No DOM scraping needed.
