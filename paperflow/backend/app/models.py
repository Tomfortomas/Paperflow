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


# ----------------------------------------------------------------------- Phase 4: Field Map


class MilestoneCategory(str, Enum):
    """The kind of contribution that earns a paper its milestone status."""

    PROBLEM_DEFINITION = "problem_definition"
    METHOD_PARADIGM = "method_paradigm"
    DATASET = "dataset"
    BENCHMARK = "benchmark"
    SYSTEM = "system"
    THEORY = "theory"
    SURVEY = "survey"
    UNKNOWN = "unknown"


class MilestonePaper(BaseModel):
    """One milestone paper produced by the milestone detector.

    The fields mirror PRD §4.6 — score, category, evidence and risk are all
    first-class so the UI can show ``why milestone`` next to it.
    """

    id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    citation_count: Optional[int] = None
    influential_citation_count: Optional[int] = None
    velocity: Optional[float] = None  # citations / years_since_publication
    milestone_score: float = 0.0
    why_milestone: str = ""
    category: MilestoneCategory = MilestoneCategory.UNKNOWN
    risk: Optional[str] = None
    evidence: List[Evidence] = Field(default_factory=list)
    user_confirmed: Optional[bool] = None  # True/False after human review


class TimelineEventType(str, Enum):
    MILESTONE = "milestone"
    FOLLOW_UP = "follow_up"
    BENCHMARK = "benchmark"
    SURVEY = "survey"
    DATASET = "dataset"
    SYSTEM = "system"
    OTHER = "other"


class TimelineEvent(BaseModel):
    """One ordered entry on the technology timeline (PRD §4.7)."""

    id: str
    year: Optional[int] = None
    paper_id: Optional[str] = None  # local paper.id if this is in the library
    title: str
    authors: List[str] = Field(default_factory=list)
    venue: Optional[str] = None
    event_type: TimelineEventType = TimelineEventType.OTHER
    problem: Optional[str] = None
    key_idea: Optional[str] = None
    pipeline: Optional[str] = None
    evaluation: Optional[str] = None
    influence: Optional[str] = None
    reliability: ReliabilityLevel = ReliabilityLevel.R1
    evidence: List[Evidence] = Field(default_factory=list)


class FieldMap(BaseModel):
    """Aggregated domain-level artifact (PRD §4.8).

    Fields mirror the PRD: factual sections are R1, trend / opportunity
    sections are R2 and the UI hides R2 by default.
    """

    id: str
    seed_paper_id: str
    seed_title: Optional[str] = None
    field_summary: Optional[str] = None
    task_taxonomy: List[str] = Field(default_factory=list)
    datasets_benchmarks: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    milestones: List[MilestonePaper] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    method_families: List[str] = Field(default_factory=list)
    evaluation_protocols: List[str] = Field(default_factory=list)
    open_problems: List[Claim] = Field(default_factory=list)
    recent_trends: List[Claim] = Field(default_factory=list)
    research_opportunities: List[Claim] = Field(default_factory=list)
    evidence_index: List[Evidence] = Field(default_factory=list)
    generated_at: Optional[float] = None
