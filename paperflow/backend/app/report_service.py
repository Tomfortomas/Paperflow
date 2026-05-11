from __future__ import annotations

from typing import Optional

import fitz

from app.agent import PaperAgent, default_agent
from app.evidence_verifier import EvidenceVerifier
from app.models import PaperSession, ReadingReport
from app.pdf_parser import ParsedPdf, parse_pdf


class ReportService:
    """End-to-end pipeline: parse PDF, run agent, verify evidence locations."""

    def __init__(self, agent: PaperAgent = None) -> None:
        self.agent = agent if agent is not None else default_agent()
        self._last_parsed: Optional[ParsedPdf] = None

    def generate_report(self, session: PaperSession) -> ReadingReport:
        parsed, text = self._read_paper(session)
        self._last_parsed = parsed
        report = self.agent.generate_reading_report(
            paper_id=session.paper.id,
            source_name=session.paper.pdf_path.name,
            paper_text=text,
        )
        if parsed is not None and parsed.chunks:
            EvidenceVerifier(parsed).annotate_report(report)
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

