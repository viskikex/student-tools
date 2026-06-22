"""Regex-based date extraction for the auto-generated key-dates table.

Deliberately dumb: no schedule parsing, no NLP. Every date-looking string
gets a row with the line it appeared on, sorted chronologically. The reader
judges relevance — the tool just makes sure nothing date-shaped hides in
paragraph six of the late-work policy.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import date, datetime, timezone

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_MONTH_RE = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?"
    r"|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)

# "February 13", "Feb. 13th, 2026" — month name required, year optional
_NAMED = re.compile(
    rf"\b{_MONTH_RE}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s*(\d{{4}}))?",
    re.IGNORECASE,
)

# "04/05", "4/5/26", "04/05/2026" — not part of a longer digit/slash run,
# so "2026/27" or URL fragments don't half-match
_NUMERIC = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?![\d/])")

_YEAR = re.compile(r"\b(20[2-3]\d)\b")


def infer_year(text: str) -> int | None:
    """Most common plausible year mentioned anywhere in the document."""
    years = Counter(int(y) for y in _YEAR.findall(text))
    if years:
        return years.most_common(1)[0][0]
    return None


def defang(text: str) -> str:
    """Neutralize Obsidian wikilinks/embeds (``[[note]]`` / ``![[note]]``) by
    inserting a zero-width space after each ``[`` that is followed by another ``[``.
    A plain ``str.replace("[[", ...)`` is non-overlapping and leaves a live ``[[``
    behind on a run of 3+ brackets; the lookahead handles runs of any length.
    We also break Markdown image syntax ``![](url)`` (a ZWSP after ``!`` when it
    precedes ``[``): Obsidian auto-loads remote images, so an image in untrusted
    syllabus text is a tracking beacon; the ZWSP downgrades it to a plain text link.
    Shared with convert.py so the syllabus tool keeps one copy of the defang.
    Mirrors canvas-grabber's inline() defang."""
    text = re.sub(r"!(?=\[)", "!​", text)
    return re.sub(r"\[(?=\[)", "[​", text)


def _clean_context(line: str) -> str:
    text = re.sub(r"\s+", " ", line).strip(" #|->*•\t").strip()
    if len(text) > 110:
        text = text[:107].rstrip() + "…"
    # Contexts land in a markdown table: keep pipes from breaking it, and defang
    # Obsidian wikilinks/embeds ([[note]] / ![[note]]) so a syllabus line can't
    # pull in other vault notes.
    return defang(text).replace("|", "\\|")


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extract_dates(text: str, default_year: int) -> list[tuple[date, str]]:
    """Scan line by line; return (date, context-line) pairs, sorted, deduped."""
    found: dict[tuple[date, str], None] = {}
    for line in text.splitlines():
        hits: list[date] = []
        for m in _NAMED.finditer(line):
            month = _MONTHS[m.group(1)[:3].lower()]
            year = int(m.group(3)) if m.group(3) else default_year
            d = _safe_date(year, month, int(m.group(2)))
            if d:
                hits.append(d)
        for m in _NUMERIC.finditer(line):
            month, day = int(m.group(1)), int(m.group(2))
            if not (1 <= month <= 12 and 1 <= day <= 31):
                continue
            year = default_year
            if m.group(3):
                raw = int(m.group(3))
                year = raw + 2000 if raw < 100 else raw
            d = _safe_date(year, month, day)
            if d:
                hits.append(d)
        if hits:
            context = _clean_context(line)
            for d in hits:
                found.setdefault((d, context))
    return sorted(found)


def render_table(entries: list[tuple[date, str]]) -> str:
    if not entries:
        return "_No dates found in the document._"
    lines = [
        "| Date | Day | Where it appears |",
        "|------|-----|------------------|",
    ]
    for d, context in entries:
        lines.append(f"| {d:%Y-%m-%d} | {d:%a} | {context} |")
    return "\n".join(lines)


# ---- machine-readable feed: <slug>.schedule.json ----
# A structured export of the same key dates render_table() renders, sharing the
# canvas-grabber slice's contract so the two can be merged downstream by a
# consumer (e.g. an assistant). Cross-tool merging is deliberately NOT done here:
# this tool only ever emits its own slice and never reads another's output
# (student-tools/CLAUDE.md). Like the .md, it's a static re-run-to-refresh file.


def _date_id(d: date, context: str) -> str:
    """Stable id for a key date, so a consumer can dedupe across re-runs. The
    (date, context) pair is already the extractor's dedupe key, so hashing it
    yields the same id every run for the same row."""
    digest = hashlib.sha1(f"{d.isoformat()}|{context}".encode("utf-8")).hexdigest()
    return f"{d.isoformat()}-{digest[:8]}"


def key_date_items(
    entries: list[tuple[date, str]], source_file: str, today: date | None = None
) -> list[dict]:
    """Normalize (date, context) pairs into schedule items.

    Shares the canvas slice's core keys — ``source``, ``title``, ``type``,
    ``due_at`` — so a merge is trivial. ``due_at`` is **date-only** ISO
    (``YYYY-MM-DD``): a syllabus never states a time, so we don't invent one — a
    consumer treats it as all-day. Syllabus-specific extras: ``weekday`` (the
    computed day, which catches professor typos), ``past`` (date is before
    today — note this is NOT canvas's ``overdue``, which also means unsubmitted;
    a key date can be a finished exam or a holiday), and ``source_file``.
    """
    today = today or date.today()
    return [
        {
            "source": "syllabus",
            "id": _date_id(d, context),
            "title": context,
            "course": None,          # syllabus has no reliable course identity (CLAUDE.md)
            "type": "key-date",
            "due_at": d.isoformat(),  # date-only; time unknown
            "weekday": f"{d:%a}",
            "past": d < today,
            "source_file": source_file,
        }
        for d, context in entries
    ]


def schedule_feed(
    entries: list[tuple[date, str]],
    source_file: str,
    *,
    now: datetime | None = None,
    today: date | None = None,
) -> dict:
    """Wrap the items with staleness metadata, mirroring the canvas slice's
    envelope. ``timezone`` is null because the dates are tz-naive (date-only)."""
    now = now or datetime.now(timezone.utc)
    items = key_date_items(entries, source_file, today=today)
    return {
        "generated_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "timezone": None,
        "source": "syllabus",
        "count": len(items),
        "items": items,
    }
