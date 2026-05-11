"""Milestone paper detection.

Given a list of :class:`~app.r1_clients.R1Candidate` from the R1 search,
score each candidate and surface the most likely "milestone papers"
following PRD §4.6.

Signals used (all heuristic — Field Map UI still asks the user to
confirm / reject):

* ``citation_count`` and ``influential_citation_count``
* ``velocity`` (citations per year since publication)
* ``venue`` quality (top venues earn a small bonus)
* ``recency`` adjustment (very new papers can't have many cites yet)
* ``category`` heuristics based on the title — survey / benchmark /
  dataset / paradigm cues earn a category-specific bonus.

The scoring is deliberately transparent: every signal contributes a
named term that ends up in :attr:`MilestonePaper.why_milestone`. The
user can always disagree.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence

from app.models import (
    Evidence,
    EvidenceLocationStatus,
    MilestoneCategory,
    MilestonePaper,
    ReliabilityLevel,
)
from app.r1_clients import R1Candidate


_TOP_VENUE_KEYWORDS = (
    "neurips", "nips", "icml", "iclr", "cvpr", "iccv", "eccv",
    "acl", "emnlp", "naacl", "siggraph", "kdd", "aaai", "ijcai",
    "nature", "science", "jmlr", "tmlr",
)


# Title regexes that earn a category bonus.
_CATEGORY_RULES = (
    (re.compile(r"\bsurvey\b|\breview\b", re.I), MilestoneCategory.SURVEY, "Survey / review article"),
    (re.compile(r"\bbenchmark\b|\bleaderboard\b|\bevaluation\b", re.I), MilestoneCategory.BENCHMARK, "Introduces / refines a benchmark"),
    (re.compile(r"\bdataset\b|\bcorpus\b|\bbenchmark dataset\b", re.I), MilestoneCategory.DATASET, "Introduces a dataset"),
    (re.compile(r"\btransformer|\battention is all\b|\bdiffusion\b|\bgan\b|\bautoencoder\b|\barchitecture\b|\bparadigm\b", re.I), MilestoneCategory.METHOD_PARADIGM, "Introduces a method paradigm"),
    (re.compile(r"\bsystem\b|\bplatform\b|\btoolkit\b|\bframework\b", re.I), MilestoneCategory.SYSTEM, "Releases a system / framework"),
    (re.compile(r"\btheorem\b|\bcomplexity\b|\bconvergence\b|\bguarantee\b", re.I), MilestoneCategory.THEORY, "Theoretical contribution"),
)


@dataclass
class _ScoreBreakdown:
    score: float
    reasons: List[str]
    category: MilestoneCategory


def detect_milestones(
    candidates: Sequence[R1Candidate],
    *,
    limit: int = 10,
    min_score: float = 1.0,
    now_year: Optional[int] = None,
) -> List[MilestonePaper]:
    """Score candidates and return the top ``limit`` milestone papers.

    Args:
        candidates: R1 candidates produced by the search pipeline.
        limit: how many milestones to keep (sorted by score desc).
        min_score: candidates below this score are filtered out.
        now_year: override for "current year" — used to compute velocity
            and recency adjustments. Defaults to ``datetime.utcnow().year``.
    """

    if not candidates:
        return []
    year_now = now_year or datetime.utcnow().year
    scored: List[tuple[R1Candidate, _ScoreBreakdown]] = []
    seen_fingerprints: set[str] = set()
    for cand in candidates:
        fp = cand.fingerprint()
        if fp in seen_fingerprints:
            continue
        seen_fingerprints.add(fp)
        breakdown = _score_candidate(cand, year_now=year_now)
        if breakdown.score < min_score:
            continue
        scored.append((cand, breakdown))

    scored.sort(key=lambda entry: entry[1].score, reverse=True)
    return [_to_milestone(cand, breakdown, year_now=year_now) for cand, breakdown in scored[:limit]]


def _score_candidate(cand: R1Candidate, *, year_now: int) -> _ScoreBreakdown:
    reasons: List[str] = []
    score = 0.0

    cites = cand.citation_count or 0
    if cites > 0:
        contribution = math.log10(max(cites, 1)) * 1.2  # 10 cites ≈ 1.2, 1000 cites ≈ 3.6
        score += contribution
        reasons.append(f"{cites} citations")

    influential = cand.influential_citation_count or 0
    if influential > 0:
        score += math.log10(max(influential, 1)) * 1.4
        reasons.append(f"{influential} influential citations")

    velocity = _velocity(cand, year_now=year_now)
    if velocity is not None and velocity > 0:
        score += min(velocity / 50.0, 2.0)  # 50 cites/year ≈ +1, 100/yr ≈ +2 (capped)
        reasons.append(f"{velocity:.1f} citations/year")

    if cand.venue and any(token in cand.venue.lower() for token in _TOP_VENUE_KEYWORDS):
        score += 0.6
        reasons.append(f"top venue ({cand.venue})")

    if cand.source.endswith(":survey"):
        score += 0.5
        reasons.append("appeared as a survey in R1 search")

    if cand.source.endswith(":benchmark"):
        score += 0.4
        reasons.append("shares a benchmark with the seed paper")

    if cand.tldr:
        score += 0.2
        reasons.append("has a Semantic Scholar TLDR")

    # Title-driven category bonus.
    category = MilestoneCategory.UNKNOWN
    for pattern, cat, label in _CATEGORY_RULES:
        if pattern.search(cand.title or ""):
            category = cat
            score += 0.3
            reasons.append(label)
            break

    # Recency adjustment: very new papers can't have many cites, so we
    # boost them slightly if they already have momentum.
    if cand.year and (year_now - cand.year) <= 2 and (cand.citation_count or 0) >= 20:
        score += 0.5
        reasons.append(f"early traction ({cand.citation_count} cites in ≤2 years)")

    return _ScoreBreakdown(score=score, reasons=reasons, category=category)


def _velocity(cand: R1Candidate, *, year_now: int) -> Optional[float]:
    if not cand.year or not cand.citation_count:
        return None
    years = max(year_now - cand.year, 1)
    return cand.citation_count / years


def _to_milestone(
    cand: R1Candidate,
    breakdown: _ScoreBreakdown,
    *,
    year_now: int,
) -> MilestonePaper:
    velocity = _velocity(cand, year_now=year_now)
    why = "; ".join(breakdown.reasons) if breakdown.reasons else "Heuristic milestone candidate"
    risk = _risk_note(cand, breakdown)
    evidence: List[Evidence] = []
    if cand.tldr:
        evidence.append(
            Evidence(
                id=f"ms-{cand.fingerprint()[:24]}-tldr",
                source=cand.source,
                quote=cand.tldr,
                location_status=EvidenceLocationStatus.QUOTE_ONLY,
            )
        )
    return MilestonePaper(
        id=f"ms-{cand.fingerprint()[:24]}",
        title=cand.title or "(untitled)",
        authors=list(cand.authors),
        year=cand.year,
        venue=cand.venue,
        url=cand.url,
        doi=cand.doi,
        arxiv_id=cand.arxiv_id,
        semantic_scholar_id=cand.semantic_scholar_id,
        citation_count=cand.citation_count,
        influential_citation_count=cand.influential_citation_count,
        velocity=round(velocity, 2) if velocity is not None else None,
        milestone_score=round(breakdown.score, 3),
        why_milestone=why,
        category=breakdown.category,
        risk=risk,
        evidence=evidence,
    )


def _risk_note(cand: R1Candidate, breakdown: _ScoreBreakdown) -> Optional[str]:
    notes: List[str] = []
    if (cand.citation_count or 0) < 30 and (cand.year or 0) < 2023:
        notes.append("low citation count for a paper older than 2 years")
    if breakdown.category == MilestoneCategory.UNKNOWN:
        notes.append("title gave no clear paradigm / benchmark / dataset cue")
    if not cand.doi and not cand.arxiv_id:
        notes.append("no DOI / arXiv id; manual verification recommended")
    return "; ".join(notes) if notes else None


def milestone_reliability() -> ReliabilityLevel:
    """Milestone facts are R1 (sourced from external metadata)."""

    return ReliabilityLevel.R1


def group_milestones_by_category(
    milestones: Iterable[MilestonePaper],
) -> Dict[MilestoneCategory, List[MilestonePaper]]:
    grouped: Dict[MilestoneCategory, List[MilestonePaper]] = {}
    for ms in milestones:
        grouped.setdefault(ms.category, []).append(ms)
    return grouped
