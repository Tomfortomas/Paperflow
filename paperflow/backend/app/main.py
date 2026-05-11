from __future__ import annotations

import re
import tempfile
from pathlib import Path
from threading import Thread
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.deepseek import DeepSeekClient
from app.metadata import (
    MetadataError,
    classify_url,
    fetch_metadata_from_url,
    pdf_url_from_metadata,
)
from app.models import (
    Claim,
    ImportSourceType,
    PaperMetadata,
    PaperSession,
    ReadingReport,
    ReliabilityLevel,
    TaskStatus,
)
from app.obsidian import render_obsidian_note
from app.report_service import ReportService
from app.storage import PaperStorage
from app.zotero import ZoteroError, ZoteroReader


class AskRequest(BaseModel):
    question: str


class ArxivImportRequest(BaseModel):
    url: str


class UrlImportRequest(BaseModel):
    url: str


class ZoteroImportRequest(BaseModel):
    item_key: Optional[str] = None
    zotero_dir: Optional[str] = None


class ExportResponse(BaseModel):
    note_path: str


def create_app(
    storage_root: Path = Path("paperflow_data"),
    report_service: Optional[ReportService] = None,
) -> FastAPI:
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

    def create_session_from_pdf(
        tmp_path: Path,
        *,
        title: str,
        metadata: Optional[PaperMetadata] = None,
    ) -> PaperSession:
        session = storage.create_paper_session(tmp_path, title=title, metadata=metadata)
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

    # ----------------------------------------------------------- import paths

    @app.post("/api/papers/import")
    async def import_paper(file: UploadFile = File(...)):
        suffix = Path(file.filename or "paper.pdf").suffix or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)

        title = Path(file.filename or "paper.pdf").stem
        metadata = PaperMetadata(title=title, source_type=ImportSourceType.LOCAL_PDF)
        return create_session_from_pdf(tmp_path, title=title, metadata=metadata)

    @app.post("/api/papers/import-arxiv")
    def import_arxiv(request: ArxivImportRequest):
        arxiv_id = _extract_arxiv_id_strict(request.url)
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

        try:
            metadata = fetch_metadata_from_url(arxiv_id)
        except MetadataError:
            metadata = PaperMetadata(
                title=f"arxiv-{_safe_arxiv_name(arxiv_id)}",
                arxiv_id=arxiv_id,
                source_type=ImportSourceType.ARXIV,
                source_url=f"https://arxiv.org/abs/{arxiv_id}",
            )

        title = (metadata.title or f"arxiv-{_safe_arxiv_name(arxiv_id)}").strip()
        return create_session_from_pdf(tmp_path, title=title, metadata=metadata)

    @app.post("/api/papers/import-url")
    def import_url(request: UrlImportRequest):
        """Generic import: arXiv URL, DOI, Semantic Scholar URL, or OpenReview URL.

        Fetches metadata, then attempts to download a PDF if one can be inferred
        (arXiv or OpenReview). If no PDF can be inferred, the import fails with
        a clear message so the user can upload a local PDF instead.
        """

        try:
            metadata = fetch_metadata_from_url(request.url)
        except MetadataError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        pdf_url = pdf_url_from_metadata(metadata)
        if not pdf_url:
            source = metadata.source_type.value if metadata.source_type else "unknown"
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Imported metadata from {source}, but cannot infer a PDF URL. "
                    f"Please upload the PDF directly via /api/papers/import."
                ),
            )

        try:
            response = httpx.get(pdf_url, follow_redirects=True, timeout=60)
            response.raise_for_status()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to download PDF from {pdf_url}: {exc}")
        if not response.content.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail=f"Response from {pdf_url} was not a PDF")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = Path(tmp.name)

        title = (metadata.title or "paper").strip()
        return create_session_from_pdf(tmp_path, title=title, metadata=metadata)

    @app.post("/api/papers/import-zotero")
    def import_zotero(request: ZoteroImportRequest):
        """Import every paper-like Zotero item that has a PDF attachment.

        If ``item_key`` is provided, only that single Zotero item is imported.
        """

        reader = ZoteroReader(zotero_dir=Path(request.zotero_dir) if request.zotero_dir else None)
        if not reader.is_available():
            raise HTTPException(
                status_code=400,
                detail=f"Zotero library not found at {reader.zotero_dir}",
            )
        try:
            items = reader.list_items()
        except ZoteroError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        if request.item_key:
            items = [item for item in items if item.item_key == request.item_key]
            if not items:
                raise HTTPException(status_code=404, detail=f"No Zotero item with key {request.item_key}")

        sessions: List[PaperSession] = []
        for item in items:
            if item.pdf_path is None:
                continue
            metadata = item.to_metadata()
            sessions.append(create_session_from_pdf(item.pdf_path, title=metadata.title or "paper", metadata=metadata))
        return {"imported": len(sessions), "sessions": sessions}

    @app.get("/api/zotero/preview")
    def zotero_preview(zotero_dir: Optional[str] = None, limit: int = 50):
        """Peek at the Zotero library without importing anything."""

        reader = ZoteroReader(zotero_dir=Path(zotero_dir) if zotero_dir else None)
        if not reader.is_available():
            raise HTTPException(
                status_code=400,
                detail=f"Zotero library not found at {reader.zotero_dir}",
            )
        try:
            items = reader.list_items(limit=limit)
        except ZoteroError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return [
            {
                "item_key": item.item_key,
                "title": item.title,
                "authors": item.authors,
                "year": item.year,
                "venue": item.venue,
                "doi": item.doi,
                "arxiv_id": item.arxiv_id,
                "has_pdf": item.pdf_path is not None,
            }
            for item in items
        ]

    # ----------------------------------------------------------- library

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


# ----------------------------------------------------------------- helpers


def _extract_arxiv_id_strict(value: str) -> str:
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


# Kept for older imports.
extract_arxiv_id = _extract_arxiv_id_strict


def _safe_arxiv_name(arxiv_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", arxiv_id)


# Kept for older imports.
safe_arxiv_name = _safe_arxiv_name
