"""Phase 1 helper-level tests for the TUI evidence renderer."""

from __future__ import annotations

from paperflow_tui.app import evidence_lines


def test_evidence_lines_includes_page_section_bbox_and_location() -> None:
    lines = evidence_lines(
        [
            {
                "id": "e1",
                "page": 2,
                "section": "Method",
                "source": "Paper.pdf",
                "quote": "Paperflow extracts evidence-aware reports.",
                "bbox": [72.0, 110.5, 540.4, 200.9],
                "location_status": "exact",
            }
        ]
    )

    assert lines, "evidence_lines should not be empty"
    header = lines[0]
    assert "p.2" in header
    assert "Method" in header
    assert "Paper.pdf" in header
    assert "bbox=(72,110)-(540,201)" in header
    assert "located precisely" in header
    assert lines[1].strip().startswith("\u201c")


def test_evidence_lines_falls_back_when_no_bbox_or_status() -> None:
    lines = evidence_lines(
        [
            {
                "page": 1,
                "section": "Abstract",
                "source": "Paper.pdf",
                "quote": "Hello",
            }
        ]
    )
    header = lines[0]
    assert "bbox=" not in header
    assert "located" not in header
    assert "p.1" in header
