"""Springer EPUB3 XHTML → Obsidian-flavored markdown.

The XHTML we get from Kortext is Springer's structured output. Key shapes
we care about:

  <h1 class="ChapterTitle">2. Intrapersonal ...</h1>
  <h2 class="Heading"><span class="HeadingNumber">2.1 </span>Difference ...</h2>
  <h3 class="Heading"><span class="HeadingNumber">2.2.2 </span>...</h3>
  <p class="Para" id="ParN">body text<span class="CitationRef">...</span>...</p>
  <span class="CitationRef"><a href="#CRn">YYYY</a></span>
  <em class="EmphasisTypeItalic">italic</em>
  <strong class="EmphasisTypeBold">bold</strong>
  <section class="Section1|Section2|...">  -- wraps each subsection
  <div class="FormalPara"> -- callout boxes (e.g. "Mindfulness Practice")
  <ul>/<ol>/<li> -- lists, possibly nested inside <div class="Para">
  <a epub:type="biblioref" href="#CR53">1987</a>  -- inline citation links

Out of scope for v1:
  - Figures/tables: we replace with `[Figure 2.1 — caption]` style placeholders.
  - Footnotes/biblio: collapse to plain text inline.
  - Math: pass MathML through as a fenced ```math``` block (rare in this book).

This is intentionally simple — readable markdown for study, not perfect
fidelity to the source. Iterate after seeing chapter 1 output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Comment, NavigableString, Tag


@dataclass
class ChapterRender:
    """Result of rendering one XHTML chapter."""
    title: str               # e.g. "2. Intrapersonal Communication and Interpersonal Communication"
    title_clean: str         # e.g. "Intrapersonal Communication and Interpersonal Communication"
    number: str | None       # e.g. "2", or None for front/back matter
    markdown: str            # full markdown body


def render_chapter(xhtml: bytes | str) -> ChapterRender:
    soup = BeautifulSoup(xhtml, "html.parser")

    # Extract title from <h1 class="ChapterTitle"> or fall back to <title>.
    # Use _heading_text so Springer's split-span Part headings render correctly.
    title_el = soup.select_one("h1.ChapterTitle, h1[class*='ChapterTitle']")
    if title_el is None:
        title_el = soup.find("h1")
    if title_el is None:
        head_title = soup.find("title")
        raw_title = head_title.get_text(strip=True) if head_title else "Untitled"
    else:
        raw_title = _heading_text(title_el)

    raw_title = raw_title.strip()
    number, title_clean = _split_number(raw_title)

    body = soup.find("body")
    if body is None:
        return ChapterRender(title=raw_title, title_clean=title_clean, number=number, markdown="")

    # Drop chapter chrome (the citation block at the top of every chapter):
    for sel in (
        "div.ChapterContextInformation",
        "div.AuthorGroup",
        "div.MainTitleSection",  # we already extracted the title; don't duplicate it
    ):
        for el in body.select(sel):
            el.decompose()

    # Also remove any top-level h1 — the title is already captured; we don't
    # want it re-rendered as ## inside the body. Parts have a bare <h1>; chapters
    # had it nested in MainTitleSection (handled above), but be safe and remove
    # all body-level h1s.
    for el in body.find_all("h1"):
        el.decompose()

    # Strip HTML comments — Springer wraps abstract content in <!--Begin Abstract-->
    # / <!--End Abstract--> sentinels that BeautifulSoup otherwise emits as text.
    for c in body.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    parts: list[str] = []
    _render_children(body, parts, depth=2)

    md = _post_process("\n".join(parts))

    return ChapterRender(title=raw_title, title_clean=title_clean, number=number, markdown=md)


# ---- title parsing ------------------------------------------------------

_NUMBER_RE = re.compile(r"^(\d+)\.\s+(.+)$")


def _split_number(title: str) -> tuple[str | None, str]:
    """'2. Intrapersonal ...' → ('2', 'Intrapersonal ...')."""
    m = _NUMBER_RE.match(title.strip())
    if m:
        return m.group(1), m.group(2).strip()
    return None, title.strip()


# ---- block-level rendering ---------------------------------------------


_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BLOCK_SKIP_TAGS = {"script", "style", "head"}

# Tags that are purely inline — they must never be treated as block-level elements.
# When _render_children encounters these as direct children of a block container,
# it accumulates them into a pending inline run (along with NavigableString text
# nodes) and flushes the run as a paragraph once a real block element appears.
_INLINE_TAGS = frozenset({
    "span", "a", "em", "i", "b", "strong", "u", "s", "del", "ins",
    "sub", "sup", "code", "small", "cite", "q", "abbr", "mark", "br",
    "time", "data", "ruby", "rb", "rt",
})


def _render_children(parent: Tag, out: list[str], depth: int) -> None:
    """Walk parent's children and emit markdown blocks into `out`.

    depth=2 means top-level sections in the chapter get '##'. We never emit
    '#' from here; the chapter title is the document's only h1 and is added
    by the caller in build_markdown.

    Inline nodes (NavigableString text, <span>, <em>, <a>, etc.) that appear
    as direct children of a block container are accumulated into a pending run
    and flushed as an implicit paragraph once a block-level sibling (or the
    end of children) is reached.  This prevents spurious newlines between, for
    example, a plain-text fragment, an inline citation span, and more plain
    text that all belong to the same sentence.
    """
    _pending: list = []  # accumulated inline run: NavigableString + inline Tags

    def _flush() -> None:
        if not _pending:
            return
        text = _inline_text_nodes(_pending).strip()
        if text:
            out.append(text + "\n")
        _pending.clear()

    for child in parent.children:
        if isinstance(child, NavigableString):
            # Accumulate non-whitespace text (or whitespace that bridges an
            # active inline run, so "foo <em>bar</em> baz" stays together).
            if str(child).strip() or _pending:
                _pending.append(child)
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name.lower()
        if name in _BLOCK_SKIP_TAGS:
            continue

        # Inline element → join the pending run; do NOT treat as a block.
        if name in _INLINE_TAGS:
            _pending.append(child)
            continue

        # Block-level element: flush any pending inline run first.
        _flush()

        if name in _HEADING_TAGS:
            level = int(name[1])
            # Springer's h1 is the chapter title; their h2/h3/h4 are sections.
            # Map their h2 → ##, h3 → ###, h4 → ####.
            md_level = max(2, level)
            text = _heading_text(child)
            out.append(f"\n{'#' * md_level} {text}\n")
            continue
        if name == "section":
            _render_children(child, out, depth + 1)
            continue
        if name in ("div",):
            classes = set(child.get("class") or [])
            if "KeywordGroup" in classes:
                _render_keyword_group(child, out)
                continue
            if "FormalPara" in classes or "FormalParaRenderingStyle1" in classes \
                    or "FormalParaRenderingStyle3" in classes:
                _render_formal_para(child, out, depth)
            else:
                _render_children(child, out, depth)
            continue
        if name == "p":
            text = _inline_text(child)
            if text:
                out.append(text + "\n")
            continue
        if name == "ul":
            for li in child.find_all("li", recursive=False):
                out.append(f"- {_li_text(li)}")
            out.append("")
            continue
        if name == "ol":
            for i, li in enumerate(child.find_all("li", recursive=False), 1):
                out.append(f"{i}. {_li_text(li)}")
            out.append("")
            continue
        if name == "figure":
            cap = child.find("figcaption")
            cap_text = _inline_text(cap) if cap else ""
            out.append(f"\n> [Figure — {cap_text}]\n")
            continue
        if name == "table":
            out.append("\n> [Table omitted in markdown — see source XHTML]\n")
            continue
        if name == "blockquote":
            inner = _inline_text(child)
            out.append("> " + inner.replace("\n", "\n> "))
            continue
        # Default: recurse, hoping children produce blocks.
        _render_children(child, out, depth)

    # Flush any trailing inline run (e.g. a sentence at the end of a <div>
    # with no following block sibling).
    _flush()


def _li_text(li: Tag) -> str:
    """Extract list item text, handling Springer's ItemNumber/ItemContent structure.

    Springer wraps list items as:
        <li><div class="ItemNumber">1.</div><div class="ItemContent">…</div></li>
    The ItemNumber is the explicit marker; we emit our own counter (for <ol>)
    or bullet (for <ul>), so we read only ItemContent and ignore ItemNumber.
    Plain <li> elements (no ItemContent div) are read in full.
    """
    content = li.find("div", class_="ItemContent")
    return _inline_text(content if content is not None else li)


def _heading_text(h: Tag) -> str:
    """Render a heading. Two Springer-specific shapes need help here:
      1. <h2><span class="HeadingNumber">2.1 </span>Title...</h2>  → "2.1 Title..."
      2. <h1><span class="PartNumber">Part I</span><span class="PartTitle">A Prov...</span></h1>
         → "Part I — A Prov..."  (em-dash separator; sibling spans have no whitespace)
    """
    part_num = h.find("span", class_="PartNumber")
    part_title = h.find("span", class_="PartTitle")
    if part_num is not None and part_title is not None:
        return f"{_inline_text(part_num).strip()} — {_inline_text(part_title).strip()}"

    num_el = h.find("span", class_="HeadingNumber")
    if num_el is None:
        return _inline_text(h)
    number = _inline_text(num_el).strip()
    num_el.extract()
    rest = _inline_text(h).strip()
    return f"{number} {rest}".strip()


def _render_keyword_group(div: Tag, out: list[str]) -> None:
    """Render the Springer keyword block as a styled callout."""
    keywords = [_inline_text(k).strip() for k in div.find_all("span", class_="Keyword")]
    keywords = [k for k in keywords if k]
    if not keywords:
        return
    out.append("\n> **Keywords:** " + "; ".join(keywords) + "\n")


def _render_formal_para(div: Tag, out: list[str], depth: int) -> None:
    """Springer 'FormalPara' divs are callout-style boxes (mindfulness practice,
    concrete strategies, key terms, etc.). We render them as a > quote block
    with a bold heading."""
    heading = div.find("div", class_="Heading")
    heading_text = _inline_text(heading) if heading else ""
    body_parts: list[str] = []
    for child in div.children:
        if isinstance(child, Tag) and child.find(class_="Heading") is child:
            continue
        if isinstance(child, Tag) and "Heading" in (child.get("class") or []):
            continue
        if isinstance(child, NavigableString):
            t = str(child).strip()
            if t:
                body_parts.append(t)
            continue
        if isinstance(child, Tag):
            sub: list[str] = []
            _render_children(child, sub, depth + 1)
            body_parts.append("\n".join(sub).strip())

    body_md = "\n".join(p for p in body_parts if p).strip()
    if heading_text:
        out.append(f"\n> **{heading_text}**")
    else:
        out.append("\n>")
    for line in body_md.splitlines():
        out.append(f"> {line}")
    out.append("")


# ---- inline rendering ---------------------------------------------------


def _inline_text_nodes(nodes) -> str:
    """Render an iterable of NavigableString/Tag nodes as inline markdown.

    This is the shared implementation used by both _inline_text (which passes
    a tag's children) and _render_children's pending-run flush (which passes
    an accumulated list of mixed nodes).
    """
    parts: list[str] = []
    for child in nodes:
        if isinstance(child, NavigableString):
            parts.append(str(child))
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name.lower()
        if name in ("em", "i"):
            parts.append(f"*{_inline_text(child)}*")
            continue
        if name in ("strong", "b"):
            parts.append(f"**{_inline_text(child)}**")
            continue
        if name == "span":
            classes = set(child.get("class") or [])
            if "HeadingNumber" in classes:
                # Already part of heading text — emit as plain text.
                parts.append(_inline_text(child))
                continue
            if "CitationRef" in classes:
                # Inline citation like "(Smith, 2020)" — keep visible.
                parts.append(_inline_text(child))
                continue
            if "EmphasisTypeItalic" in classes:
                parts.append(f"*{_inline_text(child)}*")
                continue
            if "EmphasisTypeBold" in classes:
                parts.append(f"**{_inline_text(child)}**")
                continue
            parts.append(_inline_text(child))
            continue
        if name == "a":
            # Inline citation refs and similar — render text only.
            parts.append(_inline_text(child))
            continue
        if name == "br":
            parts.append("\n")
            continue
        # Default: recurse as inline.
        parts.append(_inline_text(child))
    return _collapse_ws("".join(parts))


def _inline_text(el: Tag) -> str:
    """Render an element's contents as inline markdown text."""
    return _inline_text_nodes(el.children)


def _collapse_ws(s: str) -> str:
    return re.sub(r"[ \t]+", " ", s).strip()


# ---- post-processing ----------------------------------------------------


def _post_process(md: str) -> str:
    # Collapse 3+ blank lines into 2.
    md = re.sub(r"\n{3,}", "\n\n", md)
    # Ensure space after sentence-ending citation in a heading-ish line.
    md = re.sub(r"[ \t]+\n", "\n", md)
    return md.strip() + "\n"
