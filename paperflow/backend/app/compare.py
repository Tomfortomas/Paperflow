"""Multi-paper comparison (PRD §4.9).

Given a list of papers (their :class:`ReadingReport` and metadata), pivot
the relevant R0 claims into a comparison table with one row per
dimension (Task, Dataset, Benchmark/Metric, Method, Compute, Key result,
Limitations, Availability).

A *cell* keeps:

* The paper id and title for traceability.
* The extracted value (or the first relevant claim's quote).
* The evidence list that backed the original claim — so the UI can
  jump back into the PDF.
* A ``comparison_risk`` note when the settings differ from siblings on
  the same row (different benchmark protocol, different scale, …).

The comparison agent is deliberately heuristic: it pivots existing
R0 claims rather than re-asking the LLM. This keeps the table cheap to
produce, evidence-grounded, and free of cross-paper hallucination.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.models import (
    Claim,
    ComparisonCell,
    ComparisonRow,
    ComparisonTable,
    Evidence,
    Paper,
    ReadingReport,
    ReliabilityLevel,
)


_DIMENSION_HINTS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Task", ("task",)),
    ("Dataset", ("dataset", "corpus", "training data")),
    ("Benchmark / metric", ("benchmark", "metric", "evaluation")),
    ("Method", ("method", "approach", "architecture", "model")),
    ("Input / Output", ("input", "output", "modality")),
    ("Compute / Training", ("compute", "training", "gpu", "tpu", "scale", "fine-tune")),
    ("Key result", ("result", "performance", "improve", "outperform", "achiev")),
    ("Strengths", ("strength", "advantage", "contribution")),
    ("Limitations", ("limitation", "drawback", "fail", "weakness")),
    ("Availability", ("code", "open source", "release", "model release", "checkpoint")),
)


def compare_papers(
    papers: Sequence[Paper],
    reports: Dict[str, ReadingReport],
    *,
    dimensions: Optional[Sequence[str]] = None,
    comparison_id: Optional[str] = None,
) -> ComparisonTable:
    """Build a :class:`ComparisonTable` over ``papers``.

    Args:
        papers: papers to compare; order is preserved as the column
            order of the resulting table.
        reports: ``{paper_id: ReadingReport}``. Papers without a report
            still get rows, but their cells will be marked as missing.
        dimensions: optional override of the dimension list. Defaults to
            all dimensions defined in :data:`_DIMENSION_HINTS`.
        comparison_id: optional explicit id.
    """

    requested = list(dimensions or [name for name, _ in _DIMENSION_HINTS])
    rows: List[ComparisonRow] = []
    for dim in requested:
        rows.append(_build_row(dim, papers, reports))

    notes = _comparison_notes(papers, rows)

    return ComparisonTable(
        id=comparison_id or f"cmp-{uuid.uuid4().hex[:12]}",
        paper_ids=[paper.id for paper in papers],
        dimensions=rows,
        notes=notes,
        generated_at=time.time(),
    )


# ---------------------------------------------------------------- internals


def _build_row(
    dim: str,
    papers: Sequence[Paper],
    reports: Dict[str, ReadingReport],
) -> ComparisonRow:
    cells: List[ComparisonCell] = []
    risk_signatures: List[Optional[str]] = []
    for paper in papers:
        report = reports.get(paper.id)
        value, evidence = _pick_value(dim, report)
        risk_sig = _risk_signature(dim, value)
        risk_signatures.append(risk_sig)
        cells.append(
            ComparisonCell(
                paper_id=paper.id,
                paper_title=paper.title,
                value=value,
                evidence=evidence,
            )
        )

    # Pairwise comparison risks: tag a cell when its setting clearly
    # differs from any sibling on the same row.
    base_risk = _baseline_risk_for_dim(dim)
    distinct = {sig for sig in risk_signatures if sig}
    if base_risk and len(distinct) > 1:
        for cell, sig in zip(cells, risk_signatures):
            if cell.value is None:
                continue
            cell.comparison_risk = base_risk

    return ComparisonRow(
        dimension=dim,
        description=_description_for_dim(dim),
        cells=cells,
    )


def _pick_value(dim: str, report: Optional[ReadingReport]) -> Tuple[Optional[str], List[Evidence]]:
    if report is None:
        return None, []
    hints = _hints_for_dim(dim)
    # Prefer claims from a section whose title matches the dimension's
    # hints, then fall back to scanning section titles + claim text.
    for section in report.sections:
        title = (section.title or "").lower()
        if any(hint in title for hint in hints):
            claim = _best_claim(section.claims)
            if claim:
                return claim.text, list(claim.evidence)
    # Fall back: scan all claims for any hint match.
    for section in report.sections:
        for claim in section.claims:
            if any(hint in claim.text.lower() for hint in hints):
                return claim.text, list(claim.evidence)
    for claim in report.summary:
        if any(hint in claim.text.lower() for hint in hints):
            return claim.text, list(claim.evidence)
    return None, []


def _best_claim(claims: Iterable[Claim]) -> Optional[Claim]:
    """Pick the most useful R0 claim — prefer ones with quoted evidence."""

    best: Optional[Claim] = None
    for claim in claims:
        if not best:
            best = claim
            continue
        if claim.evidence and not best.evidence:
            best = claim
    return best


def _hints_for_dim(dim: str) -> Tuple[str, ...]:
    for name, hints in _DIMENSION_HINTS:
        if name == dim:
            return hints
    return (dim.lower(),)


def _description_for_dim(dim: str) -> str:
    return {
        "Task": "What problem does each paper solve?",
        "Dataset": "Training / evaluation data.",
        "Benchmark / metric": "How are results measured?",
        "Method": "Core technical approach.",
        "Input / Output": "Modality of inputs and outputs.",
        "Compute / Training": "Reported compute and training set-up.",
        "Key result": "Headline reported numbers (do not directly rank across settings).",
        "Strengths": "Self-reported strengths.",
        "Limitations": "Self-reported limitations or open issues.",
        "Availability": "Code / data / model release status.",
    }.get(dim, "")


def _risk_signature(dim: str, value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    lowered = value.lower()
    if dim == "Benchmark / metric":
        match = re.search(r"\b(top-1|top-5|mAP|f1|bleu|rouge|iou|miou|success|reward)\b", lowered)
        if match:
            return match.group(1)
        return "unknown-protocol"
    if dim == "Dataset":
        match = re.search(r"\b(imagenet|coco|cifar|wikitext|squad|glue|metaworld|rlbench)\b", lowered)
        return match.group(1) if match else "unknown-dataset"
    if dim == "Compute / Training":
        match = re.search(r"(\d+)\s*(?:gpus?|tpus?|hours?|days?)", lowered)
        return match.group(0) if match else "unknown-compute"
    return value.strip()[:80]


def _baseline_risk_for_dim(dim: str) -> Optional[str]:
    if dim == "Benchmark / metric":
        return "different protocol / metric — direct ranking is unsafe"
    if dim == "Dataset":
        return "different dataset — accuracy is not directly comparable"
    if dim == "Compute / Training":
        return "different compute budget — efficiency claims must be normalised"
    if dim == "Key result":
        return "different setting — numbers above need a fair-comparison check"
    return None


def _comparison_notes(papers: Sequence[Paper], rows: Sequence[ComparisonRow]) -> List[Claim]:
    """Narrative R2 callouts surfaced above the table.

    The agent flags every row where at least one cell has a risk note —
    those rows are the ones reviewers will challenge first.
    """

    notes: List[Claim] = []
    for row in rows:
        risky_cells = [c for c in row.cells if c.comparison_risk]
        if not risky_cells:
            continue
        titles = ", ".join(c.paper_title or c.paper_id for c in risky_cells)
        notes.append(
            Claim(
                id=f"cmp-note-{row.dimension.lower().replace(' ', '-')}",
                text=(
                    f"Comparison risk on \"{row.dimension}\" — settings differ for: {titles}. "
                    f"{row.cells[0].comparison_risk or ''}"
                ).strip(),
                reliability=ReliabilityLevel.R2,
                uncertainty="Heuristic — please verify the underlying settings before ranking.",
            )
        )
    if not notes:
        notes.append(
            Claim(
                id="cmp-note-no-risk",
                text="No dimension flagged a comparison risk — values look pivot-safe.",
                reliability=ReliabilityLevel.R2,
                uncertainty="Heuristic — small samples can miss subtle setting differences.",
            )
        )
    return notes
