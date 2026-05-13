# Paperflow Status / Paperflow 项目状态

Paperflow currently ships two front-ends on top of the same backend agent harness.

Paperflow 当前有两个前端，共用同一个后端 Agent harness。

- **Web**: React + Vite + TypeScript, report-first Workspace, PDF viewer, Agent rail, and Obsidian export.
- **TUI**: Textual + httpx, keyboard-driven Library / Workspace / R0-R1-R2 / Evidence / Q&A flow.

- **Web**：React + Vite + TypeScript，report-first Workspace、PDF viewer、Agent rail、Obsidian export。
- **TUI**：Textual + httpx，键盘驱动 Library / Workspace / R0-R1-R2 / Evidence / Q&A flow。

## v0.7

- [x] Public-facing bilingual README narrative for an evidence-first AI paper workspace.
- [x] README-ready bilingual demo visuals for import, evidence highlight, Agent chat, reliability model, and Obsidian export.
- [x] PDF search and quote matching with segmented text highlights.
- [x] Responsive PDF toolbar for narrower IDE / Cursor workspace panes.
- [x] Landing page and HTML README copy aligned with the public product story.

- [x] 面向外部传播的双语 README 叙事：证据优先的 AI 论文工作台。
- [x] README 可用的双语演示视觉：导入、证据高亮、Agent 对话、可靠性分级、Obsidian 导出。
- [x] PDF 搜索与 quote 匹配支持分段文本高亮。
- [x] PDF toolbar 适配较窄的 IDE / Cursor workspace pane。
- [x] Landing page 与 HTML README 文案对齐对外产品叙事。

## v0.6

- [x] Replace serial full-report generation with a staged Agent pipeline: fast paper briefing, parallel chunk extraction, coordinator deduplication, and final synthesis.
- [x] Share the same paper briefing with every chunk agent so parallel extraction stays globally consistent and avoids repeated claims.
- [x] Preserve partial reports during extraction while the final coordinator pass merges duplicates, fills missing required sections conservatively, and keeps exact evidence quotes.
- [x] Add richer generation status messages for briefing, parallel chunk extraction, per-chunk completion, and coordinator synthesis.

- [x] 将串行全文报告生成替换为分阶段 Agent pipeline：快速 paper briefing、并行 chunk 抽取、coordinator 去重合并、最终综合。
- [x] 所有 chunk agent 共享同一份 paper briefing，让并行抽取仍保持全局一致，并减少重复 claim。
- [x] 并行抽取过程中继续保存 partial report，最终由 coordinator 合并重复、保守补齐缺失 section，并保留精确 evidence quote。
- [x] 增加更细的生成状态：briefing、并行 chunk 抽取、单个 chunk 完成、coordinator synthesis。

## v0.5

- [x] Render PDF pages at device-pixel-ratio resolution so text stays sharp on Retina and large displays.
- [x] Add continuous PDF scrolling with toolbar controls for direct page jump and zoom presets.
- [x] Move the PDF into an independent Workspace pane that becomes a left column on large screens.
- [x] Keep evidence-driven PDF opening: clicking evidence opens the PDF pane, jumps to the page, and scrolls the highlight into view when bbox data exists.

- [x] PDF 页面按 device-pixel-ratio 渲染，Retina 和大屏下文字更清晰。
- [x] PDF 支持连续滚动阅读，toolbar 支持直接输入页码跳转，并提供缩放预设。
- [x] PDF 从报告流中独立成 Workspace pane，大屏下变成左侧栏。
- [x] 保留 evidence-driven PDF 打开逻辑：点击 evidence 会打开 PDF pane、跳到对应页，并在有 bbox 时把高亮滚到视野中。

## v0.4

- [x] Chunked full-paper Reading Reports over bounded DeepSeek chunks.
- [x] Dynamic partial reports so the first key findings appear before full completion.
- [x] Coverage-aware UI such as `覆盖全文 50%` and `覆盖全文 100% · 8 chunks`.
- [x] Live parsing metrics while generation is still running.
- [x] Transparent Agent progress for extraction, request preparation, model wait, coverage, and persistence.
- [x] Runtime Agent configuration for local API key, model, and report timeout.
- [x] Persist Agent chat threads in SQLite and restore the latest transcript when the Workspace opens.
- [x] Upgrade chat answers to a DeepSeek-backed chat agent over report + selected evidence + R1 cache, with a report-grounded fallback.
- [x] Surface report and chat work through the task lifecycle; report import/rerun now runs through the task queue wrapper and chat records completed task snapshots.
- [x] Add SSE streaming for Agent chat step/final events, with frontend stream consumption and final transcript sync.
- [x] Deepen PDF evidence interactions: evidence detail can open the PDF viewer, jump to the evidence page, and reuse bbox highlights when available.
- [x] Add Agent-enriched Field Map / lineage graph edges with source type, rationale, confidence, and UI labels that distinguish Agent suggestions from rule-derived relations.

## v0.3

- [x] Formal Agent Conversation rail replacing the old focused Q&A area.
- [x] Paper-scoped chat API: `POST /api/papers/{paper_id}/chat`.
- [x] Evidence-aware chat inputs: selected claim, evidence, page, quote, and section.
- [x] Right-rail information architecture for Agent status, config, evidence, chat, and Obsidian export.

## v0.2

- [x] Evidence Workflow: PyMuPDF block parser, evidence verification, PDF.js page jump, bbox highlight, and select-to-ask.
- [x] Metadata & Import: arXiv, CrossRef, Semantic Scholar, OpenReview, Zotero, and DOI/arXiv/content-hash deduplication.
- [x] Real R1 Search: six-lane related-work search over Semantic Scholar, OpenAlex fallback, Papers with Code, and local references.
- [x] Field Map: milestones, timeline, task taxonomy, datasets, benchmarks, method families, open problems, trends, and R2 opportunities.
- [x] Compare + R2 + Task Queue: multi-paper compare, research insights, Field Map Obsidian export, cancel/retry/resume task APIs.

## v0.1

- [x] Library-first home with status tracking (`queued` -> `processing` -> `completed` / `failed`).
- [x] DeepSeek-backed PaperAgent generating R0 Reading Reports.
- [x] R0 / R1 / R2 reliability badges in UI and data model.
- [x] Evidence quote, page, and section per claim.
- [x] Background agent task with persistent reports.
- [x] Obsidian-native paper note export.
- [x] Focused Q&A around dataset / benchmark / method / compute / limitations.
