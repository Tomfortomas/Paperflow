from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import List, Optional

from app.metadata import dedup_key_from_metadata
from app.models import (
    ImportSourceType,
    Paper,
    PaperMetadata,
    PaperSession,
    ReadingReport,
    TaskStatus,
)


# Columns added in Phase 2. Stored as nullable so existing rows survive migration.
_METADATA_COLUMNS = [
    ("authors_json", "text"),
    ("year", "integer"),
    ("venue", "text"),
    ("arxiv_id", "text"),
    ("doi", "text"),
    ("semantic_scholar_id", "text"),
    ("openreview_id", "text"),
    ("content_hash", "text"),
    ("source_type", "text"),
    ("source_url", "text"),
    ("abstract", "text"),
]


class PaperStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.pdf_dir = root / "pdfs"
        self.note_dir = root / "notes"
        self.report_dir = root / "reports"
        self.chunk_dir = root / "chunks"  # Phase 1: cached PDF parse output
        self.db_path = root / "paperflow.sqlite3"
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.note_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def chunks_path(self, paper_id: str) -> Path:
        return self.chunk_dir / f"{paper_id}.json"

    def r1_path(self, paper_id: str) -> Path:
        directory = self.root / "r1"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{paper_id}.json"

    def save_r1(self, paper_id: str, payload: dict) -> Path:
        path = self.r1_path(paper_id)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_r1(self, paper_id: str) -> Optional[dict]:
        path = self.r1_path(paper_id)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return None

    # --------------------------------------------------------------- Field Map (Phase 4)

    def field_map_dir(self) -> Path:
        directory = self.root / "field_maps"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def field_map_path(self, field_map_id: str) -> Path:
        return self.field_map_dir() / f"{field_map_id}.json"

    def save_field_map(self, field_map_id: str, payload: dict) -> Path:
        path = self.field_map_path(field_map_id)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_field_map(self, field_map_id: str) -> Optional[dict]:
        path = self.field_map_path(field_map_id)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return None

    def list_field_maps(self) -> List[dict]:
        items: List[dict] = []
        for path in sorted(self.field_map_dir().glob("*.json")):
            try:
                items.append(json.loads(path.read_text(encoding="utf-8")))
            except ValueError:
                continue
        return items

    # --------------------------------------------------------------- create

    def create_paper_session(
        self,
        source_path: Path,
        title: Optional[str] = None,
        *,
        metadata: Optional[PaperMetadata] = None,
        replace_existing: bool = True,
    ) -> PaperSession:
        """Register a new paper from ``source_path`` and queue it for the agent.

        Phase 2: If ``metadata`` is given, persist authors/year/venue/etc. and
        de-dupe against existing rows using the strongest available identity
        (content_hash → DOI → arXiv ID → S2/OpenReview id → title+author+year).
        """

        content_hash = _sha256_of_file(source_path)
        if metadata is None:
            metadata = PaperMetadata(
                title=title or source_path.stem,
                source_type=ImportSourceType.LOCAL_PDF,
                content_hash=content_hash,
            )
        else:
            metadata = metadata.model_copy(
                update={"content_hash": metadata.content_hash or content_hash}
            )

        chosen_title = (metadata.title or title or source_path.stem).strip() or source_path.stem

        duplicates = self._delete_by_dedup(metadata, fallback_title=chosen_title) if replace_existing else []

        paper_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        target_path = self.pdf_dir / f"{_safe_filename(chosen_title)}.pdf"
        shutil.copy2(source_path, target_path)

        status = TaskStatus(stage="queued", message="Queued for Agent parsing", progress=0.05)
        paper = Paper(
            id=paper_id,
            title=chosen_title,
            pdf_path=target_path,
            status=status,
            metadata=metadata,
        )

        with self._connect() as conn:
            conn.execute(
                """
                insert into papers (
                    id, title, pdf_path, note_path,
                    authors_json, year, venue, arxiv_id, doi,
                    semantic_scholar_id, openreview_id, content_hash,
                    source_type, source_url, abstract
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper.id,
                    paper.title,
                    str(paper.pdf_path),
                    None,
                    json.dumps(metadata.authors or [], ensure_ascii=False),
                    metadata.year,
                    metadata.venue,
                    metadata.arxiv_id,
                    metadata.doi,
                    metadata.semantic_scholar_id,
                    metadata.openreview_id,
                    metadata.content_hash,
                    metadata.source_type.value if metadata.source_type else None,
                    metadata.source_url,
                    metadata.abstract,
                ),
            )
            conn.execute(
                "insert into sessions (id, paper_id, stage, message, progress) values (?, ?, ?, ?, ?)",
                (session_id, paper.id, status.stage, status.message, status.progress),
            )

        duplicate_of = duplicates[0][0] if duplicates else None
        duplicate_reason = duplicates[0][1] if duplicates else None
        return PaperSession(
            id=session_id,
            paper=paper,
            status=status,
            duplicate_of=duplicate_of,
            duplicate_warning=_duplicate_warning(duplicate_reason, duplicate_of),
        )

    # --------------------------------------------------------------- read

    def list_papers(self) -> List[Paper]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select
                    papers.*,
                    sessions.stage as session_stage,
                    sessions.message as session_message,
                    sessions.progress as session_progress
                from papers
                left join sessions on sessions.paper_id = papers.id
                order by papers.created_at desc
                """
            ).fetchall()
        return [self._row_to_paper(row) for row in rows]

    def get_paper(self, paper_id: str) -> Paper:
        paper = next((p for p in self.list_papers() if p.id == paper_id), None)
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

    def find_by_metadata(self, metadata: PaperMetadata) -> Optional[Paper]:
        """Look up an existing paper using the strongest available dedup key."""

        kind, key = dedup_key_from_metadata(metadata)
        return self._find_by_key(kind, key)

    def _find_by_key(self, kind: str, key: str) -> Optional[Paper]:
        if not key:
            return None
        with self._connect() as conn:
            if kind == "arxiv_id":
                candidates = conn.execute(
                    f"select papers.*, sessions.stage as session_stage, "
                    f"sessions.message as session_message, sessions.progress as session_progress "
                    f"from papers left join sessions on sessions.paper_id = papers.id "
                    f"where papers.arxiv_id is not null"
                ).fetchall()
                row = next(
                    (candidate for candidate in candidates if _canonical_arxiv_id(candidate["arxiv_id"]) == key),
                    None,
                )
            elif kind in {"content_hash", "doi", "semantic_scholar_id", "openreview_id"}:
                row = conn.execute(
                    f"select papers.*, sessions.stage as session_stage, "
                    f"sessions.message as session_message, sessions.progress as session_progress "
                    f"from papers left join sessions on sessions.paper_id = papers.id "
                    f"where papers.{kind} = ? limit 1",
                    (key,),
                ).fetchone()
            else:
                row = conn.execute(
                    "select papers.*, sessions.stage as session_stage, "
                    "sessions.message as session_message, sessions.progress as session_progress "
                    "from papers left join sessions on sessions.paper_id = papers.id "
                    "where papers.title = ? limit 1",
                    (key,),
                ).fetchone()
        return self._row_to_paper(row) if row is not None else None

    # --------------------------------------------------------------- write

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

    def update_paper_metadata(self, paper_id: str, metadata: PaperMetadata) -> None:
        """Patch the existing row with extra metadata (used after agent enrichment)."""

        with self._connect() as conn:
            conn.execute(
                """
                update papers
                set
                    authors_json = coalesce(?, authors_json),
                    year = coalesce(?, year),
                    venue = coalesce(?, venue),
                    arxiv_id = coalesce(?, arxiv_id),
                    doi = coalesce(?, doi),
                    semantic_scholar_id = coalesce(?, semantic_scholar_id),
                    openreview_id = coalesce(?, openreview_id),
                    content_hash = coalesce(?, content_hash),
                    source_type = coalesce(?, source_type),
                    source_url = coalesce(?, source_url),
                    abstract = coalesce(?, abstract),
                    title = coalesce(?, title)
                where id = ?
                """,
                (
                    json.dumps(metadata.authors, ensure_ascii=False) if metadata.authors else None,
                    metadata.year,
                    metadata.venue,
                    metadata.arxiv_id,
                    metadata.doi,
                    metadata.semantic_scholar_id,
                    metadata.openreview_id,
                    metadata.content_hash,
                    metadata.source_type.value if metadata.source_type else None,
                    metadata.source_url,
                    metadata.abstract,
                    (metadata.title or "").strip() or None,
                    paper_id,
                ),
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

    # --------------------------------------------------------------- delete

    def delete_papers_by_title(self, title: str, pdf_path: Optional[Path] = None) -> None:
        """Legacy V1.1 helper kept for backward compatibility."""

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
            self._delete_rows(conn, rows)

    def delete_paper(self, paper_id: str) -> bool:
        """Delete one library entry and all local artifacts owned by it."""

        with self._connect() as conn:
            rows = conn.execute(
                "select id, pdf_path, note_path from papers where id = ?",
                (paper_id,),
            ).fetchall()
            if not rows:
                return False
            self._delete_rows(conn, rows)
        return True

    def _delete_by_dedup(self, metadata: PaperMetadata, *, fallback_title: str) -> List[tuple[Paper, str]]:
        """Delete any existing rows that match the new paper's strongest dedup key."""

        matches: List[tuple[Paper, str]] = []
        with self._connect() as conn:
            rows = self._matching_duplicate_rows(conn, metadata, fallback_title=fallback_title)
            for row, reason in rows:
                matches.append((self._row_to_paper(row), reason))
            self._delete_rows(conn, [row for row, _ in rows])
        return matches

    def _matching_duplicate_rows(
        self,
        conn: sqlite3.Connection,
        metadata: PaperMetadata,
        *,
        fallback_title: str,
    ) -> List[tuple[sqlite3.Row, str]]:
        base_query = (
            "select papers.*, sessions.stage as session_stage, "
            "sessions.message as session_message, sessions.progress as session_progress "
            "from papers left join sessions on sessions.paper_id = papers.id "
        )
        rows: List[tuple[sqlite3.Row, str]] = []

        if metadata.arxiv_id:
            target = _canonical_arxiv_id(metadata.arxiv_id)
            candidates = conn.execute(f"{base_query} where papers.arxiv_id is not null").fetchall()
            rows = [
                (row, "arxiv_id")
                for row in candidates
                if _canonical_arxiv_id(row["arxiv_id"]) == target
            ]
            if rows:
                return rows

        for kind, value, reason in [
            ("doi", metadata.doi.lower() if metadata.doi else None, "doi"),
            ("semantic_scholar_id", metadata.semantic_scholar_id, "semantic_scholar_id"),
            ("openreview_id", metadata.openreview_id, "openreview_id"),
            ("content_hash", metadata.content_hash, "content_hash"),
        ]:
            if value:
                found = conn.execute(f"{base_query} where papers.{kind} = ?", (value,)).fetchall()
                if found:
                    return [(row, reason) for row in found]

        _kind, key = dedup_key_from_metadata(metadata)
        if key and fallback_title:
            found = conn.execute(
                f"{base_query} where papers.title = ?",
                (key if _kind == "title_author_year" else fallback_title,),
            ).fetchall()
            if found:
                return [(row, "title") for row in found]

        if fallback_title:
            found = conn.execute(
                f"{base_query} where papers.title = ?",
                (fallback_title,),
            ).fetchall()
            if found:
                return [(row, "title") for row in found]

        return rows

    def _delete_rows(self, conn: sqlite3.Connection, rows: List[sqlite3.Row]) -> None:
        for row in rows:
            conn.execute("delete from sessions where paper_id = ?", (row["id"],))
            conn.execute("delete from papers where id = ?", (row["id"],))
            report_path = self.report_dir / f"{row['id']}.json"
            self._unlink_if_exists(report_path)
            self._unlink_if_exists(self.chunks_path(row["id"]))
            self._unlink_if_exists(self.r1_path(row["id"]))
            self._delete_field_maps_for_seed(row["id"])
            self._unlink_if_exists(Path(row["pdf_path"]))
            if row["note_path"]:
                self._unlink_if_exists(Path(row["note_path"]))

    def _delete_field_maps_for_seed(self, paper_id: str) -> None:
        for path in self.field_map_dir().glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if payload.get("seed_paper_id") == paper_id:
                self._unlink_if_exists(path)

    def _unlink_if_exists(self, path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    # --------------------------------------------------------------- internals

    def _row_to_paper(self, row: sqlite3.Row) -> Paper:
        status = self._normalize_status(
            row["id"],
            row["session_stage"],
            row["session_message"],
            row["session_progress"],
        )
        metadata = self._row_to_metadata(row)
        return Paper(
            id=row["id"],
            title=row["title"],
            pdf_path=Path(row["pdf_path"]),
            note_path=Path(row["note_path"]) if row["note_path"] else None,
            status=status,
            metadata=metadata,
        )

    def _row_to_metadata(self, row: sqlite3.Row) -> Optional[PaperMetadata]:
        # Determine if any metadata is actually present beyond title.
        columns = row.keys()
        if "source_type" not in columns:
            return None

        authors_json = row["authors_json"]
        authors: List[str] = []
        if authors_json:
            try:
                authors = list(json.loads(authors_json))
            except (TypeError, ValueError):
                authors = []

        source_type_raw = row["source_type"]
        try:
            source_type = ImportSourceType(source_type_raw) if source_type_raw else ImportSourceType.LOCAL_PDF
        except ValueError:
            source_type = ImportSourceType.LOCAL_PDF

        return PaperMetadata(
            title=row["title"],
            authors=authors,
            year=row["year"],
            venue=row["venue"],
            arxiv_id=row["arxiv_id"],
            doi=row["doi"],
            semantic_scholar_id=row["semantic_scholar_id"],
            openreview_id=row["openreview_id"],
            content_hash=row["content_hash"],
            source_type=source_type,
            source_url=row["source_url"],
            abstract=row["abstract"],
        )

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

            existing = {row["name"] for row in conn.execute("pragma table_info(papers)").fetchall()}
            for column, ctype in _METADATA_COLUMNS:
                if column not in existing:
                    conn.execute(f"alter table papers add column {column} {ctype}")

            # Indexes that make dedup queries cheap.
            conn.execute("create index if not exists idx_papers_content_hash on papers(content_hash)")
            conn.execute("create index if not exists idx_papers_doi on papers(doi)")
            conn.execute("create index if not exists idx_papers_arxiv_id on papers(arxiv_id)")


# ----------------------------------------------------------------- helpers


def _safe_filename(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in " ._-" else "_" for char in value).strip()
    return safe or "paper"


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_arxiv_id(value: str) -> str:
    return re.sub(r"v\d+$", "", value.strip().lower())


def _duplicate_warning(reason: Optional[str], duplicate: Optional[Paper]) -> Optional[str]:
    if duplicate is None:
        return None
    reason_labels = {
        "arxiv_id": "同 arXiv 编号",
        "doi": "同 DOI",
        "semantic_scholar_id": "同 Semantic Scholar ID",
        "openreview_id": "同 OpenReview ID",
        "content_hash": "同 PDF 内容",
        "title": "相同标题",
    }
    label = reason_labels.get(reason or "", "疑似重复")
    return f"疑似重复：已替换{label}的旧条目「{duplicate.title}」。"
