"""pdf → text: plain extraction plus conservative repair of broken ligatures.

PDFs carry no real structure, so output is honest flat text. Canvas's
"print syllabus" PDFs map ligatures to wrong codepoints ("Informa!on",
'A"endance'); `!` and `"` never appear mid-word in English, so repairing
them between letters is safe.
"""

from __future__ import annotations

import re

from pypdf import PdfReader

_UNICODE_LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
}

_BROKEN_TI = re.compile(r"(?<=[A-Za-z])!(?=[a-z])")
_BROKEN_TT = re.compile(r'(?<=[A-Za-z])"(?=[a-z])')


def _repair(text: str) -> str:
    for bad, good in _UNICODE_LIGATURES.items():
        text = text.replace(bad, good)
    text = _BROKEN_TI.sub("ti", text)
    text = _BROKEN_TT.sub("tt", text)
    return text


def pdf_to_markdown(path) -> str:
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = _repair(page.extract_text() or "").strip()
        if text:
            pages.append(text)
    return "\n\n".join(pages) + "\n"
