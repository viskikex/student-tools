"""docx → markdown: headings, lists, and tables preserved; everything else prose."""

from __future__ import annotations

import re

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


def _paragraph_md(p: Paragraph) -> str | None:
    text = re.sub(r"\s+", " ", p.text).strip()
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
    parts = [re.sub(r"\s+", " ", p.text).strip() for p in cell.paragraphs]
    text = "<br>".join(part for part in parts if part)
    return text.replace("|", "\\|") or " "


def _table_md(table: Table) -> str | None:
    rows = [[_cell_md(c) for c in row.cells] for row in table.rows]
    rows = [r for r in rows if any(cell.strip() for cell in r)]
    if not rows:
        return None
    width = max(len(r) for r in rows)
    rows = [r + [" "] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |"]
    lines.append("|" + "---|" * width)
    lines.extend("| " + " | ".join(r) + " |" for r in rows[1:])
    return "\n".join(lines)


def docx_to_markdown(path) -> str:
    doc = Document(path)
    chunks: list[str] = []
    for block in _iter_blocks(doc):
        if isinstance(block, Paragraph):
            md = _paragraph_md(block)
        else:
            md = _table_md(block)
        if md:
            chunks.append(md)
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
