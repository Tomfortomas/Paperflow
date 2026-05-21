from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional

import httpx

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

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
_BLOCK_BATCH = 100  # Notion API limit per append-children request


def _notion_token() -> str:
    token = os.getenv("NOTION_TOKEN", "").strip()
    if not token:
        raise ValueError("NOTION_TOKEN environment variable is not set")
    return token


def _notion_parent_page_id() -> str:
    pid = os.getenv("NOTION_PARENT_PAGE_ID", "").strip()
    if not pid:
        raise ValueError("NOTION_PARENT_PAGE_ID environment variable is not set")
    return pid


def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


# ---------------------------------------------------------------- block builders


def _rich_text(content: str) -> List[Dict]:
    return [{"type": "text", "text": {"content": content[:2000]}}]


def _heading2(text: str) -> Dict:
    return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": _rich_text(text)}}


def _heading3(text: str) -> Dict:
    return {"object": "block", "type": "heading_3", "heading_3": {"rich_text": _rich_text(text)}}


def _bullet(text: str, children: Optional[List[Dict]] = None) -> Dict:
    block: Dict[str, Any] = {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _rich_text(text)},
    }
    if children:
        block["bulleted_list_item"]["children"] = children
    return block


def _quote(text: str) -> Dict:
    return {"object": "block", "type": "quote", "quote": {"rich_text": _rich_text(text)}}


def _callout(text: str, emoji: str = "warning") -> Dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": _rich_text(text),
            "icon": {"type": "emoji", "emoji": emoji},
        },
    }


def _paragraph(text: str) -> Dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(text)}}


# ---------------------------------------------------------------- content renderers


def _blocks_for_claims(claims: Iterable[Claim]) -> List[Dict]:
    blocks: List[Dict] = []
    for claim in claims:
        children: List[Dict] = []
        if claim.uncertainty:
            children.append(_callout(f"Uncertainty: {claim.uncertainty}", "\u26a0\ufe0f"))
        for evidence in claim.evidence:
            location = f"p. {evidence.page}" if evidence.page else evidence.section or evidence.source
            children.append(_quote(f"{location}: {evidence.quote}"))
        blocks.append(_bullet(f"[{claim.reliability.value}] {claim.text}", children or None))
    return blocks


def _blocks_for_related_work(item: RelatedWorkItem) -> List[Dict]:
    children = [
        _bullet(f"Relation: {item.relation}"),
        _bullet(f"Source: {item.source}"),
    ]
    return [_bullet(f"[{item.reliability.value}] {item.title}", children)]


def _blocks_for_milestone(ms: MilestonePaper) -> List[Dict]:
    head = f"{ms.title} ({ms.year or '?'}) \u00b7 {ms.category} \u00b7 score {ms.milestone_score:.2f}"
    children: List[Dict] = []
    meta_parts: List[str] = []
    if ms.authors:
        meta_parts.append(", ".join(ms.authors[:3]) + (", \u2026" if len(ms.authors) > 3 else ""))
    if ms.venue:
        meta_parts.append(ms.venue)
    if ms.velocity is not None:
        meta_parts.append(f"{ms.velocity}/yr")
    if meta_parts:
        children.append(_bullet(" \u00b7 ".join(meta_parts)))
    if ms.why_milestone:
        children.append(_bullet(f"Why: {ms.why_milestone}"))
    if ms.risk:
        children.append(_callout(f"Risk: {ms.risk}", "\u26a0\ufe0f"))
    return [_bullet(head, children or None)]


def _blocks_for_timeline_event(event: TimelineEvent) -> List[Dict]:
    head = f"{event.year or '—'} \u00b7 {event.event_type} \u00b7 {event.title}"
    children: List[Dict] = []
    if event.venue:
        children.append(_bullet(f"Venue: {event.venue}"))
    if event.key_idea:
        children.append(_bullet(f"Idea: {event.key_idea}"))
    if event.influence:
        children.append(_bullet(f"Influence: {event.influence}"))
    return [_bullet(head, children or None)]


# ---------------------------------------------------------------- Notion API helper


def _create_notion_page(token: str, parent_page_id: str, title: str, blocks: List[Dict]) -> str:
    """Create a Notion page with the given blocks; handles 100-block batching."""
    hdrs = _headers(token)
    payload: Dict[str, Any] = {
        "parent": {"page_id": parent_page_id},
        "properties": {"title": {"title": [{"text": {"content": title[:2000]}}]}},
        "children": blocks[:_BLOCK_BATCH],
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{NOTION_API_BASE}/pages", headers=hdrs, json=payload)
        resp.raise_for_status()
        page_data = resp.json()
        page_id: str = page_data["id"]
        page_url: str = page_data.get("url", f"https://notion.so/{page_id.replace('-', '')}")

        remaining = blocks[_BLOCK_BATCH:]
        for i in range(0, len(remaining), _BLOCK_BATCH):
            batch = remaining[i: i + _BLOCK_BATCH]
            r = client.patch(
                f"{NOTION_API_BASE}/blocks/{page_id}/children",
                headers=hdrs,
                json={"children": batch},
            )
            r.raise_for_status()

    return page_url


# ---------------------------------------------------------------- public API


def create_paper_notion_page(paper: Paper, report: ReadingReport) -> str:
    """Export a reading report to a new Notion page. Returns the page URL."""
    token = _notion_token()
    parent_page_id = _notion_parent_page_id()

    blocks: List[Dict] = []
    blocks.append(_paragraph(f"PDF: {paper.pdf_path.name}"))

    blocks.append(_heading2("Executive Summary"))
    blocks.extend(_blocks_for_claims(report.summary))

    blocks.append(_heading2("R0 Reading Report"))
    for section in report.sections:
        blocks.append(_heading3(section.title))
        blocks.extend(_blocks_for_claims(section.claims))

    blocks.append(_heading2("R1 Related Work Context"))
    for item in report.related_work:
        blocks.extend(_blocks_for_related_work(item))

    blocks.append(_heading2("Evidence Index"))
    all_claims: List[Claim] = list(report.summary)
    for sec in report.sections:
        all_claims.extend(sec.claims)
    for claim in all_claims:
        for evidence in claim.evidence:
            location = f"p. {evidence.page}" if evidence.page else evidence.section or evidence.source
            blocks.append(_bullet(
                f"[{claim.reliability.value}] {claim.text} \u2014 {location}: {evidence.quote}"
            ))

    return _create_notion_page(token, parent_page_id, paper.title, blocks)


def create_field_map_notion_page(
    field_map: FieldMap,
    *,
    insights: Optional[ResearchInsightReport] = None,
) -> str:
    """Export a field map to a new Notion page. Returns the page URL."""
    token = _notion_token()
    parent_page_id = _notion_parent_page_id()
    title = f"Field Map \u00b7 {field_map.seed_title or field_map.id}"

    blocks: List[Dict] = []

    if field_map.field_summary:
        blocks.append(_heading2("Field Summary"))
        blocks.append(_paragraph(field_map.field_summary))

    def _chip_section(label: str, items: List[str]) -> None:
        if items:
            blocks.append(_heading2(label))
            blocks.append(_paragraph(", ".join(items)))

    _chip_section("Task Taxonomy", field_map.task_taxonomy)
    _chip_section("Datasets / Benchmarks", field_map.datasets_benchmarks)
    _chip_section("Metrics", field_map.metrics)
    _chip_section("Method Families", field_map.method_families)

    if field_map.milestones:
        blocks.append(_heading2("Milestone Papers"))
        for ms in field_map.milestones:
            blocks.extend(_blocks_for_milestone(ms))

    if field_map.timeline:
        blocks.append(_heading2("Technology Timeline"))
        for event in field_map.timeline:
            blocks.extend(_blocks_for_timeline_event(event))

    if field_map.open_problems:
        blocks.append(_heading2("Open Problems"))
        blocks.extend(_blocks_for_claims(field_map.open_problems))

    if field_map.recent_trends:
        blocks.append(_heading2("Recent Trends (R2)"))
        blocks.extend(_blocks_for_claims(field_map.recent_trends))

    if field_map.research_opportunities:
        blocks.append(_heading2("Research Opportunities (R2)"))
        blocks.extend(_blocks_for_claims(field_map.research_opportunities))

    if insights is not None and insights.insights:
        blocks.append(_heading2("R2 Research Insights"))
        for insight in insights.insights:
            insight_text = f"R2 \u00b7 {insight.kind}: {insight.text}"
            if insight.rationale:
                insight_text += f"\n\nRationale: {insight.rationale}"
            blocks.append(_callout(insight_text, "\U0001f4a1"))

    return _create_notion_page(token, parent_page_id, title, blocks)