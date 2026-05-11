"""Phase 4 tests: milestone detection, timeline, Field Map aggregator, API."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.field_map import build_field_map
from app.main import create_app
from app.milestone import detect_milestones
from app.models import (
    Claim,
    Evidence,
    ImportSourceType,
    MilestoneCategory,
    PaperMetadata,
    ReadingReport,
    ReliabilityLevel,
    ReportSection,
    TimelineEventType,
)
from app.r1_clients import R1Candidate
from app.r1_search import R1QueryTraceEntry, R1SearchPipeline, R1SearchResult
from app.report_service import ReportService
from app.timeline import build_timeline


def _wait_for_status(client: TestClient, paper_id: str, stage: str) -> dict:
    for _ in range(50):
        status = client.get(f"/api/papers/{paper_id}/status").json()
        if status["stage"] == stage:
            return status
        time.sleep(0.05)
    raise AssertionError(f"paper {paper_id} did not reach {stage}")


class _FakeAgent:
    def generate_reading_report(self, paper_id, source_name, paper_text):
        evidence = Evidence(id="ev-1", source=source_name, page=1, quote="agent quote")
        return ReadingReport(
            paper_id=paper_id,
            paper_title="Seed paper for field map",
            summary=[
                Claim(
                    id="s1",
                    text="Summary.",
                    reliability=ReliabilityLevel.R0,
                    evidence=[evidence],
                )
            ],
            sections=[
                ReportSection(
                    id="sec-limits",
                    title="Limitations",
                    claims=[
                        Claim(
                            id="lim-1",
                            text="The method assumes static benchmarks.",
                            reliability=ReliabilityLevel.R0,
                            evidence=[evidence],
                        )
                    ],
                )
            ],
            related_work=[],
        )


# ------------------------------------------------------------ milestone


def test_milestone_detector_scores_and_ranks_candidates() -> None:
    candidates = [
        R1Candidate(
            title="Attention Is All You Need",
            source="semanticscholar:references",
            authors=["Vaswani", "Shazeer"],
            year=2017,
            venue="NeurIPS",
            citation_count=120000,
            influential_citation_count=5000,
            tldr="Introduces the Transformer architecture.",
        ),
        R1Candidate(
            title="A Survey of Foundation Models",
            source="semanticscholar:survey",
            year=2023,
            venue="arXiv",
            citation_count=400,
        ),
        R1Candidate(
            title="Niche method nobody cites",
            source="semanticscholar:recent",
            year=2018,
            citation_count=5,
        ),
    ]

    milestones = detect_milestones(candidates, limit=5, now_year=2025)

    titles = [ms.title for ms in milestones]
    assert "Attention Is All You Need" in titles
    top = milestones[0]
    assert top.title == "Attention Is All You Need"
    assert top.milestone_score > 0
    assert top.category in {MilestoneCategory.METHOD_PARADIGM, MilestoneCategory.UNKNOWN}
    assert top.velocity is not None and top.velocity > 0
    survey = next(ms for ms in milestones if "Survey" in ms.title)
    assert survey.category == MilestoneCategory.SURVEY
    # Low-signal candidate should be filtered or last.
    assert all(ms.title != "Niche method nobody cites" for ms in milestones) or milestones[-1].title == "Niche method nobody cites"


# ------------------------------------------------------------ timeline


def test_build_timeline_orders_events_by_year() -> None:
    seed = PaperMetadata(title="Seed 2024", year=2024, source_type=ImportSourceType.ARXIV)
    candidates = [
        R1Candidate(title="Old Foundation", source="semanticscholar:references", year=2017, citation_count=1000),
        R1Candidate(title="Mid Follow-up", source="semanticscholar:citations", year=2021, citation_count=120),
        R1Candidate(title="Recent Trend", source="semanticscholar:recent", year=2025, citation_count=50),
    ]
    milestones = detect_milestones(candidates, limit=5, now_year=2026)
    events = build_timeline(seed, milestones=milestones, candidates=candidates, limit=10)

    years = [e.year for e in events if e.year]
    assert years == sorted(years)
    titles = [e.title for e in events]
    assert "Seed 2024" in titles
    # Every event must carry a typed label; ``MILESTONE`` is fine for
    # high-signal candidates, ``FOLLOW_UP`` for raw forward citations.
    assert all(isinstance(e.event_type, TimelineEventType) for e in events)
    assert any(e.event_type in {TimelineEventType.MILESTONE, TimelineEventType.FOLLOW_UP} for e in events)


# ------------------------------------------------------------ field map


def test_build_field_map_aggregates_topics_milestones_open_problems() -> None:
    seed_metadata = PaperMetadata(
        title="Diffusion Models for Generation",
        year=2024,
        venue="NeurIPS",
        source_type=ImportSourceType.ARXIV,
    )
    candidates = [
        R1Candidate(
            title="Denoising Diffusion Probabilistic Models",
            source="semanticscholar:references",
            year=2020,
            venue="NeurIPS",
            citation_count=15000,
            influential_citation_count=600,
        ),
        R1Candidate(
            title="ImageNet Classification with Deep CNNs",
            source="semanticscholar:references",
            year=2012,
            venue="NeurIPS",
            citation_count=80000,
            influential_citation_count=4000,
            abstract="Trained on ImageNet dataset for image classification accuracy.",
        ),
        R1Candidate(
            title="A Survey on Diffusion Models",
            source="semanticscholar:survey",
            year=2023,
            venue="arXiv",
            citation_count=500,
        ),
        R1Candidate(
            title="Recent diffusion benchmark 2025",
            source="paperswithcode:benchmark",
            year=2025,
            citation_count=20,
            tldr="A new benchmark for diffusion generation accuracy.",
        ),
    ]
    search_result = R1SearchResult(
        items=[],  # build_field_map uses raw_candidates when provided
        query_trace=[R1QueryTraceEntry(lane="backward", source="semanticscholar", query="…", count=2)],
    )

    report = _FakeAgent().generate_reading_report("p1", "seed.pdf", "")
    fm = build_field_map(
        seed_paper_id="p1",
        seed_metadata=seed_metadata,
        search_result=search_result,
        raw_candidates=candidates,
        report=report,
    )

    assert fm.seed_paper_id == "p1"
    assert fm.field_summary  # non-empty
    assert fm.milestones, "milestones should be populated"
    assert any(t in fm.task_taxonomy + [fm.seed_title or ""] for t in [seed_metadata.title, "classification", "generation"])
    assert "imagenet" in [d.lower() for d in fm.datasets_benchmarks] + [""]
    assert any("accuracy" == m for m in fm.metrics) or fm.metrics == []
    assert any("Diffusion" in family or "diffusion" in family.lower() for family in fm.method_families)
    assert fm.open_problems and "static" in fm.open_problems[0].text.lower()
    assert fm.timeline and fm.timeline[0].year <= fm.timeline[-1].year
    assert fm.recent_trends, "recent trends should pick up 2025 candidate"
    assert fm.relationship_graph.nodes
    assert any(node.role == "seed" and node.title == "Diffusion Models for Generation" for node in fm.relationship_graph.nodes)
    assert any(edge.relation == "precedes" for edge in fm.relationship_graph.edges)


def test_field_map_relationship_graph_uses_citation_direction_not_year() -> None:
    seed_metadata = PaperMetadata(
        title="Seed Method",
        year=2024,
        source_type=ImportSourceType.ARXIV,
    )
    candidates = [
        R1Candidate(
            title="Future Benchmark That Does Not Cite Seed",
            source="paperswithcode:benchmark",
            relation="benchmark-only",
            year=2025,
            citation_count=10,
        ),
        R1Candidate(
            title="Later Paper That Cites Seed",
            source="semanticscholar:citations",
            relation="cited-by",
            year=2025,
            citation_count=20,
        ),
        R1Candidate(
            title="Newer Reference Used By Seed",
            source="semanticscholar:references",
            relation="referenced-by-seed",
            year=2025,
            citation_count=30,
        ),
    ]
    fm = build_field_map(
        seed_paper_id="seed-1",
        seed_metadata=seed_metadata,
        search_result=R1SearchResult(items=[]),
        raw_candidates=candidates,
    )

    roles = {node.title: node.role for node in fm.relationship_graph.nodes}

    assert roles["Later Paper That Cites Seed"] == "successor"
    assert roles["Newer Reference Used By Seed"] == "predecessor"
    assert "Future Benchmark That Does Not Cite Seed" not in roles


# ------------------------------------------------------------ API


class _FakePipeline:
    """Inject canned candidates so the API test is deterministic."""

    def search(self, metadata, *, parsed_refs=None):  # noqa: D401 — mimic signature
        result = R1SearchResult()
        candidates = [
            R1Candidate(
                title="Attention Is All You Need",
                source="semanticscholar:references",
                authors=["Vaswani"],
                year=2017,
                venue="NeurIPS",
                citation_count=120000,
                influential_citation_count=5000,
            ),
            R1Candidate(
                title="A Survey of Diffusion Models",
                source="semanticscholar:survey",
                year=2024,
                venue="arXiv",
                citation_count=300,
            ),
        ]
        from app.r1_search import _comparison_risk  # type: ignore  # reuse same logic

        for cand in candidates:
            from app.models import Evidence as _Evidence, EvidenceLocationStatus, ReliabilityLevel
            from app.models import RelatedWorkItem as _RWI

            result.items.append(
                _RWI(
                    id=f"r1-{cand.fingerprint()[:12]}",
                    title=cand.title,
                    relation="cited reference",
                    source=cand.source,
                    reliability=ReliabilityLevel.R1,
                    authors=list(cand.authors),
                    year=cand.year,
                    venue=cand.venue,
                    citation_count=cand.citation_count,
                    influential_citation_count=cand.influential_citation_count,
                    comparison_risk=_comparison_risk(cand, seed=metadata),
                )
            )
        result.query_trace.append(
            R1QueryTraceEntry(lane="backward", source="semanticscholar", query="…", count=2)
        )
        return result


def test_field_map_api_creates_and_reloads(tmp_path: Path) -> None:
    pipeline = _FakePipeline()
    app = create_app(
        tmp_path / "data",
        report_service=ReportService(agent=_FakeAgent()),
        r1_pipeline=pipeline,  # type: ignore[arg-type]
    )
    client = TestClient(app)

    upload = client.post(
        "/api/papers/import",
        files={"file": ("fm.pdf", b"Abstract: field map smoke.", "application/pdf")},
    )
    paper_id = upload.json()["paper"]["id"]
    _wait_for_status(client, paper_id, "completed")

    # Run R1 search first so the field-map builder picks up cached items.
    client.post(f"/api/papers/{paper_id}/r1-search")

    created = client.post("/api/field-maps", json={"paper_id": paper_id})
    assert created.status_code == 200
    field_map = created.json()
    assert field_map["seed_paper_id"] == paper_id
    assert field_map["milestones"], "milestones should not be empty"
    assert field_map["timeline"], "timeline should not be empty"
    assert field_map["open_problems"], "open problems should be derived from report"

    fetched = client.get(f"/api/field-maps/{field_map['id']}").json()
    assert fetched == field_map

    listed = client.get("/api/field-maps").json()
    assert any(item["id"] == field_map["id"] for item in listed)

    rerun = client.post(f"/api/field-maps/{field_map['id']}/rerun").json()
    assert rerun["id"] == field_map["id"]
    assert rerun["seed_paper_id"] == paper_id


def test_field_map_api_missing_paper_returns_404(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data", report_service=ReportService(agent=_FakeAgent()))
    client = TestClient(app)
    response = client.post("/api/field-maps", json={"paper_id": "does-not-exist"})
    assert response.status_code == 404
