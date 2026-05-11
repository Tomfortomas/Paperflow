"""R1 search pipeline — implements V2 PRD §4.6.

Six lanes, each producing a ranked list of :class:`R1Candidate`:

* ``seed`` — anchors on the seed paper itself (kept for trace; usually empty).
* ``backward`` — referenced papers (Semantic Scholar /paper/{id}/references,
  with regex-parsed references as fallback when the API has no record).
* ``forward`` — papers that cite this work (S2 /citations, OpenAlex fallback).
* ``benchmark`` — papers sharing tasks / datasets (Papers with Code).
* ``survey`` — survey/review papers found via S2 search.
* ``recent`` — new work from the past 18 months.

Candidates are merged, deduplicated by fingerprint, and converted to
:class:`RelatedWorkItem` for the report. The orchestrator also computes a
``comparison_risk`` string per item using heuristics on venue, year, and
shared task/dataset signals.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional, Sequence

from app.models import Evidence, EvidenceLocationStatus, PaperMetadata, ReliabilityLevel, RelatedWorkItem
from app.r1_clients import (
    OpenAlexClient,
    PapersWithCodeClient,
    R1Candidate,
    SemanticScholarClient,
)
from app.refs_parser import ParsedReference


@dataclass
class R1QueryTraceEntry:
    lane: str
    source: str
    query: str
    count: int


@dataclass
class R1SearchResult:
    items: List[RelatedWorkItem] = field(default_factory=list)
    query_trace: List[R1QueryTraceEntry] = field(default_factory=list)
    seed_resolved_at: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "items": [item.model_dump() for item in self.items],
            "query_trace": [trace.__dict__ for trace in self.query_trace],
            "seed_resolved_at": self.seed_resolved_at,
        }


class R1SearchPipeline:
    """Run the six-lane R1 search for a given seed paper."""

    def __init__(
        self,
        *,
        semantic_scholar: Optional[SemanticScholarClient] = None,
        openalex: Optional[OpenAlexClient] = None,
        papers_with_code: Optional[PapersWithCodeClient] = None,
        lane_limits: Optional[dict] = None,
    ) -> None:
        self.s2 = semantic_scholar or SemanticScholarClient()
        self.oa = openalex or OpenAlexClient()
        self.pwc = papers_with_code or PapersWithCodeClient()
        self.limits = {
            "backward": 25,
            "forward": 25,
            "benchmark": 10,
            "survey": 6,
            "recent": 12,
            **(lane_limits or {}),
        }

    # ----------------------------------------------------------- entrypoint

    def search(
        self,
        metadata: PaperMetadata,
        *,
        parsed_refs: Optional[Sequence[ParsedReference]] = None,
    ) -> R1SearchResult:
        result = R1SearchResult()
        seed = self._resolve_seed(metadata)
        if seed is not None:
            result.seed_resolved_at = time.time()

        # ------------------------------------------------ backward (references)
        backward = self._run_backward(seed, metadata, parsed_refs or [], result)

        # ------------------------------------------------ forward (cited-by)
        forward = self._run_forward(seed, metadata, result)

        # ------------------------------------------------ benchmark (PwC)
        benchmark = self._run_benchmark(metadata, result)

        # ------------------------------------------------ survey
        survey = self._run_survey(metadata, result)

        # ------------------------------------------------ recent
        recent = self._run_recent(metadata, result)

        merged = self._merge_and_rank([backward, forward, benchmark, survey, recent])
        result.items = [self._to_related(c, seed_metadata=metadata) for c in merged]
        return result

    # ----------------------------------------------------------- helpers

    def _resolve_seed(self, metadata: PaperMetadata) -> Optional[dict]:
        identifier = None
        if metadata.semantic_scholar_id:
            identifier = metadata.semantic_scholar_id
        elif metadata.arxiv_id:
            identifier = f"ARXIV:{metadata.arxiv_id}"
        elif metadata.doi:
            identifier = f"DOI:{metadata.doi}"
        if identifier:
            seed = self.s2.resolve(identifier)
            if seed:
                return seed
        if metadata.title:
            hits = self.s2.search(metadata.title, limit=1, lane="seed")
            if hits:
                # Normalise to the same shape as ``s2.resolve`` so the rest of
                # the pipeline can rely on ``paperId``.
                seed = dict(hits[0].__dict__)
                if seed.get("semantic_scholar_id"):
                    seed["paperId"] = seed["semantic_scholar_id"]
                return seed
        return None

    def _run_backward(
        self,
        seed: Optional[dict],
        metadata: PaperMetadata,
        parsed_refs: Sequence[ParsedReference],
        result: R1SearchResult,
    ) -> List[R1Candidate]:
        candidates: List[R1Candidate] = []
        seed_id = (seed or {}).get("paperId") if isinstance(seed, dict) else None
        if seed_id:
            fetched = self.s2.references(seed_id, limit=self.limits["backward"])
            candidates.extend(fetched)
            result.query_trace.append(
                R1QueryTraceEntry(
                    lane="backward",
                    source="semanticscholar",
                    query=f"/paper/{seed_id}/references",
                    count=len(fetched),
                )
            )
        if not candidates and metadata.doi:
            work = self.oa.resolve_by_doi(metadata.doi)
            if work:
                fetched = self.oa.references_of(work, limit=self.limits["backward"])
                candidates.extend(fetched)
                result.query_trace.append(
                    R1QueryTraceEntry(
                        lane="backward",
                        source="openalex",
                        query=f"works/doi:{metadata.doi} → referenced_works",
                        count=len(fetched),
                    )
                )
        if not candidates and parsed_refs:
            for ref in parsed_refs[: self.limits["backward"]]:
                candidates.append(_candidate_from_ref(ref))
            result.query_trace.append(
                R1QueryTraceEntry(
                    lane="backward",
                    source="local-refs",
                    query="regex-extracted bibliography",
                    count=len(candidates),
                )
            )
        return candidates

    def _run_forward(
        self,
        seed: Optional[dict],
        metadata: PaperMetadata,
        result: R1SearchResult,
    ) -> List[R1Candidate]:
        candidates: List[R1Candidate] = []
        seed_id = (seed or {}).get("paperId") if isinstance(seed, dict) else None
        if seed_id:
            fetched = self.s2.citations(seed_id, limit=self.limits["forward"])
            candidates.extend(fetched)
            result.query_trace.append(
                R1QueryTraceEntry(
                    lane="forward",
                    source="semanticscholar",
                    query=f"/paper/{seed_id}/citations",
                    count=len(fetched),
                )
            )
        if not candidates and metadata.doi:
            work = self.oa.resolve_by_doi(metadata.doi)
            if work and work.get("id"):
                short_id = work["id"].rsplit("/", 1)[-1]
                fetched = self.oa.cited_by(short_id, limit=self.limits["forward"])
                candidates.extend(fetched)
                result.query_trace.append(
                    R1QueryTraceEntry(
                        lane="forward",
                        source="openalex",
                        query=f"works?filter=cites:{short_id}",
                        count=len(fetched),
                    )
                )
        return candidates

    def _run_benchmark(self, metadata: PaperMetadata, result: R1SearchResult) -> List[R1Candidate]:
        if not metadata.title:
            return []
        paper = self.pwc.find_paper(metadata.title)
        if paper is None:
            result.query_trace.append(
                R1QueryTraceEntry(
                    lane="benchmark",
                    source="paperswithcode",
                    query=f"/papers?title={metadata.title[:80]}",
                    count=0,
                )
            )
            return []
        neighbors = self.pwc.benchmark_neighbors(paper, limit=self.limits["benchmark"])
        result.query_trace.append(
            R1QueryTraceEntry(
                lane="benchmark",
                source="paperswithcode",
                query=f"/papers/{paper.get('id')}/tasks → neighbours",
                count=len(neighbors),
            )
        )
        return neighbors

    def _run_survey(self, metadata: PaperMetadata, result: R1SearchResult) -> List[R1Candidate]:
        if not metadata.title:
            return []
        query = f"survey {metadata.title}"
        hits = self.s2.search(query, limit=self.limits["survey"], lane="survey")
        survey_hits = [
            cand
            for cand in hits
            if cand.title and ("survey" in cand.title.lower() or "review" in cand.title.lower())
        ]
        result.query_trace.append(
            R1QueryTraceEntry(
                lane="survey",
                source="semanticscholar",
                query=query,
                count=len(survey_hits),
            )
        )
        return survey_hits

    def _run_recent(self, metadata: PaperMetadata, result: R1SearchResult) -> List[R1Candidate]:
        if not metadata.title:
            return []
        hits = self.s2.search(metadata.title, limit=self.limits["recent"], lane="recent")
        cutoff = datetime.utcnow().year - 1
        recent = [c for c in hits if (c.year or 0) >= cutoff]
        result.query_trace.append(
            R1QueryTraceEntry(
                lane="recent",
                source="semanticscholar",
                query=f"{metadata.title[:80]} (year ≥ {cutoff})",
                count=len(recent),
            )
        )
        return recent

    # ----------------------------------------------------------- merging

    def _merge_and_rank(self, lanes: Iterable[List[R1Candidate]]) -> List[R1Candidate]:
        seen: dict[str, R1Candidate] = {}
        for lane in lanes:
            for cand in lane:
                fp = cand.fingerprint()
                if fp not in seen:
                    seen[fp] = cand
                else:
                    # Prefer entries with more populated fields.
                    if _score(cand) > _score(seen[fp]):
                        seen[fp] = cand

        ordered = sorted(
            seen.values(),
            key=lambda c: (
                -(c.influential_citation_count or 0),
                -(c.citation_count or 0),
                -(c.year or 0),
            ),
        )
        return ordered

    def _to_related(self, cand: R1Candidate, *, seed_metadata: PaperMetadata) -> RelatedWorkItem:
        relation = cand.relation or "related work"
        evidence: List[Evidence] = []
        if cand.tldr:
            evidence.append(
                Evidence(
                    id=f"r1-{cand.fingerprint()[:24]}-tldr",
                    source=cand.source,
                    quote=cand.tldr,
                    location_status=EvidenceLocationStatus.QUOTE_ONLY,
                )
            )
        elif cand.abstract:
            evidence.append(
                Evidence(
                    id=f"r1-{cand.fingerprint()[:24]}-abs",
                    source=cand.source,
                    quote=(cand.abstract or "")[:600],
                    location_status=EvidenceLocationStatus.QUOTE_ONLY,
                )
            )

        return RelatedWorkItem(
            id=f"r1-{cand.fingerprint()[:24]}",
            title=cand.title or "(untitled)",
            relation=relation,
            source=cand.source,
            reliability=ReliabilityLevel.R1,
            evidence=evidence,
            authors=cand.authors,
            year=cand.year,
            venue=cand.venue,
            url=cand.url,
            doi=cand.doi,
            arxiv_id=cand.arxiv_id,
            semantic_scholar_id=cand.semantic_scholar_id,
            citation_count=cand.citation_count,
            influential_citation_count=cand.influential_citation_count,
            comparison_risk=_comparison_risk(cand, seed=seed_metadata),
        )


# ---------------------------------------------------------------- helpers


def _score(candidate: R1Candidate) -> int:
    score = 0
    if candidate.doi:
        score += 4
    if candidate.arxiv_id:
        score += 3
    if candidate.semantic_scholar_id:
        score += 2
    if candidate.year:
        score += 1
    if candidate.citation_count is not None:
        score += 1
    if candidate.influential_citation_count is not None:
        score += 1
    if candidate.tldr or candidate.abstract:
        score += 1
    return score


def _candidate_from_ref(ref: ParsedReference) -> R1Candidate:
    return R1Candidate(
        title=ref.title or ref.raw,
        source="local-refs",
        authors=ref.authors,
        year=ref.year,
        doi=ref.doi.lower() if ref.doi else None,
        arxiv_id=ref.arxiv_id,
        relation="cited reference (parsed locally)",
    )


def _comparison_risk(cand: R1Candidate, *, seed: PaperMetadata) -> Optional[str]:
    """Surface common pitfalls when comparing this candidate against the seed."""

    notes: List[str] = []
    if cand.year and seed.year and abs((cand.year - seed.year)) >= 5:
        notes.append(f"different era (seed {seed.year} vs {cand.year})")
    if cand.venue and seed.venue and cand.venue.lower() != seed.venue.lower():
        notes.append(f"different venue ({cand.venue} vs {seed.venue})")
    if cand.source.startswith("paperswithcode:benchmark"):
        notes.append("verify benchmark protocol / metric matches")
    if cand.source.endswith(":citations") and (cand.year or 0) < (seed.year or 0):
        notes.append("citing paper predates seed — check arXiv/preprint dates")
    if not cand.doi and not cand.arxiv_id:
        notes.append("no DOI / arXiv id — manual lookup recommended")
    return "; ".join(notes) if notes else None
