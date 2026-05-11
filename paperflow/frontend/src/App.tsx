import { useEffect, useMemo, useState } from "react";

import { createPaperflowClient, type PaperflowClient } from "./api";
import { PdfViewer, type PdfBboxHighlight } from "./PdfViewer";
import type {
  AgentStatus,
  Claim,
  Evidence,
  FieldMap,
  FieldMapRelationshipGraph,
  MilestonePaper,
  Paper,
  PaperChatResponse,
  PaperSession,
  R1QueryTraceEntry,
  ReadingReport,
  RelatedWorkItem,
  TaskStatus,
  TimelineEvent,
} from "./types";
import "./styles.css";

const defaultClient = createPaperflowClient();
type Locale = "zh" | "en";

const UI_TEXT = {
  zh: {
    readyStatus: "已准备好自动执行 R0 + 轻量 R1 处理。",
    backendMissing: "后端未连接。请先启动 FastAPI 再加载文献库。",
    queuedStatus: "PDF 已加入 Agent 解析队列。",
    importFailed: "导入失败。",
    reportUnavailable: "这篇论文的报告还不可用。",
    parseTimeout: "Agent 解析超时。你可以在论文工作台里重试。",
    eyebrow: "本地优先的论文研读台",
    libraryTitle: "Paperflow",
    heroDescription:
      "导入论文，生成带证据的阅读报告，并保存为 Obsidian 原生笔记。",
    agentLabel: "Agent",
    configured: "已配置",
    missingKey: "缺少 key",
    languageToggle: "English",
    importPdf: "导入 PDF",
    importPdfHint: "本地 PDF 文件",
    arxivImportTitle: "从 arXiv 导入",
    arxivPlaceholder: "arXiv ID 或链接",
    importArxiv: "下载并解析",
    arxivQueuedStatus: "arXiv PDF 已开始下载并加入解析队列。",
    emptyArxiv: "请输入 arXiv 链接或 ID。",
    urlImportTitle: "从 URL 导入",
    urlPlaceholder: "DOI / Semantic Scholar / OpenReview",
    importUrl: "解析元数据并下载",
    urlQueuedStatus: "已识别 URL 元数据,开始下载 PDF。",
    emptyUrl: "请输入论文 URL 或 DOI。",
    zoteroImportTitle: "从 Zotero 导入",
    zoteroPath: "~/Zotero/zotero.sqlite",
    zoteroImportButton: "导入本地 Zotero 库",
    zoteroImported: (count: number) => `已从 Zotero 导入 ${count} 篇论文。`,
    zoteroEmpty: "Zotero 库为空或没有可解析的 PDF 附件。",
    importsLabel: "导入论文",
    librarySection: "文献库",
    recentPapers: "最近论文",
    paperCount: (n: number) => `${n} 篇`,
    notePrefix: "笔记",
    openPaper: (title: string) => `打开 ${title}`,
    openPaperAction: "打开",
    deletePaper: (title: string) => `删除 ${title}`,
    deletePaperAction: "删除",
    confirmDeletePaper: (title: string) => `确认删除 ${title}`,
    confirmDeletePaperAction: "确认删除",
    deleteFailed: "删除失败。",
    processingStatus: "处理状态",
    savedReports: "已保存报告",
    navImport: "导入",
    navPapers: "论文",
    navReport: "报告",
    navFieldMap: "Field Map",
    noNote: "尚未保存 Obsidian 笔记",
    backToLibrary: "返回文献库",
    reportNotReady: "Agent 报告还没生成。",
    readingReport: "阅读报告",
    executiveSummary: "执行摘要",
    relatedWork: "R1 相关工作",
    evidenceButton: (count: number) => `查看 ${count} 条证据`,
    selectedClaim: "选中的结论",
    agentStatus: "Agent 状态",
    noActiveTask: "当前没有任务。",
    rerunAgent: "重新运行 Agent",
    evidenceDetail: "证据详情",
    missingEvidence: "缺少证据。",
    selectClaim: "选择一个 claim 查看证据。",
    agentChat: "Agent 对话",
    chatIdle: "等待提问",
    chatRunning: "Agent 正在处理",
    chatCompleted: "回答已生成",
    chatFailed: "回答失败",
    askPlaceholder: "例如:只看 benchmark 和 dataset",
    ask: "发送",
    processCards: "过程",
    obsidian: "Obsidian",
    saveNote: "保存 / 更新 Obsidian 笔记",
    savedTo: (path: string) => `已保存到 ${path}`,
    page: (page: number) => `p. ${page}`,
    pdfPanel: "PDF 阅读",
    selectionAsk: "针对选区追问",
    selectionPlaceholder: "在 PDF 中选中文本,再点这里追问。",
    enableViewer: "打开 PDF 阅读器",
    disableViewer: "关闭 PDF 阅读器",
    locationExact: "已精确定位",
    locationPageQuote: "已定位到页 + 段落",
    locationQuoteOnly: "无法在 PDF 中定位",
    locationMissing: "缺少证据原文",
    r1RunSearch: "运行 R1 检索",
    r1Running: "正在跑 R1 搜索…",
    r1Updated: (count: number) => `R1 检索完成,共 ${count} 篇相关论文。`,
    r1Failed: "R1 检索失败:",
    r1QueryTrace: "R1 检索踪迹",
    r1ComparisonRisk: "对比风险:",
    r1CitedBy: (count: number) => `${count} 引用`,
    r1InfluentialCitedBy: (count: number) => `${count} 高影响力引用`,
    fieldMapTitle: "领域地图",
    fieldMapGenerate: "生成 Field Map",
    fieldMapRegenerate: "重跑 Field Map",
    fieldMapRunning: "Field Map 生成中…",
    fieldMapFailed: "Field Map 生成失败:",
    fieldMapSummary: "领域摘要",
    fieldMapTaskTaxonomy: "任务定义",
    fieldMapDatasets: "数据集 / Benchmark",
    fieldMapMetrics: "评价指标",
    fieldMapMethodFamilies: "方法家族",
    fieldMapMilestones: "里程碑论文",
    fieldMapTimeline: "技术时间线",
    fieldMapRelationshipGraph: "前后关系图",
    fieldMapGraphPredecessor: "前置基础",
    fieldMapGraphSeed: "Seed",
    fieldMapGraphSuccessor: "后续影响",
    fieldMapOpenProblems: "未解决问题",
    fieldMapRecentTrends: "近期趋势 (R2)",
    fieldMapOpportunities: "研究机会 (R2)",
    fieldMapEmpty:
      "尚未生成 Field Map。先运行 R1 检索可以让结果更可信。",
    fieldMapWhy: "判定理由:",
    fieldMapRisk: "风险:",
    statusLabels: {
      queued: "排队中",
      processing: "解析中",
      completed: "已完成",
      failed: "失败",
      unknown: "未知",
    },
    taskMessages: {
      "Ready for automatic R0 + lightweight R1 processing.":
        "已准备好自动执行 R0 + 轻量 R1 处理。",
      "Backend not connected. Start FastAPI to load your library.":
        "后端未连接。请先启动 FastAPI 再加载文献库。",
      "Queued PDF for Agent parsing...": "PDF 已加入 Agent 解析队列。",
      "arXiv PDF download queued for parsing.":
        "arXiv PDF 已开始下载并加入解析队列。",
      "Import failed.": "导入失败。",
      "Reading report generated": "阅读报告已生成",
      "Queued for Agent parsing": "已加入 Agent 解析队列",
      "DeepSeek PaperAgent is parsing the PDF":
        "DeepSeek PaperAgent 正在解析 PDF",
      "Queued for Agent rerun": "已加入 Agent 重跑队列",
    },
    sectionTitles: {
      Task: "任务",
      Dataset: "数据集",
      "Benchmark / Metric": "Benchmark / 指标",
      Method: "方法",
      "Input / Output": "输入 / 输出",
      "Compute / Training": "算力 / 训练",
      Limitations: "局限性",
      "Agent Required": "需要配置 Agent",
    },
  },
  en: {
    readyStatus: "Ready for automatic R0 + lightweight R1 processing.",
    backendMissing: "Backend not connected. Start FastAPI to load your library.",
    queuedStatus: "Queued PDF for Agent parsing...",
    importFailed: "Import failed.",
    reportUnavailable: "Report is not available for this paper yet.",
    parseTimeout:
      "Agent parsing timed out. You can retry from the paper workspace.",
    eyebrow: "Local-first research workspace",
    libraryTitle: "Paperflow Library",
    heroDescription:
      "Bring in papers, generate evidence-aware reading reports, and save Obsidian-native notes for long-term research.",
    agentLabel: "Agent",
    configured: "configured",
    missingKey: "missing key",
    languageToggle: "中文",
    importPdf: "Import PDF",
    importPdfHint: "Drop a PDF or browse to choose one",
    arxivImportTitle: "Import from arXiv",
    arxivPlaceholder: "Paste an arXiv URL or ID, e.g. 2605.08063v1",
    importArxiv: "Download and Parse",
    arxivQueuedStatus: "arXiv PDF download queued for parsing.",
    emptyArxiv: "Enter an arXiv URL or ID.",
    urlImportTitle: "Import from URL",
    urlPlaceholder:
      "arXiv / DOI / Semantic Scholar / OpenReview URL, auto-detected",
    importUrl: "Fetch metadata and download",
    urlQueuedStatus: "Metadata fetched, downloading PDF.",
    emptyUrl: "Enter a paper URL or DOI.",
    zoteroImportTitle: "Import from Zotero",
    zoteroPath: "~/Zotero/zotero.sqlite",
    zoteroImportButton: "Import local Zotero library",
    zoteroImported: (count: number) => `Imported ${count} papers from Zotero.`,
    zoteroEmpty: "Zotero library is empty or has no PDF attachments.",
    importsLabel: "Import",
    librarySection: "Library",
    recentPapers: "Recent Papers",
    paperCount: (n: number) => `${n} item${n === 1 ? "" : "s"}`,
    notePrefix: "Note",
    openPaper: (title: string) => `Open ${title}`,
    openPaperAction: "Open",
    deletePaper: (title: string) => `Delete ${title}`,
    deletePaperAction: "Delete",
    confirmDeletePaper: (title: string) => `Confirm delete ${title}`,
    confirmDeletePaperAction: "Confirm delete",
    deleteFailed: "Delete failed.",
    processingStatus: "Processing Status",
    savedReports: "Saved Reports",
    navImport: "Import",
    navPapers: "Papers",
    navReport: "Report",
    navFieldMap: "Field Map",
    noNote: "No Obsidian note yet",
    backToLibrary: "Back to Library",
    reportNotReady: "Agent report is not ready yet.",
    readingReport: "Reading Report",
    executiveSummary: "Executive Summary",
    relatedWork: "R1 Related Work",
    evidenceButton: (count: number) =>
      `View ${count} evidence item${count === 1 ? "" : "s"}`,
    selectedClaim: "Selected claim",
    agentStatus: "Agent Status",
    noActiveTask: "No active task.",
    rerunAgent: "Re-run Agent",
    evidenceDetail: "Evidence Detail",
    missingEvidence: "Missing evidence.",
    selectClaim: "Select a claim to inspect its evidence.",
    agentChat: "Agent Chat",
    chatIdle: "Waiting for a question",
    chatRunning: "Agent is working",
    chatCompleted: "Answer generated",
    chatFailed: "Answer failed",
    askPlaceholder: "e.g. focus on benchmark and dataset",
    ask: "Send",
    processCards: "Process",
    obsidian: "Obsidian",
    saveNote: "Save / Update Obsidian Note",
    savedTo: (path: string) => `Saved to ${path}`,
    page: (page: number) => `p. ${page}`,
    pdfPanel: "PDF Viewer",
    selectionAsk: "Ask about selection",
    selectionPlaceholder:
      "Select text in the PDF, then click to ask.",
    enableViewer: "Open PDF viewer",
    disableViewer: "Close PDF viewer",
    locationExact: "located precisely",
    locationPageQuote: "page + paragraph",
    locationQuoteOnly: "no PDF location",
    locationMissing: "no evidence quote",
    r1RunSearch: "Run R1 search",
    r1Running: "Running R1 search…",
    r1Updated: (count: number) => `R1 search returned ${count} related papers.`,
    r1Failed: "R1 search failed: ",
    r1QueryTrace: "R1 query trace",
    r1ComparisonRisk: "Comparison risk: ",
    r1CitedBy: (count: number) => `${count} cites`,
    r1InfluentialCitedBy: (count: number) => `${count} high-impact cites`,
    fieldMapTitle: "Field Map",
    fieldMapGenerate: "Generate Field Map",
    fieldMapRegenerate: "Re-run Field Map",
    fieldMapRunning: "Building Field Map…",
    fieldMapFailed: "Field Map failed: ",
    fieldMapSummary: "Field Summary",
    fieldMapTaskTaxonomy: "Task Taxonomy",
    fieldMapDatasets: "Datasets / Benchmarks",
    fieldMapMetrics: "Metrics",
    fieldMapMethodFamilies: "Method Families",
    fieldMapMilestones: "Milestone Papers",
    fieldMapTimeline: "Technology Timeline",
    fieldMapRelationshipGraph: "Lineage Graph",
    fieldMapGraphPredecessor: "Predecessors",
    fieldMapGraphSeed: "Seed",
    fieldMapGraphSuccessor: "Successors",
    fieldMapOpenProblems: "Open Problems",
    fieldMapRecentTrends: "Recent Trends (R2)",
    fieldMapOpportunities: "Research Opportunities (R2)",
    fieldMapEmpty:
      "No Field Map yet. Running R1 search first will give better results.",
    fieldMapWhy: "Why milestone: ",
    fieldMapRisk: "Risk: ",
    statusLabels: {
      queued: "queued",
      processing: "processing",
      completed: "completed",
      failed: "failed",
      unknown: "unknown",
    },
    taskMessages: {},
    sectionTitles: {},
  },
};

interface AppProps {
  initialPapers?: Paper[];
  initialReports?: Record<string, ReadingReport>;
  client?: PaperflowClient;
}

type ImportActivityStage =
  | "uploading"
  | "downloading"
  | "resolving"
  | "queued"
  | "processing"
  | "slow"
  | "completed"
  | "failed";

interface ImportActivity {
  stage: ImportActivityStage;
  title?: string;
  message?: string;
}

type ChatPanelStatus = "idle" | "running" | "completed" | "failed";

export function App({
  initialPapers = [],
  initialReports = {},
  client = defaultClient,
}: AppProps) {
  const [locale, setLocale] = useState<Locale>(readInitialLocale);
  const text = UI_TEXT[locale];
  const [papers, setPapers] = useState(initialPapers);
  const [reports, setReports] = useState(initialReports);
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null);
  const [status, setStatus] = useState(UI_TEXT.en.readyStatus);
  const [error, setError] = useState<string | null>(null);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [arxivInput, setArxivInput] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [importNotice, setImportNotice] = useState<string | null>(null);
  const [importActivity, setImportActivity] = useState<ImportActivity | null>(null);

  useEffect(() => {
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
    if (typeof window.localStorage?.setItem === "function") {
      window.localStorage.setItem("paperflow-locale", locale);
    }
  }, [locale]);

  useEffect(() => {
    if (initialPapers.length > 0) {
      return;
    }
    void refreshLibrary();
  }, [client, initialPapers.length]);

  async function refreshLibrary() {
    try {
      const [library, agent] = await Promise.all([
        client.listPapers(),
        client.getAgentStatus(),
      ]);
      setPapers(library);
      setAgentStatus(agent);
    } catch {
      setStatus(UI_TEXT.en.backendMissing);
    }
  }

  function acceptImportedSession(session: PaperSession) {
    setImportNotice(session.duplicate_warning ?? null);
    setImportActivity({
      stage: "queued",
      title: session.paper.title,
    });
    setPapers((current) => [
      session.paper,
      ...current.filter(
        (p) =>
          p.id !== session.paper.id &&
          p.id !== session.duplicate_of?.id &&
          p.title !== session.paper.title,
      ),
    ]);
    setSelectedPaper(session.paper);
    void pollPaper(session.paper.id);
  }

  async function handleImport(file: File) {
    setError(null);
    setStatus(UI_TEXT.en.queuedStatus);
    setImportActivity({ stage: "uploading", title: file.name });
    try {
      const session = await client.importPaper(file);
      acceptImportedSession(session);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : text.importFailed);
      setStatus(UI_TEXT.en.importFailed);
      setImportActivity({ stage: "failed", title: file.name });
    }
  }

  async function handleArxivImport() {
    const value = arxivInput.trim();
    if (!value) {
      setError(text.emptyArxiv);
      return;
    }
    setError(null);
    setStatus(UI_TEXT.en.arxivQueuedStatus);
    setImportActivity({ stage: "downloading", title: value });
    try {
      const session = await client.importArxiv(value);
      acceptImportedSession(session);
      setArxivInput("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : text.importFailed);
      setStatus(UI_TEXT.en.importFailed);
      setImportActivity({ stage: "failed", title: value });
    }
  }

  async function handleUrlImport() {
    const value = urlInput.trim();
    if (!value) {
      setError(text.emptyUrl);
      return;
    }
    setError(null);
    setStatus(UI_TEXT.en.urlQueuedStatus);
    setImportActivity({ stage: "resolving", title: value });
    try {
      const session = await client.importUrl(value);
      acceptImportedSession(session);
      setUrlInput("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : text.importFailed);
      setStatus(UI_TEXT.en.importFailed);
      setImportActivity({ stage: "failed", title: value });
    }
  }

  async function handleZoteroImport() {
    setError(null);
    setImportActivity({ stage: "resolving", title: "Zotero" });
    try {
      const result = await client.importZotero();
      if (result.imported === 0) {
        setStatus(UI_TEXT.en.zoteroEmpty);
        setImportActivity(null);
        return;
      }
      setStatus(UI_TEXT.en.zoteroImported(result.imported));
      setImportActivity({
        stage: "queued",
        message:
          locale === "zh"
            ? `已从 Zotero 接收 ${result.imported} 篇论文，正在解析。`
            : `Received ${result.imported} Zotero paper(s), parsing now.`,
      });
      await refreshLibrary();
      result.sessions.forEach((session) => {
        void pollPaper(session.paper.id);
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : text.importFailed);
      setImportActivity({ stage: "failed", title: "Zotero" });
    }
  }

  async function openPaper(paper: Paper) {
    setSelectedPaper(paper);
    if (reports[paper.id]) {
      return;
    }
    if (paper.status?.stage !== "completed") {
      void pollPaper(paper.id);
      return;
    }
    try {
      const report = await client.getReport(paper.id);
      setReports((current) => ({ ...current, [paper.id]: report }));
      if (report.paper_title) {
        updatePaperTitle(paper.id, report.paper_title);
      }
    } catch {
      setStatus(UI_TEXT.en.reportUnavailable);
    }
  }

  async function deletePaper(paper: Paper) {
    if (pendingDeleteId !== paper.id) {
      setPendingDeleteId(paper.id);
      return;
    }
    setError(null);
    try {
      await client.deletePaper(paper.id);
      setPendingDeleteId(null);
      setPapers((current) => current.filter((candidate) => candidate.id !== paper.id));
      setReports((current) => {
        const next = { ...current };
        delete next[paper.id];
        return next;
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : text.deleteFailed);
    }
  }

  async function pollPaper(paperId: string) {
    for (let attempt = 0; attempt < 240; attempt += 1) {
      const nextStatus = await client.getStatus(paperId);
      updatePaperStatus(paperId, nextStatus);
      setStatus(nextStatus.message);
      if (attempt === 0) {
        setImportActivity((current) =>
          current?.title
            ? { ...current, stage: "processing", title: current.title }
            : current,
        );
      }
      if (attempt === 20) {
        setImportActivity((current) =>
          current?.title ? { ...current, stage: "slow", title: current.title } : current,
        );
      }
      if (nextStatus.stage === "completed") {
        const report = await client.getReport(paperId);
        setReports((current) => ({ ...current, [paperId]: report }));
        if (report.paper_title) {
          updatePaperTitle(paperId, report.paper_title);
        }
        setImportActivity({
          stage: "completed",
          title: report.paper_title ?? papers.find((paper) => paper.id === paperId)?.title,
        });
        return;
      }
      if (nextStatus.stage === "failed") {
        setError(nextStatus.message);
        setImportActivity({
          stage: "failed",
          title: papers.find((paper) => paper.id === paperId)?.title,
          message: nextStatus.message,
        });
        return;
      }
      await sleep(1500);
    }
    setError(text.parseTimeout);
  }

  function updatePaperStatus(paperId: string, nextStatus: TaskStatus) {
    setPapers((current) =>
      current.map((paper) =>
        paper.id === paperId ? { ...paper, status: nextStatus } : paper,
      ),
    );
    setSelectedPaper((current) =>
      current?.id === paperId ? { ...current, status: nextStatus } : current,
    );
  }

  async function rerunPaper(paperId: string) {
    const session = await client.rerunAgent(paperId);
    updatePaperStatus(paperId, session.status);
    setReports((current) => {
      const next = { ...current };
      delete next[paperId];
      return next;
    });
    void pollPaper(paperId);
  }

  function updatePaperNote(paperId: string, notePath: string) {
    setPapers((current) =>
      current.map((paper) =>
        paper.id === paperId ? { ...paper, note_path: notePath } : paper,
      ),
    );
    setSelectedPaper((current) =>
      current?.id === paperId ? { ...current, note_path: notePath } : current,
    );
  }

  function updatePaperTitle(paperId: string, title: string) {
    setPapers((current) =>
      current.map((paper) =>
        paper.id === paperId ? { ...paper, title } : paper,
      ),
    );
    setSelectedPaper((current) =>
      current?.id === paperId ? { ...current, title } : current,
    );
  }

  if (selectedPaper) {
    return (
      <Workspace
        client={client}
        onBack={() => setSelectedPaper(null)}
        locale={locale}
        agentStatus={agentStatus}
        importActivity={importActivity}
        importNotice={importNotice}
        onLocaleToggle={() => setLocale(locale === "zh" ? "en" : "zh")}
        onNoteSaved={(notePath) => updatePaperNote(selectedPaper.id, notePath)}
        onRerun={() => void rerunPaper(selectedPaper.id)}
        paper={selectedPaper}
        report={reports[selectedPaper.id]}
      />
    );
  }

  const displayedStatus = buildLibraryStatus(papers, status, locale);

  return (
    <main className="home">
      <TopNav
        agentStatus={agentStatus}
        locale={locale}
        mode="home"
        onLocaleToggle={() => setLocale(locale === "zh" ? "en" : "zh")}
      />
      <header className="masthead">
        <div>
          <p className="eyebrow">{text.eyebrow}</p>
          <h1 className="masthead-title">{text.libraryTitle}</h1>
          <p className="masthead-standfirst">{text.heroDescription}</p>
        </div>
      </header>

      <section className="import-drawer" id="import">
        <div className="import-drawer-head">
          <h2 className="label-section">{text.importsLabel}</h2>
        </div>
        <div className="import-grid">
          <div className="import-field import-field-pdf">
            <h3 className="import-field-title">{text.importPdf}</h3>
            <p className="import-field-hint">{text.importPdfHint}</p>
            <input
              aria-label={text.importPdf}
              accept="application/pdf"
              type="file"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  void handleImport(file);
                }
              }}
            />
          </div>

          <div className="import-field">
            <h3 className="import-field-title">{text.arxivImportTitle}</h3>
            <p className="import-field-hint">{text.arxivPlaceholder}</p>
            <div className="import-row">
              <input
                aria-label={text.arxivImportTitle}
                placeholder={text.arxivPlaceholder}
                value={arxivInput}
                onChange={(event) => setArxivInput(event.target.value)}
              />
              <button
                type="button"
                className="btn-ghost"
                onClick={() => void handleArxivImport()}
              >
                {text.importArxiv}
              </button>
            </div>
          </div>

          <div className="import-field">
            <h3 className="import-field-title">{text.urlImportTitle}</h3>
            <p className="import-field-hint">{text.urlPlaceholder}</p>
            <div className="import-row">
              <input
                aria-label={text.urlImportTitle}
                placeholder={text.urlPlaceholder}
                value={urlInput}
                onChange={(event) => setUrlInput(event.target.value)}
              />
              <button
                type="button"
                className="btn-ghost"
                onClick={() => void handleUrlImport()}
              >
                {text.importUrl}
              </button>
            </div>
          </div>

          <div className="import-field">
            <h3 className="import-field-title">{text.zoteroImportTitle}</h3>
            <p className="import-field-hint mono">{text.zoteroPath}</p>
            <div className="import-row">
              <button
                type="button"
                className="btn-ghost"
                onClick={() => void handleZoteroImport()}
              >
                {text.zoteroImportButton}
              </button>
            </div>
          </div>
        </div>
      </section>

      {error ? <p className="warning-line">{error}</p> : null}
      {importNotice ? <p className="notice-line">{importNotice}</p> : null}
      <ImportActivityBanner activity={importActivity} locale={locale} />

      <section className="paper-section" id="papers">
        <div className="paper-section-head">
          <h2 className="label-section">{text.recentPapers}</h2>
          <span className="count">{text.paperCount(papers.length)}</span>
        </div>
        {papers.length === 0 ? (
          <p className="paper-list-empty">
            {locale === "zh"
              ? "文献库还是空的。导入第一篇 PDF / arXiv / URL 开始。"
              : "Library is empty. Import a PDF, arXiv link, or URL to begin."}
          </p>
        ) : (
          <ol className="paper-list">
            {papers.map((paper, idx) => (
              <li className="paper-row" key={paper.id}>
                <span className="paper-ord">
                  {String(idx + 1).padStart(2, "0")}
                </span>
                <div className="paper-body">
                  <h3 className="paper-title">{paper.title}</h3>
                  <PaperMetadataLine paper={paper} />
                  <p className="paper-path">{paper.pdf_path}</p>
                  <PaperProcessingLine locale={locale} paper={paper} />
                  {paper.note_path ? (
                    <p className="paper-note-line">
                      {text.notePrefix} <span className="mono">{paper.note_path}</span>
                    </p>
                  ) : null}
                </div>
                <div className="paper-actions">
                  <StatusBadge locale={locale} status={paper.status} />
                  <button
                    type="button"
                    className={`btn-secondary ${pendingDeleteId === paper.id ? "is-danger" : ""}`}
                    aria-label={
                      pendingDeleteId === paper.id
                        ? text.confirmDeletePaper(paper.title)
                        : text.deletePaper(paper.title)
                    }
                    onClick={() => void deletePaper(paper)}
                  >
                    {pendingDeleteId === paper.id
                      ? text.confirmDeletePaperAction
                      : text.deletePaperAction}
                  </button>
                  <button
                    type="button"
                    className="btn-primary"
                    aria-label={text.openPaper(paper.title)}
                    onClick={() => void openPaper(paper)}
                  >
                    {text.openPaperAction}
                  </button>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      <footer className="footer-strip">
        <div className="footer-block">
          <h2 className="label-section">{text.processingStatus}</h2>
          <p>{displayedStatus}</p>
        </div>
        <div className="footer-block">
          <h2 className="label-section">{text.savedReports}</h2>
          <ul className="saved-reports-list">
            {papers.length === 0 ? (
              <li className="empty">{text.noNote}</li>
            ) : (
              papers.map((paper) => (
                <li
                  key={paper.id}
                  className={paper.note_path ? "" : "empty"}
                >
                  <span className="saved-report-title">{paper.title}</span>
                  <span className="saved-report-path">
                    {paper.note_path ?? text.noNote}
                  </span>
                </li>
              ))
            )}
          </ul>
        </div>
      </footer>
    </main>
  );
}

/* ============================================================================
   Workspace
   ============================================================================ */

function TopNav({
  agentStatus,
  currentTitle,
  locale,
  mode,
  onBack,
  onLocaleToggle,
}: {
  agentStatus: AgentStatus | null;
  currentTitle?: string;
  locale: Locale;
  mode: "home" | "workspace";
  onBack?: () => void;
  onLocaleToggle: () => void;
}) {
  const text = UI_TEXT[locale];
  return (
    <nav className="top-nav" aria-label={locale === "zh" ? "全局导航" : "Global navigation"}>
      <div className="top-nav-brand">
        <a href={mode === "home" ? "#import" : "#report"}>Paperflow</a>
        <span>{mode === "home" ? text.librarySection : (currentTitle ?? text.readingReport)}</span>
      </div>
      <div className="top-nav-links">
        {mode === "workspace" && onBack ? (
          <button type="button" className="top-nav-back" onClick={onBack}>
            {text.backToLibrary}
          </button>
        ) : null}
        {mode === "home" ? (
          <>
            <a href="#import">{text.navImport}</a>
            <a href="#papers">{text.navPapers}</a>
          </>
        ) : (
          <>
            <a href="#report">{text.navReport}</a>
            <a href="#field-map">{text.navFieldMap}</a>
          </>
        )}
        <span
          className={`agent-chip ${agentStatus?.configured ? "ready" : "missing"}`}
        >
          {text.agentLabel} ·{" "}
          {agentStatus?.configured
            ? `${text.configured} (${agentStatus.mode})`
            : text.missingKey}
        </span>
        <button type="button" className="language-toggle" onClick={onLocaleToggle}>
          {text.languageToggle}
        </button>
      </div>
    </nav>
  );
}

function Workspace({
  paper,
  report,
  client,
  locale,
  agentStatus,
  importActivity,
  importNotice,
  onLocaleToggle,
  onNoteSaved,
  onRerun,
  onBack,
}: {
  paper: Paper;
  report?: ReadingReport;
  client: PaperflowClient;
  locale: Locale;
  agentStatus: AgentStatus | null;
  importActivity: ImportActivity | null;
  importNotice?: string | null;
  onLocaleToggle: () => void;
  onNoteSaved: (notePath: string) => void;
  onRerun: () => void;
  onBack: () => void;
}) {
  const text = UI_TEXT[locale];
  const displayTitle = report?.paper_title ?? paper.title;
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState<PaperChatResponse | null>(null);
  const [chatStatus, setChatStatus] = useState<ChatPanelStatus>("idle");
  const [notePath, setNotePath] = useState<string | null>(paper.note_path ?? null);
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(
    report?.summary[0] ?? null,
  );
  const [pdfViewerOpen, setPdfViewerOpen] = useState(false);
  const [pdfPage, setPdfPage] = useState(1);
  const [r1Running, setR1Running] = useState(false);
  const [r1Error, setR1Error] = useState<string | null>(null);
  const [r1Trace, setR1Trace] = useState<R1QueryTraceEntry[]>([]);
  const [relatedOverride, setRelatedOverride] = useState<RelatedWorkItem[] | null>(
    null,
  );
  const [fieldMap, setFieldMap] = useState<FieldMap | null>(null);
  const [fieldMapRunning, setFieldMapRunning] = useState(false);
  const [fieldMapError, setFieldMapError] = useState<string | null>(null);

  const isReportReady = paper.status?.stage === "completed";
  const pdfUrl = useMemo(() => client.pdfUrl(paper.id), [client, paper.id]);

  useEffect(() => {
    if (!selectedClaim && report?.summary[0]) {
      setSelectedClaim(report.summary[0]);
    }
  }, [report, selectedClaim]);

  // When the user selects a claim, jump the PDF viewer to the first evidence
  // page so the highlight is immediately visible.
  useEffect(() => {
    const firstEvidence = selectedClaim?.evidence?.[0];
    if (firstEvidence?.page) {
      setPdfPage(firstEvidence.page);
    }
  }, [selectedClaim]);

  const highlight: PdfBboxHighlight | null = (() => {
    const first = selectedClaim?.evidence?.[0];
    if (!first?.page || !first.bbox) return null;
    return { page: first.page, bbox: first.bbox };
  })();

  async function askAgentChat() {
    if (!question.trim()) {
      return;
    }
    const firstEvidence = selectedClaim?.evidence?.[0];
    const userQuestion = question;
    setQuestion("");
    setChatStatus("running");
    setChat({
      id: `local-${Date.now()}`,
      paper_id: paper.id,
      status: "running",
      steps: [
        { id: "read-report", label: "Read report", status: "running" },
        { id: "locate-evidence", label: "Locate evidence", status: "pending" },
        { id: "check-r1", label: "Check R1 context", status: "pending" },
        { id: "compose-answer", label: "Compose answer", status: "pending" },
      ],
      messages: [{ id: `user-${Date.now()}`, role: "user", content: userQuestion }],
      answer: {
        id: "pending",
        text: "",
        reliability: "R2",
        evidence: [],
      },
    });
    try {
      const result = await client.chatPaper(paper.id, {
        question: userQuestion,
        selected_claim_id: selectedClaim?.id ?? null,
        selected_evidence_id: firstEvidence?.id ?? null,
        page: firstEvidence?.page ?? null,
        quote: firstEvidence?.quote ?? null,
        section: firstEvidence?.section ?? null,
      });
      setChat(result);
      setChatStatus("completed");
    } catch {
      setChatStatus("failed");
      setChat((current) =>
        current
          ? {
              ...current,
              status: "failed",
              steps: current.steps.map((step) =>
                step.status === "running" ? { ...step, status: "failed" } : step,
              ),
            }
          : null,
      );
    }
  }

  async function askSelection(quote: string, page: number) {
    if (!quote.trim()) return;
    try {
      const result = await client.askSelection(paper.id, { quote, page });
      setChat({
        id: `selection-${Date.now()}`,
        paper_id: paper.id,
        status: "completed",
        steps: [
          { id: "read-report", label: "Read report", status: "completed" },
          { id: "locate-evidence", label: "Locate evidence", status: "completed" },
          { id: "compose-answer", label: "Compose answer", status: "completed" },
        ],
        messages: [
          { id: `user-selection-${Date.now()}`, role: "user", content: quote },
          {
            id: `assistant-selection-${Date.now()}`,
            role: "assistant",
            content: result.text,
            reliability: result.reliability,
            evidence: result.evidence,
            uncertainty: result.uncertainty,
          },
        ],
        answer: result,
      });
      setChatStatus("completed");
    } catch {
      /* swallow */
    }
  }

  async function exportNote() {
    const result = await client.exportObsidian(paper.id);
    setNotePath(result.note_path);
    onNoteSaved(result.note_path);
  }

  async function runR1Search() {
    setR1Running(true);
    setR1Error(null);
    try {
      const result = await client.runR1Search(paper.id);
      setRelatedOverride(result.items);
      setR1Trace(result.query_trace || []);
    } catch (caught) {
      setR1Error(
        caught instanceof Error ? caught.message : "R1 search failed",
      );
    } finally {
      setR1Running(false);
    }
  }

  async function buildFieldMap() {
    setFieldMapRunning(true);
    setFieldMapError(null);
    try {
      const fm = fieldMap
        ? await client.rerunFieldMap(fieldMap.id)
        : await client.createFieldMap(paper.id);
      setFieldMap(fm);
    } catch (caught) {
      setFieldMapError(
        caught instanceof Error ? caught.message : "Field Map failed",
      );
    } finally {
      setFieldMapRunning(false);
    }
  }

  if (!report) {
    return (
      <main className="workspace">
        <TopNav
          agentStatus={agentStatus}
          currentTitle={displayTitle}
          locale={locale}
          mode="workspace"
          onBack={onBack}
          onLocaleToggle={onLocaleToggle}
        />
        <section className="workspace-main">
          {importNotice ? <p className="notice-line">{importNotice}</p> : null}
          <ImportActivityBanner activity={importActivity} locale={locale} />
          <div className="empty-report">
            <h2 className="eyebrow">{text.readingReport}</h2>
            <h1>{displayTitle}</h1>
            <StatusBadge locale={locale} status={paper.status} />
            <p>
              {paper.status?.message
                ? localizeTaskMessage(paper.status.message, locale)
                : text.reportNotReady}
            </p>
          </div>
        </section>
        <Rail
          chat={chat}
          chatStatus={chatStatus}
          locale={locale}
          notePath={notePath}
          onAsk={askAgentChat}
          onExport={exportNote}
          onQuestionChange={setQuestion}
          onRerun={onRerun}
          paper={paper}
          question={question}
          selectedClaim={selectedClaim}
        />
      </main>
    );
  }

  const related = relatedOverride ?? report.related_work;

  return (
    <main className="workspace">
      <TopNav
        agentStatus={agentStatus}
        currentTitle={displayTitle}
        locale={locale}
        mode="workspace"
        onBack={onBack}
        onLocaleToggle={onLocaleToggle}
      />
      <section className="workspace-main">
        {importNotice ? <p className="notice-line">{importNotice}</p> : null}
        <ImportActivityBanner activity={importActivity} locale={locale} />

        <header className="report-head" id="report">
          <h2 className="eyebrow">{text.readingReport}</h2>
          <h1>{displayTitle}</h1>
          <p className="path-line">{paper.pdf_path}</p>
          <div className="report-head-tools">
            <StatusBadge locale={locale} status={paper.status} />
            {isReportReady ? (
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setPdfViewerOpen((v) => !v)}
              >
                {pdfViewerOpen ? text.disableViewer : text.enableViewer}
              </button>
            ) : null}
          </div>
        </header>

        {pdfViewerOpen && isReportReady ? (
          <section className="pdf-viewer-shell">
            <PdfViewer
              pdfUrl={pdfUrl}
              page={pdfPage}
              highlight={highlight}
              onPageChange={setPdfPage}
              onSelection={(quote, page) => void askSelection(quote, page)}
            />
          </section>
        ) : null}

        {report.summary.length > 0 ? (
          <section className="report-section">
            <div className="section-head">
              <h3>{text.executiveSummary}</h3>
            </div>
            <ol className="claim-list">
              {report.summary.map((claim, idx) => (
                <ClaimItem
                  claim={claim}
                  key={claim.id}
                  locale={locale}
                  ord={idx + 1}
                  selected={selectedClaim?.id === claim.id}
                  onSelect={setSelectedClaim}
                />
              ))}
            </ol>
          </section>
        ) : null}

        {report.sections.map((section) => (
          <section className="report-section" key={section.id}>
            <div className="section-head">
              <h3>{localizeSectionTitle(section.title, locale)}</h3>
            </div>
            <ol className="claim-list">
              {section.claims.map((claim, idx) => (
                <ClaimItem
                  claim={claim}
                  key={claim.id}
                  locale={locale}
                  ord={idx + 1}
                  selected={selectedClaim?.id === claim.id}
                  onSelect={setSelectedClaim}
                />
              ))}
            </ol>
          </section>
        ))}

        <section className="report-section">
          <div className="section-head">
            <h3>{text.relatedWork}</h3>
            <div className="section-head-actions">
              <button
                type="button"
                className="btn-ghost"
                onClick={() => void runR1Search()}
                disabled={r1Running}
              >
                {r1Running ? text.r1Running : text.r1RunSearch}
              </button>
            </div>
          </div>
          {r1Error ? (
            <p className="warning-line">
              {text.r1Failed}
              {r1Error}
            </p>
          ) : null}
          <ol className="related-list">
            {related.map((item, idx) => (
              <RelatedItem
                item={item}
                key={item.id}
                locale={locale}
                ord={idx + 1}
              />
            ))}
          </ol>
          {r1Trace.length > 0 ? (
            <details className="r1-trace">
              <summary>{text.r1QueryTrace}</summary>
              <ul>
                {r1Trace.map((entry, idx) => (
                  <li key={`${entry.lane}-${idx}`}>
                    <code>
                      [{entry.lane}/{entry.source}]
                    </code>
                    <span>{entry.query}</span>
                    <span className="trace-count">{entry.count}</span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </section>

        <FieldMapSection
          fieldMap={fieldMap}
          running={fieldMapRunning}
          error={fieldMapError}
          locale={locale}
          onGenerate={() => void buildFieldMap()}
        />
      </section>

      <Rail
        chat={chat}
        chatStatus={chatStatus}
        locale={locale}
        notePath={notePath}
        onAsk={askAgentChat}
        onExport={exportNote}
        onQuestionChange={setQuestion}
        onRerun={onRerun}
        paper={paper}
        question={question}
        selectedClaim={selectedClaim}
      />
    </main>
  );
}

/* ============================================================================
   Pieces
   ============================================================================ */

function ImportActivityBanner({
  activity,
  locale,
}: {
  activity: ImportActivity | null;
  locale: Locale;
}) {
  if (!activity) {
    return null;
  }
  const message = importActivityMessage(activity, locale);
  return (
    <section className={`import-activity is-${activity.stage}`} aria-live="polite">
      <div>
        <p className="label-section">
          {locale === "zh" ? "处理反馈" : "Processing Feedback"}
        </p>
        <p className="import-activity-message">{message}</p>
      </div>
      <span className="import-activity-pulse" aria-hidden="true" />
    </section>
  );
}

function PaperProcessingLine({
  paper,
  locale,
}: {
  paper: Paper;
  locale: Locale;
}) {
  if (!paper.status || paper.status.stage === "completed") {
    return null;
  }
  const progress = Math.max(0, Math.min(100, Math.round((paper.status.progress ?? 0) * 100)));
  return (
    <div className="paper-processing-line">
      <span>{localizeTaskMessage(paper.status.message, locale)}</span>
      <span className="mono">{progress}%</span>
      <span className="paper-progress-track" aria-hidden="true">
        <span style={{ width: `${progress}%` }} />
      </span>
    </div>
  );
}

function ClaimItem({
  claim,
  locale,
  ord,
  onSelect,
  selected = false,
}: {
  claim: Claim;
  locale: Locale;
  ord: number;
  onSelect?: (claim: Claim) => void;
  selected?: boolean;
}) {
  const text = UI_TEXT[locale];
  return (
    <li className={`claim-item ${selected ? "selected" : ""}`}>
      <span className="claim-ord">{String(ord).padStart(2, "0")}</span>
      <div className="claim-body">
        <p className="claim-text">
          <span className={`badge ${claim.reliability.toLowerCase()}`}>
            {claim.reliability}
          </span>{" "}
          {claim.text}
        </p>
        {claim.uncertainty ? (
          <p className="claim-uncertainty">{claim.uncertainty}</p>
        ) : null}
      </div>
      <div className="claim-actions">
        <button
          type="button"
          className="btn-link"
          onClick={() => onSelect?.(claim)}
        >
          {text.evidenceButton(claim.evidence.length)}
        </button>
      </div>
    </li>
  );
}

function RelatedItem({
  item,
  locale,
  ord,
}: {
  item: RelatedWorkItem;
  locale: Locale;
  ord: number;
}) {
  const text = UI_TEXT[locale];
  return (
    <li className="related-item">
      <span className="paper-ord">{String(ord).padStart(2, "0")}</span>
      <div className="related-body">
        <h4 className="related-title">
          <span className={`badge ${item.reliability.toLowerCase()}`}>
            {item.reliability}
          </span>
          {item.title}
        </h4>
        <RelatedMetaLine item={item} locale={locale} />
        <p className="related-relation">{item.relation}</p>
        {item.evidence?.[0]?.quote ? (
          <p className="related-tldr">{item.evidence[0].quote}</p>
        ) : null}
        <p className="related-source">{item.source}</p>
        {item.comparison_risk ? (
          <p className="warning small">
            {text.r1ComparisonRisk}
            {item.comparison_risk}
          </p>
        ) : null}
      </div>
    </li>
  );
}

function Rail({
  chat,
  chatStatus,
  locale,
  notePath,
  onAsk,
  onExport,
  onQuestionChange,
  onRerun,
  paper,
  question,
  selectedClaim,
}: {
  chat: PaperChatResponse | null;
  chatStatus: ChatPanelStatus;
  locale: Locale;
  notePath: string | null;
  onAsk: () => Promise<void>;
  onExport: () => Promise<void>;
  onQuestionChange: (question: string) => void;
  onRerun: () => void;
  paper: Paper;
  question: string;
  selectedClaim: Claim | null;
}) {
  const text = UI_TEXT[locale];
  return (
    <aside className="workspace-rail">
      <section className="rail-block">
        <p className="label-section">{text.agentStatus}</p>
        <StatusBadge locale={locale} status={paper.status} />
        <p className="rail-message">
          {paper.status?.message
            ? localizeTaskMessage(paper.status.message, locale)
            : text.noActiveTask}
        </p>
        <button type="button" className="btn-link" onClick={onRerun}>
          {text.rerunAgent}
        </button>
      </section>

      <section className="rail-block">
        <p className="label-section">{text.evidenceDetail}</p>
        {selectedClaim ? (
          <>
            <p className="rail-evidence-claim">{selectedClaim.text}</p>
            {selectedClaim.evidence.length > 0 ? (
              <div className="rail-evidence">
                {selectedClaim.evidence.map((evidence) => (
                  <div className="evidence-block" key={evidence.id}>
                    <p className="evidence-quote">{evidence.quote}</p>
                    <p className="evidence-meta">
                      <span>{evidence.source}</span>
                      {evidence.page ? (
                        <span>{text.page(evidence.page)}</span>
                      ) : null}
                      {evidence.section ? <span>{evidence.section}</span> : null}
                      <LocationGlyph evidence={evidence} locale={locale} />
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="rail-message warning">{text.missingEvidence}</p>
            )}
          </>
        ) : (
          <p className="rail-message muted-soft">{text.selectClaim}</p>
        )}
      </section>

      <section className="rail-block agent-chat">
        <div className="agent-chat-head">
          <p className="label-section">{text.agentChat}</p>
          <span className={`agent-chat-status is-${chatStatus}`}>
            {chatStatus === "running"
              ? text.chatRunning
              : chatStatus === "completed"
                ? text.chatCompleted
                : chatStatus === "failed"
                  ? text.chatFailed
                  : text.chatIdle}
          </span>
        </div>
        {chat ? (
          <>
            <div className="agent-process" aria-label={text.processCards}>
              {chat.steps.map((step) => (
                <div className={`agent-process-card is-${step.status}`} key={step.id}>
                  <span className="agent-process-dot" aria-hidden="true" />
                  <div>
                    <p>{step.label}</p>
                    {step.detail ? <span>{step.detail}</span> : null}
                  </div>
                </div>
              ))}
            </div>
            <div className="agent-transcript">
              {chat.messages.map((message) => (
                <article className={`agent-message is-${message.role}`} key={message.id}>
                  <p className="agent-message-role">
                    {message.role === "user" ? "You" : "Agent"}
                    {message.reliability ? (
                      <span className={`badge ${message.reliability.toLowerCase()}`}>
                        {message.reliability}
                      </span>
                    ) : null}
                  </p>
                  <p>{message.content}</p>
                  {message.evidence && message.evidence.length > 0 ? (
                    <p className="agent-message-evidence">
                      {message.evidence[0].quote}
                    </p>
                  ) : null}
                </article>
              ))}
            </div>
          </>
        ) : (
          <p className="rail-message muted-soft">{text.chatIdle}</p>
        )}
        <div className="agent-composer">
          <input
            placeholder={text.askPlaceholder}
            value={question}
            onChange={(event) => onQuestionChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                void onAsk();
              }
            }}
          />
          <button
            type="button"
            className="btn-link"
            disabled={!question.trim() || chatStatus === "running"}
            onClick={() => void onAsk()}
          >
            {text.ask}
          </button>
        </div>
      </section>

      <section className="rail-block">
        <p className="label-section">{text.obsidian}</p>
        <button
          type="button"
          className="btn-link"
          onClick={() => void onExport()}
        >
          {text.saveNote}
        </button>
        {notePath ? (
          <p className="rail-saved">{text.savedTo(notePath)}</p>
        ) : (
          <p className="rail-message muted-soft">{text.noNote}</p>
        )}
      </section>
    </aside>
  );
}

function StatusBadge({
  status,
  locale,
}: {
  status?: TaskStatus;
  locale: Locale;
}) {
  const stage = status?.stage ?? "unknown";
  const text = UI_TEXT[locale];
  const label =
    text.statusLabels[stage as keyof typeof text.statusLabels] ?? stage;
  return <span className={`status-badge ${stage}`}>{label}</span>;
}

function LocationGlyph({
  evidence,
  locale,
}: {
  evidence: Evidence;
  locale: Locale;
}) {
  const text = UI_TEXT[locale];
  const status =
    evidence.location_status ?? (evidence.page ? "page_and_quote" : "quote_only");
  const labels: Record<string, string> = {
    exact: text.locationExact,
    page_and_quote: text.locationPageQuote,
    quote_only: text.locationQuoteOnly,
    missing: text.locationMissing,
  };
  return (
    <span className={`location-glyph location-${status}`}>
      {labels[status] ?? status}
    </span>
  );
}

function RelatedMetaLine({
  item,
  locale,
}: {
  item: RelatedWorkItem;
  locale: Locale;
}) {
  const text = UI_TEXT[locale];
  const parts: { key: string; node: React.ReactNode }[] = [];
  const authors = item.authors ?? [];
  if (authors.length > 0) {
    const head = authors.slice(0, 3).join(", ");
    parts.push({
      key: "authors",
      node: <span>{authors.length > 3 ? `${head}, et al.` : head}</span>,
    });
  }
  if (item.year) {
    parts.push({ key: "year", node: <span className="mono">{item.year}</span> });
  }
  if (item.venue) {
    parts.push({ key: "venue", node: <span>{item.venue}</span> });
  }
  if (item.citation_count != null) {
    parts.push({
      key: "cites",
      node: <span className="mono">{text.r1CitedBy(item.citation_count)}</span>,
    });
  }
  if (item.influential_citation_count != null) {
    parts.push({
      key: "influence",
      node: (
        <span className="mono">
          {text.r1InfluentialCitedBy(item.influential_citation_count)}
        </span>
      ),
    });
  }
  if (item.arxiv_id) {
    parts.push({
      key: "arxiv",
      node: <span className="mono">arXiv:{item.arxiv_id}</span>,
    });
  }
  if (item.doi) {
    parts.push({
      key: "doi",
      node: <span className="mono">DOI:{item.doi}</span>,
    });
  }
  if (parts.length === 0) {
    return null;
  }
  return (
    <p className="meta-line">
      {parts.map((part) => (
        <span key={part.key}>{part.node}</span>
      ))}
    </p>
  );
}

function PaperMetadataLine({ paper }: { paper: Paper }) {
  const metadata = paper.metadata ?? null;
  if (!metadata) {
    return null;
  }
  const parts: { key: string; node: React.ReactNode }[] = [];
  const authors = metadata.authors ?? [];
  if (authors.length > 0) {
    const head = authors.slice(0, 3).join(", ");
    parts.push({
      key: "authors",
      node: <span>{authors.length > 3 ? `${head}, et al.` : head}</span>,
    });
  }
  if (metadata.year) {
    parts.push({
      key: "year",
      node: <span className="mono">{metadata.year}</span>,
    });
  }
  if (metadata.venue) {
    parts.push({ key: "venue", node: <span>{metadata.venue}</span> });
  }
  if (metadata.arxiv_id) {
    parts.push({
      key: "arxiv",
      node: <span className="mono">arXiv:{metadata.arxiv_id}</span>,
    });
  }
  if (metadata.doi) {
    parts.push({
      key: "doi",
      node: <span className="mono">DOI:{metadata.doi}</span>,
    });
  }
  if (metadata.source_type && metadata.source_type !== "local_pdf") {
    parts.push({
      key: "source",
      node: <span className="mono">{metadata.source_type}</span>,
    });
  }
  if (parts.length === 0) {
    return null;
  }
  return (
    <p className="meta-line">
      {parts.map((part) => (
        <span key={part.key}>{part.node}</span>
      ))}
    </p>
  );
}

/* ============================================================================
   Field Map
   ============================================================================ */

function FieldMapSection({
  fieldMap,
  running,
  error,
  locale,
  onGenerate,
}: {
  fieldMap: FieldMap | null;
  running: boolean;
  error: string | null;
  locale: Locale;
  onGenerate: () => void;
}) {
  const text = UI_TEXT[locale];
  return (
    <section className="report-section field-map-section" id="field-map">
      <div className="section-head">
        <h3>{text.fieldMapTitle}</h3>
        <div className="section-head-actions">
          <button
            type="button"
            className="btn-ghost"
            onClick={onGenerate}
            disabled={running}
          >
            {running
              ? text.fieldMapRunning
              : fieldMap
                ? text.fieldMapRegenerate
                : text.fieldMapGenerate}
          </button>
        </div>
      </div>
      {error ? (
        <p className="warning-line">
          {text.fieldMapFailed}
          {error}
        </p>
      ) : null}
      {!fieldMap ? <p className="field-map-empty">{text.fieldMapEmpty}</p> : null}
      {fieldMap ? <FieldMapBody fieldMap={fieldMap} locale={locale} /> : null}
    </section>
  );
}

function FieldMapBody({
  fieldMap,
  locale,
}: {
  fieldMap: FieldMap;
  locale: Locale;
}) {
  const text = UI_TEXT[locale];
  return (
    <>
      <div className="field-map-body">
        {fieldMap.field_summary ? (
          <article className="field-map-summary">
            <h4>{text.fieldMapSummary}</h4>
            <p>{fieldMap.field_summary}</p>
          </article>
        ) : (
          <article className="field-map-summary">
            <h4>{text.fieldMapSummary}</h4>
            <p className="muted-soft">{text.fieldMapEmpty}</p>
          </article>
        )}

        <div className="field-map-taxa">
          <FieldMapTaxon
            label={text.fieldMapTaskTaxonomy}
            items={fieldMap.task_taxonomy}
          />
          <FieldMapTaxon
            label={text.fieldMapDatasets}
            items={fieldMap.datasets_benchmarks}
          />
          <FieldMapTaxon label={text.fieldMapMetrics} items={fieldMap.metrics} />
          <FieldMapTaxon
            label={text.fieldMapMethodFamilies}
            items={fieldMap.method_families}
          />
        </div>
      </div>

      {fieldMap.relationship_graph?.nodes.length ? (
        <RelationshipGraph graph={fieldMap.relationship_graph} locale={locale} />
      ) : null}

      {fieldMap.milestones.length > 0 ? (
        <article className="field-map-milestones">
          <h4>{text.fieldMapMilestones}</h4>
          <ol className="milestone-list">
            {fieldMap.milestones.map((ms, idx) => (
              <MilestoneItem
                key={ms.id}
                milestone={ms}
                ord={idx + 1}
                locale={locale}
              />
            ))}
          </ol>
        </article>
      ) : null}

      {fieldMap.timeline.length > 0 ? (
        <article className="field-map-timeline-wrap">
          <h4>{text.fieldMapTimeline}</h4>
          <ol className="timeline-list">
            {fieldMap.timeline.map((event) => (
              <TimelineItem key={event.id} event={event} />
            ))}
          </ol>
        </article>
      ) : null}

      {fieldMap.open_problems.length > 0 ? (
        <PullList
          title={text.fieldMapOpenProblems}
          claims={fieldMap.open_problems}
        />
      ) : null}
      {fieldMap.recent_trends.length > 0 ? (
        <PullList
          title={text.fieldMapRecentTrends}
          claims={fieldMap.recent_trends}
        />
      ) : null}
      {fieldMap.research_opportunities.length > 0 ? (
        <PullList
          title={text.fieldMapOpportunities}
          claims={fieldMap.research_opportunities}
        />
      ) : null}
    </>
  );
}

function RelationshipGraph({
  graph,
  locale,
}: {
  graph: FieldMapRelationshipGraph;
  locale: Locale;
}) {
  const text = UI_TEXT[locale];
  const nodes = graph.nodes.slice(0, 12);
  const columns = {
    predecessor: nodes.filter((node) => node.role === "predecessor"),
    seed: nodes.filter((node) => node.role === "seed"),
    successor: nodes.filter((node) => node.role !== "predecessor" && node.role !== "seed"),
  };
  const columnDefs = [
    { key: "predecessor", label: text.fieldMapGraphPredecessor, x: 92, nodes: columns.predecessor },
    { key: "seed", label: text.fieldMapGraphSeed, x: 360, nodes: columns.seed },
    { key: "successor", label: text.fieldMapGraphSuccessor, x: 628, nodes: columns.successor },
  ];
  const positions = new Map<string, { x: number; y: number }>();
  columnDefs.forEach((column) => {
    const count = Math.max(1, column.nodes.length);
    column.nodes.forEach((node, idx) => {
      const y = 78 + ((idx + 1) * 220) / (count + 1);
      positions.set(node.id, { x: column.x, y });
    });
  });

  return (
    <article className="relationship-graph-wrap">
      <h4>{text.fieldMapRelationshipGraph}</h4>
      <div className="relationship-graph" aria-label={text.fieldMapRelationshipGraph}>
        <svg viewBox="0 0 720 340">
          <defs>
            <marker
              id="graph-arrow"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" />
            </marker>
          </defs>
          {columnDefs.map((column) => (
            <text key={column.key} className="relationship-column-label" x={column.x} y="28">
              {column.label}
            </text>
          ))}
          {graph.edges.map((edge) => {
            const source = positions.get(edge.source);
            const target = positions.get(edge.target);
            if (!source || !target) return null;
            const mid = (source.x + target.x) / 2;
            return (
              <path
                key={edge.id}
                className="relationship-edge"
                d={`M ${source.x + 44} ${source.y} C ${mid} ${source.y}, ${mid} ${target.y}, ${target.x - 44} ${target.y}`}
                markerEnd="url(#graph-arrow)"
              />
            );
          })}
          {nodes.map((node) => {
            const pos = positions.get(node.id);
            if (!pos) return null;
            const reliability = node.reliability ?? "R1";
            const roleLabel = relationshipRoleLabel(node.role, locale);
            const tooltipX = pos.x < 360 ? pos.x + 46 : pos.x - 266;
            const tooltipY = Math.max(42, pos.y - 54);
            const tooltipLabel = `${node.title} · ${roleLabel}${
              node.year ? ` · ${node.year}` : ""
            } · ${reliability}`;
            return (
              <g
                key={node.id}
                aria-label={tooltipLabel}
                className={`relationship-node relationship-node-${node.role}`}
                role="img"
                tabIndex={0}
              >
                <title>{tooltipLabel}</title>
                <circle cx={pos.x} cy={pos.y} r="34" />
                <text className="relationship-node-year" x={pos.x} y={pos.y - 6}>
                  {node.year ?? "seed"}
                </text>
                <text className="relationship-node-kind" x={pos.x} y={pos.y + 12}>
                  {node.event_type.replace("_", " ")}
                </text>
                <foreignObject
                  className="relationship-tooltip"
                  height="96"
                  width="220"
                  x={tooltipX}
                  y={tooltipY}
                >
                  <div className="relationship-tooltip-card">
                    <p className="relationship-tooltip-title">{node.title}</p>
                    <p className="relationship-tooltip-meta">
                      <span>{roleLabel}</span>
                      {node.year ? <span>{node.year}</span> : null}
                      <span>{reliability}</span>
                    </p>
                  </div>
                </foreignObject>
              </g>
            );
          })}
        </svg>
        <ol className="relationship-node-list">
          {nodes.map((node) => (
            <RelationshipNodeRow key={node.id} node={node} />
          ))}
        </ol>
      </div>
    </article>
  );
}

function relationshipRoleLabel(role: string, locale: Locale) {
  const text = UI_TEXT[locale];
  if (role === "predecessor") return text.fieldMapGraphPredecessor;
  if (role === "seed") return text.fieldMapGraphSeed;
  return text.fieldMapGraphSuccessor;
}

function RelationshipNodeRow({
  node,
}: {
  node: FieldMapRelationshipGraph["nodes"][number];
}) {
  const reliability = node.reliability ?? "R1";
  return (
    <li className={`relationship-node-row is-${node.role}`}>
      <span className={`badge ${reliability.toLowerCase()}`}>{reliability}</span>
      <span className="relationship-node-title">{node.title}</span>
      {node.year ? <span className="mono">{node.year}</span> : null}
    </li>
  );
}

function FieldMapTaxon({ label, items }: { label: string; items: string[] }) {
  if (!items || items.length === 0) {
    return null;
  }
  return (
    <article>
      <h4>{label}</h4>
      <p className="field-map-tag-text">
        {items.map((item, idx) => (
          <span key={`${item}-${idx}`}>{item}</span>
        ))}
      </p>
    </article>
  );
}

function MilestoneItem({
  milestone,
  ord,
  locale,
}: {
  milestone: MilestonePaper;
  ord: number;
  locale: Locale;
}) {
  const text = UI_TEXT[locale];
  return (
    <li className="milestone-item">
      <span className="milestone-ord">{String(ord).padStart(2, "0")}</span>
      <div>
        <p className="milestone-title">{milestone.title}</p>
        <p className="milestone-meta">
          {milestone.authors.length > 0 ? (
            <span>
              {milestone.authors.slice(0, 3).join(", ")}
              {milestone.authors.length > 3 ? ", et al." : ""}
            </span>
          ) : null}
          {milestone.year ? (
            <span className="mono">{milestone.year}</span>
          ) : null}
          {milestone.venue ? <span>{milestone.venue}</span> : null}
          {milestone.velocity ? (
            <span className="mono">{milestone.velocity}/yr</span>
          ) : null}
        </p>
        <p className="milestone-category">{milestone.category}</p>
        <p className="milestone-why">{milestone.why_milestone}</p>
        {milestone.risk ? (
          <p className="milestone-risk">
            {text.fieldMapRisk}
            {milestone.risk}
          </p>
        ) : null}
      </div>
      <span className="milestone-score">
        {milestone.milestone_score.toFixed(2)}
      </span>
    </li>
  );
}

function TimelineItem({ event }: { event: TimelineEvent }) {
  return (
    <li className="timeline-item">
      <span className="timeline-year">{event.year ?? "—"}</span>
      <div className="timeline-body">
        <span className={`timeline-type is-${event.event_type}`}>
          {event.event_type.replace("_", " ")}
        </span>
        <p className="timeline-title">
          {event.title}
          {event.venue ? <span className="meta"> · {event.venue}</span> : null}
        </p>
        {event.key_idea ? <p className="timeline-key">{event.key_idea}</p> : null}
      </div>
    </li>
  );
}

function PullList({ title, claims }: { title: string; claims: Claim[] }) {
  return (
    <article className="field-map-pull">
      <h4>{title}</h4>
      <ul className="pull-list">
        {claims.map((claim) => (
          <li className="pull-item" key={claim.id}>
            <span className={`badge ${claim.reliability.toLowerCase()}`}>
              {claim.reliability}
            </span>
            <div className="pull-item-body">
              <p className="pull-item-text">{claim.text}</p>
              {claim.uncertainty ? (
                <p className="pull-item-meta">{claim.uncertainty}</p>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </article>
  );
}

/* ============================================================================
   Helpers
   ============================================================================ */

function readInitialLocale(): Locale {
  if (typeof window === "undefined") {
    return "zh";
  }
  if (typeof window.localStorage?.getItem !== "function") {
    return "zh";
  }
  return window.localStorage.getItem("paperflow-locale") === "en" ? "en" : "zh";
}

function localizeTaskMessage(message: string, locale: Locale) {
  const text = UI_TEXT[locale];
  const taskMessages = text.taskMessages as Record<string, string>;
  if (locale === "zh" && message.startsWith("Agent not configured")) {
    return "Agent 未配置。请设置 DEEPSEEK_API_KEY 或 ~/.deepseek/config.toml。";
  }
  return taskMessages[message] ?? message;
}

function localizeSectionTitle(title: string, locale: Locale) {
  const sectionTitles = UI_TEXT[locale].sectionTitles as Record<string, string>;
  return sectionTitles[title] ?? title;
}

function buildLibraryStatus(papers: Paper[], status: string, locale: Locale) {
  const active = papers.filter((paper) =>
    ["queued", "processing"].includes(paper.status?.stage ?? ""),
  ).length;
  const failed = papers.filter((paper) => paper.status?.stage === "failed").length;
  const completed = papers.filter((paper) => paper.status?.stage === "completed").length;
  const idleStatus = status === UI_TEXT.en.readyStatus || status === "Reading report generated";

  if (!idleStatus && active === 0) {
    return localizeTaskMessage(status, locale);
  }

  if (locale === "zh") {
    if (papers.length === 0) {
      return "文献库为空，等待导入第一篇论文。";
    }
    const failedPart = failed > 0 ? `，${failed} 篇失败` : "";
    const activePart = active > 0 ? `，${active} 篇处理中` : "，当前没有后台任务";
    return `${papers.length} 篇论文，${completed} 篇报告已完成${activePart}${failedPart}。`;
  }

  if (papers.length === 0) {
    return "Library is empty, waiting for the first paper.";
  }
  const failedPart = failed > 0 ? `, ${failed} failed` : "";
  const activePart = active > 0 ? `, ${active} in progress` : ", no background tasks";
  return `${papers.length} paper${papers.length === 1 ? "" : "s"}, ${completed} report${
    completed === 1 ? "" : "s"
  } completed${activePart}${failedPart}.`;
}

function importActivityMessage(activity: ImportActivity, locale: Locale) {
  const title = activity.title?.trim();
  if (activity.message) {
    return activity.message;
  }
  if (locale === "zh") {
    switch (activity.stage) {
      case "uploading":
        return "正在上传 PDF。上传成功后会自动加入 Agent 解析队列。";
      case "downloading":
        return `正在下载 ${title || "arXiv PDF"}，下载完成后会开始解析。`;
      case "resolving":
        return `正在解析 ${title || "导入来源"}，稍后会创建论文条目。`;
      case "queued":
        return `已接收 ${title || "论文"}，Agent 正在解析。`;
      case "processing":
        return `${title || "论文"} 正在解析，阅读报告生成后会自动打开。`;
      case "slow":
        return `${title || "论文"} 仍在解析。PDF 较长或模型响应慢时会多等一会，不代表卡住。`;
      case "completed":
        return `${title || "论文"} 阅读报告已生成。`;
      case "failed":
        return `${title || "论文"} 处理失败，请查看错误信息。`;
    }
  }
  switch (activity.stage) {
    case "uploading":
      return "Uploading PDF. It will enter the Agent queue after upload succeeds.";
    case "downloading":
      return `Downloading ${title || "arXiv PDF"}; parsing starts after download.`;
    case "resolving":
      return `Resolving ${title || "import source"} and creating a paper entry.`;
    case "queued":
      return `Received ${title || "paper"}; the Agent is parsing it.`;
    case "processing":
      return `${title || "Paper"} is being parsed. The report opens automatically when ready.`;
    case "slow":
      return `${title || "Paper"} is still parsing. Long PDFs or slow model responses can take longer; this does not mean it is stuck.`;
    case "completed":
      return `${title || "Paper"} reading report is ready.`;
    case "failed":
      return `${title || "Paper"} failed. Check the error details.`;
  }
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
