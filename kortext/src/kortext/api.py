"""Kortext API client.

After recon (see recon/ directory + the project README/CLAUDE.md), it turns
out Kortext serves Springer-formatted EPUB3 chapters as plain XHTML through
a REST API gated by a short-lived JWT. The JWT itself is obtained from
`https://app.na1.kortext.com/account/token` using the session cookies that
the auth flow saved into auth-state.json.

This module owns:
  - loading the saved session
  - minting + caching a JWT
  - fetching the EPUB package manifest (spine + chapter listing)
  - fetching individual chapter XHTML

Rate limiting: a small inter-request delay is applied. Be polite. The whole
book is ~17 requests; there's no need to hammer.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from playwright.sync_api import APIRequestContext, BrowserContext, sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUTH_STATE_PATH = PROJECT_ROOT / "auth-state.json"

APP_BASE = "https://app.na1.kortext.com"
READ_BASE = "https://read.na1.kortext.com"
TOKEN_URL = f"{APP_BASE}/account/token"

# Inter-request politeness delay (seconds). Conservative.
REQUEST_DELAY_S = 0.4

# EPUB / OPF XML namespaces.
NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
}


@dataclass
class SpineItem:
    """One entry in the EPUB reading order."""
    idref: str
    href: str             # path inside the EPUB, e.g. "html/539576_3_En_2_Chapter.xhtml"
    media_type: str       # e.g. "application/xhtml+xml"
    linear: bool          # spine linear="no" items are aux (Cover, etc.)


@dataclass
class BookManifest:
    book_id: str
    title: str
    subtitle: str | None
    authors: list[str]
    isbn: str | None
    publisher: str | None
    spine: list[SpineItem]
    # navigation: list of (label, href_in_book) from toc.ncx, hierarchical structure preserved.
    nav: list[dict]


def decode_jwt_payload(token: str) -> dict:
    """Decode the JWT payload (no signature verification — for our own inspection)."""
    payload = token.split(".")[1]
    padded = payload + "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


class KortextClient:
    """Stateful client. Holds a Playwright context (for cookies) and a JWT."""

    def __init__(self, auth_state_path: Path = AUTH_STATE_PATH):
        self._auth_state_path = auth_state_path
        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None
        self._req: APIRequestContext | None = None
        self._token: str | None = None
        self._token_exp: float | None = None  # unix ts

    # ---- lifecycle -------------------------------------------------------

    def __enter__(self) -> "KortextClient":
        if not self._auth_state_path.exists():
            raise RuntimeError(
                f"No auth state at {self._auth_state_path}. "
                f"Run `python .claude/skills/kortext-import/scripts/auth.py` first."
            )
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(storage_state=str(self._auth_state_path))
        self._req = self._context.request
        return self

    def __exit__(self, *exc) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    # ---- token -----------------------------------------------------------

    def _ensure_token(self) -> str:
        now = time.time()
        # Refresh if we don't have one or it expires within 60s.
        if self._token is None or (self._token_exp and self._token_exp - now < 60):
            assert self._req is not None
            resp = self._req.get(TOKEN_URL)
            if resp.status != 200:
                raise RuntimeError(
                    f"token endpoint returned {resp.status}; "
                    f"saved auth state may be expired — re-run auth.py"
                )
            token = resp.text().strip().strip('"')
            # A stale session often returns 200 with an empty body or an HTML
            # login page rather than a clean 401. Putting that into an
            # Authorization header throws a cryptic "Invalid character in header
            # content" downstream, so catch it here and give the actionable
            # message the README/troubleshooting promises.
            if token.count(".") != 2 or not all(token.split(".")):
                raise RuntimeError(
                    "token endpoint returned 200 but not a valid JWT "
                    "(likely an HTML login page) — saved auth state is expired, "
                    "re-run auth.py / kortext-auth"
                )
            self._token = token
            try:
                payload = decode_jwt_payload(self._token)
                self._token_exp = payload.get("exp")
            except Exception:
                self._token_exp = now + 3600  # fall back to 1hr guess
        return self._token

    def token_info(self) -> dict:
        """For debugging / logging."""
        token = self._ensure_token()
        payload = decode_jwt_payload(token)
        exp = payload.get("exp")
        return {
            "exp_iso": datetime.fromtimestamp(exp, tz=timezone.utc).isoformat() if exp else None,
            "seconds_remaining": int(exp - time.time()) if exp else None,
            "user": payload.get("name"),
            "email": payload.get("email"),
        }

    # ---- raw fetch -------------------------------------------------------

    def _get(self, url: str) -> bytes:
        assert self._req is not None
        token = self._ensure_token()
        resp = self._req.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        if resp.status != 200:
            raise RuntimeError(f"{resp.status} {url}: {resp.text()[:200]}")
        body = resp.body()
        time.sleep(REQUEST_DELAY_S)
        return body

    # ---- high level ------------------------------------------------------

    def list_books(self) -> list[dict]:
        """Return books in the user's library."""
        # The /extracts endpoint listed in network log was for highlights.
        # The book metadata for an individual book lives at /api/library/v1/books/<id>.
        # The full library listing endpoint is the one the library UI uses;
        # we'll discover via /api/library/v1/books on demand. For now, return
        # whatever Kortext gives.
        url = f"{READ_BASE}/api/library/v1/books?pageNo=1&pageSize=100"
        return json.loads(self._get(url).decode("utf-8"))

    def get_book_metadata(self, book_id: str) -> dict:
        url = f"{READ_BASE}/api/library/v1/books/{book_id}?enhanceBook=true"
        return json.loads(self._get(url).decode("utf-8"))

    def get_manifest(self, book_id: str) -> BookManifest:
        """Fetch package.opf + toc.ncx, parse into a BookManifest."""
        opf_bytes = self._get(
            f"{READ_BASE}/api/content/v1/epub/epub-page/{book_id}/OEBPS/package.opf"
        )
        ncx_bytes = self._get(
            f"{READ_BASE}/api/content/v1/epub/epub-page/{book_id}/OEBPS/toc.ncx"
        )
        return _parse_manifest(book_id, opf_bytes, ncx_bytes)

    def get_chapter_xhtml(self, book_id: str, href: str) -> bytes:
        """Fetch one EPUB chapter file. href is relative to OEBPS/, e.g.
        'html/539576_3_En_2_Chapter.xhtml'."""
        url = f"{READ_BASE}/api/content/v1/epub/epub-page/{book_id}/OEBPS/{href}"
        return self._get(url)


# ---- OPF / NCX parsing --------------------------------------------------


def _parse_manifest(book_id: str, opf_bytes: bytes, ncx_bytes: bytes) -> BookManifest:
    opf = ET.fromstring(opf_bytes)
    metadata = opf.find("opf:metadata", NS)
    manifest = opf.find("opf:manifest", NS)
    spine = opf.find("opf:spine", NS)
    assert metadata is not None and manifest is not None and spine is not None

    # Build id → manifest item map.
    items_by_id: dict[str, dict[str, str]] = {}
    for item in manifest.findall("opf:item", NS):
        items_by_id[item.attrib["id"]] = {
            "href": item.attrib["href"],
            "media_type": item.attrib.get("media-type", ""),
        }

    spine_items: list[SpineItem] = []
    for itemref in spine.findall("opf:itemref", NS):
        idref = itemref.attrib["idref"]
        if idref not in items_by_id:
            continue
        meta = items_by_id[idref]
        spine_items.append(
            SpineItem(
                idref=idref,
                href=meta["href"],
                media_type=meta["media_type"],
                linear=itemref.attrib.get("linear", "yes") != "no",
            )
        )

    def first_text(tag: str) -> str | None:
        el = metadata.find(f"dc:{tag}", NS)
        return el.text if el is not None and el.text else None

    title = first_text("title") or "Untitled"
    subtitle = None
    for t in metadata.findall("dc:title", NS):
        if t.attrib.get("id") == "pub-subtitle":
            subtitle = t.text
    authors = [c.text for c in metadata.findall("dc:creator", NS) if c.text]
    publisher = first_text("publisher")
    identifier = first_text("identifier")
    isbn = None
    if identifier and "isbn" in identifier.lower():
        isbn = identifier.split(":")[-1]

    nav = _parse_ncx(ncx_bytes)

    return BookManifest(
        book_id=book_id,
        title=title,
        subtitle=subtitle,
        authors=authors,
        isbn=isbn,
        publisher=publisher,
        spine=spine_items,
        nav=nav,
    )


def _parse_ncx(ncx_bytes: bytes) -> list[dict]:
    """Parse toc.ncx into a hierarchical list of {label, href, children}."""
    ncx_ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
    root = ET.fromstring(ncx_bytes)
    nav_map = root.find("ncx:navMap", ncx_ns)
    if nav_map is None:
        return []

    def walk(point) -> dict:
        label_el = point.find("ncx:navLabel/ncx:text", ncx_ns)
        content_el = point.find("ncx:content", ncx_ns)
        return {
            "label": label_el.text if label_el is not None else "",
            "href": content_el.attrib.get("src", "") if content_el is not None else "",
            "children": [walk(c) for c in point.findall("ncx:navPoint", ncx_ns)],
        }

    return [walk(p) for p in nav_map.findall("ncx:navPoint", ncx_ns)]
