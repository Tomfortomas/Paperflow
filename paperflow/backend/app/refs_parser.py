"""Regex-based references parser.

We isolate the ``References`` section in the PDF text, split it into
individual reference strings, and try to extract title / authors /
year / DOI / arXiv id for each entry. The output feeds the R1 search
pipeline (``Backward`` lane).

This is intentionally a heuristic parser — it is good enough to feed
Semantic Scholar / OpenAlex lookups, where we then prefer the resolver's
canonical metadata over the regex output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.pdf_parser import ParsedPdf


# Sentinel section headers that mark the start of the references list.
_REFERENCES_RE = re.compile(r"^\s*(references|bibliography)\s*$", re.IGNORECASE | re.MULTILINE)

# Match lines like "[12]" (square brackets, with or without prefix).
_BRACKET_REF_RE = re.compile(r"^\s*\[(\d+)\]\s*(.*)$")

# Match lines like "12. Author, A...".
_NUMBERED_REF_RE = re.compile(r"^\s*(\d+)\.\s+(.*)$")

# DOI / arXiv detection inside a reference string.
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s,;)\]\"']+)", re.IGNORECASE)
_ARXIV_RE = re.compile(r"arxiv[:\s]+(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)

# Year detection — pick the first 19xx/20xx token (most refs include one).
_YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")


@dataclass
class ParsedReference:
    raw: str
    index: Optional[int] = None
    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None

    def best_query(self) -> str:
        """Return the best identifier for upstream lookup (DOI > arXiv > title)."""

        if self.doi:
            return f"DOI:{self.doi}"
        if self.arxiv_id:
            return f"ARXIV:{self.arxiv_id}"
        return (self.title or self.raw)[:200]


def extract_references(text: str) -> List[ParsedReference]:
    """Extract a list of references from a paper's full text."""

    if not text:
        return []
    refs_block = _isolate_references_block(text)
    if not refs_block:
        return []
    raw_entries = _split_entries(refs_block)
    return [_parse_entry(entry, index=idx) for idx, entry in enumerate(raw_entries, start=1)]


def extract_references_from_parsed(parsed: ParsedPdf) -> List[ParsedReference]:
    """Same as :func:`extract_references` but reuses chunk text from PyMuPDF."""

    if not parsed.chunks:
        return []
    text = "\n".join(chunk.text for chunk in parsed.chunks)
    return extract_references(text)


# ---------------------------------------------------------------- internals


def _isolate_references_block(text: str) -> str:
    match = _REFERENCES_RE.search(text)
    if match is None:
        return ""
    block = text[match.end() :]
    # Stop at the next section if any (Appendix, Acknowledgements, Supplement).
    end_match = re.search(
        r"^\s*(appendix|supplementary|acknowledg(?:e?)ments?|author\s+contributions)\s*$",
        block,
        re.IGNORECASE | re.MULTILINE,
    )
    if end_match is not None:
        block = block[: end_match.start()]
    return block.strip()


def _split_entries(block: str) -> List[str]:
    """Split a references block into individual reference strings."""

    lines = [line.rstrip() for line in block.splitlines() if line.strip()]
    entries: List[str] = []
    current: List[str] = []
    seen_index = False

    for line in lines:
        if _BRACKET_REF_RE.match(line) or _NUMBERED_REF_RE.match(line):
            if current:
                entries.append(" ".join(current).strip())
            current = [line]
            seen_index = True
        else:
            current.append(line)

    if current:
        entries.append(" ".join(current).strip())

    if seen_index:
        return entries

    # Fall back to paragraph splits if no numbered prefixes were found.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", block) if p.strip()]
    return paragraphs if paragraphs else entries


def _parse_entry(raw: str, *, index: int) -> ParsedReference:
    text = re.sub(r"\s+", " ", raw).strip()
    parsed_index: Optional[int] = index

    bracket = _BRACKET_REF_RE.match(text)
    if bracket:
        parsed_index = int(bracket.group(1))
        text = bracket.group(2).strip()
    else:
        numbered = _NUMBERED_REF_RE.match(text)
        if numbered:
            parsed_index = int(numbered.group(1))
            text = numbered.group(2).strip()

    ref = ParsedReference(raw=text, index=parsed_index)

    doi_match = _DOI_RE.search(text)
    if doi_match:
        ref.doi = doi_match.group(1).rstrip(".,;)\"'").lower()

    arxiv_match = _ARXIV_RE.search(text)
    if arxiv_match:
        ref.arxiv_id = arxiv_match.group(1)

    year_match = _YEAR_RE.search(text)
    if year_match:
        ref.year = int(year_match.group(1))

    ref.authors, ref.title = _split_authors_and_title(text, year=ref.year)
    return ref


def _split_authors_and_title(text: str, *, year: Optional[int]) -> tuple[List[str], Optional[str]]:
    """Heuristic split: ``Authors. Year. Title.`` or ``Authors. Title. Year.``.

    Returns ``(authors, title)``. The title is taken as the first long
    text segment after the author list. Falls back to ``(empty, full text)``
    when no clear separator can be found.
    """

    pieces = [p.strip() for p in re.split(r"\.\s+(?=[A-Z])", text) if p.strip()]
    if len(pieces) < 2:
        return [], text or None

    author_segment = pieces[0]
    title_candidate: Optional[str] = None
    for piece in pieces[1:]:
        # Skip year-only segments.
        if year and piece.strip().startswith(str(year)):
            continue
        if len(piece) < 5:
            continue
        title_candidate = piece.rstrip(".")
        break

    authors = _split_authors(author_segment)
    return authors, title_candidate or text


def _split_authors(segment: str) -> List[str]:
    raw_parts = re.split(r",\s*|\band\b|;\s*", segment)
    cleaned = []
    for part in raw_parts:
        candidate = part.strip(" .")
        if candidate and len(candidate) > 1 and not candidate[0].isdigit():
            cleaned.append(candidate)
        if len(cleaned) >= 8:
            break
    return cleaned
