"""Technology timeline builder (PRD §4.7).

Builds a chronological list of :class:`TimelineEvent`s out of:

* The seed paper (always included).
* The detected :class:`MilestonePaper` set.
* The remaining R1 candidates (kept as ``follow_up`` events).

Each event records year, paper metadata, event type and a short
``key_idea`` / ``influence`` blurb derived from the candidate's TLDR
or abstract. Reliability is R1 — the timeline is grounded in external
metadata returned by the R1 search.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from app.models import (
    Evidence,
    EvidenceLocationStatus,
    MilestoneCategory,
    MilestonePaper,
    PaperMetadata,
    ReliabilityLevel,
    TimelineEvent,
    TimelineEventType,
)
from app.r1_clients import R1Candidate


def build_timeline(
    seed: PaperMetadata,
    *,
    milestones: Sequence[MilestonePaper],
    candidates: Sequence[R1Candidate],
    limit: int = 25,
) -> List[TimelineEvent]:
    """Return an ordered list of timeline events for the seed paper's field."""

    events: List[TimelineEvent] = []
    used_keys: set[str] = set()

    seed_event = _seed_event(seed)
    if seed_event is not None:
        events.append(seed_event)
        used_keys.add(_event_key(seed_event))

    for ms in milestones:
        event = _milestone_to_event(ms)
        key = _event_key(event)
        if key in used_keys:
            continue
        events.append(event)
        used_keys.add(key)

    for cand in candidates:
        if not cand.year:
            continue
        event = _candidate_to_event(cand)
        key = _event_key(event)
        if key in used_keys:
            continue
        events.append(event)
        used_keys.add(key)

    events.sort(key=lambda e: (e.year or 0, e.title.lower()))
    return events[:limit]


# ---------------------------------------------------------------- helpers


def _seed_event(seed: PaperMetadata) -> Optional[TimelineEvent]:
    if not seed.title:
        return None
    return TimelineEvent(
        id="tl-seed",
        year=seed.year,
        title=seed.title,
        authors=list(seed.authors or []),
        venue=seed.venue,
        event_type=TimelineEventType.OTHER,
        key_idea=seed.abstract[:240] if seed.abstract else None,
        reliability=ReliabilityLevel.R0,
    )


def _milestone_to_event(ms: MilestonePaper) -> TimelineEvent:
    event_type = _category_to_event_type(ms.category)
    key_idea = ms.why_milestone or None
    influence = None
    if ms.citation_count:
        influence = f"{ms.citation_count} citations"
        if ms.influential_citation_count:
            influence += f", {ms.influential_citation_count} influential"
    return TimelineEvent(
        id=f"tl-{ms.id}",
        year=ms.year,
        title=ms.title,
        authors=list(ms.authors),
        venue=ms.venue,
        event_type=event_type,
        key_idea=key_idea,
        influence=influence,
        reliability=ReliabilityLevel.R1,
        evidence=list(ms.evidence),
    )


def _candidate_to_event(cand: R1Candidate) -> TimelineEvent:
    event_type = _source_to_event_type(cand.source)
    key_idea = cand.tldr or (cand.abstract[:240] if cand.abstract else None)
    influence: Optional[str] = None
    if cand.citation_count:
        influence = f"{cand.citation_count} citations"
    evidence: List[Evidence] = []
    if cand.tldr:
        evidence.append(
            Evidence(
                id=f"tl-{cand.fingerprint()[:24]}-tldr",
                source=cand.source,
                quote=cand.tldr,
                location_status=EvidenceLocationStatus.QUOTE_ONLY,
            )
        )
    return TimelineEvent(
        id=f"tl-{cand.fingerprint()[:24]}",
        year=cand.year,
        title=cand.title or "(untitled)",
        authors=list(cand.authors),
        venue=cand.venue,
        event_type=event_type,
        key_idea=key_idea,
        influence=influence,
        reliability=ReliabilityLevel.R1,
        evidence=evidence,
    )


def _category_to_event_type(category: MilestoneCategory) -> TimelineEventType:
    return {
        MilestoneCategory.BENCHMARK: TimelineEventType.BENCHMARK,
        MilestoneCategory.DATASET: TimelineEventType.DATASET,
        MilestoneCategory.SURVEY: TimelineEventType.SURVEY,
        MilestoneCategory.SYSTEM: TimelineEventType.SYSTEM,
    }.get(category, TimelineEventType.MILESTONE)


def _source_to_event_type(source: str) -> TimelineEventType:
    if source.endswith(":survey"):
        return TimelineEventType.SURVEY
    if source.endswith(":benchmark"):
        return TimelineEventType.BENCHMARK
    if source.endswith(":citations") or source.endswith(":recent"):
        return TimelineEventType.FOLLOW_UP
    return TimelineEventType.OTHER


def _event_key(event: TimelineEvent) -> str:
    return f"{(event.title or '').lower().strip()}::{event.year or 0}"


def merge_user_events(
    base: Iterable[TimelineEvent],
    extras: Iterable[TimelineEvent],
) -> List[TimelineEvent]:
    """Merge an existing timeline with user-added events, deduping by key."""

    seen: dict[str, TimelineEvent] = {}
    for event in list(base) + list(extras):
        key = _event_key(event)
        if key not in seen:
            seen[key] = event
    out = list(seen.values())
    out.sort(key=lambda e: (e.year or 0, e.title.lower()))
    return out
