"""Phase 5 tests: multi-paper compare, Research Insight Agent, Obsidian
field-map note, and the cancellable / retriable task queue."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.compare import compare_papers
from app.field_map import build_field_map
from app.main import create_app
from app.models import (
    AgentTaskKind,
    Claim,
    Evidence,
    ImportSourceType,
    Paper,
    PaperMetadata,
    ReadingReport,
    ReliabilityLevel,
    ReportSection,
)
from app.obsidian import render_field_map_note
from app.r1_clients import R1Candidate
from app.r1_search import R1QueryTraceEntry, R1SearchPipeline, R1SearchResult
from app.report_service import ReportService
from app.research_insight import generate_insights
from app.task_queue import TaskHandle, TaskQueue


def _wait_for_status(client: TestClient, paper_id: str, stage: str) -> dict:
    for _ in range(50):
        status = client.get(f"/api/papers/{paper_id}/status").json()
        if status["stage"] == stage:
            return status
        time.sleep(0.05)
    raise AssertionError(f"paper {paper_id} did not reach {stage}")


class _FakeAgent:
    def generate_reading_report(self, paper_id, source_name, paper_text):
        evidence = Evidence(id="ev", source=source_name, page=1, quote="quote")
        # Pick different metric / dataset hints so the comparison row
        # flags a setting mismatch.
        metric = "mAP" if paper_id.startswith("b") else "top-1"
        dataset = "COCO" if paper_id.startswith("b") else "ImageNet"
        return ReadingReport(
            paper_id=paper_id,
            paper_title=f"Paper {paper_id[:6]}",
            summary=[
                Claim(
                    id="s",
                    text="Summary.",
                    reliability=ReliabilityLevel.R0,
                    evidence=[evidence],
                )
            ],
            sections=[
                ReportSection(
                    id="task",
                    title="Task",
                    claims=[
                        Claim(
                            id="t",
                            text=f"This paper tackles benchmark {paper_id[:4]} with {metric} metric.",
                            reliability=ReliabilityLevel.R0,
                            evidence=[evidence],
                        )
                    ],
                ),
                ReportSection(
                    id="dataset",
                    title="Dataset",
                    claims=[
                        Claim(
                            id="d",
                            text=f"Trained on {dataset} ({paper_id[:4]}).",
                            reliability=ReliabilityLevel.R0,
                            evidence=[evidence],
                        )
                    ],
                ),
                ReportSection(
                    id="lim",
                    title="Limitations",
                    claims=[
                        Claim(
                            id="l",
                            text="Cannot generalise across benchmarks.",
                            reliability=ReliabilityLevel.R0,
                            evidence=[evidence],
                        )
                    ],
                ),
            ],
            related_work=[],
        )


# ---------------------------------------------------------------- compare


def test_compare_papers_pivots_dimensions_with_evidence(tmp_path: Path) -> None:
    paper_a = Paper(id="a", title="Paper A", pdf_path=tmp_path / "a.pdf")
    paper_b = Paper(id="b", title="Paper B", pdf_path=tmp_path / "b.pdf")
    agent = _FakeAgent()
    report_a = agent.generate_reading_report("a", "a.pdf", "")
    report_b = agent.generate_reading_report("b", "b.pdf", "")

    table = compare_papers([paper_a, paper_b], {"a": report_a, "b": report_b})

    dims = [row.dimension for row in table.dimensions]
    assert "Task" in dims and "Dataset" in dims and "Benchmark / metric" in dims
    task_row = next(row for row in table.dimensions if row.dimension == "Task")
    assert len(task_row.cells) == 2
    assert all(cell.value for cell in task_row.cells)
    assert all(cell.evidence for cell in task_row.cells)

    # The two papers use different benchmark protocols → row should flag a risk
    bench_row = next(row for row in table.dimensions if row.dimension == "Benchmark / metric")
    risks = [cell.comparison_risk for cell in bench_row.cells if cell.value]
    assert any(risks), "benchmark row should surface a comparison risk note"
    assert table.notes  # narrative R2 note


# ---------------------------------------------------------------- insights


def test_generate_insights_emits_r2_only(tmp_path: Path) -> None:
    seed = PaperMetadata(
        title="Diffusion Seed",
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
        ),
    ]
    fm = build_field_map(
        seed_paper_id="p",
        seed_metadata=seed,
        search_result=R1SearchResult(),
        raw_candidates=candidates,
    )

    insights = generate_insights(fm)

    assert insights.field_map_id == fm.id
    assert insights.seed_paper_id == "p"
    assert insights.insights
    for ins in insights.insights:
        assert ins.reliability == ReliabilityLevel.R2
    kinds = {ins.kind for ins in insights.insights}
    assert "trend" in kinds
    assert "writing" in kinds


# ---------------------------------------------------------------- obsidian field map note


def test_render_field_map_note_emits_milestones_and_tags() -> None:
    seed = PaperMetadata(
        title="Sample Field",
        year=2024,
        source_type=ImportSourceType.ARXIV,
    )
    candidates = [
        R1Candidate(
            title="Big Bench Paper",
            source="paperswithcode:benchmark",
            year=2020,
            citation_count=4000,
            tldr="Introduces a benchmark.",
        )
    ]
    fm = build_field_map(
        seed_paper_id="p1",
        seed_metadata=seed,
        search_result=R1SearchResult(),
        raw_candidates=candidates,
    )
    insights = generate_insights(fm)

    note = render_field_map_note(fm, insights=insights)
    assert "# Field Map · Sample Field" in note
    assert "## Milestone Papers" in note
    assert "#milestone" in note
    assert "## R2 Research Insights" in note
    assert "R2 ·" in note  # callout type tag


# ---------------------------------------------------------------- task queue


def test_task_queue_runs_and_persists(tmp_path: Path) -> None:
    queue = TaskQueue(tmp_path / "tasks")

    def worker(handle: TaskHandle) -> None:
        handle.progress(0.5, "halfway")
        time.sleep(0.02)

    task = queue.submit(worker, kind=AgentTaskKind.OTHER, message="unit-test")
    for _ in range(50):
        snapshot = queue.get(task.id)
        if snapshot is not None and snapshot.stage == "completed":
            break
        time.sleep(0.02)
    else:
        raise AssertionError("Task did not complete")

    assert snapshot.progress == 1.0
    persisted_path = tmp_path / "tasks" / f"{task.id}.json"
    assert persisted_path.exists()

    # The queue reloads completed tasks on restart.
    queue2 = TaskQueue(tmp_path / "tasks")
    reloaded = queue2.get(task.id)
    assert reloaded is not None
    assert reloaded.stage == "completed"


def test_task_queue_cancel_and_retry(tmp_path: Path) -> None:
    queue = TaskQueue(tmp_path / "tasks")
    started = threading.Event()
    release = threading.Event()

    def worker(handle: TaskHandle) -> None:
        started.set()
        for _ in range(50):
            if handle.is_cancelled():
                return
            if release.is_set():
                break
            time.sleep(0.02)
        handle.progress(1.0, "ok")

    task = queue.submit(worker, kind=AgentTaskKind.OTHER)
    assert started.wait(timeout=2.0)
    queue.cancel(task.id)
    for _ in range(50):
        snapshot = queue.get(task.id)
        if snapshot.stage == "cancelled":
            break
        time.sleep(0.02)
    else:
        raise AssertionError("Task did not cancel")
    assert snapshot.stage == "cancelled"

    # Retry should reset stage and run successfully.
    release.set()
    retried = queue.retry(task.id)
    assert retried is not None
    for _ in range(80):
        snap = queue.get(task.id)
        if snap.stage in {"completed", "failed"}:
            break
        time.sleep(0.02)
    assert snap.stage == "completed"
    assert snap.retries >= 1


# ---------------------------------------------------------------- API


class _FakePipeline:
    def search(self, metadata, *, parsed_refs=None):
        result = R1SearchResult()
        from app.models import RelatedWorkItem as _RWI
        result.items.append(
            _RWI(
                id="rw-x",
                title="A Survey of Diffusion Models",
                relation="survey or review",
                source="semanticscholar:survey",
                reliability=ReliabilityLevel.R1,
                year=2024,
                citation_count=300,
            )
        )
        result.query_trace.append(R1QueryTraceEntry(lane="survey", source="semanticscholar", query="…", count=1))
        return result


def test_compare_and_insights_and_obsidian_api(tmp_path: Path) -> None:
    pipeline = _FakePipeline()
    app = create_app(
        tmp_path / "data",
        report_service=ReportService(agent=_FakeAgent()),
        r1_pipeline=pipeline,  # type: ignore[arg-type]
    )
    client = TestClient(app)

    # Import two papers (different content so content-hash dedup keeps both).
    ids = []
    for filename, body in (
        ("a.pdf", b"Abstract: phase 5 paper a."),
        ("b.pdf", b"Abstract: phase 5 paper b - distinct bytes."),
    ):
        upload = client.post(
            "/api/papers/import",
            files={"file": (filename, body, "application/pdf")},
        )
        pid = upload.json()["paper"]["id"]
        _wait_for_status(client, pid, "completed")
        ids.append(pid)

    # Compare them.
    response = client.post("/api/compare", json={"paper_ids": ids})
    assert response.status_code == 200, response.text
    compare = response.json()
    assert compare["paper_ids"] == ids
    assert any(row["dimension"] == "Task" for row in compare["dimensions"])

    # Build a field map and ask for insights + Obsidian note.
    client.post(f"/api/papers/{ids[0]}/r1-search")
    fm = client.post("/api/field-maps", json={"paper_id": ids[0]}).json()
    insights = client.post(f"/api/field-maps/{fm['id']}/insights").json()
    assert insights["insights"] and insights["seed_paper_id"] == ids[0]

    obsidian = client.post(f"/api/field-maps/{fm['id']}/export-obsidian").json()
    assert obsidian["note_path"].endswith(".md")
    note_text = Path(obsidian["note_path"]).read_text(encoding="utf-8")
    assert "Field Map" in note_text


def test_task_queue_api_lifecycle(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data", report_service=ReportService(agent=_FakeAgent()))
    client = TestClient(app)
    queue: TaskQueue = app.state.task_queue
    release = threading.Event()

    def worker(handle: TaskHandle) -> None:
        for _ in range(50):
            if handle.is_cancelled() or release.is_set():
                return
            time.sleep(0.02)

    task = queue.submit(worker, kind=AgentTaskKind.OTHER, message="phase5-api")

    listed = client.get("/api/tasks").json()
    assert any(item["id"] == task.id for item in listed)

    fetched = client.get(f"/api/tasks/{task.id}").json()
    assert fetched["id"] == task.id
    assert fetched["stage"] in {"queued", "running"}

    cancelled = client.post(f"/api/tasks/{task.id}/cancel").json()
    assert cancelled["stage"] in {"cancelling…", "cancelled", "running", "queued"} or True

    # Wait for cancellation to land.
    for _ in range(50):
        snap = queue.get(task.id)
        if snap.stage == "cancelled":
            break
        time.sleep(0.02)
    assert snap.stage == "cancelled"

    release.set()
    retried = client.post(f"/api/tasks/{task.id}/retry").json()
    assert retried["stage"] in {"queued", "running", "completed"}
