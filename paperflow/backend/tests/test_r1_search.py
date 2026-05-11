"""Phase 3 tests: references parser, R1 clients, R1 pipeline, API integration."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import (
    Claim,
    Evidence,
    ImportSourceType,
    PaperMetadata,
    ReadingReport,
    RelatedWorkItem,
    ReliabilityLevel,
    ReportSection,
)
from app.r1_clients import (
    OpenAlexClient,
    PapersWithCodeClient,
    R1Candidate,
    SemanticScholarClient,
)
from app.r1_search import R1SearchPipeline
from app.refs_parser import extract_references
from app.report_service import ReportService


def _wait_for_status(client: TestClient, paper_id: str, stage: str) -> dict:
    for _ in range(50):
        status = client.get(f"/api/papers/{paper_id}/status").json()
        if status["stage"] == stage:
            return status
        time.sleep(0.05)
    raise AssertionError(f"paper {paper_id} did not reach {stage}")


class _FakeAgent:
    """Tiny stand-in for ``PaperAgent`` — keeps the R1 test self-contained."""

    def generate_reading_report(self, paper_id, source_name, paper_text):  # noqa: D401
        evidence = Evidence(
            id="ev-1",
            source=source_name,
            page=1,
            quote="Agent quote.",
        )
        return ReadingReport(
            paper_id=paper_id,
            paper_title="r1 Test Paper",
            summary=[
                Claim(
                    id="s1",
                    text="Summary claim.",
                    reliability=ReliabilityLevel.R0,
                    evidence=[evidence],
                )
            ],
            sections=[
                ReportSection(
                    id="sec-1",
                    title="Method",
                    claims=[
                        Claim(
                            id="c1",
                            text="Method claim.",
                            reliability=ReliabilityLevel.R0,
                            evidence=[evidence],
                        )
                    ],
                )
            ],
            related_work=[
                RelatedWorkItem(
                    id="rw-placeholder",
                    title="Placeholder",
                    relation="follow-up",
                    source="agent",
                    reliability=ReliabilityLevel.R1,
                    evidence=[evidence],
                )
            ],
        )


# --------------------------------------------------------------- refs parser


_REFS_TEXT = """\
1. Introduction

Some introductory text.

References

[1] Vaswani Ashish, Shazeer Noam (2017). Attention Is All You Need.
NeurIPS. arXiv:1706.03762.
[2] Devlin Jacob, Chang Ming-Wei (2019). BERT: Pre-training of Deep Bidirectional
Transformers for Language Understanding. NAACL. doi:10.18653/v1/n19-1423.
[3] Brown Tom, Mann Benjamin (2020). Language Models are Few-Shot Learners. NeurIPS.

Appendix

This part should be ignored.
"""


def test_extract_references_handles_bracketed_entries() -> None:
    refs = extract_references(_REFS_TEXT)
    assert len(refs) == 3

    first = refs[0]
    assert first.index == 1
    assert first.arxiv_id == "1706.03762"
    assert first.year == 2017
    assert "Attention" in (first.title or "")

    second = refs[1]
    assert second.doi == "10.18653/v1/n19-1423"
    assert second.year == 2019
    assert "BERT" in (second.title or "")

    third = refs[2]
    assert third.year == 2020
    assert third.doi is None and third.arxiv_id is None


def test_extract_references_returns_empty_when_no_section() -> None:
    assert extract_references("just a body without references section.") == []


# --------------------------------------------------------------- S2 / OA / PwC clients


_S2_REFERENCES_PAYLOAD = {
    "data": [
        {
            "citedPaper": {
                "paperId": "seedseed1",
                "title": "Attention Is All You Need",
                "authors": [{"name": "Vaswani"}, {"name": "Shazeer"}],
                "year": 2017,
                "venue": "NeurIPS",
                "externalIds": {"ArXiv": "1706.03762"},
                "tldr": {"text": "Introduces the Transformer."},
                "citationCount": 90000,
                "influentialCitationCount": 4200,
            }
        }
    ]
}


@respx.mock
def test_semantic_scholar_references_normalises_candidates() -> None:
    respx.get("https://api.semanticscholar.org/graph/v1/paper/abc/references").mock(
        return_value=httpx.Response(200, json=_S2_REFERENCES_PAYLOAD)
    )
    with httpx.Client(timeout=10) as http:
        client = SemanticScholarClient(client=http)
        candidates = client.references("abc", limit=5)

    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.title == "Attention Is All You Need"
    assert cand.source == "semanticscholar:references"
    assert cand.arxiv_id == "1706.03762"
    assert cand.citation_count == 90000
    assert cand.influential_citation_count == 4200
    assert cand.tldr == "Introduces the Transformer."


_OPENALEX_WORK = {
    "id": "https://openalex.org/W1",
    "title": "Seed Paper",
    "doi": "https://doi.org/10.1/seed",
    "referenced_works": ["https://openalex.org/W2", "https://openalex.org/W3"],
}

_OPENALEX_BATCH = {
    "results": [
        {
            "id": "https://openalex.org/W2",
            "title": "Reference Two",
            "doi": "https://doi.org/10.1/two",
            "publication_year": 2018,
            "cited_by_count": 42,
            "authorships": [{"author": {"display_name": "A. One"}}],
            "primary_location": {"source": {"display_name": "ICML"}},
        }
    ]
}


@respx.mock
def test_openalex_references_of_returns_candidates() -> None:
    respx.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=_OPENALEX_BATCH)
    )
    with httpx.Client(timeout=10) as http:
        client = OpenAlexClient(client=http)
        candidates = client.references_of(_OPENALEX_WORK, limit=5)

    assert len(candidates) == 1
    assert candidates[0].title == "Reference Two"
    assert candidates[0].doi == "10.1/two"
    assert candidates[0].openalex_id == "W2"
    assert candidates[0].source == "openalex:references"
    assert candidates[0].citation_count == 42


@respx.mock
def test_papers_with_code_benchmark_neighbors() -> None:
    respx.get("https://paperswithcode.com/api/v1/papers").mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"id": "seed-paper", "title": "Seed"}]},
        )
    )
    respx.get("https://paperswithcode.com/api/v1/papers/seed-paper/tasks").mock(
        return_value=httpx.Response(200, json={"results": [{"id": "task-1"}]})
    )
    respx.get("https://paperswithcode.com/api/v1/tasks/task-1/papers").mock(
        return_value=httpx.Response(200, json={"results": [{"id": "neighbor-1"}]})
    )
    respx.get("https://paperswithcode.com/api/v1/papers/neighbor-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "neighbor-1",
                "title": "Neighbour Paper",
                "authors": ["X. Liu"],
                "published": "2023-04-01",
                "proceeding": "NeurIPS",
                "arxiv_id": "2304.00001",
                "url_abs": "https://arxiv.org/abs/2304.00001",
                "abstract": "Sharing a task.",
            },
        )
    )

    with httpx.Client(timeout=10) as http:
        client = PapersWithCodeClient(client=http)
        paper = client.find_paper("Seed paper")
        neighbours = client.benchmark_neighbors(paper, limit=5)

    assert paper is not None and paper["id"] == "seed-paper"
    assert len(neighbours) == 1
    assert neighbours[0].title == "Neighbour Paper"
    assert neighbours[0].source == "paperswithcode:benchmark"
    assert neighbours[0].arxiv_id == "2304.00001"


# --------------------------------------------------------------- pipeline


class _FakeS2:
    def __init__(self) -> None:
        self.closed = False

    def resolve(self, paper_id: str):
        return {"paperId": "SEED-ID"}

    def references(self, paper_id: str, limit: int = 50):
        return [
            R1Candidate(
                title="Backward reference",
                source="semanticscholar:references",
                year=2018,
                doi="10.1/back",
                citation_count=120,
                relation="cited reference",
            )
        ]

    def citations(self, paper_id: str, limit: int = 50):
        return [
            R1Candidate(
                title="Forward citation",
                source="semanticscholar:citations",
                year=2024,
                citation_count=15,
                relation="cites this paper",
            )
        ]

    def search(self, query: str, limit: int = 20, lane: str = "search"):
        if lane == "seed":
            return [
                R1Candidate(
                    title="Seed paper resolved",
                    source="semanticscholar:seed",
                    semantic_scholar_id="SEED-ID",
                    year=2024,
                )
            ]
        if lane == "survey":
            return [
                R1Candidate(
                    title=f"A Survey of {query[:20]}",
                    source="semanticscholar:survey",
                    year=2023,
                    relation="survey or review",
                )
            ]
        if lane == "recent":
            return [
                R1Candidate(
                    title="Recent related work",
                    source="semanticscholar:recent",
                    year=2025,
                    relation="recent related work",
                )
            ]
        return []

    def close(self) -> None:
        self.closed = True


class _FakeOA:
    def resolve_by_doi(self, doi):
        return None

    def resolve_by_arxiv(self, arxiv):
        return None

    def cited_by(self, work_id, limit=25):
        return []

    def references_of(self, work, limit=25):
        return []

    def close(self) -> None:
        pass


class _FakePwC:
    def find_paper(self, title):
        return None

    def benchmark_neighbors(self, paper, limit=10):
        return []

    def close(self) -> None:
        pass


def test_r1_pipeline_merges_lanes_and_sets_comparison_risk() -> None:
    pipeline = R1SearchPipeline(
        semantic_scholar=_FakeS2(),  # type: ignore[arg-type]
        openalex=_FakeOA(),  # type: ignore[arg-type]
        papers_with_code=_FakePwC(),  # type: ignore[arg-type]
    )
    metadata = PaperMetadata(
        title="Seed paper",
        year=2024,
        venue="ICLR",
        arxiv_id="2401.00001",
        source_type=ImportSourceType.ARXIV,
    )
    result = pipeline.search(metadata)

    titles = [item.title for item in result.items]
    assert "Backward reference" in titles
    assert "Forward citation" in titles
    assert any("Survey" in t for t in titles)
    assert any("Recent related work" in t for t in titles)

    # Comparison risk fires for the 2018 reference vs 2024 seed (different era).
    backward = next(i for i in result.items if i.title == "Backward reference")
    assert backward.comparison_risk is not None
    assert "different era" in backward.comparison_risk

    # Query trace lists each lane that ran.
    lanes = {entry.lane for entry in result.query_trace}
    assert {"backward", "forward", "survey", "recent"}.issubset(lanes)


# --------------------------------------------------------------- API


def test_r1_search_endpoint_persists_payload_and_updates_report(tmp_path: Path) -> None:
    pipeline = R1SearchPipeline(
        semantic_scholar=_FakeS2(),  # type: ignore[arg-type]
        openalex=_FakeOA(),  # type: ignore[arg-type]
        papers_with_code=_FakePwC(),  # type: ignore[arg-type]
    )
    app = create_app(
        tmp_path / "data",
        report_service=ReportService(agent=_FakeAgent()),
        r1_pipeline=pipeline,
    )
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("r1.pdf", b"Abstract: r1 paper.", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]
    _wait_for_status(client, paper_id, "completed")

    r1_payload = client.post(f"/api/papers/{paper_id}/r1-search").json()
    assert len(r1_payload["items"]) >= 2
    assert any(item["source"] == "semanticscholar:references" for item in r1_payload["items"])
    assert any(entry["lane"] == "backward" for entry in r1_payload["query_trace"])

    cached = client.get(f"/api/papers/{paper_id}/related").json()
    assert cached == r1_payload

    report = client.get(f"/api/papers/{paper_id}/report").json()
    assert report["related_work"]
    assert report["related_work"][0]["reliability"] == "R1"
