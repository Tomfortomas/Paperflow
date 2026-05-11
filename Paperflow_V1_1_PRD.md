# Paperflow V1.1 PRD

## 1. Product Goal

Paperflow V1.1 的目标是把 V1 从“能跑的论文 Agent 原型”打磨成“真正可用的单篇论文深度阅读工作台”。

V1 已经验证了核心技术链路：导入 PDF、调用 DeepSeek-backed paper agent、生成 R0/R1/R2 Reading Report、保存 Obsidian-native note。但 V1 的界面仍保留了未来三栏 IDE 的占位设计：左栏和中间栏在 PDF evidence workflow 尚未完成前价值不大，反而稀释了用户注意力。

V1.1 不追求扩展复杂功能，而是聚焦两个目标：

- 让用户打开论文后立刻看到最有价值的 Agent Reading Report。
- 让长时间 Agent 解析、去重、持久化、证据查看、Obsidian 保存这些基础体验可靠、清晰、可重复。

## 2. Target Users

V1.1 继续面向 AI 研究者和工程师。用户默认具备论文阅读能力，但希望系统自动完成耗时的整理、定位和初步归纳工作。

核心场景：

- 导入一篇新论文，等待 Agent 自动解析。
- 快速判断论文的任务、方法、benchmark、结果、限制和 related work。
- 针对某个模块继续追问，例如 dataset、metric、compute、limitation。
- 把结果沉淀为 Obsidian note。
- 下次打开同一论文时直接恢复已有解析结果。

## 3. V1 Observed Problems

V1 试用中暴露出以下问题：

- 三栏布局中左栏和中间 PDF 占位区没有真实功能，用户会困惑“这两栏有什么用”。
- 导入同名 PDF 会产生重复 paper cards。
- Report 最初只存在内存中，服务重启后会出现 `Report is not available for this paper yet`。
- 大 PDF 通过同步接口解析时，Agent 调用时间较长，UI 看起来像“没有反应”。
- Library 页面只展示 paper cards，没有明确告诉用户当前论文是否已解析、解析中、失败或可打开。
- Evidence 目前只能看 quote，不能跳转 PDF；因此不应把 PDF reader 作为主界面中心。

## 4. V1.1 Product Thesis

V1.1 应该从“三栏论文 IDE 原型”收敛为“两栏 Report-first 工作台”：

```text
Library
→ 导入 / 打开论文
→ Paper Workspace
→ 左侧大区域：Reading Report
→ 右侧窄区域：Agent Actions / Evidence Detail / Focused Q&A / Obsidian Save
```

在 PDF.js 证据跳转真正完成之前，不把 PDF reader 放在主位。PDF 只作为可打开资源和 evidence source 存在。

## 5. V1.1 Core Workflow

```text
用户导入 PDF
→ 系统检查是否已有同名论文
→ 若已有，则替换旧记录和旧 report
→ 创建 paper session
→ 后台启动 Agent 解析任务
→ Library / Workspace 显示实时状态
→ Agent 生成 Reading Report
→ Report 持久化到本地
→ 用户打开两栏 Workspace 阅读 report
→ 用户点击 claim 查看 evidence detail
→ 用户按关注点追问 Agent
→ 用户保存 / 更新 Obsidian note
```

## 6. V1.1 Scope

V1.1 必须支持：

- 两栏 Paper Workspace。
- 去掉无功能的左侧 paper session 占位栏。
- 去掉无功能的中间 PDF reader 占位栏。
- Library 中同名 PDF 导入自动替换旧记录。
- Library 中每篇论文显示解析状态：`queued`、`processing`、`completed`、`failed`。
- Report 持久化到本地，后端重启后仍可打开。
- Import 后不阻塞 UI，长任务必须有状态反馈。
- Reading Report 默认作为主视图。
- Evidence Detail 作为右侧面板展示，而不是占用主内容区。
- Focused Q&A 在右侧面板中进行，回答继续带 R0/R1/R2。
- Obsidian note 保存/更新按钮明确可见。
- 没有 DeepSeek key 时明确提示“Agent not configured”，而不是生成伪 R0 结果。

## 7. V1.1 Non-goals

V1.1 暂不做：

- 完整 PDF.js 阅读器。
- Evidence 点击跳转 PDF 坐标。
- 多论文对比。
- Connected Papers 式 citation graph。
- 完整 Semantic Scholar / OpenAlex 自动查新。
- Zotero 双向同步。
- 多用户协作。

这些留到 V1.2/V2。

## 8. UX Layout

### 8.1 Library

Library 页面继续保留，但需要更清晰。

每个 paper card 显示：

- Paper title。
- PDF path。
- Status badge：`Processing` / `Completed` / `Failed`。
- Last updated time。
- Open Report 按钮。
- Re-run Agent 按钮。
- Save/Update Obsidian note 状态。

Library 顶部显示：

- Import PDF。
- 当前 DeepSeek Agent 状态：configured / missing key。
- Processing queue 状态。

### 8.2 Paper Workspace

Paper Workspace 改为两栏：

```text
┌──────────────────────────────────────────────┬──────────────────────────┐
│ Reading Report                               │ Side Panel               │
│ - Executive Summary                          │ - Agent Status            │
│ - Task                                       │ - Evidence Detail         │
│ - Dataset                                    │ - Focused Q&A             │
│ - Benchmark / Metric                         │ - Obsidian Save           │
│ - Method                                     │ - Re-run Agent            │
│ - Input / Output                             │                          │
│ - Compute / Training                         │                          │
│ - Limitations                                │                          │
│ - R1 Related Work                            │                          │
└──────────────────────────────────────────────┴──────────────────────────┘
```

主区只做一件事：让用户高效阅读 Agent 生成的 report。

右侧只放行动和上下文：

- 当前选中的 claim。
- Evidence quote、source、page、section。
- Focused question 输入框。
- 最新回答。
- Save Obsidian note。
- Re-run Agent。

## 9. Reading Report Requirements

Reading Report 保持两级结构：

- Executive Summary。
- Detailed Sections。

必须包含：

- Task。
- Dataset。
- Benchmark / Metric。
- Method。
- Input / Output。
- Compute / Training。
- Limitations。
- R1 Related Work Context。

每个 claim 必须包含：

- Claim text。
- Reliability badge：R0 / R1 / R2。
- Evidence count。
- Source。
- Uncertainty if present。

点击 claim 后，右侧 Evidence Detail 面板展示：

- Quote。
- Page。
- Section。
- Source paper / current paper。
- Reliability explanation。
- Missing evidence warning if no evidence.

## 10. Agent Requirements

V1.1 明确规定：论文理解必须由 AI Agent 完成，规则代码只负责机械提取和存储。

允许规则代码做：

- PDF 文件保存。
- PDF 文本提取。
- 页码和文本 chunk 建立。
- SQLite 存储。
- Report JSON 持久化。
- Obsidian Markdown 渲染。

不允许规则代码做：

- 推断论文任务。
- 判断 benchmark。
- 总结 method。
- 生成 limitations。
- 判断 R0/R1/R2。
- 生成 related work context。

这些必须由 `PaperAgent` 完成。

Agent 输出必须是结构化 JSON，并被后端校验为 `ReadingReport`。

## 11. Task And Status Requirements

V1.1 需要引入最小后台任务状态，不一定要完整 Celery/RQ，但必须让 UI 不阻塞。

状态模型：

- `queued`：文件已上传，等待 Agent。
- `processing`：Agent 正在解析。
- `completed`：report 可用。
- `failed`：解析失败，显示错误。

导入接口不应等待完整 Agent 解析结束后才返回。推荐流程：

```text
POST /api/papers/import
→ 立即返回 paper session + queued/processing status
→ 后台执行 Agent
→ 前端轮询 GET /api/papers/{id}/status
→ completed 后读取 report
```

如果 V1.1 仍采用同步实现，必须至少显示 loading overlay 和超时错误。但推荐实现后台任务。

## 12. Storage Requirements

V1.1 本地存储必须可靠：

- 同名 PDF 只保留一个 paper record。
- Re-import 同名 PDF 替换旧 PDF、旧 report、旧 note 状态。
- Report 保存为 JSON 文件。
- Obsidian note 保存为 Markdown 文件。
- 后端重启后 Library 能恢复 paper list。
- 后端重启后 report 能恢复。
- Failed task 要保留错误信息，方便用户重试。

## 13. Obsidian Requirements

V1.1 的 Obsidian note 应作为正式产物，而不是简单导出。

Note 必须包含：

- YAML frontmatter。
- PDF link。
- Executive Summary。
- R0 Reading Report。
- R1 Related Work Context。
- Evidence Index。
- Focused Q&A。
- Follow-up Ideas placeholder。

保存逻辑：

- 第一次保存创建 note。
- 后续保存更新 note。
- UI 显示 note path。
- Library 显示该 paper 是否已有 note。

## 14. Error Handling

V1.1 必须清晰处理以下错误：

- DeepSeek key missing。
- DeepSeek API timeout。
- DeepSeek 返回非 JSON。
- Report schema validation failed。
- PDF 无法提取文本。
- 用户重复导入同名 PDF。
- 后端重启后 report 文件缺失。

错误展示原则：

- 不要静默失败。
- 不要只在 terminal 打日志。
- Library 和 Workspace 都要能看到失败状态。
- 用户要能点击 retry。

## 15. Success Metrics

V1.1 成功的标准：

- 用户导入论文后能明确看到系统正在处理。
- 同一 PDF 多次导入不会产生重复卡片。
- 打开论文时默认看到完整 Reading Report，而不是空白占位区。
- 用户能在 1 次点击内查看任意 claim 的 evidence。
- 后端重启后 report 仍能打开。
- 用户能保存并找到 Obsidian note。
- 没有 DeepSeek key 时，用户能明确知道需要配置 Agent。

## 16. Implementation Priority

优先级从高到低：

1. 两栏 Workspace UI。
2. 去重与 report 持久化。
3. 最小后台任务/status。
4. Evidence Detail 右侧面板。
5. Focused Q&A 结果保存。
6. Obsidian note 更新状态。
7. Agent config/status 展示。

## 17. Future After V1.1

V1.2 可以开始补真正的 PDF evidence workflow：

- PDF.js 阅读器。
- Evidence quote 高亮。
- 点击 evidence 跳页。
- 用户选中 PDF 文本后追问。
- Section outline。
- References parser。

V2 再扩展：

- Semantic Scholar / OpenAlex cited-by。
- Field Map。
- Citation graph。
- 多论文对比。
- Zotero integration。
