from pathlib import Path
from threading import Event
import time

import httpx
from fastapi.testclient import TestClient

from app.main import create_app, extract_arxiv_id
from app.deepseek import set_report_read_timeout_seconds
from app.metadata import MetadataError
from app.models import ImportSourceType, PaperMetadata, ReadingReport
from app.report_service import ReportService
from tests.test_core_pipeline import FakePaperAgent


def test_import_lists_reads_asks_and_exports_note(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("paper.pdf", b"Abstract: A paper reading IDE.\nBenchmark: Evidence coverage.", "application/pdf")},
    )

    assert response.status_code == 200
    session = response.json()
    paper_id = session["paper"]["id"]
    assert session["report"] is None
    wait_for_status(client, paper_id, "completed")

    library = client.get("/api/papers").json()
    assert library[0]["id"] == paper_id
    assert library[0]["title"] == "Actual Paper Title"
    assert library[0]["status"]["stage"] == "completed"

    report = client.get(f"/api/papers/{paper_id}/report").json()
    assert report["summary"][0]["reliability"] == "R0"
    assert report["related_work"][0]["reliability"] == "R1"
    assert report["agent_run"]["elapsed_seconds"] is not None

    answer = client.post(
        f"/api/papers/{paper_id}/ask",
        json={"question": "只看 benchmark"},
    ).json()
    assert answer["reliability"] == "R0"
    assert "agent extracted" in answer["text"].lower()

    note = client.post(f"/api/papers/{paper_id}/export-obsidian").json()
    assert note["note_path"].endswith("Actual Paper Title.md")
    assert Path(note["note_path"]).exists()


def test_chat_returns_transcript_steps_and_evidence(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("paper.pdf", b"Abstract: A paper reading IDE.\nBenchmark: Evidence coverage.", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]
    wait_for_status(client, paper_id, "completed")

    chat = client.post(
        f"/api/papers/{paper_id}/chat",
        json={
            "question": "只看 benchmark",
            "selected_claim_id": "claim-task",
            "selected_evidence_id": "e2",
            "page": 2,
            "quote": "structured reports",
        },
    )

    assert chat.status_code == 200
    payload = chat.json()
    assert payload["paper_id"] == paper_id
    assert payload["status"] == "completed"
    assert [step["label"] for step in payload["steps"]] == [
        "Read report",
        "Locate evidence",
        "Check R1 context",
        "Compose answer",
        "Persist transcript",
    ]
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][1]["role"] == "assistant"
    assert payload["answer"]["reliability"] == "R0"
    assert payload["answer"]["evidence"][0]["quote"]
    assert payload["used_context"]

    chats = client.get(f"/api/papers/{paper_id}/chats").json()
    assert len(chats) == 1
    assert chats[0]["messages"][0]["content"] == "只看 benchmark"
    assert chats[0]["messages"][1]["role"] == "assistant"

    tasks = client.get("/api/tasks").json()
    assert any(task["kind"] == "chat" and task["paper_id"] == paper_id for task in tasks)


def test_chat_stream_returns_step_and_final_events(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("paper.pdf", b"Abstract: A paper reading IDE.", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]
    wait_for_status(client, paper_id, "completed")

    stream = client.post(f"/api/papers/{paper_id}/chat/stream", json={"question": "只看 task"})

    assert stream.status_code == 200
    assert "event: step" in stream.text
    assert "event: final" in stream.text
    assert "chat_response" in stream.text


def test_chat_rejects_empty_question(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("paper.pdf", b"Abstract: A paper reading IDE.", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]
    wait_for_status(client, paper_id, "completed")

    chat = client.post(f"/api/papers/{paper_id}/chat", json={"question": "  "})

    assert chat.status_code == 400


def test_reimport_same_content_replaces_old_library_entry(tmp_path: Path) -> None:
    """Phase 2: identical PDF bytes should dedup via content_hash."""

    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    payload = b"Abstract: identical bytes"
    for _ in range(2):
        response = client.post(
            "/api/papers/import",
            files={"file": ("same-paper.pdf", payload, "application/pdf")},
        )
        assert response.status_code == 200
        wait_for_status(client, response.json()["paper"]["id"], "completed")

    library = client.get("/api/papers").json()

    assert [paper["title"] for paper in library] == ["Actual Paper Title"]
    assert library[0]["metadata"]["content_hash"]


def test_reimport_different_bytes_with_same_filename_keeps_both(tmp_path: Path) -> None:
    """Phase 2: distinct content_hashes should *not* dedup, even if filenames match."""

    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    for content in [b"Abstract: first", b"Abstract: second"]:
        response = client.post(
            "/api/papers/import",
            files={"file": ("same-name.pdf", content, "application/pdf")},
        )
        assert response.status_code == 200
        wait_for_status(client, response.json()["paper"]["id"], "completed")

    library = client.get("/api/papers").json()
    assert len(library) == 2
    hashes = {paper["metadata"]["content_hash"] for paper in library}
    assert len(hashes) == 2


def test_reimport_same_arxiv_replaces_existing_and_warns(tmp_path: Path, monkeypatch) -> None:
    def fake_get(url, follow_redirects, timeout):
        content = b"%PDF-1.4\nAbstract: v2 bytes" if "v2" in url else b"%PDF-1.4\nAbstract: v1 bytes"
        return FakeDownloadResponse(content)

    monkeypatch.setattr("app.main.httpx.get", fake_get)
    monkeypatch.setattr(
        "app.main.fetch_metadata_from_url",
        lambda identifier: PaperMetadata(
            title="Same arXiv Paper",
            arxiv_id="2605.08063v2" if "v2" in identifier else "2605.08063v1",
            source_type=ImportSourceType.ARXIV,
            source_url=f"https://arxiv.org/abs/{identifier}",
        ),
    )
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    first = client.post("/api/papers/import-arxiv", json={"url": "https://arxiv.org/abs/2605.08063v1"}).json()
    wait_for_status(client, first["paper"]["id"], "completed")
    second = client.post("/api/papers/import-arxiv", json={"url": "https://arxiv.org/abs/2605.08063v2"}).json()

    library = client.get("/api/papers").json()
    assert len(library) == 1
    assert library[0]["id"] == second["paper"]["id"]
    assert second["duplicate_warning"]
    assert second["duplicate_of"]["id"] == first["paper"]["id"]


def test_report_persists_after_app_restart(tmp_path: Path) -> None:
    storage_root = tmp_path / "data"
    app = create_app(storage_root, report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)
    response = client.post(
        "/api/papers/import",
        files={"file": ("persistent.pdf", b"Abstract: persistent", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]
    wait_for_status(client, paper_id, "completed")

    restarted_client = TestClient(create_app(storage_root, report_service=ReportService(agent=FakePaperAgent())))
    report = restarted_client.get(f"/api/papers/{paper_id}/report")

    assert report.status_code == 200
    assert report.json()["summary"][0]["text"] == "AI agent summary"


def test_processing_import_is_marked_failed_after_app_restart(tmp_path: Path) -> None:
    storage_root = tmp_path / "data"
    blocking_service = BlockingReportService()
    app = create_app(storage_root, report_service=blocking_service)
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("interrupted.pdf", b"Abstract: interrupted", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]

    assert blocking_service.started.wait(timeout=2)
    assert client.get(f"/api/papers/{paper_id}/status").json()["stage"] == "processing"

    restarted_client = TestClient(create_app(storage_root, report_service=ReportService(agent=FakePaperAgent())))
    status = restarted_client.get(f"/api/papers/{paper_id}/status").json()

    assert status["stage"] == "failed"
    assert "Backend restarted" in status["message"]
    blocking_service.release.set()


def test_delete_paper_removes_library_entry_and_artifacts(tmp_path: Path) -> None:
    storage_root = tmp_path / "data"
    app = create_app(storage_root, report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("delete-me.pdf", b"Abstract: delete me", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]
    pdf_path = Path(response.json()["paper"]["pdf_path"])
    wait_for_status(client, paper_id, "completed")
    report_path = storage_root / "reports" / f"{paper_id}.json"

    note = client.post(f"/api/papers/{paper_id}/export-obsidian").json()
    note_path = Path(note["note_path"])
    client.post(f"/api/papers/{paper_id}/chat", json={"question": "只看 task"})
    assert client.get(f"/api/papers/{paper_id}/chats").json()

    delete_response = client.delete(f"/api/papers/{paper_id}")

    assert delete_response.status_code == 204
    assert client.get("/api/papers").json() == []
    assert client.get(f"/api/papers/{paper_id}/status").status_code == 404
    assert client.get(f"/api/papers/{paper_id}/report").status_code == 404
    assert client.get(f"/api/papers/{paper_id}/chats").status_code == 404
    assert not pdf_path.exists()
    assert not report_path.exists()
    assert not note_path.exists()


def test_import_returns_before_agent_completes_and_status_can_be_polled(tmp_path: Path) -> None:
    blocking_service = BlockingReportService()
    app = create_app(tmp_path / "data", report_service=blocking_service)
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("slow.pdf", b"Abstract: slow", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]

    assert response.status_code == 200
    assert response.json()["report"] is None
    assert blocking_service.started.wait(timeout=2)
    assert client.get(f"/api/papers/{paper_id}/status").json()["stage"] == "processing"

    blocking_service.release.set()
    assert wait_for_status(client, paper_id, "completed")["progress"] == 1.0


def test_processing_status_uses_non_misleading_initial_progress(tmp_path: Path) -> None:
    blocking_service = BlockingReportService()
    app = create_app(tmp_path / "data", report_service=blocking_service)
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("slow.pdf", b"Abstract: slow", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]

    assert blocking_service.started.wait(timeout=2)
    status = client.get(f"/api/papers/{paper_id}/status").json()

    assert status["stage"] == "processing"
    assert status["progress"] < 0.35
    assert "preparing" in status["message"].lower()
    blocking_service.release.set()


def test_processing_status_surfaces_deepseek_wait_context(tmp_path: Path) -> None:
    blocking_service = BlockingDeepSeekProgressService()
    app = create_app(tmp_path / "data", report_service=blocking_service)
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("slow-deepseek.pdf", b"Abstract: slow model", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]

    assert blocking_service.started.wait(timeout=2)
    status = client.get(f"/api/papers/{paper_id}/status").json()

    assert status["stage"] == "processing"
    assert status["progress"] >= 0.35
    assert "DeepSeek report generation is running" in status["message"]
    assert "model=deepseek-v4-flash" in status["message"]
    assert "timeout=90s" in status["message"]
    blocking_service.release.set()


def test_partial_report_is_available_while_agent_continues(tmp_path: Path) -> None:
    partial_service = PartialReportService()
    app = create_app(tmp_path / "data", report_service=partial_service)
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("partial.pdf", b"Abstract: partial", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]

    assert partial_service.partial_ready.wait(timeout=2)
    status = client.get(f"/api/papers/{paper_id}/status").json()
    report = client.get(f"/api/papers/{paper_id}/report").json()

    assert status["stage"] == "processing"
    assert "Partial reading report available" in status["message"]
    assert report["summary"][0]["text"] == "First chunk summary"
    assert report["agent_run"]["coverage_percent"] == 0.5
    assert report["agent_run"]["elapsed_seconds"] is not None

    partial_service.release.set()


def test_report_completion_survives_chunk_cache_failure(tmp_path: Path, monkeypatch) -> None:
    def fail_save_chunks(*args, **kwargs):
        raise OSError("chunk cache unavailable")

    monkeypatch.setattr("app.main.save_chunks", fail_save_chunks)
    app = create_app(tmp_path / "data", report_service=ChunkCacheFailureReportService())
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("cache-failure.pdf", b"Abstract: cache failure", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]

    status = wait_for_status(client, paper_id, "completed")
    report = client.get(f"/api/papers/{paper_id}/report").json()

    assert status["message"] == "Reading report generated"
    assert report["summary"][0]["text"] == "Report survives chunk cache failure"


def test_deepseek_read_timeout_surfaces_actionable_failed_status(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data", report_service=TimeoutReportService())
    client = TestClient(app)

    response = client.post(
        "/api/papers/import",
        files={"file": ("timeout.pdf", b"Abstract: timeout", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]

    status = wait_for_status(client, paper_id, "failed")

    assert "DeepSeek report generation timed out" in status["message"]


def test_agent_status_endpoint_reports_configured_state(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    status = client.get("/api/agent/status").json()

    assert status["configured"] is True
    assert status["mode"] == "injected"


def test_agent_config_endpoint_updates_model_and_timeout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DEEPSEEK_REPORT_READ_TIMEOUT", "90")
    try:
        app = create_app(tmp_path / "data")
        client = TestClient(app)

        initial = client.get("/api/agent/config").json()
        assert initial["model"] == "deepseek-v4-flash"
        assert initial["report_read_timeout"] == 90

        updated = client.put(
            "/api/agent/config",
            json={"model": "deepseek-v4-pro", "report_read_timeout": 120},
        )

        assert updated.status_code == 200
        payload = updated.json()
        assert payload["model"] == "deepseek-v4-pro"
        assert payload["report_read_timeout"] == 120
        assert client.get("/api/agent/status").json()["model"] == "deepseek-v4-pro"
    finally:
        set_report_read_timeout_seconds(None)


def test_agent_config_endpoint_accepts_api_key_without_echoing_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_CONFIG_PATH", str(tmp_path / "missing.toml"))
    app = create_app(tmp_path / "data")
    client = TestClient(app)

    initial = client.get("/api/agent/config").json()
    assert initial["configured"] is False
    assert initial["has_api_key"] is False

    updated = client.put(
        "/api/agent/config",
        json={"api_key": "runtime-key", "model": "deepseek-v4-pro"},
    )

    payload = updated.json()
    assert updated.status_code == 200
    assert payload["configured"] is True
    assert payload["has_api_key"] is True
    assert payload["model"] == "deepseek-v4-pro"
    assert "runtime-key" not in str(payload)


def test_missing_agent_configuration_surfaces_failed_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_CONFIG_PATH", str(tmp_path / "missing.toml"))
    app = create_app(tmp_path / "data")
    client = TestClient(app)

    agent_status = client.get("/api/agent/status").json()
    response = client.post(
        "/api/papers/import",
        files={"file": ("needs-agent.pdf", b"Abstract: needs agent", "application/pdf")},
    )
    paper_id = response.json()["paper"]["id"]

    assert agent_status["configured"] is False
    assert wait_for_status(client, paper_id, "failed")["message"].startswith("Agent not configured")


def test_import_arxiv_uses_real_metadata_when_available(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    def fake_get(url, follow_redirects, timeout):
        captured["url"] = url
        captured["follow_redirects"] = follow_redirects
        captured["timeout"] = timeout
        return FakeDownloadResponse(b"%PDF-1.4\nAbstract: arXiv paper")

    monkeypatch.setattr("app.main.httpx.get", fake_get)
    monkeypatch.setattr(
        "app.main.fetch_metadata_from_url",
        lambda _identifier: PaperMetadata(
            title="Stubbed arXiv Title",
            authors=["Alice Liu", "Bob Chen"],
            year=2025,
            venue="arXiv",
            arxiv_id="2605.08063v1",
            source_type=ImportSourceType.ARXIV,
            source_url="https://arxiv.org/abs/2605.08063v1",
        ),
    )
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    response = client.post("/api/papers/import-arxiv", json={"url": "https://arxiv.org/abs/2605.08063v1"})
    paper_id = response.json()["paper"]["id"]

    assert response.status_code == 200
    assert captured["url"] == "https://arxiv.org/pdf/2605.08063v1.pdf"
    paper = response.json()["paper"]
    assert paper["title"] == "Stubbed arXiv Title"
    assert paper["metadata"]["authors"] == ["Alice Liu", "Bob Chen"]
    assert paper["metadata"]["arxiv_id"] == "2605.08063v1"
    assert paper["metadata"]["source_type"] == "arxiv"
    assert wait_for_status(client, paper_id, "completed")["stage"] == "completed"


def test_import_arxiv_falls_back_when_metadata_unavailable(tmp_path: Path, monkeypatch) -> None:
    def fake_get(url, follow_redirects, timeout):
        return FakeDownloadResponse(b"%PDF-1.4\nAbstract: arXiv paper")

    def fake_fetch(_identifier):
        raise MetadataError("upstream offline")

    monkeypatch.setattr("app.main.httpx.get", fake_get)
    monkeypatch.setattr("app.main.fetch_metadata_from_url", fake_fetch)
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    response = client.post("/api/papers/import-arxiv", json={"url": "https://arxiv.org/abs/2605.08063v1"})
    paper = response.json()["paper"]
    assert response.status_code == 200
    assert paper["title"] == "arxiv-2605.08063v1"
    assert paper["metadata"]["arxiv_id"] == "2605.08063v1"
    assert paper["metadata"]["source_type"] == "arxiv"


def test_import_url_routes_to_metadata_then_downloads_pdf(tmp_path: Path, monkeypatch) -> None:
    def fake_get(url, follow_redirects, timeout):
        return FakeDownloadResponse(b"%PDF-1.4\nAbstract: url import")

    monkeypatch.setattr("app.main.httpx.get", fake_get)
    monkeypatch.setattr(
        "app.main.fetch_metadata_from_url",
        lambda _u: PaperMetadata(
            title="Imported via URL",
            arxiv_id="2401.99999",
            source_type=ImportSourceType.ARXIV,
        ),
    )
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    response = client.post(
        "/api/papers/import-url",
        json={"url": "https://arxiv.org/abs/2401.99999"},
    )
    assert response.status_code == 200
    paper = response.json()["paper"]
    assert paper["title"] == "Imported via URL"
    assert paper["metadata"]["arxiv_id"] == "2401.99999"


def test_import_url_rejects_doi_when_no_pdf_url_inferable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.fetch_metadata_from_url",
        lambda _u: PaperMetadata(
            title="DOI-only paper",
            doi="10.1234/no-pdf",
            source_type=ImportSourceType.DOI,
        ),
    )
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    response = client.post(
        "/api/papers/import-url",
        json={"url": "https://doi.org/10.1234/no-pdf"},
    )
    assert response.status_code == 400
    assert "cannot infer a PDF URL" in response.json()["detail"]


def test_extract_arxiv_id_accepts_common_forms() -> None:
    assert extract_arxiv_id("https://arxiv.org/abs/2605.08063v1") == "2605.08063v1"
    assert extract_arxiv_id("https://arxiv.org/pdf/2605.08063v1.pdf") == "2605.08063v1"
    assert extract_arxiv_id("arXiv:2605.08063") == "2605.08063"


class FakeDownloadResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


def wait_for_status(client: TestClient, paper_id: str, stage: str) -> dict:
    for _ in range(50):
        status = client.get(f"/api/papers/{paper_id}/status").json()
        if status["stage"] == stage:
            return status
        time.sleep(0.05)
    raise AssertionError(f"paper {paper_id} did not reach {stage}")


class BlockingReportService:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.inner = ReportService(agent=FakePaperAgent())

    def generate_report(self, session) -> ReadingReport:
        self.started.set()
        self.release.wait(timeout=5)
        return self.inner.generate_report(session)


class BlockingDeepSeekProgressService:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.inner = ReportService(agent=FakePaperAgent())

    def generate_report(self, session, on_progress=None) -> ReadingReport:
        if on_progress is not None:
            on_progress(
                "DeepSeek report generation is running "
                "(model=deepseek-v4-flash, timeout=90s, input=18 chars)"
            )
        self.started.set()
        self.release.wait(timeout=5)
        return self.inner.generate_report(session)


class PartialReportService:
    def __init__(self) -> None:
        self.partial_ready = Event()
        self.release = Event()
        self.inner = ReportService(agent=FakePaperAgent())

    def generate_report(self, session, on_progress=None, on_partial_report=None) -> ReadingReport:
        if on_partial_report is not None:
            partial = ReadingReport(
                paper_id=session.paper.id,
                summary=[
                    {
                        "id": "partial-summary",
                        "text": "First chunk summary",
                        "reliability": "R0",
                        "evidence": [],
                    }
                ],
                agent_run={
                    "coverage_percent": 0.5,
                    "covered_chars": 12000,
                    "total_chars": 24000,
                    "chunks_processed": 1,
                },
            )
            on_partial_report(partial)
        self.partial_ready.set()
        self.release.wait(timeout=5)
        return self.inner.generate_report(session)


class ChunkCacheFailureReportService:
    def generate_report(self, session) -> ReadingReport:
        return ReadingReport(
            paper_id=session.paper.id,
            summary=[
                {
                    "id": "summary",
                    "text": "Report survives chunk cache failure",
                    "reliability": "R0",
                    "evidence": [],
                }
            ],
        )

    def parsed_pdf(self):
        return type("Parsed", (), {"chunks": [object()]})()


class TimeoutReportService:
    def generate_report(self, session) -> ReadingReport:
        raise httpx.ReadTimeout("The read operation timed out")
