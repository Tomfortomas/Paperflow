from pathlib import Path
from threading import Event
import time

from fastapi.testclient import TestClient

from app.main import create_app, extract_arxiv_id
from app.models import ReadingReport
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


def test_reimport_same_filename_replaces_old_library_entry(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    for content in [b"Abstract: first", b"Abstract: second"]:
        response = client.post(
            "/api/papers/import",
            files={"file": ("same-paper.pdf", content, "application/pdf")},
        )
        assert response.status_code == 200
        wait_for_status(client, response.json()["paper"]["id"], "completed")

    library = client.get("/api/papers").json()

    assert [paper["title"] for paper in library] == ["Actual Paper Title"]


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


def test_import_arxiv_downloads_pdf_and_queues_agent(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    def fake_get(url, follow_redirects, timeout):
        captured["url"] = url
        captured["follow_redirects"] = follow_redirects
        captured["timeout"] = timeout
        return FakeDownloadResponse(b"%PDF-1.4\nAbstract: arXiv paper")

    monkeypatch.setattr("app.main.httpx.get", fake_get)
    app = create_app(tmp_path / "data", report_service=ReportService(agent=FakePaperAgent()))
    client = TestClient(app)

    response = client.post("/api/papers/import-arxiv", json={"url": "https://arxiv.org/abs/2605.08063v1"})
    paper_id = response.json()["paper"]["id"]

    assert response.status_code == 200
    assert captured["url"] == "https://arxiv.org/pdf/2605.08063v1.pdf"
    assert response.json()["paper"]["title"] == "arxiv-2605.08063v1"
    assert wait_for_status(client, paper_id, "completed")["stage"] == "completed"


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
