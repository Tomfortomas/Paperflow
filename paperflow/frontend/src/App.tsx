import { useEffect, useState } from "react";

import { createPaperflowClient, type PaperflowClient } from "./api";
import type { AgentStatus, Claim, Paper, ReadingReport, TaskStatus } from "./types";
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
    eyebrow: "本地优先的研究工作台",
    libraryTitle: "Paperflow 文献库",
    heroDescription: "导入论文，生成带证据的阅读报告，并保存为 Obsidian 原生笔记，方便长期研究沉淀。",
    agentLabel: "Agent",
    configured: "已配置",
    missingKey: "缺少 key",
    languageToggle: "English",
    importPdf: "导入 PDF",
    arxivImportTitle: "从 arXiv 导入",
    arxivPlaceholder: "粘贴 arXiv 链接或 ID，例如 2605.08063v1",
    importArxiv: "下载并解析",
    arxivQueuedStatus: "arXiv PDF 已开始下载并加入解析队列。",
    emptyArxiv: "请输入 arXiv 链接或 ID。",
    recentPapers: "最近论文",
    notePrefix: "笔记：",
    openPaper: (title: string) => `打开 ${title}`,
    processingStatus: "处理状态",
    savedReports: "已保存报告",
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
    focusedQa: "聚焦追问",
    askPlaceholder: "例如：只看 benchmark 和 dataset",
    ask: "提问",
    obsidian: "Obsidian",
    saveNote: "保存 / 更新 Obsidian 笔记",
    savedTo: (path: string) => `已保存到 ${path}`,
    page: (page: number) => ` 第 ${page} 页`,
    statusLabels: {
      queued: "排队中",
      processing: "解析中",
      completed: "已完成",
      failed: "失败",
      unknown: "未知",
    },
    taskMessages: {
      "Ready for automatic R0 + lightweight R1 processing.": "已准备好自动执行 R0 + 轻量 R1 处理。",
      "Backend not connected. Start FastAPI to load your library.": "后端未连接。请先启动 FastAPI 再加载文献库。",
      "Queued PDF for Agent parsing...": "PDF 已加入 Agent 解析队列。",
      "arXiv PDF download queued for parsing.": "arXiv PDF 已开始下载并加入解析队列。",
      "Import failed.": "导入失败。",
      "Reading report generated": "阅读报告已生成",
      "Queued for Agent parsing": "已加入 Agent 解析队列",
      "DeepSeek PaperAgent is parsing the PDF": "DeepSeek PaperAgent 正在解析 PDF",
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
    parseTimeout: "Agent parsing timed out. You can retry from the paper workspace.",
    eyebrow: "Local-first research workspace",
    libraryTitle: "Paperflow Library",
    heroDescription: "Bring in papers, generate evidence-aware reading reports, and save Obsidian-native notes for long-term research.",
    agentLabel: "Agent",
    configured: "configured",
    missingKey: "missing key",
    languageToggle: "中文",
    importPdf: "Import PDF",
    arxivImportTitle: "Import from arXiv",
    arxivPlaceholder: "Paste an arXiv URL or ID, e.g. 2605.08063v1",
    importArxiv: "Download and Parse",
    arxivQueuedStatus: "arXiv PDF download queued for parsing.",
    emptyArxiv: "Enter an arXiv URL or ID.",
    recentPapers: "Recent Papers",
    notePrefix: "Note:",
    openPaper: (title: string) => `Open ${title}`,
    processingStatus: "Processing Status",
    savedReports: "Saved Reports",
    noNote: "No Obsidian note yet",
    backToLibrary: "Back to Library",
    reportNotReady: "Agent report is not ready yet.",
    readingReport: "Reading Report",
    executiveSummary: "Executive Summary",
    relatedWork: "R1 Related Work",
    evidenceButton: (count: number) => `View ${count} evidence item${count === 1 ? "" : "s"}`,
    selectedClaim: "Selected claim",
    agentStatus: "Agent Status",
    noActiveTask: "No active task.",
    rerunAgent: "Re-run Agent",
    evidenceDetail: "Evidence Detail",
    missingEvidence: "Missing evidence.",
    selectClaim: "Select a claim to inspect its evidence.",
    focusedQa: "Focused Q&A",
    askPlaceholder: "e.g. 只看 benchmark 和 dataset",
    ask: "Ask",
    obsidian: "Obsidian",
    saveNote: "Save / Update Obsidian Note",
    savedTo: (path: string) => `Saved to ${path}`,
    page: (page: number) => ` p. ${page}`,
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

  async function handleImport(file: File) {
    setError(null);
    setStatus(UI_TEXT.en.queuedStatus);
    try {
      const session = await client.importPaper(file);
      setPapers((current) => [
        session.paper,
        ...current.filter((paper) => paper.id !== session.paper.id && paper.title !== session.paper.title),
      ]);
      setSelectedPaper(session.paper);
      void pollPaper(session.paper.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : text.importFailed);
      setStatus(UI_TEXT.en.importFailed);
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
    try {
      const session = await client.importArxiv(value);
      setPapers((current) => [
        session.paper,
        ...current.filter((paper) => paper.id !== session.paper.id && paper.title !== session.paper.title),
      ]);
      setSelectedPaper(session.paper);
      setArxivInput("");
      void pollPaper(session.paper.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : text.importFailed);
      setStatus(UI_TEXT.en.importFailed);
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

  async function pollPaper(paperId: string) {
    for (let attempt = 0; attempt < 240; attempt += 1) {
      const nextStatus = await client.getStatus(paperId);
      updatePaperStatus(paperId, nextStatus);
      setStatus(nextStatus.message);
      if (nextStatus.stage === "completed") {
        const report = await client.getReport(paperId);
        setReports((current) => ({ ...current, [paperId]: report }));
        if (report.paper_title) {
          updatePaperTitle(paperId, report.paper_title);
        }
        return;
      }
      if (nextStatus.stage === "failed") {
        setError(nextStatus.message);
        return;
      }
      await sleep(1500);
    }
    setError(text.parseTimeout);
  }

  function updatePaperStatus(paperId: string, nextStatus: TaskStatus) {
    setPapers((current) =>
      current.map((paper) => (paper.id === paperId ? { ...paper, status: nextStatus } : paper)),
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
      current.map((paper) => (paper.id === paperId ? { ...paper, note_path: notePath } : paper)),
    );
    setSelectedPaper((current) =>
      current?.id === paperId ? { ...current, note_path: notePath } : current,
    );
  }

  function updatePaperTitle(paperId: string, title: string) {
    setPapers((current) =>
      current.map((paper) => (paper.id === paperId ? { ...paper, title } : paper)),
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
        onNoteSaved={(notePath) => updatePaperNote(selectedPaper.id, notePath)}
        onRerun={() => void rerunPaper(selectedPaper.id)}
        paper={selectedPaper}
        report={reports[selectedPaper.id]}
      />
    );
  }

  return (
    <main className="app-shell">
      <section className="library-hero">
        <div>
          <p className="eyebrow">{text.eyebrow}</p>
          <h1>{text.libraryTitle}</h1>
          <p>{text.heroDescription}</p>
          <p className={`agent-chip ${agentStatus?.configured ? "ready" : "missing"}`}>
            {text.agentLabel}: {agentStatus?.configured ? `${text.configured} (${agentStatus.mode})` : text.missingKey}
          </p>
          <button type="button" className="language-toggle" onClick={() => setLocale(locale === "zh" ? "en" : "zh")}>
            {text.languageToggle}
          </button>
        </div>
        <label className="import-card">
          <span>{text.importPdf}</span>
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
        </label>
      </section>
      <section className="arxiv-import panel">
        <div>
          <h2>{text.arxivImportTitle}</h2>
          <p className="muted">{text.arxivPlaceholder}</p>
        </div>
        <input
          aria-label={text.arxivImportTitle}
          placeholder={text.arxivPlaceholder}
          value={arxivInput}
          onChange={(event) => setArxivInput(event.target.value)}
        />
        <button type="button" onClick={() => void handleArxivImport()}>
          {text.importArxiv}
        </button>
      </section>
      {error ? <p className="warning">{error}</p> : null}

      <section className="library-grid">
        <LibraryPanel title={text.recentPapers}>
          {papers.map((paper) => (
            <article className="paper-card" key={paper.id}>
              <div>
                <h2>{paper.title}</h2>
                <p>{paper.pdf_path}</p>
                <StatusBadge locale={locale} status={paper.status} />
                {paper.note_path ? <p className="muted">{text.notePrefix} {paper.note_path}</p> : null}
              </div>
              <button type="button" onClick={() => void openPaper(paper)}>
                {text.openPaper(paper.title)}
              </button>
            </article>
          ))}
        </LibraryPanel>

        <LibraryPanel title={text.processingStatus}>
          <p className="muted">{localizeTaskMessage(status, locale)}</p>
        </LibraryPanel>

        <LibraryPanel title={text.savedReports}>
          {papers.map((paper) => (
            <p key={paper.id}>{paper.note_path ?? text.noNote}</p>
          ))}
        </LibraryPanel>
      </section>
    </main>
  );
}

function LibraryPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function Workspace({
  paper,
  report,
  client,
  locale,
  onNoteSaved,
  onRerun,
  onBack,
}: {
  paper: Paper;
  report?: ReadingReport;
  client: PaperflowClient;
  locale: Locale;
  onNoteSaved: (notePath: string) => void;
  onRerun: () => void;
  onBack: () => void;
}) {
  const text = UI_TEXT[locale];
  const displayTitle = report?.paper_title ?? paper.title;
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Claim | null>(null);
  const [notePath, setNotePath] = useState<string | null>(paper.note_path ?? null);
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(report?.summary[0] ?? null);

  useEffect(() => {
    if (!selectedClaim && report?.summary[0]) {
      setSelectedClaim(report.summary[0]);
    }
  }, [report, selectedClaim]);

  async function askFocusedQuestion() {
    if (!question.trim()) {
      return;
    }
    const result = await client.askPaper(paper.id, question);
    setAnswer(result);
  }

  async function exportNote() {
    const result = await client.exportObsidian(paper.id);
    setNotePath(result.note_path);
    onNoteSaved(result.note_path);
  }

  if (!report) {
    return (
      <main className="workspace workspace-two-column">
        <section className="report-pane empty-report">
          <button type="button" onClick={onBack}>
            {text.backToLibrary}
          </button>
          <h1>{displayTitle}</h1>
          <StatusBadge locale={locale} status={paper.status} />
          <p>{paper.status?.message ? localizeTaskMessage(paper.status.message, locale) : text.reportNotReady}</p>
        </section>
        <SidePanel
          answer={answer}
          locale={locale}
          notePath={notePath}
          onAsk={askFocusedQuestion}
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

  return (
    <main className="workspace workspace-two-column">
      <section className="report-pane">
        <div className="report-header">
          <button type="button" onClick={onBack}>
            {text.backToLibrary}
          </button>
          <div>
            <p className="eyebrow">{text.readingReport}</p>
            <h2>{text.readingReport}</h2>
            <h1>{displayTitle}</h1>
            <p className="muted">{paper.pdf_path}</p>
          </div>
          <StatusBadge locale={locale} status={paper.status} />
        </div>

        <h3>{text.executiveSummary}</h3>
        {report.summary.map((claim) => (
          <ClaimCard
            claim={claim}
            key={claim.id}
            locale={locale}
            selected={selectedClaim?.id === claim.id}
            onSelect={setSelectedClaim}
          />
        ))}

        {report.sections.map((section) => (
          <section className="report-section" key={section.id}>
            <h3>{localizeSectionTitle(section.title, locale)}</h3>
            {section.claims.map((claim) => (
              <ClaimCard
                claim={claim}
                key={claim.id}
                locale={locale}
                selected={selectedClaim?.id === claim.id}
                onSelect={setSelectedClaim}
              />
            ))}
          </section>
        ))}

        <section className="report-section">
          <h3>{text.relatedWork}</h3>
          {report.related_work.map((item) => (
            <article className="claim-card" key={item.id}>
              <span className={`badge ${item.reliability.toLowerCase()}`}>
                {item.reliability}
              </span>
              <strong>{item.title}</strong>
              <p>{item.relation}</p>
              <p className="muted">{item.source}</p>
            </article>
          ))}
        </section>
      </section>

      <SidePanel
        answer={answer}
        locale={locale}
        notePath={notePath}
        onAsk={askFocusedQuestion}
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

function ClaimCard({
  claim,
  locale,
  onSelect,
  selected = false,
}: {
  claim: Claim;
  locale: Locale;
  onSelect?: (claim: Claim) => void;
  selected?: boolean;
}) {
  const text = UI_TEXT[locale];
  return (
    <article className={`claim-card ${selected ? "selected" : ""}`}>
      <div className="claim-row">
        <span className={`badge ${claim.reliability.toLowerCase()}`}>{claim.reliability}</span>
        <p>{claim.text}</p>
      </div>
      {claim.uncertainty ? <p className="warning">{claim.uncertainty}</p> : null}
      <button type="button" onClick={() => onSelect?.(claim)}>
        {text.evidenceButton(claim.evidence.length)}
      </button>
    </article>
  );
}

function SidePanel({
  answer,
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
  answer: Claim | null;
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
    <aside className="side-panel">
      <section className="side-card">
        <p className="eyebrow">{text.agentStatus}</p>
        <StatusBadge locale={locale} status={paper.status} />
        <p className="muted">{paper.status?.message ? localizeTaskMessage(paper.status.message, locale) : text.noActiveTask}</p>
        <button type="button" onClick={onRerun}>
          {text.rerunAgent}
        </button>
      </section>

      <section className="side-card">
        <p className="eyebrow">{text.evidenceDetail}</p>
        {selectedClaim ? (
          <>
            <strong>{text.selectedClaim}</strong>
            <p>{selectedClaim.text}</p>
            {selectedClaim.evidence.length > 0 ? (
              <div className="evidence-list">
                {selectedClaim.evidence.map((evidence) => (
                  <blockquote key={evidence.id}>
                    <strong>{evidence.source}</strong>
                    {evidence.page ? <span>{text.page(evidence.page)}</span> : null}
                    {evidence.section ? <span> · {evidence.section}</span> : null}
                    <p>{evidence.quote}</p>
                  </blockquote>
                ))}
              </div>
            ) : (
              <p className="warning">{text.missingEvidence}</p>
            )}
          </>
        ) : (
          <p className="muted">{text.selectClaim}</p>
        )}
      </section>

      <section className="side-card chat-panel">
        <p className="eyebrow">{text.focusedQa}</p>
        <input
          placeholder={text.askPlaceholder}
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
        />
        <button type="button" onClick={() => void onAsk()}>
          {text.ask}
        </button>
        {answer ? <ClaimCard claim={answer} locale={locale} /> : null}
      </section>

      <section className="side-card">
        <p className="eyebrow">{text.obsidian}</p>
        <button type="button" onClick={() => void onExport()}>
          {text.saveNote}
        </button>
        {notePath ? <p className="muted">{text.savedTo(notePath)}</p> : <p className="muted">{text.noNote}</p>}
      </section>
    </aside>
  );
}

function StatusBadge({ status, locale }: { status?: TaskStatus; locale: Locale }) {
  const stage = status?.stage ?? "unknown";
  const text = UI_TEXT[locale];
  return <span className={`status-badge ${stage}`}>{text.statusLabels[stage as keyof typeof text.statusLabels] ?? stage}</span>;
}

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

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
