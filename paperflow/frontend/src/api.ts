import type {
  AgentStatus,
  Claim,
  FieldMap,
  Paper,
  ParsedPdfPayload,
  PaperSession,
  R1SearchResult,
  ReadingReport,
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
  getStatus(paperId: string): Promise<TaskStatus>;
  getReport(paperId: string): Promise<ReadingReport>;
  askPaper(paperId: string, question: string): Promise<Claim>;
  askSelection(paperId: string, payload: AskSelectionPayload): Promise<Claim>;
  getChunks(paperId: string): Promise<ParsedPdfPayload>;
  pdfUrl(paperId: string): string;
  runR1Search(paperId: string): Promise<R1SearchResult>;
  getRelated(paperId: string): Promise<R1SearchResult>;
  createFieldMap(paperId: string): Promise<FieldMap>;
  getFieldMap(fieldMapId: string): Promise<FieldMap>;
  listFieldMaps(): Promise<FieldMap[]>;
  rerunFieldMap(fieldMapId: string): Promise<FieldMap>;
  exportObsidian(paperId: string): Promise<{ note_path: string }>;
  rerunAgent(paperId: string): Promise<PaperSession>;
  getAgentStatus(): Promise<AgentStatus>;
}

export function createPaperflowClient(baseUrl = "http://127.0.0.1:8000"): PaperflowClient {
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
  };
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}
