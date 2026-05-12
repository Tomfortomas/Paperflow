from __future__ import annotations

import inspect
from typing import Callable, Optional

import fitz

from app.agent import PaperAgent, default_agent
from app.deepseek import report_read_timeout_seconds
from app.evidence_verifier import EvidenceVerifier
from app.models import PaperSession, ReadingReport
from app.pdf_parser import ParsedPdf, parse_pdf


class ReportService:
    """End-to-end pipeline: parse PDF, run agent, verify evidence locations."""

    def __init__(self, agent: PaperAgent = None) -> None:
        self.agent = agent if agent is not None else default_agent()
        self._last_parsed: Optional[ParsedPdf] = None

    def generate_report(
        self,
        session: PaperSession,
        on_progress: Optional[Callable[[str], None]] = None,
        on_partial_report: Optional[Callable[[ReadingReport], None]] = None,
    ) -> ReadingReport:
        parsed, text = self._read_paper(session)
        self._last_parsed = parsed
        if on_progress is not None:
            on_progress(f"PDF text extraction completed (input={_format_char_count(len(text))} chars)")
        client = getattr(self.agent, "client", None)
        if client is not None and on_progress is not None:
            model = getattr(client, "model", "unknown")
            on_progress(_deepseek_request_message(model=model, text=text))
            on_progress(_deepseek_wait_message(model=model, text=text))
        agent_params = inspect.signature(self.agent.generate_reading_report).parameters
        if "on_partial_report" in agent_params:
            kwargs = {"on_partial_report": on_partial_report}
        else:
            kwargs = {}
        if "on_progress" in agent_params:
            kwargs["on_progress"] = on_progress
        report = self.agent.generate_reading_report(
            paper_id=session.paper.id,
            source_name=session.paper.pdf_path.name,
            paper_text=text,
            **kwargs,
        )
        if on_progress is not None:
            on_progress("DeepSeek report received; locating evidence")
        if parsed is not None and parsed.chunks:
            EvidenceVerifier(parsed).annotate_report(report)
        if on_progress is not None:
            on_progress("Evidence locations resolved; saving report")
        return report

    def parsed_pdf(self) -> Optional[ParsedPdf]:
        """Return the :class:`ParsedPdf` produced during the last run, if any."""

        return self._last_parsed

    def _read_paper(self, session: PaperSession):
        path = session.paper.pdf_path
        if path.suffix.lower() == ".pdf":
            try:
                parsed = parse_pdf(path)
                if parsed.chunks:
                    text = _chunks_to_text(parsed)
                    if text.strip():
                        return parsed, text
            except Exception:
                pass
            try:
                document = fitz.open(path)
                try:
                    pages = [page.get_text("text").strip() for page in document]
                finally:
                    document.close()
                text = "\n".join(page for page in pages if page)
                if text.strip():
                    return None, text
            except Exception:
                pass

        try:
            return None, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return None, session.paper.title


def _chunks_to_text(parsed: ParsedPdf) -> str:
    return "\n".join(chunk.text for chunk in parsed.chunks)


def _deepseek_wait_message(*, model: str, text: str) -> str:
    timeout = report_read_timeout_seconds()
    return (
        "DeepSeek report generation is running "
        f"(model={model}, timeout={timeout:g}s, input={_deepseek_input_desc(text)} chars)"
    )


def _deepseek_request_message(*, model: str, text: str) -> str:
    timeout = report_read_timeout_seconds()
    return (
        "DeepSeek request prepared "
        f"(model={model}, timeout={timeout:g}s, input={_deepseek_input_desc(text)} chars)"
    )


def _deepseek_input_desc(text: str) -> str:
    total = _format_char_count(len(text))
    return f"{total}/{total}"


def _format_char_count(value: int) -> str:
    if value >= 1000:
        return f"{value / 1000:.1f}k"
    return str(value)

