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
    """Most common plausible year mentioned anywhere in the document.

    Ties break toward the smaller year so the result is independent of the
    order years appear in the text (a cross-year syllabus mentioning 2026 and
    2027 equally must pick the same default regardless of which is named first).
    """
    years = Counter(int(y) for y in _YEAR.findall(text))
    if not years:
        return None
    top = years.most_common()
    best_count = top[0][1]
    return min(y for y, c in top if c == best_count)


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


def _normalize_context(line: str) -> str:
    """Whitespace-normalize and strip table/list markers. Returns CLEAN TEXT —
    no defang, no pipe-escape, no truncation. This is the dedupe key, the JSON
    ``title`` value, and the _date_id hash input, so it must not carry render
    artifacts (ZWSP from defang, markdown ``\\|`` escapes) that would break
    consumer string-search/dedup. Defang + pipe-escape + truncation are applied
    only at markdown-render time in render_table (ZWSP-in-title and truncated-context-id-collision issues)."""
    return re.sub(r"\s+", " ", line).strip(" #|->*•\t").strip()


def _truncate_for_display(context: str, limit: int = 110) -> str:
    """Truncate a normalized context for table/JSON display. The full context is
    retained for dedupe and id hashing; only the rendered form is shortened."""
    if len(context) > limit:
        return context[: limit - 3].rstrip() + "…"
    return context


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extract_dates(text: str, default_year: int) -> list[tuple[date, str]]:
    """Scan line by line; return (date, context-line) pairs, sorted, deduped.

    A line may name a date range spanning the year boundary ('Dec 15 - Jan 10'):
    when two or more dates share a line and a later one inherited the year (no
    explicit year stated) but its month is earlier than a prior hit's month, the
    later one rolls into the next year. Only inherited years are adjusted — an
    explicit year is always honored as written.
    """
    found: dict[tuple[date, str], None] = {}
    for line in text.splitlines():
        hits: list[tuple[int, date, bool]] = []  # (start pos, date, year_was_explicit)
        for m in _NAMED.finditer(line):
            month = _MONTHS[m.group(1)[:3].lower()]
            explicit = m.group(3) is not None
            year = int(m.group(3)) if explicit else default_year
            d = _safe_date(year, month, int(m.group(2)))
            if d:
                hits.append((m.start(), d, explicit))
        for m in _NUMERIC.finditer(line):
            a, b = int(m.group(1)), int(m.group(2))
            # Unambiguous day-first (e.g. 31/12): first number can't be a month.
            if a > 12 and 1 <= b <= 12:
                month, day = b, a
            elif 1 <= a <= 12 and 1 <= b <= 31:
                month, day = a, b
            else:
                continue
            explicit = m.group(3) is not None
            if explicit:
                raw = int(m.group(3))
                # Standard 2-digit-year pivot (Y2K convention): 0-49 -> 20xx,
                # 50-99 -> 19xx. Unconditional raw+2000 sent '4/5/99' to 2099 —
                # 73 years into the future for a syllabus that's never dated
                # more than a couple years out.
                year = raw + (2000 if raw < 50 else 1900) if raw < 100 else raw
            else:
                year = default_year
            d = _safe_date(year, month, day)
            if d:
                hits.append((m.start(), d, explicit))
        if hits:
            # _NAMED and _NUMERIC run as separate passes; restore true textual
            # order so the cross-boundary roll-over below compares adjacent dates.
            hits.sort(key=lambda h: h[0])
            context = _normalize_context(line)
            # Roll inherited-year dates whose month precedes a prior hit's month
            # into the next year (cross-boundary ranges like 'Dec 15 - Jan 10').
            resolved: list[date] = []
            for i, (_pos, d, explicit) in enumerate(hits):
                if explicit or i == 0:
                    resolved.append(d)
                    continue
                prior = resolved[-1]
                if d.year == prior.year and d.month < prior.month:
                    rolled = _safe_date(d.year + 1, d.month, d.day)
                    resolved.append(rolled if rolled else d)
                else:
                    resolved.append(d)
            for d in resolved:
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
        cell = _truncate_for_display(defang(context).replace("|", "\\|"))
        lines.append(f"| {d:%Y-%m-%d} | {d:%a} | {cell} |")
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
            "id": _date_id(d, context),  # full context -> no id collision
            "title": _truncate_for_display(context),  # display form only
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
    if now.tzinfo is None:
        # A tz-naive now (the type hint allows it) would format with no 'Z'
        # and no offset — a silently ambiguous timestamp in the feed. Assume
        # UTC, matching the aware default above.
        now = now.replace(tzinfo=timezone.utc)
    items = key_date_items(entries, source_file, today=today)
    return {
        "generated_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "timezone": None,
        "source": "syllabus",
        "count": len(items),
        "items": items,
    }
