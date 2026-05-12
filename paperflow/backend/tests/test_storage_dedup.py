"""Tests for Phase 2 dedup + metadata persistence in :mod:`app.storage`."""

from __future__ import annotations

from pathlib import Path

from app.models import ImportSourceType, PaperMetadata
from app.storage import PaperStorage


def _write_pdf(path: Path, content: bytes = b"%PDF-1.4\nFake PDF") -> Path:
    path.write_bytes(content)
    return path


def test_metadata_round_trip(tmp_path: Path) -> None:
    storage = PaperStorage(tmp_path / "data")
    pdf = _write_pdf(tmp_path / "first.pdf")
    metadata = PaperMetadata(
        title="My Paper",
        authors=["Alice Liu", "Bob Chen"],
        year=2024,
        venue="ICLR",
        arxiv_id="2401.12345",
        doi="10.1145/foo",
        source_type=ImportSourceType.ARXIV,
        source_url="https://arxiv.org/abs/2401.12345",
        abstract="An abstract.",
    )
    session = storage.create_paper_session(pdf, metadata=metadata)
    assert session.paper.metadata is not None
    assert session.paper.metadata.authors == ["Alice Liu", "Bob Chen"]
    assert session.paper.metadata.year == 2024

    listed = storage.list_papers()
    assert len(listed) == 1
    persisted = listed[0].metadata
    assert persisted is not None
    assert persisted.title == "My Paper"
    assert persisted.authors == ["Alice Liu", "Bob Chen"]
    assert persisted.year == 2024
    assert persisted.venue == "ICLR"
    assert persisted.doi == "10.1145/foo"
    assert persisted.arxiv_id == "2401.12345"
    assert persisted.source_type is ImportSourceType.ARXIV
    assert persisted.content_hash is not None


def test_storage_migrates_legacy_paperflow_data_paths(tmp_path: Path) -> None:
    root = tmp_path / "data"
    storage = PaperStorage(root)
    pdf = _write_pdf(root / "pdfs" / "legacy.pdf")
    note = (root / "notes" / "legacy.md")
    note.write_text("# Legacy", encoding="utf-8")
    with storage._connect() as conn:
        conn.execute(
            "insert into papers (id, title, pdf_path, note_path) values (?, ?, ?, ?)",
            (
                "legacy-paper",
                "Legacy Paper",
                "paperflow_data/pdfs/legacy.pdf",
                "paperflow_data/notes/legacy.md",
            ),
        )
        conn.execute(
            "insert into sessions (id, paper_id, stage, message, progress) values (?, ?, ?, ?, ?)",
            ("session-legacy", "legacy-paper", "completed", "Reading report generated", 1.0),
        )

    migrated = PaperStorage(root).get_paper("legacy-paper")

    assert migrated.pdf_path == pdf
    assert migrated.note_path == note


def test_dedup_by_doi_replaces_existing(tmp_path: Path) -> None:
    storage = PaperStorage(tmp_path / "data")
    pdf_a = _write_pdf(tmp_path / "a.pdf", b"%PDF-1.4\nA")
    pdf_b = _write_pdf(tmp_path / "b.pdf", b"%PDF-1.4\nB")  # different content_hash

    meta = PaperMetadata(
        title="Same Paper",
        doi="10.1/abc",
        source_type=ImportSourceType.DOI,
    )
    s1 = storage.create_paper_session(pdf_a, metadata=meta)
    s2 = storage.create_paper_session(pdf_b, metadata=meta)

    listed = storage.list_papers()
    assert len(listed) == 1
    assert listed[0].id == s2.paper.id
    assert listed[0].id != s1.paper.id


def test_dedup_by_content_hash_replaces_existing(tmp_path: Path) -> None:
    storage = PaperStorage(tmp_path / "data")
    pdf_a = _write_pdf(tmp_path / "v1.pdf", b"%PDF-1.4\nSAME-BYTES")
    pdf_b = _write_pdf(tmp_path / "v2.pdf", b"%PDF-1.4\nSAME-BYTES")

    meta_a = PaperMetadata(title="A", source_type=ImportSourceType.LOCAL_PDF)
    meta_b = PaperMetadata(title="B", source_type=ImportSourceType.LOCAL_PDF)
    storage.create_paper_session(pdf_a, metadata=meta_a)
    storage.create_paper_session(pdf_b, metadata=meta_b)

    listed = storage.list_papers()
    assert len(listed) == 1
    assert listed[0].title == "B"


def test_dedup_by_arxiv_id_strips_version(tmp_path: Path) -> None:
    storage = PaperStorage(tmp_path / "data")
    pdf_v1 = _write_pdf(tmp_path / "v1.pdf", b"%PDF-1.4\nA")
    pdf_v2 = _write_pdf(tmp_path / "v2.pdf", b"%PDF-1.4\nB")

    meta_v1 = PaperMetadata(
        title="A", arxiv_id="2401.12345v1", source_type=ImportSourceType.ARXIV
    )
    meta_v2 = PaperMetadata(
        title="A", arxiv_id="2401.12345v2", source_type=ImportSourceType.ARXIV
    )
    storage.create_paper_session(pdf_v1, metadata=meta_v1)
    storage.create_paper_session(pdf_v2, metadata=meta_v2)

    listed = storage.list_papers()
    assert len(listed) == 1
    assert listed[0].metadata is not None
    assert listed[0].metadata.arxiv_id == "2401.12345v2"


def test_find_by_metadata_returns_existing_row(tmp_path: Path) -> None:
    storage = PaperStorage(tmp_path / "data")
    pdf = _write_pdf(tmp_path / "p.pdf")
    meta = PaperMetadata(
        title="P",
        doi="10.2/xyz",
        source_type=ImportSourceType.DOI,
    )
    session = storage.create_paper_session(pdf, metadata=meta)

    found = storage.find_by_metadata(meta)
    assert found is not None
    assert found.id == session.paper.id
    assert found.metadata is not None
    assert found.metadata.doi == "10.2/xyz"


def test_update_paper_metadata_patches_only_missing_fields(tmp_path: Path) -> None:
    storage = PaperStorage(tmp_path / "data")
    pdf = _write_pdf(tmp_path / "p.pdf")
    base = PaperMetadata(title="Bare", source_type=ImportSourceType.LOCAL_PDF)
    session = storage.create_paper_session(pdf, metadata=base)

    enrichment = PaperMetadata(
        authors=["Carol"],
        year=2025,
        venue="ICML",
        source_type=ImportSourceType.LOCAL_PDF,  # should not overwrite
    )
    storage.update_paper_metadata(session.paper.id, enrichment)

    paper = storage.get_paper(session.paper.id)
    assert paper.metadata is not None
    assert paper.metadata.title == "Bare"  # unchanged
    assert paper.metadata.authors == ["Carol"]
    assert paper.metadata.year == 2025
    assert paper.metadata.venue == "ICML"
