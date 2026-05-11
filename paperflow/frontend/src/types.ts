export type ReliabilityLevel = "R0" | "R1" | "R2";

export type EvidenceLocationStatus =
  | "exact"
  | "page_and_quote"
  | "quote_only"
  | "missing";

export interface Evidence {
  id: string;
  source: string;
  page?: number;
  section?: string;
  quote: string;
  bbox?: [number, number, number, number] | null;
  location_status?: EvidenceLocationStatus;
}

export interface Claim {
  id: string;
  text: string;
  reliability: ReliabilityLevel;
  evidence: Evidence[];
  uncertainty?: string;
}

export interface ReportSection {
  id: string;
  title: string;
  claims: Claim[];
}

export interface RelatedWorkItem {
  id: string;
  title: string;
  relation: string;
  source: string;
  reliability: ReliabilityLevel;
  evidence: Evidence[];
  authors?: string[];
  year?: number | null;
  venue?: string | null;
  url?: string | null;
  doi?: string | null;
  arxiv_id?: string | null;
  semantic_scholar_id?: string | null;
  citation_count?: number | null;
  influential_citation_count?: number | null;
  comparison_risk?: string | null;
}

export interface R1QueryTraceEntry {
  lane: string;
  source: string;
  query: string;
  count: number;
}

export interface R1SearchResult {
  items: RelatedWorkItem[];
  query_trace: R1QueryTraceEntry[];
  seed_resolved_at?: number | null;
}

export interface ReadingReport {
  paper_id: string;
  paper_title?: string;
  summary: Claim[];
  sections: ReportSection[];
  related_work: RelatedWorkItem[];
}

export interface TaskStatus {
  stage: "queued" | "processing" | "completed" | "failed" | string;
  message: string;
  progress: number;
}

export type ImportSourceType =
  | "local_pdf"
  | "arxiv"
  | "doi"
  | "semantic_scholar"
  | "openreview"
  | "zotero";

export interface PaperMetadata {
  title?: string | null;
  authors?: string[];
  year?: number | null;
  venue?: string | null;
  arxiv_id?: string | null;
  doi?: string | null;
  semantic_scholar_id?: string | null;
  openreview_id?: string | null;
  source_type?: ImportSourceType;
  source_url?: string | null;
  abstract?: string | null;
  content_hash?: string | null;
}

export interface Paper {
  id: string;
  title: string;
  pdf_path: string;
  note_path?: string;
  status?: TaskStatus;
  metadata?: PaperMetadata | null;
}

export interface ZoteroPreviewItem {
  item_key: string;
  title?: string | null;
  authors: string[];
  year?: number | null;
  venue?: string | null;
  doi?: string | null;
  arxiv_id?: string | null;
  has_pdf: boolean;
}

export interface ZoteroImportResult {
  imported: number;
  sessions: PaperSession[];
}

export interface PdfChunk {
  page: number;
  bbox: [number, number, number, number];
  text: string;
  section_guess?: string | null;
}

export interface ParsedPdfPayload {
  chunks: PdfChunk[];
  page_sizes: number[][];
}

export interface PaperSession {
  id: string;
  paper: Paper;
  status: TaskStatus;
  report?: ReadingReport | null;
}

export interface AgentStatus {
  configured: boolean;
  mode: string;
  model?: string | null;
}
