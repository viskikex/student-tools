"""docx → markdown: headings, lists, and tables preserved; everything else prose."""

from __future__ import annotations

import re
import sys
import zipfile

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

# Matches built-in "Heading 1" and school-template names like "SyllabusHeading2"
_HEADING_STYLE = re.compile(r"heading\s*(\d)", re.IGNORECASE)


def _iter_blocks(doc):
    """Yield paragraphs and tables in true document order."""
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def _list_level(p: Paragraph) -> int | None:
    """Indent level for numbered/bulleted paragraphs, else None."""
    pPr = p._p.find(qn("w:pPr"))
    if pPr is None:
        return None
    numPr = pPr.find(qn("w:numPr"))
    if numPr is None:
        return None
    ilvl = numPr.find(qn("w:ilvl"))
    return int(ilvl.get(qn("w:val"))) if ilvl is not None else 0


def _is_bold_heading(p: Paragraph, text: str) -> bool:
    """Hand-bolded section labels: whole paragraph bold, short, no sentence punctuation."""
    if len(text) > 60 or text[-1] in ".!?:;,":
        return False
    runs = [r for r in p.runs if r.text.strip()]
    return bool(runs) and all(r.bold for r in runs)

def _paragraph_text(p: Paragraph) -> str:
    """Paragraph text INCLUDING tracked-change insertions. ``Paragraph.text``
    only walks direct-child ``w:r`` elements, so a run wrapped in ``w:ins``
    (an accepted-but-unresolved insertion) is silently invisible — a syllabus
    draft with tracked changes would drop inserted dates with no warning.
    ``w:delText`` (deleted text) uses a different tag than ``w:t``, so walking
    only ``w:t`` naturally excludes deletions (correct: removed content should
    not appear) while still catching insertions."""
    parts: list[str] = []
    for el in p._p.iter():
        if el.tag == qn("w:t"):
            parts.append(el.text or "")
        elif el.tag == qn("w:tab"):
            parts.append("\t")
        elif el.tag in (qn("w:br"), qn("w:cr")):
            parts.append("\n")
    return "".join(parts)

def _paragraph_md(p: Paragraph) -> str | None:
    text = re.sub(r"\s+", " ", _paragraph_text(p)).strip()
    if not text:
        return None
    style = p.style.name if p.style is not None else ""
    m = _HEADING_STYLE.search(style or "")
    if m:
        # Doc title owns "#"; Heading 1 becomes "##", capped at "######"
        level = min(int(m.group(1)) + 1, 6)
        return "#" * level + " " + text
    level = _list_level(p)
    if level is not None:
        return "  " * level + "- " + text
    if "list" in (style or "").lower():
        return "- " + text
    if _is_bold_heading(p, text):
        return "## " + text
    return text


def _cell_md(cell) -> str:
    parts = [re.sub(r"\s+", " ", _paragraph_text(p)).strip() for p in cell.paragraphs]
    text = "<br>".join(part for part in parts if part)
    return text.replace("|", "\\|") or " "


def _dedupe_merged_cells(row) -> list[str]:
    """python-docx returns the SAME Cell object (same underlying ``_tc``
    element) for every grid position spanned by a horizontally merged cell,
    so a naive per-cell render repeats the merged text once per spanned
    column. Emit each unique cell's text once, then pad the row back to its
    original grid width so column alignment with other rows is preserved."""
    seen_tc: set[int] = set()
    texts: list[str] = []
    for c in row.cells:
        tc_id = id(c._tc)
        if tc_id in seen_tc:
            continue
        seen_tc.add(tc_id)
        texts.append(_cell_md(c))
    # Pad back to the row's full grid width with blanks so every row in the
    # table still has the same column count.
    width = len(row.cells)
    return texts + [" "] * (width - len(texts))


def _table_md(table: Table) -> str | None:
    rows = [_dedupe_merged_cells(row) for row in table.rows]
    rows = [r for r in rows if any(cell.strip() for cell in r)]
    if not rows:
        return None
    width = max(len(r) for r in rows)
    rows = [r + [" "] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |"]
    lines.append("|" + "---|" * width)
    lines.extend("| " + " | ".join(r) + " |" for r in rows[1:])
    return "\n".join(lines)


def _header_footer_text(doc) -> list[str]:
    """Text from every section's header/footer paragraphs AND tables, deduped
    for linked sections (python-docx returns a fresh proxy per section even
    when a header is 'linked to previous', i.e. inherited — same underlying
    XML, so the text is identical and would otherwise repeat once per
    section). School templates commonly lay out header content (course code |
    term | date) as a table rather than paragraphs, so both are scanned."""
    seen: set[str] = set()
    lines: list[str] = []
    for section in doc.sections:
        for part in (section.header, section.footer):
            for p in part.paragraphs:
                text = re.sub(r"\s+", " ", _paragraph_text(p)).strip()
                if text and text not in seen:
                    seen.add(text)
                    lines.append(text)
            for table in part.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            text = re.sub(r"\s+", " ", _paragraph_text(p)).strip()
                            if text and text not in seen:
                                seen.add(text)
                                lines.append(text)
    return lines


def docx_to_markdown(path) -> str:
    from docx.opc.exceptions import PackageNotFoundError
    try:
        doc = Document(path)
    except (PackageNotFoundError, zipfile.BadZipFile, KeyError) as exc:
        # Input errors scoped to the construction call; a KeyError from the
        # rendering pass below is a code bug and must surface, not be masked
        # as a corrupt-file error.
        raise ValueError(f"could not read {path} as a .docx file: {exc}") from exc
    has_tracked_changes = (
        next(doc.element.body.iter(qn("w:ins")), None) is not None
        or next(doc.element.body.iter(qn("w:del")), None) is not None
    )
    if has_tracked_changes:
        print(
            f"warning: {path} has unresolved tracked changes (insertions/deletions). "
            "Insertions are included in the output; deletions are correctly excluded, "
            "but review the source for anything Word's Track Changes view would show.",
            file=sys.stderr,
        )
    chunks: list[str] = []
    for block in _iter_blocks(doc):
        if isinstance(block, Paragraph):
            md = _paragraph_md(block)
        else:
            md = _table_md(block)
        if md:
            chunks.append(md)

    # Header/footer text is otherwise invisible to both the converted body and
    # the key-dates scan (extract_dates runs on this function's return value).
    # Syllabi commonly put the semester/term date there.
    hf_lines = _header_footer_text(doc)
    if hf_lines:
        chunks.append("## Header/footer\n\n" + "\n\n".join(hf_lines))

    # Consecutive list items stay adjacent; everything else gets a blank line
    out: list[str] = []
    for chunk in chunks:
        if out and chunk.lstrip().startswith("- ") and out[-1].lstrip().startswith("- "):
            out.append(chunk)
        else:
            if out:
                out.append("")
            out.append(chunk)
    return "\n".join(out) + "\n"
