"""Research Insight Agent (PRD §4.10).

Given a :class:`FieldMap` (and optionally the seed paper's report),
surface R2-level research insights:

* trends — what is changing across the timeline
* opportunities — under-explored milestones, fresh benchmarks
* method_angle — bridging cues across method families
* story — how to frame the field for a new reader
* writing — angles for paper introductions / related-work sections

Every insight is **strictly R2** with an ``uncertainty`` note. The
agent never silently elevates a heuristic to R0 / R1.
"""

from __future__ import annotations

import time
import uuid
from collections import Counter
from typing import List, Optional

from app.models import (
    Claim,
    Evidence,
    EvidenceLocationStatus,
    FieldMap,
    MilestoneCategory,
    ReadingReport,
    ReliabilityLevel,
    ResearchInsight,
    ResearchInsightReport,
)


def generate_insights(
    field_map: FieldMap,
    *,
    report: Optional[ReadingReport] = None,
    insight_id: Optional[str] = None,
) -> ResearchInsightReport:
    """Produce a :class:`ResearchInsightReport` for ``field_map``."""

    insights: List[ResearchInsight] = []
    insights.extend(_trend_insights(field_map))
    insights.extend(_opportunity_insights(field_map))
    insights.extend(_method_angle_insights(field_map))
    insights.extend(_story_insights(field_map, report))
    insights.extend(_writing_insights(field_map))

    return ResearchInsightReport(
        id=insight_id or f"ins-{uuid.uuid4().hex[:12]}",
        field_map_id=field_map.id,
        seed_paper_id=field_map.seed_paper_id,
        insights=insights,
        generated_at=time.time(),
    )


# ---------------------------------------------------------------- helpers


def _trend_insights(fm: FieldMap) -> List[ResearchInsight]:
    out: List[ResearchInsight] = []
    if not fm.timeline:
        return out

    years = sorted({e.year for e in fm.timeline if e.year})
    if years:
        span = years[-1] - years[0]
        out.append(
            ResearchInsight(
                id=f"trend-span-{fm.id}",
                kind="trend",
                text=(
                    f"The timeline spans {years[0]}–{years[-1]} ({span}+ years). "
                    f"Earlier work concentrates on foundations; recent {years[-1]} entries "
                    "suggest the active frontier — read the bottom of the timeline first."
                ),
                rationale=f"Timeline contains {len(fm.timeline)} events.",
            )
        )

    # Category drift over time.
    cat_counter: Counter[MilestoneCategory] = Counter(ms.category for ms in fm.milestones)
    if cat_counter:
        top = cat_counter.most_common(1)[0][0]
        out.append(
            ResearchInsight(
                id=f"trend-category-{fm.id}",
                kind="trend",
                text=f"Most milestones in this field are of category `{top}` — expect new submissions to be measured against that yardstick.",
                rationale="Most-frequent milestone category in the current Field Map.",
            )
        )
    return out


def _opportunity_insights(fm: FieldMap) -> List[ResearchInsight]:
    out: List[ResearchInsight] = []
    # Lean on the FieldMap's already-computed R2 opportunities.
    for claim in fm.research_opportunities:
        out.append(
            ResearchInsight(
                id=f"opp-{claim.id}",
                kind="opportunity",
                text=claim.text,
                rationale=claim.uncertainty or "FieldMap opportunity heuristic.",
                evidence=list(claim.evidence),
            )
        )

    # Add a fresh-benchmark opportunity if no benchmark milestone in
    # the last 3 years.
    bench_years = [ms.year or 0 for ms in fm.milestones if ms.category == MilestoneCategory.BENCHMARK]
    if bench_years and max(bench_years) < _now_year() - 3:
        out.append(
            ResearchInsight(
                id=f"opp-benchmark-{fm.id}",
                kind="opportunity",
                text=f"No benchmark milestone newer than {max(bench_years)} — proposing a refreshed evaluation could be high-leverage.",
                rationale="Heuristic: last benchmark milestone is more than 3 years old.",
            )
        )
    return out


def _method_angle_insights(fm: FieldMap) -> List[ResearchInsight]:
    out: List[ResearchInsight] = []
    families = fm.method_families[:3]
    if len(families) >= 2:
        out.append(
            ResearchInsight(
                id=f"angle-bridge-{fm.id}",
                kind="method_angle",
                text=(
                    f"The field is split across method families: {', '.join(families)}. "
                    "A bridging method that exploits the strengths of two families is a "
                    "common winning pattern at top venues."
                ),
                rationale="Field Map lists multiple method families.",
            )
        )
    return out


def _story_insights(fm: FieldMap, report: Optional[ReadingReport]) -> List[ResearchInsight]:
    out: List[ResearchInsight] = []
    if fm.field_summary:
        out.append(
            ResearchInsight(
                id=f"story-summary-{fm.id}",
                kind="story",
                text=(
                    f"One-line story: {fm.field_summary} "
                    "Use this when introducing the field in a paper / talk; refine with R1 "
                    "citations before publishing."
                ),
                rationale="Derived from FieldMap.field_summary.",
            )
        )
    if report is not None:
        limitations = [
            claim
            for section in report.sections
            for claim in section.claims
            if "limit" in (section.title or "").lower()
        ]
        if limitations:
            out.append(
                ResearchInsight(
                    id=f"story-limit-{fm.id}",
                    kind="story",
                    text=(
                        "The seed paper's own limitations make a natural opening for a follow-up: "
                        + limitations[0].text
                    ),
                    rationale="Re-uses an R0 limitation as a story hook (still R2 because the framing is inferred).",
                    evidence=[
                        Evidence(
                            id=f"story-limit-ev-{limitations[0].id}",
                            source="seed-report",
                            quote=limitations[0].text,
                            location_status=EvidenceLocationStatus.QUOTE_ONLY,
                        )
                    ],
                )
            )
    return out


def _writing_insights(fm: FieldMap) -> List[ResearchInsight]:
    out: List[ResearchInsight] = []
    if fm.milestones:
        first_three = ", ".join(ms.title for ms in fm.milestones[:3])
        out.append(
            ResearchInsight(
                id=f"write-related-{fm.id}",
                kind="writing",
                text=(
                    "Suggested related-work paragraph spine: anchor with "
                    f"{first_three}, contrast their categories, and end with the gap your "
                    "method targets. Treat this as a draft scaffold — replace with verified "
                    "R1 citations before submission."
                ),
                rationale="Top milestones from the Field Map.",
            )
        )
    return out


def _now_year() -> int:
    from datetime import datetime

    return datetime.utcnow().year


__all__ = ["generate_insights", "ResearchInsight", "ResearchInsightReport"]
