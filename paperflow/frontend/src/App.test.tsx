import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { Paper, ReadingReport } from "./types";
import type { PaperflowClient } from "./api";

const paper: Paper = {
  id: "paper-1",
  title: "Paperflow",
  pdf_path: "/vault/pdfs/Paperflow.pdf",
  note_path: "/vault/notes/Paperflow.md",
  status: { stage: "completed", message: "Reading report generated", progress: 1 },
};

const report: ReadingReport = {
  paper_id: "paper-1",
  paper_title: "Actual Paper Title",
  summary: [
    {
      id: "claim-1",
      text: "Paperflow is a paper reading IDE.",
      reliability: "R0",
      evidence: [{ id: "e1", source: "Paperflow.pdf", page: 1, quote: "paper reading IDE" }],
    },
  ],
  sections: [
    {
      id: "task",
      title: "Task",
      claims: [
        {
          id: "claim-task",
          text: "It extracts structured reading reports.",
          reliability: "R0",
          evidence: [{ id: "e2", source: "Paperflow.pdf", page: 2, quote: "structured reports" }],
        },
      ],
    },
  ],
  related_work: [
    {
      id: "rw-1",
      title: "References and cited-by expansion",
      relation: "follow-up-search-entry",
      source: "Automatic R1 placeholder",
      reliability: "R1",
      evidence: [],
    },
  ],
};

describe("Paperflow app", () => {
  it("loads the default library only once on initial render", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await new Promise((resolve) => setTimeout(resolve, 25));

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/papers", undefined);
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/agent/status", undefined);
  });

  it("renders a Library-first home with import, recent papers, status, and saved reports", () => {
    render(<App initialPapers={[paper]} initialReports={{ "paper-1": report }} />);

    expect(screen.getByRole("heading", { name: /paperflow 文献库/i })).toBeInTheDocument();
    expect(screen.getByText(/导入 PDF/i)).toBeInTheDocument();
    expect(screen.getByText(/最近论文/i)).toBeInTheDocument();
    expect(screen.getByText(/处理状态/i)).toBeInTheDocument();
    expect(screen.getByText(/已保存报告/i)).toBeInTheDocument();
    expect(screen.getByText("Paperflow")).toBeInTheDocument();
  });

  it("toggles the interface between Chinese and English", async () => {
    const user = userEvent.setup();
    render(<App initialPapers={[paper]} initialReports={{ "paper-1": report }} />);

    await user.click(screen.getByRole("button", { name: /english/i }));

    expect(screen.getByRole("heading", { name: /paperflow library/i })).toBeInTheDocument();
    expect(screen.getByText(/import pdf/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /中文/i })).toBeInTheDocument();
  });

  it("opens a Report-first workspace with reliability badges and evidence details", async () => {
    const user = userEvent.setup();
    render(<App initialPapers={[paper]} initialReports={{ "paper-1": report }} />);

    await user.click(screen.getByRole("button", { name: /打开 paperflow/i }));

    expect(screen.getByRole("heading", { name: /阅读报告/i })).toBeInTheDocument();
    expect(screen.getAllByText("Paperflow is a paper reading IDE.")[0]).toBeInTheDocument();
    expect(screen.getAllByText("R0")[0]).toBeInTheDocument();
    expect(screen.getByText(/r1 相关工作/i)).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: /查看 1 条证据/i })[0]);

    expect(screen.getByText("paper reading IDE")).toBeInTheDocument();
    // Phase 1: evidence carries a location-status badge.
    expect(screen.getByText(/已定位到页 \+ 段落/)).toBeInTheDocument();
  });

  it("offers a PDF viewer toggle once the report is ready", async () => {
    const user = userEvent.setup();
    render(<App initialPapers={[paper]} initialReports={{ "paper-1": report }} />);

    await user.click(screen.getByRole("button", { name: /打开 paperflow/i }));

    expect(screen.getByRole("button", { name: /打开 PDF 阅读器/i })).toBeInTheDocument();
  });

  it("imports a PDF without blocking and opens the report after status polling completes", async () => {
    const user = userEvent.setup();
    const queuedPaper: Paper = {
      id: "paper-2",
      title: "Queued Paper",
      pdf_path: "/vault/pdfs/Queued Paper.pdf",
      status: { stage: "queued", message: "Queued", progress: 0.05 },
    };
    const client = fakeClient({
      importPaper: vi.fn().mockResolvedValue({
        id: "session-2",
        paper: queuedPaper,
        status: queuedPaper.status,
        report: null,
      }),
      getStatus: vi.fn().mockResolvedValue({
        stage: "completed",
        message: "Reading report generated",
        progress: 1,
      }),
      getReport: vi.fn().mockResolvedValue({ ...report, paper_id: "paper-2" }),
    });

    render(<App client={client} />);
    await user.upload(
      screen.getByLabelText(/导入 PDF/i),
      new File(["paper"], "queued.pdf", { type: "application/pdf" }),
    );

    expect(await screen.findByRole("heading", { name: /阅读报告/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /actual paper title/i })).toBeInTheDocument();
    expect(client.importPaper).toHaveBeenCalledTimes(1);
    expect(client.getStatus).toHaveBeenCalledWith("paper-2");
    expect(client.getReport).toHaveBeenCalledWith("paper-2");
  });

  it("imports an arXiv link and opens the report after download completes", async () => {
    const user = userEvent.setup();
    const arxivPaper: Paper = {
      id: "paper-arxiv",
      title: "arxiv-2605.08063v1",
      pdf_path: "/vault/pdfs/arxiv-2605.08063v1.pdf",
      status: { stage: "queued", message: "Queued", progress: 0.05 },
    };
    const client = fakeClient({
      importArxiv: vi.fn().mockResolvedValue({
        id: "session-arxiv",
        paper: arxivPaper,
        status: arxivPaper.status,
        report: null,
      }),
      getStatus: vi.fn().mockResolvedValue({
        stage: "completed",
        message: "Reading report generated",
        progress: 1,
      }),
      getReport: vi.fn().mockResolvedValue({ ...report, paper_id: "paper-arxiv" }),
    });

    render(<App client={client} />);
    await user.type(screen.getByLabelText(/从 arxiv 导入/i), "https://arxiv.org/abs/2605.08063v1");
    await user.click(screen.getByRole("button", { name: /下载并解析/i }));

    expect(await screen.findByRole("heading", { name: /阅读报告/i })).toBeInTheDocument();
    expect(client.importArxiv).toHaveBeenCalledWith("https://arxiv.org/abs/2605.08063v1");
    expect(client.getStatus).toHaveBeenCalledWith("paper-arxiv");
  });
});

function fakeClient(overrides: Partial<PaperflowClient> = {}): PaperflowClient {
  return {
    listPapers: vi.fn().mockResolvedValue([]),
    importPaper: vi.fn(),
    importArxiv: vi.fn(),
    importUrl: vi.fn(),
    importZotero: vi.fn().mockResolvedValue({ imported: 0, sessions: [] }),
    previewZotero: vi.fn().mockResolvedValue([]),
    getStatus: vi.fn(),
    getReport: vi.fn(),
    askPaper: vi.fn(),
    askSelection: vi.fn(),
    getChunks: vi.fn().mockResolvedValue({ chunks: [], page_sizes: [] }),
    pdfUrl: vi.fn().mockReturnValue("http://127.0.0.1:8000/api/papers/paper-1/pdf"),
    runR1Search: vi.fn().mockResolvedValue({ items: [], query_trace: [] }),
    getRelated: vi.fn().mockResolvedValue({ items: [], query_trace: [] }),
    createFieldMap: vi.fn(),
    getFieldMap: vi.fn(),
    listFieldMaps: vi.fn().mockResolvedValue([]),
    rerunFieldMap: vi.fn(),
    comparePapers: vi.fn().mockResolvedValue({ id: "cmp", paper_ids: [], dimensions: [], notes: [] }),
    generateInsights: vi.fn().mockResolvedValue({ id: "ins", insights: [] }),
    exportFieldMapObsidian: vi.fn().mockResolvedValue({ note_path: "/tmp/field-map.md" }),
    listTasks: vi.fn().mockResolvedValue([]),
    getTask: vi.fn(),
    cancelTask: vi.fn(),
    retryTask: vi.fn(),
    exportObsidian: vi.fn(),
    rerunAgent: vi.fn(),
    getAgentStatus: vi.fn().mockResolvedValue({ configured: true, mode: "injected", model: null }),
    ...overrides,
  };
}
