from __future__ import annotations

from typing import Iterable, List, Optional

from app.models import (
    Claim,
    FieldMap,
    MilestonePaper,
    Paper,
    ReadingReport,
    RelatedWorkItem,
    ResearchInsightReport,
    TimelineEvent,
)


def render_obsidian_note(paper: Paper, report: ReadingReport) -> str:
    lines: List[str] = [
        "---",
        f"title: {paper.title}",
        "status: processed",
        "tags:",
        "  - paperflow",
        "  - reading-report",
        "reliability:",
        "  - R0",
        "  - R1",
        "---",
        "",
        f"# {paper.title}",
        "",
        f"PDF: [[{paper.pdf_path.name}]]",
        "",
        "## Executive Summary",
        "",
    ]

    lines.extend(_render_claims(report.summary))

    lines.append("## R0 Reading Report")
    lines.append("")
    for section in report.sections:
        lines.append(f"### {section.title}")
        lines.append("")
        lines.extend(_render_claims(section.claims))

    lines.append("## R1 Related Work Context")
    lines.append("")
    for item in report.related_work:
        lines.extend(_render_related_work(item))

    lines.append("## Evidence Index")
    lines.append("")
    for claim in _all_claims(report):
        lines.append(f"- `{claim.reliability.value}` {claim.text}")
        for evidence in claim.evidence:
            location = f"p. {evidence.page}" if evidence.page else evidence.section or evidence.source
            lines.append(f"  - {location}: {evidence.quote}")
    lines.append("")

    return "\n".join(lines)


def _render_claims(claims: Iterable[Claim]) -> List[str]:
    lines: List[str] = []
    for claim in claims:
        lines.append(f"- `{claim.reliability.value}` {claim.text}")
        if claim.uncertainty:
            lines.append(f"  > [!warning] Uncertainty\n  > {claim.uncertainty}")
        for evidence in claim.evidence:
            lines.append("  > [!quote] Evidence")
            if evidence.page:
                lines.append(f"  > Page: {evidence.page}")
            lines.append(f"  > {evidence.quote}")
        lines.append("")
    return lines


def _render_related_work(item: RelatedWorkItem) -> List[str]:
    lines = [
        f"- `{item.reliability.value}` [[{item.title}]]",
        f"  - Relation: {item.relation}",
        f"  - Source: {item.source}",
        "",
    ]
    return lines


def _all_claims(report: ReadingReport) -> List[Claim]:
    claims = list(report.summary)
    for section in report.sections:
        claims.extend(section.claims)
    return claims


# ---------------------------------------------------------------- Phase 5: Field Map note


def render_field_map_note(
    field_map: FieldMap,
    *,
    insights: Optional[ResearchInsightReport] = None,
) -> str:
    """Render an Obsidian-friendly Markdown note for a :class:`FieldMap`.

    Sections (PRD §10.2):

    * frontmatter (title, seed paper, tags).
    * Field Summary.
    * Task taxonomy / datasets / metrics / method families chips.
    * Milestone papers (with `#milestone` + category tags).
    * Technology timeline (chronological).
    * Open problems (R0 / R1 source preserved).
    * Recent trends + research opportunities (R2 callouts).
    * R2 Research Insights (optional — when an insight report is provided).
    """

    title = field_map.seed_title or field_map.id
    lines: List[str] = [
        "---",
        f"title: \"Field Map · {title}\"",
        f"seed_paper_id: {field_map.seed_paper_id}",
        "tags:",
        "  - paperflow",
        "  - field-map",
        "reliability:",
        "  - R1",
        "  - R2",
        "---",
        "",
        f"# Field Map · {title}",
        "",
    ]
    if field_map.field_summary:
        lines += ["## Field Summary", "", field_map.field_summary, ""]

    lines += _field_map_chip_block("Task Taxonomy", field_map.task_taxonomy)
    lines += _field_map_chip_block("Datasets / Benchmarks", field_map.datasets_benchmarks)
    lines += _field_map_chip_block("Metrics", field_map.metrics)
    lines += _field_map_chip_block("Method Families", field_map.method_families)

    if field_map.milestones:
        lines += ["## Milestone Papers", ""]
        for ms in field_map.milestones:
            lines.extend(_render_milestone(ms))
    if field_map.timeline:
        lines += ["## Technology Timeline", ""]
        for event in field_map.timeline:
            lines.extend(_render_timeline_event(event))
    if field_map.open_problems:
        lines += ["## Open Problems", ""]
        lines.extend(_render_claims(field_map.open_problems))
    if field_map.recent_trends:
        lines += ["## Recent Trends (R2)", ""]
        lines.extend(_render_claims(field_map.recent_trends))
    if field_map.research_opportunities:
        lines += ["## Research Opportunities (R2)", ""]
        lines.extend(_render_claims(field_map.research_opportunities))

    if insights is not None and insights.insights:
        lines += ["## R2 Research Insights", ""]
        for insight in insights.insights:
            lines.append(f"> [!tip] R2 · {insight.kind}")
            lines.append(f"> {insight.text}")
            if insight.rationale:
                lines.append(f"> ")
                lines.append(f"> *Rationale:* {insight.rationale}")
            lines.append("")
    return "\n".join(lines)


def _render_milestone(ms: MilestonePaper) -> List[str]:
    head = f"- **{ms.title}** ({ms.year or '?'}) · `{ms.category}` · score {ms.milestone_score:.2f}"
    lines = [head]
    meta_parts: List[str] = []
    if ms.authors:
        meta_parts.append(", ".join(ms.authors[:3]) + (", …" if len(ms.authors) > 3 else ""))
    if ms.venue:
        meta_parts.append(ms.venue)
    if ms.velocity is not None:
        meta_parts.append(f"{ms.velocity}/yr")
    if meta_parts:
        lines.append(f"  - {' · '.join(meta_parts)}")
    if ms.why_milestone:
        lines.append(f"  - *Why:* {ms.why_milestone}")
    if ms.risk:
        lines.append(f"  > [!warning] Risk\n  > {ms.risk}")
    lines.append(f"  - Tags: #milestone #{ms.category}")
    lines.append("")
    return lines


def _render_timeline_event(event: TimelineEvent) -> List[str]:
    head = f"- **{event.year or '—'}** · `{event.event_type}` · {event.title}"
    lines = [head]
    if event.venue:
        lines.append(f"  - Venue: {event.venue}")
    if event.key_idea:
        lines.append(f"  - Idea: {event.key_idea}")
    if event.influence:
        lines.append(f"  - Influence: {event.influence}")
    lines.append("")
    return lines


def _field_map_chip_block(title: str, items: List[str]) -> List[str]:
    if not items:
        return []
    chips = ", ".join(f"`{item}`" for item in items)
    return [f"## {title}", "", chips, ""]
