from __future__ import annotations

import inspect
import re
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.agent import DeepSeekPaperAgent
from app.chat_agent import generate_chat_response, sse_event
from app.compare import compare_papers
from app.deepseek import (
    DEEPSEEK_MODEL_OPTIONS,
    DeepSeekClient,
    report_read_timeout_seconds,
    set_report_read_timeout_seconds,
)
from app.evidence_verifier import EvidenceVerifier
from app.field_map import build_field_map
from app.metadata import (
    MetadataError,
    classify_url,
    fetch_metadata_from_url,
    pdf_url_from_metadata,
)
from app.models import (
    AgentTaskKind,
    Claim,
    Evidence,
    EvidenceLocationStatus,
    AgentRunMetrics,
    FieldMap,
    ImportSourceType,
    PaperMetadata,
    PaperChatMessage,
    PaperChatRequest,
    PaperChatResponse,
    PaperChatStep,
    PaperSession,
    ReadingReport,
    ReliabilityLevel,
    TaskStatus,
)
from app.obsidian import render_field_map_note, render_obsidian_note
from app.notion import create_paper_notion_page, create_field_map_notion_page
from app.pdf_parser import load_chunks, parse_pdf, save_chunks
from app.r1_search import R1SearchPipeline
from app.refs_parser import extract_references_from_parsed
from app.report_service import ReportService
from app.research_insight import generate_insights
from app.storage import PaperStorage
from app.task_queue import TaskQueue
from app.web_search import DuckDuckGoSearchClient
from app.zotero import ZoteroError, ZoteroReader

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORAGE_ROOT = PROJECT_ROOT / "data"


def _resolve_storage_root(storage_root: Optional[Path]) -> Path:
    if storage_root is not None:
        return Path(storage_root).expanduser()
    configured = os.getenv("PAPERFLOW_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_STORAGE_ROOT


def _web_search_mode() -> str:
    mode = os.getenv("PAPERFLOW_WEB_SEARCH", "auto").strip().lower()
    return mode if mode in {"auto", "off", "always"} else "auto"


def _web_search_limit() -> int:
    raw = os.getenv("PAPERFLOW_WEB_SEARCH_LIMIT", "5")
    try:
        value = int(raw)
    except ValueError:
        value = 5
    return max(1, min(8, value))


class AskRequest(BaseModel):
    question: str


class AskSelectionRequest(BaseModel):
    quote: str
    page: Optional[int] = None
    section: Optional[str] = None
    question: Optional[str] = None


class ArxivImportRequest(BaseModel):
    url: str


class UrlImportRequest(BaseModel):
    url: str


class ZoteroImportRequest(BaseModel):
    item_key: Optional[str] = None
    zotero_dir: Optional[str] = None


class ExportResponse(BaseModel):
    note_path: str


class NotionExportResponse(BaseModel):
    page_url: str


class AgentConfigRequest(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None
    report_read_timeout: Optional[float] = None


REPORT_PREPARING_MESSAGE = "PaperAgent is preparing PDF text and report context"
REPORT_TIMEOUT_MESSAGE = (
    "DeepSeek report generation timed out. The PDF may be long or the model may be slow; "
    "retry later or increase DEEPSEEK_REPORT_READ_TIMEOUT."
)


class ReportGenerationCancelled(Exception):
    pass


def _report_progress_for_message(message: str) -> float:
    if message.startswith("PDF text extraction completed"):
        return 0.25
    if message.startswith("DeepSeek request prepared"):
        return 0.32
    if message.startswith("DeepSeek briefing is running"):
        return 0.34
    if message.startswith("DeepSeek report generation is running"):
        return 0.35
    if message.startswith("DeepSeek parallel chunk extraction is running"):
        return 0.38
    chunk_match = re.match(r"^DeepSeek chunk completed \(chunk=(\d+)/(\d+)\)$", message)
    if chunk_match:
        done = int(chunk_match.group(1))
        total = max(1, int(chunk_match.group(2)))
        return min(0.86, 0.4 + 0.44 * (done / total))
    if message.startswith("DeepSeek coordinator synthesis is running"):
        return 0.88
    if message == "DeepSeek report received; locating evidence":
        return 0.92
    if message == "Evidence locations resolved; saving report":
        return 0.96
    return 0.35


def _mark_interrupted_report_runs(storage: PaperStorage) -> None:
    for paper in storage.list_papers():
        if paper.status.stage not in {"queued", "processing"}:
            continue
        try:
            report = storage.load_report(paper.id)
        except FileNotFoundError:
            storage.update_status(
                paper.id,
                TaskStatus(
                    stage="failed",
                    message="Backend restarted while PaperAgent was running. Please rerun the Agent.",
                    progress=1.0,
                ),
            )
            continue

        coverage = report.agent_run.coverage_percent if report.agent_run else None
        if coverage is None or coverage >= 0.999:
            storage.update_status(
                paper.id,
                TaskStatus(stage="completed", message="Reading report generated", progress=1.0),
            )
        else:
            storage.update_status(
                paper.id,
                TaskStatus(
                    stage="failed",
                    message="Backend restarted while PaperAgent was running. Partial report is available; rerun the Agent to complete it.",
                    progress=1.0,
                ),
            )


def _agent_deepseek_client(report_service: ReportService) -> Optional[DeepSeekClient]:
    agent = getattr(report_service, "agent", None)
    client = getattr(agent, "client", None)
    return client if isinstance(client, DeepSeekClient) else None


def _agent_config_payload(
    *,
    injected_report_service: bool,
    report_service: ReportService,
) -> dict:
    runtime_client = _agent_deepseek_client(report_service)
    env_client = DeepSeekClient.from_env()
    client = runtime_client or env_client
    mode = "injected" if injected_report_service else ("deepseek" if client else "missing-key")
    return {
        "configured": injected_report_service or client is not None,
        "has_api_key": client is not None,
        "mode": mode,
        "model": client.model if client else None,
        "model_options": DEEPSEEK_MODEL_OPTIONS,
        "report_read_timeout": report_read_timeout_seconds(),
    }


def _answer_chat_from_report(
    report: ReadingReport,
    request: PaperChatRequest,
    question: str,
) -> Claim:
    selected = _find_claim(report, request.selected_claim_id)
    if selected is not None:
        return Claim(
            id="chat-answer",
            text=selected.text,
            reliability=selected.reliability,
            evidence=_chat_evidence(selected, request),
            uncertainty=selected.uncertainty,
        )

    question_lower = question.lower()
    for section in report.sections:
        section_key = section.title.lower().split("/")[0].strip()
        if section_key and section_key in question_lower:
            claim = section.claims[0]
            return Claim(
                id="chat-answer",
                text=claim.text,
                reliability=claim.reliability,
                evidence=_chat_evidence(claim, request),
                uncertainty=claim.uncertainty,
            )
        if "benchmark" in question_lower and "benchmark" in section.title.lower():
            claim = section.claims[0]
            return Claim(
                id="chat-answer",
                text=claim.text,
                reliability=claim.reliability,
                evidence=_chat_evidence(claim, request),
                uncertainty=claim.uncertainty,
            )

    if request.quote:
        evidence = Evidence(
            id=request.selected_evidence_id or "chat-selection",
            source=report.paper_title or "selected PDF text",
            page=request.page,
            section=request.section,
            quote=request.quote.strip(),
            location_status=EvidenceLocationStatus.PAGE_AND_QUOTE if request.page else EvidenceLocationStatus.QUOTE_ONLY,
        )
        return Claim(
            id="chat-answer",
            text=f"鍩轰簬浣犻€変腑鐨勮瘉鎹紝Agent 灏嗛棶棰橀檺瀹氬湪杩欐鍘熸枃鍐咃細{request.quote.strip()[:180]}",
            reliability=ReliabilityLevel.R0,
            evidence=[evidence],
        )

    first = report.summary[0]
    return Claim(
        id="chat-answer",
        text=first.text,
        reliability=first.reliability,
        evidence=first.evidence,
        uncertainty=first.uncertainty,
    )


def _find_claim(report: ReadingReport, claim_id: Optional[str]) -> Optional[Claim]:
    if not claim_id:
        return None
    for claim in report.summary:
        if claim.id == claim_id:
            return claim
    for section in report.sections:
        for claim in section.claims:
            if claim.id == claim_id:
                return claim
    return None


def _chat_evidence(claim: Claim, request: PaperChatRequest) -> List[Evidence]:
    if request.selected_evidence_id:
        for evidence in claim.evidence:
            if evidence.id == request.selected_evidence_id:
                return [evidence]
    return claim.evidence


def create_app(
    storage_root: Optional[Path] = None,
    report_service: Optional[ReportService] = None,
    r1_pipeline: Optional[R1SearchPipeline] = None,
    web_search_client: Optional[object] = None,
) -> FastAPI:
    app = FastAPI(title="Paperflow API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    storage_root = _resolve_storage_root(storage_root)
    storage = PaperStorage(storage_root)
    injected_report_service = report_service is not None
    report_service = report_service or ReportService()
    pipeline_factory = (lambda: r1_pipeline) if r1_pipeline is not None else R1SearchPipeline
    web_search_mode = _web_search_mode()
    chat_web_search_client = (
        web_search_client
        if web_search_client is not None
        else (None if web_search_mode == "off" else DuckDuckGoSearchClient())
    )
    reports: Dict[str, ReadingReport] = {}
    task_queue = TaskQueue(storage_root / "tasks")
    _mark_interrupted_report_runs(storage)

    def create_session_from_pdf(
        tmp_path: Path,
        *,
        title: str,
        metadata: Optional[PaperMetadata] = None,
    ) -> PaperSession:
        session = storage.create_paper_session(tmp_path, title=title, metadata=metadata)
        task_queue.submit(
            lambda handle: run_report_task(session, handle),
            kind=AgentTaskKind.REPORT,
            paper_id=session.paper.id,
            message="Queued for Agent parsing",
        )
        return session

    def run_report_task(session: PaperSession, handle=None) -> Optional[str]:
        def abort_if_cancelled() -> None:
            if handle is not None and handle.is_cancelled():
                storage.update_status(
                    session.paper.id,
                    TaskStatus(stage="failed", message="Report generation cancelled.", progress=1.0),
                )
                raise ReportGenerationCancelled()

        def update_agent_progress(message: str) -> None:
            abort_if_cancelled()
            progress = _report_progress_for_message(message)
            storage.update_status(
                session.paper.id,
                TaskStatus(
                    stage="processing",
                    message=message,
                    progress=progress,
                ),
            )
            if handle is not None:
                handle.progress(progress, message)

        def save_partial_report(partial: ReadingReport) -> None:
            abort_if_cancelled()
            if partial.agent_run is None:
                partial.agent_run = AgentRunMetrics()
            partial.agent_run.elapsed_seconds = round(time.perf_counter() - started_at, 2)
            reports[session.paper.id] = partial
            storage.save_report(partial)
            if partial.paper_title:
                storage.update_paper_title(session.paper.id, partial.paper_title)
            coverage = partial.agent_run.coverage_percent if partial.agent_run else None
            chunks = partial.agent_run.chunks_processed if partial.agent_run else None
            coverage_text = f"{round((coverage or 0) * 100)}%" if coverage is not None else "partial"
            storage.update_status(
                session.paper.id,
                TaskStatus(
                    stage="processing",
                    message=f"Partial reading report available (coverage={coverage_text}, chunks={chunks or 1})",
                    progress=min(0.9, max(0.4, coverage or 0.4)),
                ),
            )
            if handle is not None:
                handle.progress(min(0.9, max(0.4, coverage or 0.4)), "Partial reading report available")

        storage.update_status(
            session.paper.id,
            TaskStatus(stage="processing", message=REPORT_PREPARING_MESSAGE, progress=0.15),
        )
        if handle is not None:
            handle.progress(0.15, REPORT_PREPARING_MESSAGE)
        started_at = time.perf_counter()
        try:
            abort_if_cancelled()
            report_params = inspect.signature(report_service.generate_report).parameters
            kwargs = {}
            if "on_progress" in report_params:
                kwargs["on_progress"] = update_agent_progress
            if "on_partial_report" in report_params:
                kwargs["on_partial_report"] = save_partial_report
            report = report_service.generate_report(session, **kwargs)
            abort_if_cancelled()
        except ReportGenerationCancelled:
            return None
        except httpx.ReadTimeout:
            storage.update_status(
                session.paper.id,
                TaskStatus(stage="failed", message=REPORT_TIMEOUT_MESSAGE, progress=1.0),
            )
            raise
        except Exception as exc:
            storage.update_status(
                session.paper.id,
                TaskStatus(stage="failed", message=str(exc), progress=1.0),
            )
            raise

        elapsed_seconds = round(time.perf_counter() - started_at, 2)
        if report.agent_run is None:
            report.agent_run = AgentRunMetrics()
        report.agent_run.elapsed_seconds = elapsed_seconds

        # Persist parsed chunks alongside the report so the viewer (and any
        # later rerun) can highlight evidence without re-parsing the PDF.
        parsed = report_service.parsed_pdf() if hasattr(report_service, "parsed_pdf") else None
        if parsed is None:
            try:
                parsed = parse_pdf(session.paper.pdf_path)
            except Exception:
                parsed = None
        if parsed is not None and parsed.chunks:
            try:
                save_chunks(storage.chunks_path(session.paper.id), parsed)
            except Exception:
                # The report itself is the critical artifact. Chunk cache writes
                # improve PDF highlighting but should not strand a completed run
                # in "processing" if the cache is unavailable.
                pass

        reports[session.paper.id] = report
        report_path = storage.save_report(report)
        if report.paper_title:
            storage.update_paper_title(session.paper.id, report.paper_title)
        storage.update_status(
            session.paper.id,
            TaskStatus(stage="completed", message="Reading report generated", progress=1.0),
        )
        if handle is not None:
            handle.progress(1.0, "Reading report generated")
        return str(report_path)

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

    @app.delete("/api/papers/{paper_id}", status_code=204)
    def delete_paper(paper_id: str):
        reports.pop(paper_id, None)
        if not storage.delete_paper(paper_id):
            raise HTTPException(status_code=404, detail="Paper not found")
        return Response(status_code=204)

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
        task_queue.submit(
            lambda handle: run_report_task(session, handle),
            kind=AgentTaskKind.REPORT,
            paper_id=paper.id,
            message="Queued for Agent rerun",
        )
        return session

    @app.get("/api/agent/status")
    def agent_status():
        config = _agent_config_payload(
            injected_report_service=injected_report_service,
            report_service=report_service,
        )
        return {
            "configured": config["configured"],
            "mode": config["mode"],
            "model": config["model"],
        }

    @app.get("/api/agent/config")
    def get_agent_config():
        return _agent_config_payload(
            injected_report_service=injected_report_service,
            report_service=report_service,
        )

    @app.put("/api/agent/config")
    def update_agent_config(request: AgentConfigRequest):
        runtime_client = _agent_deepseek_client(report_service)
        model = request.model.strip() if request.model is not None else None

        if request.api_key is not None:
            api_key = request.api_key.strip()
            if not api_key:
                raise HTTPException(status_code=400, detail="api_key cannot be empty")
            os.environ["DEEPSEEK_API_KEY"] = api_key
            runtime_client = DeepSeekClient(
                api_key=api_key,
                base_url=os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/beta",
                model=model or (runtime_client.model if runtime_client else os.getenv("DEEPSEEK_MODEL") or "deepseek-v4-flash"),
            )
            report_service.agent = DeepSeekPaperAgent(runtime_client)

        if request.report_read_timeout is not None:
            if request.report_read_timeout < 10 or request.report_read_timeout > 600:
                raise HTTPException(
                    status_code=400,
                    detail="report_read_timeout must be between 10 and 600 seconds",
                )
            set_report_read_timeout_seconds(request.report_read_timeout)

        if model is not None:
            if not model:
                raise HTTPException(status_code=400, detail="model cannot be empty")
            runtime_client = _agent_deepseek_client(report_service)
            if runtime_client is not None:
                runtime_client.model = model

        return _agent_config_payload(
            injected_report_service=injected_report_service,
            report_service=report_service,
        )

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

    def _build_and_persist_chat_response(paper_id: str, request: PaperChatRequest) -> PaperChatResponse:
        question = request.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="question is required")
        try:
            report = reports.get(paper_id) or storage.load_report(paper_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Report not found")
        chat_id = storage.default_chat_id(paper_id)
        response = generate_chat_response(
            paper_id=paper_id,
            chat_id=chat_id,
            question=question,
            request=request,
            report=report,
            r1_cache=storage.load_r1(paper_id),
            client=_agent_deepseek_client(report_service),
            web_search_client=chat_web_search_client,
            web_search_limit=_web_search_limit(),
            web_search_mode=web_search_mode,
        )
        turn_id = f"turn-{uuid.uuid4().hex[:10]}"
        persisted = storage.save_chat_turn(response, turn_id=turn_id)
        task = task_queue.record_completed(
            kind=AgentTaskKind.CHAT,
            paper_id=paper_id,
            message="Agent chat completed",
        )
        persisted.task_id = task.id
        persisted.used_context = response.used_context
        return persisted

    @app.get("/api/papers/{paper_id}/chats")
    def list_paper_chats(paper_id: str):
        try:
            storage.get_paper(paper_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Paper not found")
        return [chat.model_dump(mode="json") for chat in storage.list_chats(paper_id)]

    @app.get("/api/papers/{paper_id}/chats/{chat_id}")
    def get_paper_chat(paper_id: str, chat_id: str):
        try:
            return storage.load_chat(paper_id, chat_id).model_dump(mode="json")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Chat not found")

    @app.post("/api/papers/{paper_id}/chat")
    def chat_paper(paper_id: str, request: PaperChatRequest):
        return _build_and_persist_chat_response(paper_id, request)

    @app.post("/api/papers/{paper_id}/chat/stream")
    def stream_chat_paper(paper_id: str, request: PaperChatRequest):
        def generate():
            try:
                response = _build_and_persist_chat_response(paper_id, request)
                for step in response.steps[-5:]:
                    yield sse_event("step", step.model_dump(mode="json"))
                yield sse_event("delta", {"text": response.answer.text})
                yield sse_event("final", {"chat_response": response.model_dump(mode="json")})
            except Exception as exc:
                yield sse_event("error", {"message": str(exc)})

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/api/papers/{paper_id}/pdf")
    def get_pdf(paper_id: str):
        try:
            paper = storage.get_paper(paper_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Paper not found")
        if not paper.pdf_path.is_file():
            raise HTTPException(status_code=404, detail="PDF missing on disk")
        return FileResponse(paper.pdf_path, media_type="application/pdf", filename=paper.pdf_path.name)

    @app.get("/api/papers/{paper_id}/chunks")
    def get_chunks(paper_id: str):
        """Page-level text chunks + page sizes for the PDF viewer."""

        try:
            paper = storage.get_paper(paper_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Paper not found")

        chunks_file = storage.chunks_path(paper_id)
        parsed = load_chunks(chunks_file)
        if parsed is None and paper.pdf_path.is_file():
            try:
                parsed = parse_pdf(paper.pdf_path)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"PDF parse failed: {exc}")
            if parsed.chunks:
                save_chunks(chunks_file, parsed)
        if parsed is None:
            raise HTTPException(status_code=404, detail="No parsed chunks available")
        return parsed.to_dict()

    @app.post("/api/papers/{paper_id}/ask-selection")
    def ask_selection(paper_id: str, request: AskSelectionRequest):
        """Treat a user PDF selection as a focused R0 evidence claim.

        Used by the frontend "Ask about selection" workflow. We locate the
        selection in the parsed chunks, return a Claim whose evidence is the
        located span, and optionally pipe ``question`` into the agent later.
        """

        try:
            paper = storage.get_paper(paper_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Paper not found")

        chunks_file = storage.chunks_path(paper_id)
        parsed = load_chunks(chunks_file)
        if parsed is None and paper.pdf_path.is_file():
            parsed = parse_pdf(paper.pdf_path)
            if parsed.chunks:
                save_chunks(chunks_file, parsed)

        quote = (request.quote or "").strip()
        if not quote:
            raise HTTPException(status_code=400, detail="quote is required")

        evidence = Evidence(
            id=f"sel-{paper.id[:8]}",
            source=paper.pdf_path.name,
            page=request.page,
            section=request.section,
            quote=quote,
            location_status=EvidenceLocationStatus.QUOTE_ONLY,
        )
        if parsed is not None and parsed.chunks:
            EvidenceVerifier(parsed).annotate_evidence(evidence)

        return Claim(
            id="answer-selection",
            text=request.question.strip() if request.question else f"User selection: {quote[:200]}",
            reliability=ReliabilityLevel.R0,
            evidence=[evidence],
            uncertainty=None,
        )

    @app.post("/api/papers/{paper_id}/r1-search")
    def r1_search(paper_id: str):
        """Run the 6-lane R1 pipeline for ``paper_id`` and persist the result.

        The new R1 items overwrite the report's ``related_work`` so the
        Workspace immediately sees real candidates instead of the v0.1
        placeholder.
        """

        try:
            paper = storage.get_paper(paper_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Paper not found")

        metadata = paper.metadata or PaperMetadata(title=paper.title)
        # Reuse parsed PDF chunks for the backward lane fallback.
        chunks_file = storage.chunks_path(paper_id)
        parsed = load_chunks(chunks_file)
        if parsed is None and paper.pdf_path.is_file():
            try:
                parsed = parse_pdf(paper.pdf_path)
                if parsed.chunks:
                    save_chunks(chunks_file, parsed)
            except Exception:
                parsed = None
        parsed_refs = extract_references_from_parsed(parsed) if parsed is not None else []

        pipeline = pipeline_factory()
        try:
            result = pipeline.search(metadata, parsed_refs=parsed_refs)
        finally:
            for member in ("s2", "oa", "pwc"):
                client = getattr(pipeline, member, None)
                close = getattr(client, "close", None)
                if callable(close) and r1_pipeline is None:
                    close()

        payload = result.to_dict()
        storage.save_r1(paper_id, payload)

        # Patch the report in-memory and on disk.
        try:
            report = reports.get(paper_id) or storage.load_report(paper_id)
        except FileNotFoundError:
            report = None
        if report is not None:
            report.related_work = list(result.items)
            reports[paper_id] = report
            storage.save_report(report)
        return payload

    @app.get("/api/papers/{paper_id}/related")
    def get_related(paper_id: str):
        """Return the most recent R1 search payload (items + query trace)."""

        cached = storage.load_r1(paper_id)
        if cached is None:
            raise HTTPException(status_code=404, detail="No R1 result yet; run /r1-search first")
        return cached

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


    @app.post("/api/papers/{paper_id}/export-notion")
    def export_notion(paper_id: str):
        try:
            report = reports.get(paper_id) or storage.load_report(paper_id)
        except FileNotFoundError:
            report = None
        paper = next((candidate for candidate in storage.list_papers() if candidate.id == paper_id), None)
        if not report or not paper:
            raise HTTPException(status_code=404, detail="Paper or report not found")
        try:
            page_url = create_paper_notion_page(paper, report)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return NotionExportResponse(page_url=page_url)

    # ----------------------------------------------------------- Phase 4: Field Map

    def _build_field_map_for_paper(paper_id: str, *, run_r1_if_missing: bool = True) -> FieldMap:
        try:
            paper = storage.get_paper(paper_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Paper not found") from exc

        metadata = paper.metadata or PaperMetadata(title=paper.title)

        # Pull cached R1 result, regenerating it lazily if absent.
        r1_payload = storage.load_r1(paper_id)
        if r1_payload is None and run_r1_if_missing:
            chunks_file = storage.chunks_path(paper_id)
            parsed = load_chunks(chunks_file)
            if parsed is None and paper.pdf_path.is_file():
                try:
                    parsed = parse_pdf(paper.pdf_path)
                    if parsed.chunks:
                        save_chunks(chunks_file, parsed)
                except Exception:
                    parsed = None
            parsed_refs = extract_references_from_parsed(parsed) if parsed is not None else []
            pipeline = pipeline_factory()
            try:
                result = pipeline.search(metadata, parsed_refs=parsed_refs)
            finally:
                for member in ("s2", "oa", "pwc"):
                    client = getattr(pipeline, member, None)
                    close = getattr(client, "close", None)
                    if callable(close) and r1_pipeline is None:
                        close()
            r1_payload = result.to_dict()
            storage.save_r1(paper_id, r1_payload)
            search_result = result
        else:
            from app.models import RelatedWorkItem as _RWI
            from app.r1_search import R1QueryTraceEntry, R1SearchResult as _R1Result

            search_result = _R1Result(
                items=[_RWI.model_validate(item) for item in (r1_payload or {}).get("items", [])],
                query_trace=[
                    R1QueryTraceEntry(**entry) for entry in (r1_payload or {}).get("query_trace", [])
                ],
            )

        try:
            report = reports.get(paper_id) or storage.load_report(paper_id)
        except FileNotFoundError:
            report = None

        return build_field_map(
            seed_paper_id=paper_id,
            seed_metadata=metadata,
            search_result=search_result,
            report=report,
        )

    @app.post("/api/field-maps")
    def create_field_map(payload: Dict[str, str]):
        paper_id = payload.get("paper_id")
        if not paper_id:
            raise HTTPException(status_code=400, detail="paper_id is required")
        field_map = _build_field_map_for_paper(paper_id)
        storage.save_field_map(field_map.id, field_map.model_dump(mode="json"))
        return field_map

    @app.get("/api/field-maps/{field_map_id}")
    def get_field_map(field_map_id: str):
        cached = storage.load_field_map(field_map_id)
        if cached is None:
            raise HTTPException(status_code=404, detail="Field map not found")
        return cached

    @app.post("/api/field-maps/{field_map_id}/rerun")
    def rerun_field_map(field_map_id: str):
        cached = storage.load_field_map(field_map_id)
        if cached is None:
            raise HTTPException(status_code=404, detail="Field map not found")
        paper_id = cached.get("seed_paper_id")
        if not paper_id:
            raise HTTPException(status_code=400, detail="Field map is missing seed_paper_id")
        field_map = _build_field_map_for_paper(paper_id)
        # Reuse the original id so existing references / Obsidian links stay stable.
        field_map.id = field_map_id
        storage.save_field_map(field_map.id, field_map.model_dump(mode="json"))
        return field_map

    @app.get("/api/field-maps")
    def list_field_maps():
        return storage.list_field_maps()

    @app.post("/api/field-maps/{field_map_id}/export-obsidian")
    def export_field_map_obsidian(field_map_id: str):
        cached = storage.load_field_map(field_map_id)
        if cached is None:
            raise HTTPException(status_code=404, detail="Field map not found")
        try:
            field_map = FieldMap.model_validate(cached)
        except Exception as exc:  # pragma: no cover 鈥?bad cache shape is rare
            raise HTTPException(status_code=500, detail=f"Field map cache corrupted: {exc}")
        markdown = render_field_map_note(field_map)
        notes_dir = storage.note_dir
        notes_dir.mkdir(parents=True, exist_ok=True)
        note_name = f"field-map-{field_map.id}.md"
        path = notes_dir / note_name
        path.write_text(markdown, encoding="utf-8")
        return ExportResponse(note_path=str(path))


    @app.post("/api/field-maps/{field_map_id}/export-notion")
    def export_field_map_notion(field_map_id: str):
        cached = storage.load_field_map(field_map_id)
        if cached is None:
            raise HTTPException(status_code=404, detail="Field map not found")
        try:
            field_map = FieldMap.model_validate(cached)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Field map cache corrupted: {exc}")
        try:
            page_url = create_field_map_notion_page(field_map)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return NotionExportResponse(page_url=page_url)

    # ----------------------------------------------------------- Phase 5: Insights

    @app.post("/api/field-maps/{field_map_id}/insights")
    def field_map_insights(field_map_id: str):
        cached = storage.load_field_map(field_map_id)
        if cached is None:
            raise HTTPException(status_code=404, detail="Field map not found")
        try:
            field_map = FieldMap.model_validate(cached)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Field map cache corrupted: {exc}")
        try:
            report = reports.get(field_map.seed_paper_id) or storage.load_report(field_map.seed_paper_id)
        except FileNotFoundError:
            report = None
        return generate_insights(field_map, report=report)

    # ----------------------------------------------------------- Phase 5: Compare

    @app.post("/api/compare")
    def compare(payload: Dict[str, List[str]]):
        paper_ids = payload.get("paper_ids") or []
        if len(paper_ids) < 2:
            raise HTTPException(status_code=400, detail="Need at least two paper_ids to compare")
        papers = []
        report_map: Dict[str, ReadingReport] = {}
        for pid in paper_ids:
            try:
                paper = storage.get_paper(pid)
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail=f"Paper {pid} not found")
            papers.append(paper)
            try:
                report = reports.get(pid) or storage.load_report(pid)
                if report is not None:
                    report_map[pid] = report
            except FileNotFoundError:
                continue
        return compare_papers(papers, report_map)

    # ----------------------------------------------------------- Phase 5: Task queue

    @app.get("/api/tasks")
    def list_tasks():
        return [task.model_dump(mode="json") for task in task_queue.list()]

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: str):
        task = task_queue.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.model_dump(mode="json")

    @app.post("/api/tasks/{task_id}/cancel")
    def cancel_task(task_id: str):
        task = task_queue.cancel(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.model_dump(mode="json")

    @app.post("/api/tasks/{task_id}/retry")
    def retry_task(task_id: str):
        task = task_queue.retry(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.model_dump(mode="json")

    # Expose the queue so tests can submit fake work and inspect cancellation.
    app.state.task_queue = task_queue

    return app


app = create_app()


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



