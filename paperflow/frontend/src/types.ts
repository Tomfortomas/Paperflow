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
  agent_run?: AgentRunMetrics | null;
}

export interface AgentRunMetrics {
  model?: string | null;
  elapsed_seconds?: number | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  covered_chars?: number | null;
  total_chars?: number | null;
  coverage_percent?: number | null;
  chunks_processed?: number | null;
}

export interface PaperChatRequest {
  question: string;
  selected_claim_id?: string | null;
  selected_evidence_id?: string | null;
  page?: number | null;
  quote?: string | null;
  section?: string | null;
}

export interface PaperChatStep {
  id: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  detail?: string | null;
}

export interface PaperChatMessage {
  id: string;
  role: "user" | "assistant" | string;
  content: string;
  reliability?: ReliabilityLevel | null;
  evidence?: Evidence[];
  uncertainty?: string | null;
}

export interface PaperChatResponse {
  id: string;
  paper_id: string;
  status: "idle" | "running" | "completed" | "failed" | string;
  task_id?: string | null;
  used_context?: string[];
  steps: PaperChatStep[];
  messages: PaperChatMessage[];
  answer: Claim;
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
  duplicate_of?: Paper | null;
  duplicate_warning?: string | null;
}

export interface AgentStatus {
  configured: boolean;
  mode: string;
  has_api_key?: boolean;
  model?: string | null;
}

export interface AgentConfig extends AgentStatus {
  model_options: string[];
  report_read_timeout: number;
}

export interface AgentConfigUpdate {
  api_key?: string | null;
  model?: string | null;
  report_read_timeout?: number | null;
}

// Phase 4 — Field Map.

export type MilestoneCategory =
  | "problem_definition"
  | "method_paradigm"
  | "dataset"
  | "benchmark"
  | "system"
  | "theory"
  | "survey"
  | "unknown";

export interface MilestonePaper {
  id: string;
  title: string;
  authors: string[];
  year?: number | null;
  venue?: string | null;
  url?: string | null;
  doi?: string | null;
  arxiv_id?: string | null;
  semantic_scholar_id?: string | null;
  citation_count?: number | null;
  influential_citation_count?: number | null;
  velocity?: number | null;
  milestone_score: number;
  why_milestone: string;
  category: MilestoneCategory;
  risk?: string | null;
  evidence: Evidence[];
  user_confirmed?: boolean | null;
}

export type TimelineEventType =
  | "milestone"
  | "follow_up"
  | "benchmark"
  | "survey"
  | "dataset"
  | "system"
  | "other";

export interface TimelineEvent {
  id: string;
  year?: number | null;
  paper_id?: string | null;
  title: string;
  authors: string[];
  venue?: string | null;
  event_type: TimelineEventType;
  problem?: string | null;
  key_idea?: string | null;
  pipeline?: string | null;
  evaluation?: string | null;
  influence?: string | null;
  reliability: ReliabilityLevel;
  evidence: Evidence[];
}

export type FieldMapGraphNodeRole = "predecessor" | "seed" | "successor" | string;

export interface FieldMapGraphNode {
  id: string;
  title: string;
  role: FieldMapGraphNodeRole;
  year?: number | null;
  event_type: TimelineEventType;
  reliability?: ReliabilityLevel;
}

export interface FieldMapGraphEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  source_type?: "rule" | "agent_suggested" | "user" | string;
  rationale?: string | null;
  evidence?: Evidence[];
  confidence?: number | null;
  user_confirmed?: boolean | null;
}

export interface FieldMapRelationshipGraph {
  nodes: FieldMapGraphNode[];
  edges: FieldMapGraphEdge[];
}

export interface ComparisonCell {
  paper_id: string;
  paper_title?: string | null;
  value?: string | null;
  evidence: Evidence[];
  comparison_risk?: string | null;
}

export interface ComparisonRow {
  dimension: string;
  description?: string | null;
  cells: ComparisonCell[];
}

export interface ComparisonTable {
  id: string;
  paper_ids: string[];
  dimensions: ComparisonRow[];
  notes: Claim[];
  generated_at?: number | null;
}

export interface ResearchInsight {
  id: string;
  kind: "trend" | "opportunity" | "method_angle" | "story" | "writing" | string;
  text: string;
  rationale?: string | null;
  evidence: Evidence[];
  reliability: ReliabilityLevel;
}

export interface ResearchInsightReport {
  id: string;
  field_map_id?: string | null;
  seed_paper_id?: string | null;
  insights: ResearchInsight[];
  generated_at?: number | null;
}

export type AgentTaskStage =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | string;

export interface AgentTask {
  id: string;
  kind: string;
  paper_id?: string | null;
  stage: AgentTaskStage;
  message: string;
  progress: number;
  error?: string | null;
  started_at?: number | null;
  finished_at?: number | null;
  result_path?: string | null;
  retries: number;
}

export interface FieldMap {
  id: string;
  seed_paper_id: string;
  seed_title?: string | null;
  field_summary?: string | null;
  task_taxonomy: string[];
  datasets_benchmarks: string[];
  metrics: string[];
  milestones: MilestonePaper[];
  timeline: TimelineEvent[];
  method_families: string[];
  evaluation_protocols: string[];
  open_problems: Claim[];
  recent_trends: Claim[];
  research_opportunities: Claim[];
  evidence_index: Evidence[];
  relationship_graph?: FieldMapRelationshipGraph;
  generated_at?: number | null;
}
