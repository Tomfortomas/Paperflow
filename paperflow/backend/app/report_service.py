from __future__ import annotations

import fitz

from app.agent import PaperAgent, default_agent
from app.models import PaperSession, ReadingReport


class ReportService:
    def __init__(self, agent: PaperAgent = None) -> None:
        self.agent = agent if agent is not None else default_agent()

    def generate_report(self, session: PaperSession) -> ReadingReport:
        text = self._read_paper_text(session)
        return self.agent.generate_reading_report(
            paper_id=session.paper.id,
            source_name=session.paper.pdf_path.name,
            paper_text=text,
        )

    def _read_paper_text(self, session: PaperSession) -> str:
        if session.paper.pdf_path.suffix.lower() == ".pdf":
            try:
                document = fitz.open(session.paper.pdf_path)
                try:
                    pages = [page.get_text("text").strip() for page in document]
                finally:
                    document.close()
                text = "\n".join(page for page in pages if page)
                if text.strip():
                    return text
            except Exception:
                pass

        try:
            return session.paper.pdf_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return session.paper.title

