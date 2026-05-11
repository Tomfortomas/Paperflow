"""Field Map aggregator (PRD §4.8).

Combines:

* The seed paper's :class:`PaperMetadata` and (when available)
  :class:`ReadingReport`.
* R1 search candidates produced by :class:`R1SearchPipeline`.
* The milestone set produced by :mod:`app.milestone`.
* The timeline produced by :mod:`app.timeline`.

… into a single :class:`FieldMap`. The aggregator does not call an LLM
itself — it produces a deterministic, evidence-grounded skeleton and
leaves R2 narrative generation (trends / opportunities) to optional
agent-driven enrichment. This keeps Field Map cheap to generate, easy
to test, and trustworthy by default.
"""

from __future__ import annotations

import re
import time
import uuid
from collections import Counter
from typing import Iterable, List, Optional, Sequence

from app.milestone import detect_milestones
from app.models import (
    Claim,
    Evidence,
    EvidenceLocationStatus,
    FieldMap,
    MilestoneCategory,
    MilestonePaper,
    PaperMetadata,
    ReadingReport,
    ReliabilityLevel,
    TimelineEvent,
)
from app.r1_clients import R1Candidate
from app.r1_search import R1SearchResult
from app.timeline import build_timeline


_TASK_HINTS = (
    "segmentation", "detection", "classification", "generation", "translation",
    "summarization", "retrieval", "recognition", "reasoning", "alignment",
    "policy learning", "navigation", "manipulation", "control", "planning",
)
_DATASET_HINTS = (
    "imagenet", "coco", "kitti", "mnist", "cifar", "wikitext", "squad",
    "glue", "superglue", "openimages", "ade20k", "lvis", "ego4d", "rlbench",
    "metaworld", "calvin", "robomimic", "objaverse", "shapenet",
)
_METRIC_HINTS = (
    "accuracy", "f1", "recall", "precision", "iou", "miou", "bleu", "rouge",
    "ppl", "perplexity", "success rate", "reward",
)


def build_field_map(
    seed_paper_id: str,
    seed_metadata: PaperMetadata,
    *,
    search_result: R1SearchResult,
    raw_candidates: Sequence[R1Candidate] = (),
    report: Optional[ReadingReport] = None,
    milestone_limit: int = 8,
    timeline_limit: int = 20,
    field_map_id: Optional[str] = None,
) -> FieldMap:
    """Produce a :class:`FieldMap` for ``seed_metadata``.

    Args:
        seed_paper_id: local paper id.
        seed_metadata: structured metadata for the seed paper.
        search_result: the R1 search result for this paper (used as
            ground truth for related papers / query trace).
        raw_candidates: optional list of raw :class:`R1Candidate` objects
            from the R1 pipeline. When provided we use them for milestone
            scoring; otherwise we synthesize candidates from
            ``search_result.items``.
        report: optional Reading Report for the seed paper — when given
            we surface its limitations as Open Problems.
        milestone_limit: cap milestones at N entries.
        timeline_limit: cap timeline at N entries.
        field_map_id: override id; defaults to a uuid.
    """

    candidates = list(raw_candidates) if raw_candidates else _candidates_from_related(search_result)
    milestones = detect_milestones(candidates, limit=milestone_limit)
    timeline = build_timeline(
        seed_metadata,
        milestones=milestones,
        candidates=candidates,
        limit=timeline_limit,
    )

    method_families = _method_families(milestones, candidates)
    task_taxonomy = _surface_topics(candidates, hints=_TASK_HINTS, fallback=[seed_metadata.title or ""])
    datasets = _surface_topics(candidates, hints=_DATASET_HINTS)
    metrics = _surface_topics(candidates, hints=_METRIC_HINTS)
    open_problems = _open_problems_from_report(report)
    recent_trends = _recent_trends(candidates, year_threshold=_now_year() - 1)
    research_opportunities = _research_opportunities(milestones, candidates)
    field_summary = _field_summary(seed_metadata, milestones, timeline)
    evidence_index = _evidence_index(milestones, timeline)

    return FieldMap(
        id=field_map_id or f"fm-{uuid.uuid4().hex[:12]}",
        seed_paper_id=seed_paper_id,
        seed_title=seed_metadata.title,
        field_summary=field_summary,
        task_taxonomy=task_taxonomy,
        datasets_benchmarks=datasets,
        metrics=metrics,
        milestones=milestones,
        timeline=timeline,
        method_families=method_families,
        evaluation_protocols=_evaluation_protocols(candidates),
        open_problems=open_problems,
        recent_trends=recent_trends,
        research_opportunities=research_opportunities,
        evidence_index=evidence_index,
        generated_at=time.time(),
    )


# ---------------------------------------------------------------- internals


def _candidates_from_related(result: R1SearchResult) -> List[R1Candidate]:
    """Synthesize :class:`R1Candidate` from already-flattened ``RelatedWorkItem``."""

    candidates: List[R1Candidate] = []
    for item in result.items:
        candidates.append(
            R1Candidate(
                title=item.title,
                source=item.source,
                authors=list(item.authors),
                year=item.year,
                venue=item.venue,
                doi=item.doi,
                arxiv_id=item.arxiv_id,
                semantic_scholar_id=item.semantic_scholar_id,
                url=item.url,
                citation_count=item.citation_count,
                influential_citation_count=item.influential_citation_count,
                relation=item.relation,
            )
        )
    return candidates


def _now_year() -> int:
    from datetime import datetime

    return datetime.utcnow().year


def _surface_topics(
    candidates: Iterable[R1Candidate],
    *,
    hints: Sequence[str],
    fallback: Optional[Sequence[str]] = None,
) -> List[str]:
    counter: Counter[str] = Counter()
    for cand in candidates:
        text = " ".join(filter(None, [cand.title, cand.abstract, cand.tldr])).lower()
        for hint in hints:
            if hint in text:
                counter[hint] += 1
    if not counter and fallback:
        return [item for item in fallback if item]
    return [topic for topic, _ in counter.most_common(8)]


def _method_families(
    milestones: Sequence[MilestonePaper],
    candidates: Sequence[R1Candidate],
) -> List[str]:
    seen: List[str] = []
    for ms in milestones:
        if ms.category == MilestoneCategory.METHOD_PARADIGM and ms.title not in seen:
            seen.append(ms.title)
    # Add a few short tokens from titles (Transformer, Diffusion, …)
    pattern = re.compile(r"\b(transformer|diffusion|mamba|gan|vae|moe|rlhf|dpo|gnn|graph neural|state space|retrieval)\b", re.I)
    tokens: Counter[str] = Counter()
    for cand in candidates:
        for match in pattern.finditer(cand.title or ""):
            tokens[match.group(1).lower()] += 1
    for token, _ in tokens.most_common(6):
        label = token.title()
        if label not in seen:
            seen.append(label)
    return seen[:8]


def _evaluation_protocols(candidates: Sequence[R1Candidate]) -> List[str]:
    seen: List[str] = []
    for cand in candidates:
        if (cand.source or "").endswith(":benchmark") and cand.title and cand.title not in seen:
            seen.append(cand.title)
        if len(seen) >= 6:
            break
    return seen


def _open_problems_from_report(report: Optional[ReadingReport]) -> List[Claim]:
    if report is None:
        return []
    out: List[Claim] = []
    for section in report.sections:
        if "limit" in (section.title or "").lower() or "future" in (section.title or "").lower():
            out.extend(section.claims)
    return out[:10]


def _recent_trends(
    candidates: Sequence[R1Candidate],
    *,
    year_threshold: int,
) -> List[Claim]:
    trends: List[Claim] = []
    recent = [c for c in candidates if (c.year or 0) >= year_threshold]
    for cand in recent[:6]:
        quote = cand.tldr or cand.abstract or cand.title
        trends.append(
            Claim(
                id=f"trend-{cand.fingerprint()[:24]}",
                text=f"Trend ({cand.year}): {cand.title}",
                reliability=ReliabilityLevel.R2,
                evidence=[
                    Evidence(
                        id=f"trend-ev-{cand.fingerprint()[:24]}",
                        source=cand.source,
                        quote=(quote or "")[:600],
                        location_status=EvidenceLocationStatus.QUOTE_ONLY,
                    )
                ],
                uncertainty="Recent papers — adoption is not yet certain.",
            )
        )
    return trends


def _research_opportunities(
    milestones: Sequence[MilestonePaper],
    candidates: Sequence[R1Candidate],
) -> List[Claim]:
    opportunities: List[Claim] = []
    if not milestones and not candidates:
        return opportunities
    if any(ms.category == MilestoneCategory.BENCHMARK for ms in milestones):
        opportunities.append(
            Claim(
                id="opp-benchmark-saturation",
                text="A long-running benchmark dominates the field — consider proposing or transferring to a fresher evaluation protocol.",
                reliability=ReliabilityLevel.R2,
                uncertainty="Heuristic, based on milestone categories.",
            )
        )
    if not any((c.year or 0) >= _now_year() - 1 for c in candidates):
        opportunities.append(
            Claim(
                id="opp-stale-r1",
                text="Few very recent (≤1y) papers were returned by R1 — opportunity to publish the first follow-up in this niche.",
                reliability=ReliabilityLevel.R2,
                uncertainty="Heuristic, based on R1 candidate recency.",
            )
        )
    if any(ms.risk and "low citation count" in ms.risk for ms in milestones):
        opportunities.append(
            Claim(
                id="opp-underexplored",
                text="Some old milestones still have low citation count — possible under-explored direction.",
                reliability=ReliabilityLevel.R2,
                uncertainty="Heuristic, citation count is a noisy signal.",
            )
        )
    return opportunities


def _field_summary(
    seed: PaperMetadata,
    milestones: Sequence[MilestonePaper],
    timeline: Sequence[TimelineEvent],
) -> str:
    bits: List[str] = []
    if seed.title:
        bits.append(f"Seed paper: {seed.title}.")
    if milestones:
        top = milestones[0]
        bits.append(
            f"Top milestone candidate: {top.title} ({top.year or '?'}) — {top.why_milestone}."
        )
    years = sorted({e.year for e in timeline if e.year})
    if years:
        bits.append(f"Timeline span: {years[0]}–{years[-1]} ({len(years)} years).")
    if not bits:
        return "Field Map generated with limited information — consider rerunning R1 search first."
    return " ".join(bits)


def _evidence_index(
    milestones: Sequence[MilestonePaper],
    timeline: Sequence[TimelineEvent],
) -> List[Evidence]:
    seen_ids: set[str] = set()
    out: List[Evidence] = []
    for ms in milestones:
        for ev in ms.evidence:
            if ev.id not in seen_ids:
                seen_ids.add(ev.id)
                out.append(ev)
    for event in timeline:
        for ev in event.evidence:
            if ev.id not in seen_ids:
                seen_ids.add(ev.id)
                out.append(ev)
    return out
