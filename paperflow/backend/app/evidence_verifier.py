"""Locate agent-extracted evidence quotes inside the parsed PDF.

The :class:`EvidenceVerifier` consumes a :class:`~app.pdf_parser.ParsedPdf`
and an agent-produced :class:`~app.models.Evidence` and attempts to find
the best matching :class:`~app.pdf_parser.PageChunk`. The verifier sets:

* ``evidence.page`` — to the matched chunk's 1-based page (if it wasn't set
  already by the agent).
* ``evidence.section`` — to the chunk's section guess.
* ``evidence.bbox`` — the matched span's bounding box in PDF points.
* ``evidence.location_status`` — see :class:`EvidenceLocationStatus`.

Matching strategy (cheap and stdlib-only):

1. Normalise both quote and chunk text (lowercase, collapse whitespace, strip
   common punctuation, hyphen-broken line fixes).
2. For each chunk, compute :class:`difflib.SequenceMatcher.ratio` and locate
   the longest matching substring with ``find_longest_match``.
3. Accept the highest-scoring match above a threshold.
4. Estimate a bbox by linearly slicing the chunk's bbox horizontally and
   vertically based on the matched substring's position.

This is intentionally a heuristic — the goal is good-enough localisation
for in-PDF highlighting, not exact span detection. It runs in tens of
milliseconds for a typical paper.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from app.models import Evidence, EvidenceLocationStatus, ReadingReport
from app.pdf_parser import PageChunk, ParsedPdf


# Quote-to-chunk match must score at least this to count as PAGE_AND_QUOTE.
_PAGE_QUOTE_THRESHOLD = 0.55
# A higher score means we can trust the bbox slice and call it EXACT.
_EXACT_THRESHOLD = 0.82


@dataclass(frozen=True)
class LocatedQuote:
    page: int
    bbox: List[float]
    section_guess: Optional[str]
    score: float
    status: EvidenceLocationStatus


class EvidenceVerifier:
    """Locate evidence quotes against parsed PDF chunks."""

    def __init__(self, parsed: ParsedPdf) -> None:
        self.parsed = parsed
        self._normalised: List[Tuple[PageChunk, str]] = [
            (chunk, _normalise(chunk.text)) for chunk in parsed.chunks
        ]

    def locate(self, quote: str) -> Optional[LocatedQuote]:
        """Return the best chunk match for ``quote`` or ``None`` when missing."""

        normalised_quote = _normalise(quote)
        if not normalised_quote:
            return None

        best: Optional[LocatedQuote] = None
        best_score = 0.0
        for chunk, normalised_chunk in self._normalised:
            if not normalised_chunk:
                continue
            matcher = SequenceMatcher(None, normalised_quote, normalised_chunk, autojunk=False)
            ratio = matcher.ratio()
            if ratio < best_score:
                continue
            longest = matcher.find_longest_match(0, len(normalised_quote), 0, len(normalised_chunk))
            if longest.size == 0:
                continue
            coverage = longest.size / max(len(normalised_quote), 1)
            score = max(ratio, coverage)
            if score < _PAGE_QUOTE_THRESHOLD:
                continue
            if score <= best_score:
                continue

            bbox = _bbox_slice_for_match(
                chunk_bbox=chunk.bbox,
                chunk_len=len(normalised_chunk),
                match_start=longest.b,
                match_len=longest.size,
            )
            status = (
                EvidenceLocationStatus.EXACT
                if score >= _EXACT_THRESHOLD
                else EvidenceLocationStatus.PAGE_AND_QUOTE
            )
            best_score = score
            best = LocatedQuote(
                page=chunk.page,
                bbox=bbox,
                section_guess=chunk.section_guess,
                score=score,
                status=status,
            )

        return best

    def annotate_evidence(self, evidence: Evidence) -> Evidence:
        """Patch a single Evidence object in place with location info."""

        quote = (evidence.quote or "").strip()
        if not quote:
            evidence.location_status = EvidenceLocationStatus.MISSING
            return evidence

        located = self.locate(quote)
        if located is None:
            evidence.location_status = EvidenceLocationStatus.QUOTE_ONLY
            return evidence

        # Trust the agent's existing page only if it agrees; otherwise overwrite.
        if evidence.page is None or evidence.page != located.page:
            evidence.page = located.page
        if not evidence.section and located.section_guess:
            evidence.section = located.section_guess
        evidence.bbox = located.bbox
        evidence.location_status = located.status
        return evidence

    def annotate_report(self, report: ReadingReport) -> ReadingReport:
        """Annotate every evidence in every claim / related-work item."""

        for claim in report.summary:
            for ev in claim.evidence:
                self.annotate_evidence(ev)
        for section in report.sections:
            for claim in section.claims:
                for ev in claim.evidence:
                    self.annotate_evidence(ev)
        for item in report.related_work:
            for ev in item.evidence:
                self.annotate_evidence(ev)
        return report


# ---------------------------------------------------------------- helpers


def _normalise(text: str) -> str:
    if not text:
        return ""
    value = text.lower()
    # Fix hyphen-broken words: "evi-\ndence" → "evidence".
    value = re.sub(r"-\s*\n\s*", "", value)
    value = re.sub(r"\s+", " ", value)
    # Drop characters that frequently differ between PDF extraction and the
    # agent's paraphrased quote (smart quotes, en-dashes, etc.).
    value = re.sub(r"[\u2018\u2019\u201c\u201d\u2013\u2014]", " ", value)
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()


def _bbox_slice_for_match(
    *,
    chunk_bbox: List[float],
    chunk_len: int,
    match_start: int,
    match_len: int,
) -> List[float]:
    """Estimate a bbox for the matched substring.

    PyMuPDF gives us a single bbox per block. We can't recover precise span
    geometry without re-reading the spans, but for a one-paragraph block the
    chunk bbox is already a reasonable highlight. To make highlights tighter
    we shrink the bbox vertically based on where the match sits in the text.
    """

    x0, y0, x1, y1 = chunk_bbox
    if chunk_len <= 0 or match_len <= 0:
        return [float(x0), float(y0), float(x1), float(y1)]

    height = max(y1 - y0, 1.0)
    start_frac = max(0.0, match_start / chunk_len)
    end_frac = min(1.0, (match_start + match_len) / chunk_len)
    # Always leave at least one full text-line worth of height visible.
    min_height = min(height, 14.0)
    sliced_y0 = y0 + height * start_frac
    sliced_y1 = y0 + height * end_frac
    if sliced_y1 - sliced_y0 < min_height:
        midpoint = (sliced_y0 + sliced_y1) / 2
        sliced_y0 = max(y0, midpoint - min_height / 2)
        sliced_y1 = min(y1, midpoint + min_height / 2)
    return [float(x0), float(sliced_y0), float(x1), float(sliced_y1)]
