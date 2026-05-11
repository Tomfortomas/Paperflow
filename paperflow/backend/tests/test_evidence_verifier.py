"""Tests for the PDF parser + evidence verifier (Phase 1)."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from app.evidence_verifier import EvidenceVerifier
from app.models import (
    Claim,
    Evidence,
    EvidenceLocationStatus,
    ReadingReport,
    ReliabilityLevel,
    ReportSection,
)
from app.pdf_parser import ParsedPdf, parse_pdf, save_chunks, load_chunks


# ---------------------------------------------------------------- fixtures


def _make_pdf(path: Path) -> Path:
    """Generate a small two-page PDF with section headers and a known quote."""

    doc = fitz.open()
    page1 = doc.new_page(width=612, height=792)
    page1.insert_text((72, 72), "Abstract", fontsize=14)
    page1.insert_text(
        (72, 110),
        "Paperflow is an evidence-first reading workbench that grades every "
        "claim as R0, R1, or R2 and traces it back into the source PDF.",
        fontsize=11,
    )
    page1.insert_text((72, 200), "1. Introduction", fontsize=14)
    page1.insert_text(
        (72, 230),
        "We introduce Paperflow, a local-first IDE for paper reading.",
        fontsize=11,
    )

    page2 = doc.new_page(width=612, height=792)
    page2.insert_text((72, 72), "3. Method", fontsize=14)
    page2.insert_text(
        (72, 110),
        "The method uses a DeepSeek-backed PaperAgent to extract a Reading "
        "Report with evidence quotes and page anchors.",
        fontsize=11,
    )
    page2.insert_text((72, 200), "5. Experiments", fontsize=14)
    page2.insert_text(
        (72, 230),
        "Experiments show that the EvidenceVerifier locates 92% of quotes.",
        fontsize=11,
    )
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    return _make_pdf(tmp_path / "sample.pdf")


# ---------------------------------------------------------------- parser


def test_parse_pdf_emits_chunks_with_bbox_and_section_guesses(sample_pdf: Path) -> None:
    parsed = parse_pdf(sample_pdf)
    assert len(parsed.chunks) >= 4
    assert len(parsed.page_sizes) == 2
    assert parsed.page_sizes[0] == [612.0, 792.0]

    abstract_chunks = [c for c in parsed.chunks if "Paperflow is an evidence-first" in c.text]
    assert abstract_chunks, "Abstract body chunk should be present"
    abstract = abstract_chunks[0]
    assert abstract.page == 1
    assert abstract.section_guess == "Abstract"
    assert abstract.bbox[2] > abstract.bbox[0] and abstract.bbox[3] > abstract.bbox[1]

    method_body = next(c for c in parsed.chunks if "PaperAgent" in c.text)
    assert method_body.section_guess == "Method"
    assert method_body.page == 2


def test_chunk_cache_round_trip(sample_pdf: Path, tmp_path: Path) -> None:
    parsed = parse_pdf(sample_pdf)
    chunks_file = tmp_path / "chunks.json"
    save_chunks(chunks_file, parsed)
    restored = load_chunks(chunks_file)

    assert restored is not None
    assert len(restored.chunks) == len(parsed.chunks)
    assert restored.chunks[0].section_guess == parsed.chunks[0].section_guess


# ---------------------------------------------------------------- verifier


def test_verifier_locates_exact_quote_with_bbox_and_section(sample_pdf: Path) -> None:
    parsed = parse_pdf(sample_pdf)
    verifier = EvidenceVerifier(parsed)

    located = verifier.locate("DeepSeek-backed PaperAgent to extract a Reading Report")
    assert located is not None
    assert located.page == 2
    assert located.section_guess == "Method"
    assert located.status in {
        EvidenceLocationStatus.EXACT,
        EvidenceLocationStatus.PAGE_AND_QUOTE,
    }
    x0, y0, x1, y1 = located.bbox
    assert x1 > x0 and y1 > y0


def test_verifier_returns_none_for_unrelated_quote(sample_pdf: Path) -> None:
    parsed = parse_pdf(sample_pdf)
    verifier = EvidenceVerifier(parsed)
    assert verifier.locate("This quote does not appear anywhere in the paper.") is None


def test_verifier_handles_quote_with_smart_quotes_and_dashes(sample_pdf: Path) -> None:
    parsed = parse_pdf(sample_pdf)
    verifier = EvidenceVerifier(parsed)
    quote = "\u201cPaperflow is an evidence\u2014first reading workbench\u201d"
    located = verifier.locate(quote)
    assert located is not None
    assert located.page == 1


def test_annotate_report_patches_each_evidence(sample_pdf: Path) -> None:
    parsed = parse_pdf(sample_pdf)
    verifier = EvidenceVerifier(parsed)

    good_evidence = Evidence(
        id="e1",
        source=sample_pdf.name,
        page=None,
        quote="92% of quotes",
    )
    missing_evidence = Evidence(
        id="e2",
        source=sample_pdf.name,
        quote="this string is nowhere in the paper",
    )
    empty_evidence = Evidence(id="e3", source=sample_pdf.name, quote="   ")

    report = ReadingReport(
        paper_id="p",
        summary=[
            Claim(
                id="c1",
                text="claim",
                reliability=ReliabilityLevel.R0,
                evidence=[good_evidence, missing_evidence, empty_evidence],
            )
        ],
        sections=[ReportSection(id="s", title="Method", claims=[])],
        related_work=[],
    )

    verifier.annotate_report(report)

    assert good_evidence.page == 2
    assert good_evidence.section == "Experiments"
    assert good_evidence.bbox is not None and len(good_evidence.bbox) == 4
    assert good_evidence.location_status in {
        EvidenceLocationStatus.EXACT,
        EvidenceLocationStatus.PAGE_AND_QUOTE,
    }
    assert missing_evidence.location_status is EvidenceLocationStatus.QUOTE_ONLY
    assert empty_evidence.location_status is EvidenceLocationStatus.MISSING
