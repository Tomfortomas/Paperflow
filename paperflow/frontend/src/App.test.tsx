import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

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
  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads the default library only once on initial render", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await new Promise((resolve) => setTimeout(resolve, 25));

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/papers", undefined);
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/agent/status", undefined);
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/agent/config", undefined);
  });

  it("renders a Library-first home with import, recent papers, status, and saved reports", () => {
    render(<App initialPapers={[paper]} initialReports={{ "paper-1": report }} />);

    expect(screen.getByRole("navigation", { name: /全局导航/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: /paperflow/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /paperflow 文献库/i })).not.toBeInTheDocument();
    expect(screen.getByText(/导入 PDF/i)).toBeInTheDocument();
    expect(screen.getByText(/最近论文/i)).toBeInTheDocument();
    expect(screen.getByText(/处理状态/i)).toBeInTheDocument();
    expect(screen.getByText(/已保存报告/i)).toBeInTheDocument();
    const savedReports = screen.getByRole("heading", { name: /已保存报告/i })
      .parentElement as HTMLElement;
    expect(within(savedReports).getByText("Paperflow")).toBeInTheDocument();
    expect(within(savedReports).getByText("/vault/notes/Paperflow.md")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Paperflow" })).toBeInTheDocument();
    expect(screen.queryByText(/已准备好自动执行/)).not.toBeInTheDocument();
    expect(screen.getByText(/1 篇论文，1 篇报告已完成/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /打开 paperflow/i })).toHaveTextContent(/^打开$/);
    expect(screen.getByRole("button", { name: /删除 paperflow/i })).toHaveTextContent(/^删除$/);
    expect(screen.getByRole("button", { name: /删除 paperflow/i })).toHaveClass("btn-secondary");
  });

  it("shows subtle parse metrics in the report header", async () => {
    const user = userEvent.setup();
    render(
      <App
        initialPapers={[paper]}
        initialReports={{
          "paper-1": {
            ...report,
            agent_run: {
              elapsed_seconds: 12.4,
              total_tokens: 1532,
            },
          },
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /打开 paperflow/i }));

    expect(screen.getByText(/解析指标 · 1\.5k tokens · 12s/)).toBeInTheDocument();
  });

  it("deletes a paper after inline confirmation", async () => {
    const user = userEvent.setup();
    const client = fakeClient({
      deletePaper: vi.fn().mockResolvedValue(undefined),
    });

    render(<App client={client} initialPapers={[paper]} initialReports={{ "paper-1": report }} />);

    await user.click(screen.getByRole("button", { name: /删除 paperflow/i }));
    expect(screen.getByRole("button", { name: /确认删除 paperflow/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /确认删除 paperflow/i })).toHaveTextContent(/^确认删除$/);

    await user.click(screen.getByRole("button", { name: /确认删除 paperflow/i }));

    expect(client.deletePaper).toHaveBeenCalledWith("paper-1");
    expect(screen.queryByRole("heading", { level: 3, name: "Paperflow" })).not.toBeInTheDocument();
    expect(screen.getByText(/文献库还是空的/)).toBeInTheDocument();
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

    expect(screen.getByRole("button", { name: /返回文献库/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /field map/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /阅读报告/i })).toBeInTheDocument();
    expect(screen.getAllByText("Paperflow is a paper reading IDE.")[0]).toBeInTheDocument();
    expect(screen.getAllByText("R0")[0]).toBeInTheDocument();
    expect(screen.getByText(/r1 相关工作/i)).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: /查看 1 条证据/i })[0]);

    expect(screen.getByText("paper reading IDE")).toBeInTheDocument();
    // Phase 1: evidence carries a location-status badge.
    expect(screen.getByText(/已定位到页 \+ 段落/)).toBeInTheDocument();
  });

  it("renders an Agent chat panel with transcript and process cards", async () => {
    const user = userEvent.setup();
    const client = fakeClient({
      chatPaper: vi.fn().mockResolvedValue({
        id: "chat-1",
        paper_id: "paper-1",
        status: "completed",
        steps: [
          { id: "read-report", label: "Read report", status: "completed", detail: "Loaded report" },
          { id: "locate-evidence", label: "Locate evidence", status: "completed", detail: "Used evidence" },
          { id: "check-r1", label: "Check R1 context", status: "completed", detail: "Checked related work" },
          { id: "compose-answer", label: "Compose answer", status: "completed", detail: "Generated answer" },
        ],
        messages: [
          { id: "user-1", role: "user", content: "只看 benchmark" },
          {
            id: "assistant-1",
            role: "assistant",
            content: "It extracts structured reading reports.",
            reliability: "R0",
            evidence: [{ id: "e2", source: "Paperflow.pdf", page: 2, quote: "structured reports" }],
          },
        ],
        answer: {
          id: "chat-answer",
          text: "It extracts structured reading reports.",
          reliability: "R0",
          evidence: [{ id: "e2", source: "Paperflow.pdf", page: 2, quote: "structured reports" }],
        },
      }),
    });
    render(<App client={client} initialPapers={[paper]} initialReports={{ "paper-1": report }} />);

    await user.click(screen.getByRole("button", { name: /打开 paperflow/i }));
    await user.click(screen.getAllByRole("button", { name: /查看 1 条证据/i })[1]);
    await user.type(screen.getByPlaceholderText(/benchmark/), "只看 benchmark");
    await user.click(screen.getByRole("button", { name: /^发送$/ }));

    expect(client.chatPaper).toHaveBeenCalledWith(
      "paper-1",
      expect.objectContaining({
        question: "只看 benchmark",
        selected_claim_id: "claim-task",
        selected_evidence_id: "e2",
        page: 2,
        quote: "structured reports",
      }),
    );
    expect(await screen.findByText("Read report")).toBeInTheDocument();
    expect(screen.getByText("只看 benchmark")).toBeInTheDocument();
    expect(screen.getAllByText("It extracts structured reading reports.").length).toBeGreaterThan(0);
  });

  it("offers a PDF viewer toggle once the report is ready", async () => {
    const user = userEvent.setup();
    render(<App initialPapers={[paper]} initialReports={{ "paper-1": report }} />);

    await user.click(screen.getByRole("button", { name: /打开 paperflow/i }));

    expect(screen.getByRole("button", { name: /打开 PDF 阅读器/i })).toBeInTheDocument();
  });

  it("renders a Field Map lineage graph", async () => {
    const user = userEvent.setup();
    const client = fakeClient({
      createFieldMap: vi.fn().mockResolvedValue({
        id: "fm-1",
        seed_paper_id: "paper-1",
        seed_title: "Actual Paper Title",
        field_summary: "A compact field map.",
        task_taxonomy: [],
        datasets_benchmarks: [],
        metrics: [],
        milestones: [],
        timeline: [],
        method_families: [],
        evaluation_protocols: [],
        open_problems: [],
        recent_trends: [],
        research_opportunities: [],
        evidence_index: [],
        relationship_graph: {
          nodes: [
            { id: "old", title: "Old Foundation", role: "predecessor", year: 2017, event_type: "milestone" },
            { id: "seed", title: "Actual Paper Title", role: "seed", year: 2024, event_type: "other" },
          ],
          edges: [{ id: "old-seed", source: "old", target: "seed", relation: "precedes" }],
        },
      }),
    });

    render(<App client={client} initialPapers={[paper]} initialReports={{ "paper-1": report }} />);

    await user.click(screen.getByRole("button", { name: /打开 paperflow/i }));
    await user.click(screen.getByRole("button", { name: /生成 Field Map/i }));

    expect(await screen.findByText(/前后关系图/i)).toBeInTheDocument();
    expect(screen.getAllByText("Old Foundation").length).toBeGreaterThan(0);
    expect(screen.getByRole("img", { name: /Old Foundation · 前置基础 · 2017 · R1/i })).toBeInTheDocument();
    expect(screen.getAllByText("Actual Paper Title")[0]).toBeInTheDocument();
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

  it("shows explicit feedback while a PDF upload is in flight", async () => {
    const user = userEvent.setup();
    let resolveImport: (value: Awaited<ReturnType<PaperflowClient["importPaper"]>>) => void;
    const queuedPaper: Paper = {
      id: "paper-uploading",
      title: "Uploading Paper",
      pdf_path: "/vault/pdfs/Uploading Paper.pdf",
      status: { stage: "queued", message: "Queued", progress: 0.05 },
    };
    const client = fakeClient({
      importPaper: vi.fn().mockReturnValue(
        new Promise((resolve) => {
          resolveImport = resolve;
        }),
      ),
      getStatus: vi.fn().mockReturnValue(new Promise(() => {})),
      getReport: vi.fn(),
    });

    render(<App client={client} />);
    await user.upload(
      screen.getByLabelText(/导入 PDF/i),
      new File(["paper"], "uploading.pdf", { type: "application/pdf" }),
    );

    expect(screen.getByText(/正在上传 PDF/)).toBeInTheDocument();

    resolveImport!({
      id: "session-uploading",
      paper: queuedPaper,
      status: queuedPaper.status!,
      report: null,
    });

    expect(await screen.findByText(/已接收 Uploading Paper/)).toBeInTheDocument();
  });

  it("does not duplicate import failure messages across alerts", async () => {
    const user = userEvent.setup();
    const failedPaper: Paper = {
      id: "paper-timeout",
      title: "Timeout Paper",
      pdf_path: "/vault/pdfs/Timeout Paper.pdf",
      status: { stage: "queued", message: "Queued", progress: 0.05 },
    };
    const client = fakeClient({
      importPaper: vi.fn().mockResolvedValue({
        id: "session-timeout",
        paper: failedPaper,
        status: failedPaper.status!,
        report: null,
      }),
      getStatus: vi.fn().mockResolvedValue({
        stage: "failed",
        message: "The read operation timed out",
        progress: 0.35,
      }),
      getReport: vi.fn(),
    });
    const { container } = render(<App client={client} />);

    await user.upload(
      screen.getByLabelText(/导入 PDF/i),
      new File(["paper"], "timeout.pdf", { type: "application/pdf" }),
    );

    await waitFor(() =>
      expect(container.querySelector(".import-activity-message")).toHaveTextContent(
        "The read operation timed out",
      ),
    );
    await user.click(screen.getByRole("button", { name: /返回文献库/i }));

    expect(container.querySelector(".warning-line")).toBeNull();
    expect(container.querySelector(".import-activity-message")).toHaveTextContent(
      "The read operation timed out",
    );
  });

  it("shows an intermediate Agent parsing trace for failed papers", async () => {
    const user = userEvent.setup();
    const failedPaper: Paper = {
      ...paper,
      status: {
        stage: "failed",
        message:
          "DeepSeek report generation timed out. The PDF may be long or the model may be slow; retry later or increase DEEPSEEK_REPORT_READ_TIMEOUT.",
        progress: 1,
      },
    };

    render(<App initialPapers={[failedPaper]} />);

    await user.click(screen.getByRole("button", { name: /打开 paperflow/i }));

    expect(screen.getByText(/Agent 解析过程/)).toBeInTheDocument();
    expect(screen.getByText(/准备 PDF 文本与上下文/)).toBeInTheDocument();
    expect(screen.getByText(/等待 DeepSeek 生成阅读报告/)).toBeInTheDocument();
    expect(screen.getByText(/失败点/)).toBeInTheDocument();
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

  it("surfaces duplicate import warnings from the backend", async () => {
    const user = userEvent.setup();
    const replacementPaper: Paper = {
      id: "paper-arxiv-new",
      title: "Same arXiv Paper",
      pdf_path: "/vault/pdfs/Same arXiv Paper.pdf",
      status: { stage: "queued", message: "Queued", progress: 0.05 },
    };
    const client = fakeClient({
      importArxiv: vi.fn().mockResolvedValue({
        id: "session-new",
        paper: replacementPaper,
        status: replacementPaper.status,
        report: null,
        duplicate_warning: "疑似重复：已替换同 arXiv 编号的旧条目。",
        duplicate_of: paper,
      }),
      getStatus: vi.fn().mockResolvedValue({
        stage: "completed",
        message: "Reading report generated",
        progress: 1,
      }),
      getReport: vi.fn().mockResolvedValue({ ...report, paper_id: "paper-arxiv-new" }),
    });

    render(<App client={client} initialPapers={[paper]} />);
    await user.type(screen.getByLabelText(/从 arxiv 导入/i), "https://arxiv.org/abs/2605.08063v2");
    await user.click(screen.getByRole("button", { name: /下载并解析/i }));

    expect(await screen.findByText(/疑似重复/)).toBeInTheDocument();
  });

  it("does not show a precise percent for active Agent parsing", () => {
    render(
      <App
        initialPapers={[
          {
            ...paper,
            status: {
              stage: "processing",
              message: "PaperAgent is preparing PDF text and report context",
              progress: 0.35,
            },
          },
        ]}
      />,
    );

    expect(screen.getByText(/正在准备 PDF 文本/)).toBeInTheDocument();
    expect(screen.getAllByText("解析中").length).toBeGreaterThan(0);
    expect(screen.queryByText("35%")).not.toBeInTheDocument();
  });

  it("lets users update the DeepSeek model and report timeout", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup();
    const client = fakeClient({
      getAgentConfig: vi.fn().mockResolvedValue({
        configured: true,
        has_api_key: true,
        mode: "deepseek",
        model: "deepseek-v4-flash",
        model_options: ["deepseek-v4-flash", "deepseek-v4-pro"],
        report_read_timeout: 45,
      }),
      updateAgentConfig: vi.fn().mockResolvedValue({
        configured: true,
        has_api_key: true,
        mode: "deepseek",
        model: "deepseek-v4-pro",
        model_options: ["deepseek-v4-flash", "deepseek-v4-pro"],
        report_read_timeout: 120,
      }),
    });

    render(<App client={client} />);

    expect(await screen.findByText(/deepseek-v4-flash · 45s/)).toBeInTheDocument();
    await user.click(screen.getByText(/^Agent 配置$/i));
    await user.click(await screen.findByRole("button", { name: /Pro/i }));
    const timeoutInput = screen.getByLabelText(/报告超时/i);
    await user.clear(timeoutInput);
    await user.type(timeoutInput, "120");
    await user.click(screen.getByRole("button", { name: /保存 Agent 配置/i }));

    expect(client.updateAgentConfig).toHaveBeenCalledWith({
      model: "deepseek-v4-pro",
      report_read_timeout: 120,
    });
    expect(await screen.findByText(/Agent 配置已保存/)).toBeInTheDocument();
    vi.advanceTimersByTime(2300);
    await waitFor(() =>
      expect(screen.queryByText(/Agent 配置已保存/)).not.toBeInTheDocument(),
    );
  });

  it("lets users update the DeepSeek API key without echoing it", async () => {
    const user = userEvent.setup();
    const client = fakeClient({
      getAgentConfig: vi.fn().mockResolvedValue({
        configured: false,
        has_api_key: false,
        mode: "missing-key",
        model: null,
        model_options: ["deepseek-v4-flash", "deepseek-v4-pro"],
        report_read_timeout: 45,
      }),
      updateAgentConfig: vi.fn().mockResolvedValue({
        configured: true,
        has_api_key: true,
        mode: "deepseek",
        model: "deepseek-v4-flash",
        model_options: ["deepseek-v4-flash", "deepseek-v4-pro"],
        report_read_timeout: 45,
      }),
    });

    render(<App client={client} />);

    await user.click(await screen.findByText(/^Agent 配置$/i));
    await user.type(screen.getByLabelText(/DeepSeek API Key/i), "sk-local-test");
    await user.click(screen.getByRole("button", { name: /保存 Agent 配置/i }));

    expect(client.updateAgentConfig).toHaveBeenCalledWith({
      api_key: "sk-local-test",
      model: "",
      report_read_timeout: 45,
    });
    expect(screen.queryByDisplayValue("sk-local-test")).not.toBeInTheDocument();
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
    deletePaper: vi.fn(),
    getStatus: vi.fn(),
    getReport: vi.fn(),
    askPaper: vi.fn(),
    askSelection: vi.fn(),
    chatPaper: vi.fn(),
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
    getAgentConfig: vi.fn().mockResolvedValue({
      configured: true,
      has_api_key: true,
      mode: "injected",
      model: null,
      model_options: ["deepseek-v4-flash", "deepseek-v4-pro"],
      report_read_timeout: 45,
    }),
    updateAgentConfig: vi.fn(),
    ...overrides,
  };
}
