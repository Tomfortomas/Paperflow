from pathlib import Path

import fitz

from app.models import Claim, Evidence, ReadingReport, RelatedWorkItem, ReliabilityLevel, ReportSection
from app.obsidian import render_obsidian_note
from app.report_service import ReportService
from app.storage import PaperStorage


def test_creates_paper_session_and_lists_library(tmp_path: Path) -> None:
    storage = PaperStorage(tmp_path / "data")
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nPaperflow fixture\n")

    session = storage.create_paper_session(pdf_path)

    assert session.paper.title == "paper"
    assert session.status.stage == "queued"
    assert session.paper.pdf_path.exists()
    assert storage.list_papers()[0].id == session.paper.id


def test_storage_updates_display_title_after_agent_extracts_paper_title(tmp_path: Path) -> None:
    storage = PaperStorage(tmp_path / "data")
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nPaperflow fixture\n")
    session = storage.create_paper_session(pdf_path)

    storage.update_paper_title(session.paper.id, "Actual Paper Title")

    assert storage.get_paper(session.paper.id).title == "Actual Paper Title"


def test_claim_serializes_reliability_and_evidence() -> None:
    claim = Claim(
        id="claim-1",
        text="The paper introduces a reading assistant.",
        reliability=ReliabilityLevel.R0,
        evidence=[
            Evidence(
                id="evidence-1",
                source="paper.pdf",
                page=1,
                quote="We introduce a paper reading assistant.",
            )
        ],
    )

    data = claim.model_dump(mode="json")

    assert data["reliability"] == "R0"
    assert data["evidence"][0]["page"] == 1
    assert data["evidence"][0]["quote"].startswith("We introduce")


def test_report_service_builds_r0_report_with_evidence(tmp_path: Path) -> None:
    storage = PaperStorage(tmp_path / "data")
    pdf_path = tmp_path / "paper.txt"
    pdf_path.write_text(
        "Title: Paperflow\n"
        "Abstract: We build a paper reading IDE.\n"
        "Dataset: The paper uses arXiv papers.\n"
        "Benchmark: The report is judged by evidence coverage.\n",
        encoding="utf-8",
    )
    session = storage.create_paper_session(pdf_path)

    report = ReportService(agent=FakePaperAgent()).generate_report(session)

    assert report.summary[0].reliability == ReliabilityLevel.R0
    assert report.summary[0].evidence
    assert report.summary[0].text == "AI agent summary"
    assert "Agent Task" in [section.title for section in report.sections]
    assert report.related_work[0].reliability == ReliabilityLevel.R1


def test_report_service_extracts_text_from_real_pdf(tmp_path: Path) -> None:
    storage = PaperStorage(tmp_path / "data")
    pdf_path = tmp_path / "real-paper.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Abstract: This PDF contains extractable scientific content.")
    document.save(pdf_path)
    document.close()
    session = storage.create_paper_session(pdf_path)

    agent = FakePaperAgent()
    report = ReportService(agent=agent).generate_report(session)

    assert "extractable scientific content" in agent.received_text
    assert report.summary[0].text == "AI agent summary"


def test_report_service_delegates_report_generation_to_agent(tmp_path: Path) -> None:
    storage = PaperStorage(tmp_path / "data")
    pdf_path = tmp_path / "paper.txt"
    pdf_path.write_text("Abstract: Paperflow reads papers.", encoding="utf-8")
    session = storage.create_paper_session(pdf_path)
    agent = FakePaperAgent()

    report = ReportService(agent=agent).generate_report(session)

    assert agent.received_text.startswith("Abstract:")
    assert agent.received_paper_id == session.paper.id
    assert report.summary[0].text == "AI agent summary"


def test_obsidian_note_contains_frontmatter_badges_and_evidence(tmp_path: Path) -> None:
    storage = PaperStorage(tmp_path / "data")
    pdf_path = tmp_path / "paper.txt"
    pdf_path.write_text("Abstract: Evidence-aware reading.", encoding="utf-8")
    session = storage.create_paper_session(pdf_path)
    report = ReportService(agent=FakePaperAgent()).generate_report(session)

    note = render_obsidian_note(session.paper, report)

    assert note.startswith("---\n")
    assert "title: paper" in note
    assert "[[paper.pdf]]" in note
    assert "`R0`" in note
    assert "> [!quote] Evidence" in note
    assert "## R1 Related Work Context" in note


class FakePaperAgent:
    def __init__(self) -> None:
        self.received_text = ""
        self.received_paper_id = ""

    def generate_reading_report(self, paper_id: str, source_name: str, paper_text: str) -> ReadingReport:
        self.received_paper_id = paper_id
        self.received_text = paper_text
        evidence = Evidence(
            id="agent-evidence",
            source=source_name,
            page=1,
            quote="Agent selected evidence from the paper.",
        )
        return ReadingReport(
            paper_id=paper_id,
            paper_title="Actual Paper Title",
            summary=[
                Claim(
                    id="agent-summary",
                    text="AI agent summary",
                    reliability=ReliabilityLevel.R0,
                    evidence=[evidence],
                )
            ],
            sections=[
                ReportSection(
                    id="agent-task",
                    title="Agent Task",
                    claims=[
                        Claim(
                            id="agent-task-claim",
                            text="AI agent extracted the task.",
                            reliability=ReliabilityLevel.R0,
                            evidence=[evidence],
                        )
                    ],
                )
            ],
            related_work=[
                RelatedWorkItem(
                    id="agent-related",
                    title="AI agent related work seed",
                    relation="follow-up-search-entry",
                    source="AI agent",
                    reliability=ReliabilityLevel.R1,
                    evidence=[evidence],
                )
            ],
        )
