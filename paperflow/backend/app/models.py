from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class ReliabilityLevel(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"


class EvidenceLocationStatus(str, Enum):
    """How precisely an :class:`Evidence` quote has been located in the source."""

    EXACT = "exact"  # quote + page + bbox confirmed by fuzzy match
    PAGE_AND_QUOTE = "page_and_quote"  # quote + page, no bbox
    QUOTE_ONLY = "quote_only"  # quote could not be located in any page
    MISSING = "missing"  # no quote at all


class Evidence(BaseModel):
    id: str
    source: str
    page: Optional[int] = None
    section: Optional[str] = None
    quote: str
    # Phase 1 fields (defaults keep V1.1 reports valid):
    bbox: Optional[List[float]] = None
    location_status: EvidenceLocationStatus = EvidenceLocationStatus.PAGE_AND_QUOTE


class Claim(BaseModel):
    id: str
    text: str
    reliability: ReliabilityLevel
    evidence: List[Evidence] = Field(default_factory=list)
    uncertainty: Optional[str] = None


class ReportSection(BaseModel):
    id: str
    title: str
    claims: List[Claim] = Field(default_factory=list)


class RelatedWorkItem(BaseModel):
    id: str
    title: str
    relation: str
    source: str
    reliability: ReliabilityLevel = ReliabilityLevel.R1
    evidence: List[Evidence] = Field(default_factory=list)
    # Phase 3 fields (optional so Phase 2 reports remain valid):
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    citation_count: Optional[int] = None
    influential_citation_count: Optional[int] = None
    comparison_risk: Optional[str] = None


class ReadingReport(BaseModel):
    paper_id: str
    paper_title: Optional[str] = None
    summary: List[Claim] = Field(default_factory=list)
    sections: List[ReportSection] = Field(default_factory=list)
    related_work: List[RelatedWorkItem] = Field(default_factory=list)


class TaskStatus(BaseModel):
    stage: str
    message: str = ""
    progress: float = 0.0


# ----------------------------------------------------------------------- Paper


class ImportSourceType(str, Enum):
    LOCAL_PDF = "local_pdf"
    ARXIV = "arxiv"
    DOI = "doi"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    OPENREVIEW = "openreview"
    ZOTERO = "zotero"


class PaperMetadata(BaseModel):
    """Structured paper metadata fetched from external sources during import."""

    title: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    openreview_id: Optional[str] = None
    source_type: ImportSourceType = ImportSourceType.LOCAL_PDF
    source_url: Optional[str] = None
    abstract: Optional[str] = None
    content_hash: Optional[str] = None  # sha256 of the PDF bytes


class Paper(BaseModel):
    id: str
    title: str
    pdf_path: Path
    note_path: Optional[Path] = None
    status: Optional[TaskStatus] = None
    metadata: Optional[PaperMetadata] = None


class PaperSession(BaseModel):
    id: str
    paper: Paper
    status: TaskStatus
    report: Optional[ReadingReport] = None
