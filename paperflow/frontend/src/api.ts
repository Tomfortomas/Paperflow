import type { AgentStatus, Claim, Paper, PaperSession, ReadingReport, TaskStatus } from "./types";

export interface PaperflowClient {
  listPapers(): Promise<Paper[]>;
  importPaper(file: File): Promise<PaperSession>;
  importArxiv(url: string): Promise<PaperSession>;
  getStatus(paperId: string): Promise<TaskStatus>;
  getReport(paperId: string): Promise<ReadingReport>;
  askPaper(paperId: string, question: string): Promise<Claim>;
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
