from __future__ import annotations

import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import List

from app.models import Paper, PaperSession, ReadingReport, TaskStatus


class PaperStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.pdf_dir = root / "pdfs"
        self.note_dir = root / "notes"
        self.report_dir = root / "reports"
        self.db_path = root / "paperflow.sqlite3"
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.note_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def create_paper_session(self, source_path: Path, title: str = None) -> PaperSession:
        paper_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        title = title or source_path.stem
        target_path = self.pdf_dir / f"{title}.pdf"
        self.delete_papers_by_title(title, pdf_path=target_path)
        shutil.copy2(source_path, target_path)

        status = TaskStatus(stage="queued", message="Queued for Agent parsing", progress=0.05)
        paper = Paper(id=paper_id, title=title, pdf_path=target_path, status=status)

        with self._connect() as conn:
            conn.execute(
                "insert into papers (id, title, pdf_path, note_path) values (?, ?, ?, ?)",
                (paper.id, paper.title, str(paper.pdf_path), None),
            )
            conn.execute(
                "insert into sessions (id, paper_id, stage, message, progress) values (?, ?, ?, ?, ?)",
                (session_id, paper.id, status.stage, status.message, status.progress),
            )

        return PaperSession(id=session_id, paper=paper, status=status)

    def list_papers(self) -> List[Paper]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select
                    papers.id,
                    papers.title,
                    papers.pdf_path,
                    papers.note_path,
                    sessions.stage,
                    sessions.message,
                    sessions.progress
                from papers
                left join sessions on sessions.paper_id = papers.id
                order by papers.created_at desc
                """
            ).fetchall()

        return [
            Paper(
                id=row["id"],
                title=row["title"],
                pdf_path=Path(row["pdf_path"]),
                note_path=Path(row["note_path"]) if row["note_path"] else None,
                status=self._normalize_status(row["id"], row["stage"], row["message"], row["progress"]),
            )
            for row in rows
        ]

    def get_paper(self, paper_id: str) -> Paper:
        paper = next((candidate for candidate in self.list_papers() if candidate.id == paper_id), None)
        if paper is None:
            raise FileNotFoundError(paper_id)
        return paper

    def get_status(self, paper_id: str) -> TaskStatus:
        with self._connect() as conn:
            row = conn.execute(
                "select stage, message, progress from sessions where paper_id = ?",
                (paper_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(paper_id)
        return self._normalize_status(paper_id, row["stage"], row["message"], row["progress"])

    def update_status(self, paper_id: str, status: TaskStatus) -> None:
        with self._connect() as conn:
            conn.execute(
                "update sessions set stage = ?, message = ?, progress = ? where paper_id = ?",
                (status.stage, status.message, status.progress, paper_id),
            )

    def update_paper_title(self, paper_id: str, title: str) -> None:
        clean_title = title.strip()
        if not clean_title:
            return
        with self._connect() as conn:
            conn.execute(
                "update papers set title = ? where id = ?",
                (clean_title, paper_id),
            )

    def save_note(self, paper_id: str, markdown: str) -> Path:
        paper = next(paper for paper in self.list_papers() if paper.id == paper_id)
        note_path = self.note_dir / f"{_safe_filename(paper.title)}.md"
        note_path.write_text(markdown, encoding="utf-8")
        with self._connect() as conn:
            conn.execute(
                "update papers set note_path = ? where id = ?",
                (str(note_path), paper_id),
            )
        return note_path

    def save_report(self, report: ReadingReport) -> Path:
        report_path = self.report_dir / f"{report.paper_id}.json"
        report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return report_path

    def load_report(self, paper_id: str) -> ReadingReport:
        report_path = self.report_dir / f"{paper_id}.json"
        if not report_path.exists():
            raise FileNotFoundError(paper_id)
        return ReadingReport.model_validate_json(report_path.read_text(encoding="utf-8"))

    def delete_papers_by_title(self, title: str, pdf_path: Path = None) -> None:
        with self._connect() as conn:
            if pdf_path is None:
                rows = conn.execute(
                    "select id, pdf_path, note_path from papers where title = ?",
                    (title,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "select id, pdf_path, note_path from papers where title = ? or pdf_path = ?",
                    (title, str(pdf_path)),
                ).fetchall()
            for row in rows:
                conn.execute("delete from sessions where paper_id = ?", (row["id"],))
                conn.execute("delete from papers where id = ?", (row["id"],))
                report_path = self.report_dir / f"{row['id']}.json"
                self._unlink_if_exists(report_path)
                self._unlink_if_exists(Path(row["pdf_path"]))
                if row["note_path"]:
                    self._unlink_if_exists(Path(row["note_path"]))

    def _unlink_if_exists(self, path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def _normalize_status(self, paper_id: str, stage: str, message: str, progress: float) -> TaskStatus:
        if stage == "created" and (self.report_dir / f"{paper_id}.json").exists():
            return TaskStatus(stage="completed", message="Reading report generated", progress=1.0)
        return TaskStatus(stage=stage or "unknown", message=message or "", progress=progress or 0.0)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists papers (
                    id text primary key,
                    title text not null,
                    pdf_path text not null,
                    note_path text,
                    created_at datetime default current_timestamp
                )
                """
            )
            conn.execute(
                """
                create table if not exists sessions (
                    id text primary key,
                    paper_id text not null,
                    stage text not null,
                    message text not null,
                    progress real not null,
                    created_at datetime default current_timestamp,
                    foreign key (paper_id) references papers(id)
                )
                """
            )


def _safe_filename(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in " ._-" else "_" for char in value).strip()
    return safe or "paper"
