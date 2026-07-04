"""PowerPoint (.pptx) → Obsidian-flavored markdown for gap analysis.

Input:  a .pptx file (lecture slides)
Output: markdown with one ## heading per slide, bullets for text content,
        blockquote for speaker notes, [image] placeholder for image-only slides.

Intentionally flat — we want text that's easy to compare against textbook chapters,
not a visual reconstruction. Tables are rendered as bullet lists. SmartArt and
diagrams get an [image] placeholder.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from pptx import Presentation


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _defang(text: str) -> str:
    """Neutralize Obsidian wikilinks/embeds (``[[note]]`` / ``![[note]]``) in
    untrusted slide text by inserting a zero-width space after each ``[`` that is
    followed by another ``[``. A plain ``str.replace("[[", ...)`` is non-overlapping
    and leaves a live ``[[`` behind on a run of 3+ brackets (``[[[`` -> ``[<zwsp>[[``);
    the lookahead handles runs of any length. We also break Markdown image syntax
    ``![](url)`` (a ZWSP after ``!`` when it precedes ``[``): Obsidian auto-loads
    remote images, so an image in untrusted slide text is a tracking beacon; the
    ZWSP downgrades it to a plain text link. Mirrors canvas-grabber's inline() defang."""
    text = re.sub(r"!(?=\[)", "!​", text)
    return re.sub(r"\[(?=\[)", "[​", text)

def _clean(text: str) -> str:
    """Normalize whitespace (collapse newlines/tabs/spaces), escape markdown
    emphasis chars and table pipes, and defang wikilinks. Applied to every
    slide-text path so a multi-line title, a '*' in notes, or a pipe in a cell
    can't break a heading, italic span, or table row."""
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    text = text.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
    return _defang(text)


def _shape_text_lines(shape) -> list[str]:
    """Extract text lines from any shape with a text frame, preserving outline level."""
    lines = []
    if not shape.has_text_frame:
        return lines
    for para in shape.text_frame.paragraphs:
        text = _clean(para.text)
        if not text:
            continue
        level = para.level or 0  # 0 = top level, 1-4 = nested bullets
        indent = "  " * level
        lines.append(f"{indent}- {text}")
    return lines


def _visual_marker(shape) -> str | None:
    """Marker for a visual-only shape (no extractable text), or None if the
    shape is not visual-only. Distinguishes media (audio/video) from a still
    image/chart rather than mislabeling everything '[image]'."""
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    if shape.shape_type == MSO_SHAPE_TYPE.MEDIA:
        return "[media]"
    if shape.shape_type in (MSO_SHAPE_TYPE.PICTURE, MSO_SHAPE_TYPE.CHART):
        return "[image]"
    return None


def _iter_shapes(shapes):
    """Yield shapes recursively, descending into GROUP shapes so grouped
    textboxes/tables/images aren't silently dropped."""
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_shapes(shape.shapes)
        else:
            yield shape


def _find_title(shapes):
    """Find a title placeholder, searching inside groups (slide.shapes.title
    returns None when the title placeholder is grouped). Identifies titles by
    placeholder type, not shapes.title (which only exists on SlideShapes)."""
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from pptx.enum.shapes import PP_PLACEHOLDER
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            title = _find_title(shape.shapes)
            if title is not None:
                return title
        else:
            try:
                pf = shape.placeholder_format
            except ValueError:
                pf = None
            if pf is not None and pf.type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE):
                return shape
    return None


def _slide_title(slide) -> str | None:
    """Return slide title text, or None. Searches inside groups."""
    title_shape = _find_title(slide.shapes)
    if title_shape is None:
        return None
    return _clean(title_shape.text_frame.text) or None


def _slide_to_md(slide_num: int, slide) -> str:
    """Render one slide as a markdown section."""
    title_shape = _find_title(slide.shapes)
    title = _clean(title_shape.text_frame.text) or None if title_shape else None
    heading = f"## Slide {slide_num}" + (f" — {title}" if title else "")

    body_lines: list[str] = []
    visual_markers: list[str] = []

    for shape in _iter_shapes(slide.shapes):
        # Skip the title shape — already used above (handles grouped titles too)
        if shape == title_shape:
            continue

        marker = _visual_marker(shape)
        if marker is not None:
            if marker not in visual_markers:
                visual_markers.append(marker)
            continue

        # Tables: flatten to bullets
        if shape.has_table:
            for row in shape.table.rows:
                # Keep empty cells as '' so column count matches the header row;
                # filter only fully-empty rows.
                cells = [_clean(c.text_frame.text) for c in row.cells]
                if any(c.strip() for c in cells):
                    body_lines.append("- " + " | ".join(cells))
            continue

        # Text frames: preserve outline hierarchy
        if shape.has_text_frame:
            body_lines.extend(_shape_text_lines(shape))

    # Speaker notes
    notes_text = ""
    if slide.has_notes_slide:
        raw = _clean(slide.notes_slide.notes_text_frame.text)
        if raw:
            notes_text = f"\n> *Notes: {raw}*"

    parts = [heading]
    parts.extend(body_lines)
    # Emit every distinct visual marker even when the slide also has text —
    # the visual signal must not be silently dropped just because there's a
    # textbox on the same slide.
    parts.extend(visual_markers)
    if notes_text:
        parts.append(notes_text)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def pptx_to_markdown(pptx_path: Path, chapter: str | None = None) -> str:
    """Convert a .pptx file to markdown.

    Args:
        pptx_path: Path to the .pptx file.
        chapter:   Optional chapter label (e.g. "02") used in the header.

    Returns:
        Markdown string, ready to write to a file.
    """
    try:
        prs = Presentation(pptx_path)
    except (zipfile.BadZipFile, KeyError) as exc:
        # BadZipFile: not a zip / corrupt. KeyError: zip but not a pptx
        # (missing [Content_Types].xml). Both are input errors scoped to the
        # construction call; a KeyError from shape iteration below is a code
        # bug and must surface, not be masked as a corrupt-file error.
        raise ValueError(f"could not read {pptx_path.name} as a .pptx file: {exc}") from exc

    # Deck title: try the first slide's title, then fall back to filename
    deck_title = None
    if prs.slides:
        deck_title = _slide_title(prs.slides[0])
    if not deck_title:
        deck_title = _clean(pptx_path.stem)

    chapter_label = f"Ch {chapter} — " if chapter else ""
    # Both deck_title (from stem, already _clean'd above) and pptx_path.name
    # (filename) are interpolated into emphasis/heading context, so _clean
    # escapes pipes, emphasis chars, and defangs wikilinks — bare _defang
    # alone leaves '*' and '_' live, breaking the source-italic span.
    header = f"# {chapter_label}{deck_title}\n\n*Source: {_clean(pptx_path.name)}*"

    slide_sections = []
    for i, slide in enumerate(prs.slides, start=1):
        slide_sections.append(_slide_to_md(i, slide))

    if not slide_sections:
        print(f"warning: {pptx_path.name} has no slides", file=sys.stderr)
        return header + "\n"

    return header + "\n\n---\n\n" + "\n\n".join(slide_sections)
