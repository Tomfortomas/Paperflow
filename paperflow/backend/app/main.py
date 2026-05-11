from __future__ import annotations

import re
import tempfile
from threading import Thread
from pathlib import Path
from typing import Dict

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.deepseek import DeepSeekClient
from app.models import Claim, Evidence, PaperSession, ReadingReport, ReliabilityLevel, TaskStatus
from app.obsidian import render_obsidian_note
from app.report_service import ReportService
from app.storage import PaperStorage


class AskRequest(BaseModel):
    question: str


class ArxivImportRequest(BaseModel):
    url: str


class ExportResponse(BaseModel):
    note_path: str


def create_app(storage_root: Path = Path("paperflow_data"), report_service: ReportService = None) -> FastAPI:
    app = FastAPI(title="Paperflow API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    storage = PaperStorage(storage_root)
    injected_report_service = report_service is not None
    report_service = report_service or ReportService()
    reports: Dict[str, ReadingReport] = {}

    def create_session_from_pdf(tmp_path: Path, title: str) -> PaperSession:
        session = storage.create_paper_session(tmp_path, title=title)
        Thread(target=run_report_task, args=(session,), daemon=True).start()
        return session

    def run_report_task(session: PaperSession) -> None:
        storage.update_status(
            session.paper.id,
            TaskStatus(stage="processing", message="DeepSeek PaperAgent is parsing the PDF", progress=0.35),
        )
        try:
            report = report_service.generate_report(session)
        except Exception as exc:
            storage.update_status(
                session.paper.id,
                TaskStatus(stage="failed", message=str(exc), progress=1.0),
            )
            return

        reports[session.paper.id] = report
        storage.save_report(report)
        if report.paper_title:
            storage.update_paper_title(session.paper.id, report.paper_title)
        storage.update_status(
            session.paper.id,
            TaskStatus(stage="completed", message="Reading report generated", progress=1.0),
        )

    @app.post("/api/papers/import")
    async def import_paper(file: UploadFile = File(...)):
        suffix = Path(file.filename or "paper.pdf").suffix or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)

        title = Path(file.filename or "paper.pdf").stem
        return create_session_from_pdf(tmp_path, title=title)

    @app.post("/api/papers/import-arxiv")
    def import_arxiv(request: ArxivImportRequest):
        arxiv_id = extract_arxiv_id(request.url)
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        try:
            response = httpx.get(pdf_url, follow_redirects=True, timeout=60)
            response.raise_for_status()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to download arXiv PDF: {exc}")
        if not response.content.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="arXiv response was not a PDF")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = Path(tmp.name)

        return create_session_from_pdf(tmp_path, title=f"arxiv-{safe_arxiv_name(arxiv_id)}")

    @app.get("/api/papers")
    def list_papers():
        return storage.list_papers()

    @app.get("/api/papers/{paper_id}/status")
    def get_status(paper_id: str):
        try:
            return storage.get_status(paper_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Paper not found")

    @app.get("/api/papers/{paper_id}/report")
    def get_report(paper_id: str):
        if paper_id in reports:
            return reports[paper_id]
        try:
            report = storage.load_report(paper_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Report not found")
        reports[paper_id] = report
        return report

    @app.post("/api/papers/{paper_id}/rerun")
    def rerun_agent(paper_id: str):
        try:
            paper = storage.get_paper(paper_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Paper not found")

        session = PaperSession(
            id=f"rerun-{paper.id}",
            paper=paper,
            status=TaskStatus(stage="queued", message="Queued for Agent rerun", progress=0.05),
        )
        storage.update_status(paper.id, session.status)
        Thread(target=run_report_task, args=(session,), daemon=True).start()
        return session

    @app.get("/api/agent/status")
    def agent_status():
        client = DeepSeekClient.from_env()
        return {
            "configured": injected_report_service or client is not None,
            "mode": "injected" if injected_report_service else ("deepseek" if client else "missing-key"),
            "model": client.model if client else None,
        }

    @app.post("/api/papers/{paper_id}/ask")
    def ask_paper(paper_id: str, request: AskRequest):
        try:
            report = reports.get(paper_id) or storage.load_report(paper_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Report not found")

        question = request.question.lower()
        for section in report.sections:
            if section.title.lower().split("/")[0].strip() in question or "benchmark" in question:
                claim = section.claims[0]
                return Claim(
                    id="answer-focused",
                    text=claim.text,
                    reliability=claim.reliability,
                    evidence=claim.evidence,
                    uncertainty=claim.uncertainty,
                )

        first = report.summary[0]
        return Claim(
            id="answer-summary",
            text=first.text,
            reliability=ReliabilityLevel.R0,
            evidence=first.evidence,
        )

    @app.post("/api/papers/{paper_id}/export-obsidian")
    def export_obsidian(paper_id: str):
        try:
            report = reports.get(paper_id) or storage.load_report(paper_id)
        except FileNotFoundError:
            report = None
        paper = next((candidate for candidate in storage.list_papers() if candidate.id == paper_id), None)
        if not report or not paper:
            raise HTTPException(status_code=404, detail="Paper or report not found")

        markdown = render_obsidian_note(paper, report)
        note_path = storage.save_note(paper_id, markdown)
        return ExportResponse(note_path=str(note_path))

    return app


app = create_app()


def extract_arxiv_id(value: str) -> str:
    cleaned = value.strip()
    if cleaned.lower().startswith("arxiv:"):
        cleaned = cleaned.split(":", 1)[1].strip()

    url_match = re.search(r"arxiv\.org/(?:abs|pdf|html)/([^?#\s]+)", cleaned)
    if url_match:
        cleaned = url_match.group(1)

    cleaned = cleaned.removesuffix(".pdf")
    match = re.fullmatch(
        r"(?:[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?|\d{4}\.\d{4,5}(?:v\d+)?)",
        cleaned,
    )
    if not match:
        raise HTTPException(status_code=400, detail="Invalid arXiv URL or ID")
    return cleaned


def safe_arxiv_name(arxiv_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", arxiv_id)
