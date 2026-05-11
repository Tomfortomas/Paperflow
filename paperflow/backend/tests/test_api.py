from pathlib import Path
from threading import Event
import time

from fastapi.testclient import TestClient

from app.main import create_app, extract_arxiv_id
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

    answer = client.post(
        f"/api/papers/{paper_id}/ask",
        json={"question": "只看 benchmark"},
    ).json()
    assert answer["reliability"] == "R0"
    assert "agent extracted" in answer["text"].lower()

    note = client.post(f"/api/papers/{paper_id}/export-obsidian").json()
    assert note["note_path"].endswith("Actual Paper Title.md")
    assert Path(note["note_path"]).exists()


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


def test_agent_status_endpoint_reports_configured_state(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    status = client.get("/api/agent/status").json()

    assert status["configured"] is True
    assert status["mode"] == "injected"


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
