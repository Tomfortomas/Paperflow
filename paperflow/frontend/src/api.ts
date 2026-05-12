import type {
  AgentConfig,
  AgentConfigUpdate,
  AgentStatus,
  AgentTask,
  Claim,
  ComparisonTable,
  FieldMap,
  Paper,
  PaperChatRequest,
  PaperChatResponse,
  ParsedPdfPayload,
  PaperSession,
  R1SearchResult,
  ReadingReport,
  ResearchInsightReport,
  TaskStatus,
  ZoteroImportResult,
  ZoteroPreviewItem,
} from "./types";

export interface AskSelectionPayload {
  quote: string;
  page?: number | null;
  section?: string | null;
  question?: string | null;
}

export interface PaperflowClient {
  listPapers(): Promise<Paper[]>;
  importPaper(file: File): Promise<PaperSession>;
  importArxiv(url: string): Promise<PaperSession>;
  importUrl(url: string): Promise<PaperSession>;
  importZotero(itemKey?: string): Promise<ZoteroImportResult>;
  previewZotero(): Promise<ZoteroPreviewItem[]>;
  deletePaper(paperId: string): Promise<void>;
  getStatus(paperId: string): Promise<TaskStatus>;
  getReport(paperId: string): Promise<ReadingReport>;
  askPaper(paperId: string, question: string): Promise<Claim>;
  askSelection(paperId: string, payload: AskSelectionPayload): Promise<Claim>;
  chatPaper(paperId: string, payload: PaperChatRequest): Promise<PaperChatResponse>;
  getChunks(paperId: string): Promise<ParsedPdfPayload>;
  pdfUrl(paperId: string): string;
  runR1Search(paperId: string): Promise<R1SearchResult>;
  getRelated(paperId: string): Promise<R1SearchResult>;
  createFieldMap(paperId: string): Promise<FieldMap>;
  getFieldMap(fieldMapId: string): Promise<FieldMap>;
  listFieldMaps(): Promise<FieldMap[]>;
  rerunFieldMap(fieldMapId: string): Promise<FieldMap>;
  comparePapers(paperIds: string[]): Promise<ComparisonTable>;
  generateInsights(fieldMapId: string): Promise<ResearchInsightReport>;
  exportFieldMapObsidian(fieldMapId: string): Promise<{ note_path: string }>;
  listTasks(): Promise<AgentTask[]>;
  getTask(taskId: string): Promise<AgentTask>;
  cancelTask(taskId: string): Promise<AgentTask>;
  retryTask(taskId: string): Promise<AgentTask>;
  exportObsidian(paperId: string): Promise<{ note_path: string }>;
  rerunAgent(paperId: string): Promise<PaperSession>;
  getAgentStatus(): Promise<AgentStatus>;
  getAgentConfig(): Promise<AgentConfig>;
  updateAgentConfig(payload: AgentConfigUpdate): Promise<AgentConfig>;
}

const defaultBaseUrl =
  import.meta.env.VITE_PAPERFLOW_API_BASE_URL || "http://127.0.0.1:8000";

export function createPaperflowClient(baseUrl = defaultBaseUrl): PaperflowClient {
  return {
    async listPapers() {
      return request<Paper[]>(`${baseUrl}/api/papers`);
    },
    async importPaper(file: File) {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${baseUrl}/api/papers/import`, {
        method: "POST",
        body: form,
      });
      if (!response.ok) {
        throw new Error(`Import failed: ${response.status}`);
      }
      return response.json();
    },
    async importArxiv(url: string) {
      return request<PaperSession>(`${baseUrl}/api/papers/import-arxiv`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
    },
    async importUrl(url: string) {
      return request<PaperSession>(`${baseUrl}/api/papers/import-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
    },
    async importZotero(itemKey?: string) {
      return request<ZoteroImportResult>(`${baseUrl}/api/papers/import-zotero`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_key: itemKey ?? null }),
      });
    },
    async previewZotero() {
      return request<ZoteroPreviewItem[]>(`${baseUrl}/api/zotero/preview`);
    },
    async deletePaper(paperId: string) {
      await request<void>(`${baseUrl}/api/papers/${paperId}`, { method: "DELETE" });
    },
    async getReport(paperId: string) {
      return request<ReadingReport>(`${baseUrl}/api/papers/${paperId}/report`);
    },
    async getStatus(paperId: string) {
      return request<TaskStatus>(`${baseUrl}/api/papers/${paperId}/status`);
    },
    async askPaper(paperId: string, question: string) {
      return request<Claim>(`${baseUrl}/api/papers/${paperId}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
    },
    async askSelection(paperId: string, payload: AskSelectionPayload) {
      return request<Claim>(`${baseUrl}/api/papers/${paperId}/ask-selection`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    async chatPaper(paperId: string, payload: PaperChatRequest) {
      return request<PaperChatResponse>(`${baseUrl}/api/papers/${paperId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    async getChunks(paperId: string) {
      return request<ParsedPdfPayload>(`${baseUrl}/api/papers/${paperId}/chunks`);
    },
    pdfUrl(paperId: string) {
      return `${baseUrl}/api/papers/${paperId}/pdf`;
    },
    async runR1Search(paperId: string) {
      return request<R1SearchResult>(`${baseUrl}/api/papers/${paperId}/r1-search`, {
        method: "POST",
      });
    },
    async getRelated(paperId: string) {
      return request<R1SearchResult>(`${baseUrl}/api/papers/${paperId}/related`);
    },
    async createFieldMap(paperId: string) {
      return request<FieldMap>(`${baseUrl}/api/field-maps`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_id: paperId }),
      });
    },
    async getFieldMap(fieldMapId: string) {
      return request<FieldMap>(`${baseUrl}/api/field-maps/${fieldMapId}`);
    },
    async listFieldMaps() {
      return request<FieldMap[]>(`${baseUrl}/api/field-maps`);
    },
    async rerunFieldMap(fieldMapId: string) {
      return request<FieldMap>(`${baseUrl}/api/field-maps/${fieldMapId}/rerun`, {
        method: "POST",
      });
    },
    async comparePapers(paperIds: string[]) {
      return request<ComparisonTable>(`${baseUrl}/api/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: paperIds }),
      });
    },
    async generateInsights(fieldMapId: string) {
      return request<ResearchInsightReport>(
        `${baseUrl}/api/field-maps/${fieldMapId}/insights`,
        { method: "POST" },
      );
    },
    async exportFieldMapObsidian(fieldMapId: string) {
      return request<{ note_path: string }>(
        `${baseUrl}/api/field-maps/${fieldMapId}/export-obsidian`,
        { method: "POST" },
      );
    },
    async listTasks() {
      return request<AgentTask[]>(`${baseUrl}/api/tasks`);
    },
    async getTask(taskId: string) {
      return request<AgentTask>(`${baseUrl}/api/tasks/${taskId}`);
    },
    async cancelTask(taskId: string) {
      return request<AgentTask>(`${baseUrl}/api/tasks/${taskId}/cancel`, { method: "POST" });
    },
    async retryTask(taskId: string) {
      return request<AgentTask>(`${baseUrl}/api/tasks/${taskId}/retry`, { method: "POST" });
    },
    async exportObsidian(paperId: string) {
      return request<{ note_path: string }>(`${baseUrl}/api/papers/${paperId}/export-obsidian`, {
        method: "POST",
      });
    },
    async rerunAgent(paperId: string) {
      return request<PaperSession>(`${baseUrl}/api/papers/${paperId}/rerun`, {
        method: "POST",
      });
    },
    async getAgentStatus() {
      return request<AgentStatus>(`${baseUrl}/api/agent/status`);
    },
    async getAgentConfig() {
      return request<AgentConfig>(`${baseUrl}/api/agent/config`);
    },
    async updateAgentConfig(payload: AgentConfigUpdate) {
      return request<AgentConfig>(`${baseUrl}/api/agent/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
  };
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json();
}
