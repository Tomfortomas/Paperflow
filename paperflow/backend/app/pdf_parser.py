"""Parse a PDF into page-level text chunks with bbox + section guesses.

The output of :func:`parse_pdf` is consumed by:

* :mod:`app.evidence_verifier` — to fuzzy-match agent quotes to a page + bbox.
* Frontend PDF.js viewer — for evidence highlighting and select-to-ask.

The parser uses PyMuPDF (``fitz``). Each ``PageChunk`` covers a contiguous
block of text (PyMuPDF's "block" granularity), keeping the bbox in PDF
points (origin = top-left, y grows downward — same coords PDF.js uses).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import fitz  # PyMuPDF


# Common top-level section labels we try to detect on page text.
_SECTION_PATTERNS = [
    re.compile(r"^\s*abstract\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\.?\s+introduction\b", re.IGNORECASE),
    re.compile(r"^\s*introduction\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\.?\s+related\s+work\b", re.IGNORECASE),
    re.compile(r"^\s*related\s+work\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\.?\s+background\b", re.IGNORECASE),
    re.compile(r"^\s*\d+\.?\s+method(?:s|ology)?\b", re.IGNORECASE),
    re.compile(r"^\s*method(?:s|ology)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\.?\s+approach\b", re.IGNORECASE),
    re.compile(r"^\s*\d+\.?\s+experiments?\b", re.IGNORECASE),
    re.compile(r"^\s*experiments?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\.?\s+results?\b", re.IGNORECASE),
    re.compile(r"^\s*\d+\.?\s+evaluation\b", re.IGNORECASE),
    re.compile(r"^\s*\d+\.?\s+ablation(?:s)?\b", re.IGNORECASE),
    re.compile(r"^\s*\d+\.?\s+discussion\b", re.IGNORECASE),
    re.compile(r"^\s*\d+\.?\s+limitations?\b", re.IGNORECASE),
    re.compile(r"^\s*limitations?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\.?\s+conclusion(?:s)?\b", re.IGNORECASE),
    re.compile(r"^\s*conclusion(?:s)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*references?\s*$", re.IGNORECASE),
    re.compile(r"^\s*appendix\s*$", re.IGNORECASE),
]


@dataclass
class PageChunk:
    """One paragraph-ish block on a page.

    Attributes
    ----------
    page:
        1-based page index (matches what users see in any PDF reader).
    bbox:
        ``[x0, y0, x1, y1]`` in PDF points. Origin top-left.
    text:
        Visible text of the block, with consecutive whitespace collapsed.
    section_guess:
        Best-effort guess of the section heading this chunk belongs to.
        ``None`` if no section has been detected upstream of this chunk.
    """

    page: int
    bbox: List[float]
    text: str
    section_guess: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParsedPdf:
    """Full parser output: chunks per page + page dimensions."""

    chunks: List[PageChunk] = field(default_factory=list)
    page_sizes: List[List[float]] = field(default_factory=list)  # [[w, h], ...]

    def to_dict(self) -> dict:
        return {
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "page_sizes": list(self.page_sizes),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ParsedPdf":
        return cls(
            chunks=[PageChunk(**c) for c in data.get("chunks") or []],
            page_sizes=[list(p) for p in data.get("page_sizes") or []],
        )

    def page_text(self, page: int) -> str:
        """Concatenate the chunks of a single 1-based page."""

        return "\n".join(c.text for c in self.chunks if c.page == page)


# ---------------------------------------------------------------- parse


def parse_pdf(pdf_path: Path) -> ParsedPdf:
    """Parse ``pdf_path`` into :class:`ParsedPdf` (page chunks + sizes).

    Empty or fully whitespace blocks are dropped. Each text block has its
    whitespace normalised. The section guess for a chunk is the most-recent
    section header seen since the start of the document (across pages).
    """

    parsed = ParsedPdf()
    if not Path(pdf_path).is_file():
        return parsed

    current_section: Optional[str] = None

    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc, start=1):
            parsed.page_sizes.append([float(page.rect.width), float(page.rect.height)])
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks") or []:
                if block.get("type", 0) != 0:
                    continue
                bbox = block.get("bbox") or [0, 0, 0, 0]
                lines = block.get("lines") or []
                line_strings: List[str] = []
                for line in lines:
                    spans = [span.get("text", "") for span in line.get("spans") or []]
                    line_strings.append("".join(spans))
                text = _normalise_whitespace("\n".join(line_strings))
                if not text:
                    continue

                section_for_block = _detect_section(line_strings, fallback=current_section)
                if section_for_block != current_section and section_for_block is not None:
                    current_section = section_for_block

                parsed.chunks.append(
                    PageChunk(
                        page=page_index,
                        bbox=[float(b) for b in bbox],
                        text=text,
                        section_guess=current_section,
                    )
                )

    return parsed


def _normalise_whitespace(value: str) -> str:
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n", value)
    return value.strip()


def _detect_section(lines: Sequence[str], *, fallback: Optional[str]) -> Optional[str]:
    """If the block looks like a section heading, return the canonical label."""

    if not lines:
        return fallback
    first_line = (lines[0] or "").strip()
    if not first_line or len(first_line) > 80:
        return fallback
    for pattern in _SECTION_PATTERNS:
        if pattern.search(first_line):
            return _canonical_label(first_line)
    return fallback


def _canonical_label(line: str) -> str:
    cleaned = re.sub(r"\s+", " ", line).strip()
    # Drop a leading numeric prefix like "3." or "3.1" so labels match across papers.
    cleaned = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", cleaned)
    return cleaned.title()


# ---------------------------------------------------------------- on-disk cache


def save_chunks(path: Path, parsed: ParsedPdf) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(parsed.to_dict(), ensure_ascii=False), encoding="utf-8")
    return path


def load_chunks(path: Path) -> Optional[ParsedPdf]:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return ParsedPdf.from_dict(data)


def iter_pages(parsed: ParsedPdf) -> Iterable[int]:
    seen = set()
    for chunk in parsed.chunks:
        if chunk.page not in seen:
            seen.add(chunk.page)
            yield chunk.page
