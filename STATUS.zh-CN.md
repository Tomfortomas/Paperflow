# Paperflow 项目状态

Paperflow 当前有两个前端，共用同一个后端 Agent harness。

- **Web**：React + Vite + TypeScript，report-first Workspace、PDF viewer、Agent rail、Obsidian 导出。
- **TUI**：Textual + httpx，键盘驱动 Library / Workspace / R0-R1-R2 / Evidence / Q&A 流程。

## 版本号策略

Paperflow 目前处在 `v0.1` 系列。此前拆成 `v0.2` 到 `v0.7` 的功能，现在统一合并为首次公开发布的 `v0.1`。

以后小功能发版使用 patch 版本号，例如 `v0.1.1`、`v0.1.2`、`v0.1.3`。除非项目明确进入新的大阶段，否则不要升级到 `v0.2` 或更高版本。

## v0.1

- [x] 面向外部传播的 README 叙事：证据优先的 agentic paper 阅读工作台。
- [x] README 可用的演示视觉：导入、证据高亮、Agent 对话、可靠性分级、Obsidian 导出。
- [x] PDF 搜索与 quote 匹配支持分段文本高亮。
- [x] PDF toolbar 适配较窄的 IDE / Cursor 工作区。
- [x] Landing page 与 HTML README 文案对齐对外产品叙事。
- [x] 将串行全文报告生成替换为分阶段 Agent pipeline：快速 paper briefing、并行 chunk 抽取、coordinator 去重合并、最终综合。
- [x] 所有 chunk agent 共享同一份 paper briefing，让并行抽取仍保持全局一致，并减少重复 claim。
- [x] 并行抽取过程中继续保存 partial report，最终由 coordinator 合并重复、保守补齐缺失 section，并保留精确 evidence quote。
- [x] 增加更细的生成状态：briefing、并行 chunk 抽取、单个 chunk 完成、coordinator synthesis。
- [x] PDF 页面按 device-pixel-ratio 渲染，Retina 和大屏下文字更清晰。
- [x] PDF 支持连续滚动阅读，toolbar 支持直接输入页码跳转，并提供缩放预设。
- [x] PDF 从报告流中独立成 Workspace pane，大屏下变成左侧栏。
- [x] 保留 evidence-driven PDF 打开逻辑：点击 evidence 会打开 PDF pane、跳到对应页，并在有 bbox 时把高亮滚到视野中。
- [x] 长论文阅读报告支持 bounded DeepSeek chunks。
- [x] 首个 chunk 完成后即可保存动态部分报告。
- [x] 覆盖率感知 UI，例如 `覆盖全文 50%` 和 `覆盖全文 100% · 8 chunks`。
- [x] 生成中实时更新解析指标。
- [x] 展示 PDF 抽取、请求准备、模型等待、覆盖率、持久化等透明 Agent 过程。
- [x] 支持运行时配置本地 API key、模型和报告 timeout。
- [x] Agent 对话线程持久化到 SQLite，Workspace 打开时恢复最近 transcript。
- [x] Chat answer 升级为基于报告、选中证据、R1 cache 的 DeepSeek chat agent，并保留 report-grounded fallback。
- [x] 报告与 chat 任务进入统一 task lifecycle。
- [x] 增加 SSE chat step/final events。
- [x] 深化 PDF evidence 交互：evidence detail 可打开 PDF viewer、跳页，并复用 bbox highlight。
- [x] Field Map / lineage graph 增加 Agent-enriched edges。
- [x] 正式 Agent Conversation rail，替代旧 focused Q&A 区域。
- [x] Paper-scoped chat API：`POST /api/papers/{paper_id}/chat`。
- [x] Evidence-aware chat inputs：selected claim、evidence、page、quote、section。
- [x] 右侧 rail 信息架构：Agent status、config、evidence、chat、Obsidian 导出。
- [x] Evidence Workflow：PyMuPDF block parser、evidence verification、PDF.js page jump、bbox highlight、select-to-ask。
- [x] Metadata & Import：arXiv、CrossRef、Semantic Scholar、OpenReview、Zotero、DOI/arXiv/content-hash dedup。
- [x] Real R1 Search：Semantic Scholar、OpenAlex fallback、Papers with Code、本地 references 的六路 related-work search。
- [x] Field Map：milestones、timeline、task taxonomy、datasets、benchmarks、method families、open problems、trends、R2 opportunities。
- [x] Compare + R2 + Task Queue：多论文 compare、research insights、Field Map Obsidian 导出、cancel/retry/resume task APIs。
- [x] Library-first home with status tracking。
- [x] DeepSeek-backed PaperAgent 生成 R0 阅读报告。
- [x] R0 / R1 / R2 可靠性标签进入 UI 和数据模型。
- [x] 每条 claim 携带 evidence quote、page 和 section。
- [x] 后台 Agent task 与持久化报告。
- [x] Obsidian-native paper note 导出。
- [x] 围绕 dataset、benchmark、method、compute、limitations 的 focused Q&A。
