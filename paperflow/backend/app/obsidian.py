from __future__ import annotations

from typing import Iterable, List

from app.models import Claim, Paper, ReadingReport, RelatedWorkItem


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
