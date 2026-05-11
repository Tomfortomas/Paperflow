from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class ReliabilityLevel(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"


class Evidence(BaseModel):
    id: str
    source: str
    page: Optional[int] = None
    section: Optional[str] = None
    quote: str


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


class Paper(BaseModel):
    id: str
    title: str
    pdf_path: Path
    note_path: Optional[Path] = None
    status: Optional[TaskStatus] = None


class PaperSession(BaseModel):
    id: str
    paper: Paper
    status: TaskStatus
    report: Optional[ReadingReport] = None
