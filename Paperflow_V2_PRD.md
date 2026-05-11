# Paperflow V2 PRD

> Status: Final. This document is the locked-in design contract for the V2 open-source release.
> It supersedes V1 and V1.1 PRDs as the forward-looking spec, while keeping V1/V1.1 as historical record.

## Table Of Contents

1. [Product Goal](#1-product-goal)
2. [Target Users](#2-target-users)
3. [Product Principles](#3-product-principles)
4. [V2 Scope](#4-v2-scope)
5. [UX Design](#5-ux-design)
6. [Agent Architecture](#6-agent-architecture)
7. [Data Model](#7-data-model)
8. [API Requirements](#8-api-requirements)
9. [Storage Requirements](#9-storage-requirements)
10. [Obsidian Requirements](#10-obsidian-requirements)
11. [Error Handling](#11-error-handling)
12. [Success Metrics](#12-success-metrics)
13. [Implementation Priority](#13-implementation-priority)
14. [V2 Non-goals](#14-v2-non-goals)
15. [Acceptance Checklist](#15-acceptance-checklist)
16. [Relationship To Original SMLThoughts](#16-relationship-to-original-smlthoughts)

## 1. Product Goal

Paperflow V2 的目标是把 V1.1 的“单篇论文深度阅读工作台”升级为“面向研究者的论文理解与领域地图工作台”。

V1/V1.1 已经验证了基础闭环：

- 导入本地 PDF 或 arXiv 链接。
- 后台调用 DeepSeek-backed PaperAgent。
- 生成带 R0/R1/R2 标签的 Reading Report。
- 在 Library 和 Workspace 中显示任务状态。
- 保存 Obsidian-native note。
- 对单篇论文做聚焦追问。

V2 要完成用户原始需求中的全部功能设计：不仅要读懂一篇论文，还要帮助用户理解这篇论文所在领域、关键论文、技术演化、未解决问题和潜在研究机会。

V2 的产品主张：

```text
Paperflow = Evidence-first Paper Reading + Citation-aware Search + Field Map + Obsidian Knowledge Base
```

V2 不做泛化聊天机器人，也不做大而全文献管理器。V2 仍然围绕“研究者读论文时真正需要判断的信息”展开：每个结论都要标注可靠性，每个事实尽量能跳回证据，每个扩展搜索都要保留来源。

## 2. Target Users

V2 面向高频阅读论文的 AI 研究者、工程师和研究生。

典型用户：

- 进入新领域，需要快速建立领域地图的人。
- 读一篇论文时，需要判断任务、数据集、benchmark、模型、训练资源、结果和 limitation 的人。
- 做 related work、查新、复现实验或设计新方法的人。
- 希望把阅读结果沉淀到 Obsidian 知识库的人。
- 需要从一篇 seed paper 延伸到 milestone papers、follow-up papers 和最新论文的人。

核心使用场景：

- 导入一篇 PDF 或 arXiv 链接，生成中文 Reading Report。
- 点击 report 中任意 claim，跳转到 PDF 原文证据。
- 对 dataset、benchmark、model design、compute、limitation 继续追问。
- 自动查找当前论文 references、cited-by、related papers、benchmark papers、survey papers。
- 自动生成 Field Map：milestone papers、timeline、method evolution、evaluation evolution、open problems。
- 将单篇论文笔记、领域地图和用户追问沉淀到 Obsidian。

## 3. Product Principles

### 3.1 Evidence First

Paperflow 的所有事实性输出必须优先服务于证据可追溯。

- R0 信息必须绑定当前 PDF 的 page、section、paragraph、figure、table 或 appendix。
- R1 信息必须绑定外部论文的 title、authors、year、venue、URL，以及外部论文中的 evidence。
- R2 信息必须明确标注为推断、趋势判断、研究建议或经验判断。
- 对数值型信息必须尤其严格，不允许补全、猜测或跨 setting 直接比较。

### 3.2 Report First, Chat Second

Paperflow 的主界面不是空白聊天，而是结构化报告和证据工作台。

- 用户打开论文时默认看到 Reading Report。
- Chat 只作为围绕 section、claim、PDF 选区、Field Map 的上下文追问入口。
- Agent 生成的内容必须进入可缓存、可复用、可导出的结构化数据。

### 3.3 Local-first Knowledge Base

V2 继续保持 local-first。

- PDF、report JSON、Obsidian Markdown、Field Map JSON、用户问答历史默认保存在本地。
- 用户可以重新打开、重跑、导出和迁移。
- 外部搜索结果也要缓存，避免重复调用 API。

### 3.4 Reliability Is Product Surface

R0/R1/R2 不只是内部字段，而是 UI、数据模型、Agent prompt 和导出格式的一等公民。

用户应该始终知道：

- 这句话来自当前论文、外部论文，还是 Agent 推断？
- 证据在哪里？
- 这条信息是否缺证据？
- 不同 benchmark / dataset / metric 是否可比？

## 4. V2 Scope

V2 必须支持以下能力。

### 4.1 Paper Import

导入来源：

- 本地 PDF。
- arXiv URL / arXiv ID。
- DOI URL。
- Semantic Scholar paper URL。
- OpenReview URL。
- Zotero collection 或 Zotero selected item。

V2 可分阶段实现，但 PRD 层面需要完整设计这些入口。

导入后系统应：

- 保存原始 PDF。
- 解析 paper metadata：title、authors、year、venue、arXiv ID、DOI、URL。
- 如果用户导入的是 arXiv 链接，自动下载 PDF。
- 如果 PDF 文件名是随机名或 arXiv ID，解析完成后显示论文真实标题。
- 同一论文重复导入时自动去重，优先使用 DOI、arXiv ID、title hash、PDF hash 判断。

### 4.2 PDF Reading And Evidence Workflow

V2 必须补齐真正的 PDF evidence workflow。

功能要求：

- 使用 PDF.js 显示论文原文。
- 支持页码跳转。
- 支持 section outline。
- 支持选中文本后追问。
- Evidence quote 点击后跳转到对应 page。
- 如果能定位坐标，则高亮 evidence quote。
- 如果无法定位坐标，至少跳转到 page 并显示 quote。
- Evidence Detail 面板展示 source、page、section、quote、reliability、claim。

证据定位要求：

- PDF parser 需要保存 page text chunks。
- 每个 chunk 保留 page、bbox、section guess、text。
- Agent 输出 quote 后，Evidence Verifier 根据 quote 在 chunk 中 fuzzy match。
- fuzzy match 成功时记录 page 和 bbox。
- match 失败时标记 `evidence_location_status = quote_only`。

### 4.3 R0 Reading Report

R0 Reading Report 是单篇论文的核心产物。

必须包含：

- Paper metadata：标题、作者、年份、venue、arXiv、DOI、URL。
- Executive Summary。
- Task：任务是什么，是否由本文新定义。
- Dataset：使用哪些数据集，是自建还是公开。
- Benchmark / Metric：benchmark、metric、leaderboard、evaluation protocol。
- Method：方法结构、pipeline、关键模块。
- Model Scale：参数量、模型规模、组件规模。
- Input / Output：输入输出形式、模态、数据格式。
- Compute / Training：GPU/TPU、训练时长、batch size、数据量、训练阶段。
- Key Results：主要实验结论和数值结果。
- Strengths：论文声称的优势。
- Limitations：论文承认的限制和从证据支持的缺点。
- Related Work Claims：论文如何描述前人工作的问题。
- Theory / Methodology Insights：论文的方法论或理论层面关键发现。
- Evidence Index：claim 到 evidence 的索引。

每个 claim 必须包含：

```json
{
  "id": "claim-id",
  "text": "中文解释",
  "reliability": "R0",
  "source": "current_paper",
  "evidence": [
    {
      "quote": "原文 quote，不翻译",
      "page": 3,
      "section": "Method",
      "bbox": null,
      "location_status": "page_and_quote"
    }
  ],
  "uncertainty": null,
  "numeric_strictness": {
    "contains_number": true,
    "setting": "dataset / benchmark / metric",
    "comparison_risk": null
  }
}
```

### 4.4 Focused Questions

用户可以设置关注点，也可以临时追问。

默认关注点：

- 任务是什么？
- 数据集是什么？
- benchmark 和 metric 是什么？
- 模型怎么设计？
- 参数量是多少？
- 输入输出是什么？
- 计算资源和训练量是什么？
- 方法优势是什么？
- 方法缺点是什么？
- 本文总结的前人工作问题是什么？
- 本文有什么理论、方法论层面的关键发现？

追问要求：

- 追问回答必须继续带 R0/R1/R2。
- 如果用户追问当前论文内容，优先用 R0。
- 如果用户要求“和别的论文比较”，必须进入 R1 搜索或明确标注为 R2。
- 所有问答历史必须保存，并可导出到 Obsidian note。
- 用户可以把某个回答 pin 到 Reading Report。

### 4.5 R1 Related Work Search

V2 必须实现真实外部搜索，而不是 placeholder。

搜索入口优先级：

- Semantic Scholar API：paper metadata、references、citations、TLDR、citation count。
- OpenAlex API：paper metadata、citation graph、concepts、venue。
- arXiv API：最新预印本。
- Papers with Code：task、dataset、benchmark、leaderboard、code。
- OpenReview：ICLR/NeurIPS workshop 等评论和 rebuttal。
- Google Scholar：如果没有稳定 API，仅作为手动外链和 query 生成，不做默认爬取。
- DBLP / ACL Anthology / CVF / PMLR：按领域补充正式发表信息。

R1 搜索阶段：

1. Seed Extraction：从当前论文抽取 task、dataset、benchmark、baseline、method keywords、references。
2. Backward Citation Search：查当前论文引用的 foundational papers。
3. Forward Citation Search：查 cited-by 和 follow-up papers。
4. Benchmark Search：围绕 dataset / benchmark / metric 找代表性方法和 leaderboard。
5. Survey Search：搜索 survey、tutorial、awesome list、course note。
6. Recent Trend Search：限制最近 1-2 年，找最新 arXiv/OpenReview/venue papers。

R1 输出必须包含：

- 论文标题。
- 作者、年份、venue。
- URL / DOI / arXiv ID。
- 与当前论文关系：foundational、baseline、competitor、follow-up、survey、benchmark paper、dataset paper。
- 支撑关系的 evidence。
- 是否可与当前论文直接比较。
- comparison risk：不同数据集、不同 metric、不同 setting、不同 protocol。

R1 搜索需要保留 query trace。用户应该能看到系统为什么搜这些词、使用了哪些入口、哪些结果被采用、哪些结果被排除。

默认 query 模板：

- `"<task name>" survey benchmark dataset`
- `"<method keyword>" "<task name>" arxiv`
- `"<dataset name>" leaderboard papers with code`
- `"<benchmark name>" state of the art`
- `"<paper title>" cited by`
- `"<field name>" survey 2024 OR 2025`
- `"<method family>" limitations future work`
- `"<task name>" openreview`

Query trace 字段：

```json
{
  "query": "\"visual grounding\" benchmark dataset",
  "source": "Semantic Scholar",
  "purpose": "benchmark_search",
  "results_count": 20,
  "selected_papers": ["paper-id-1"],
  "discarded_reason": "too broad / duplicate / not same benchmark"
}
```

### 4.6 Milestone Papers

V2 必须支持自动识别某个领域/任务的 milestone papers。

候选生成：

- 高引用论文。
- 高 citation velocity 新论文。
- 顶会/顶刊论文。
- 被多个后续方法作为 baseline 或 foundation 的论文。
- 提出关键 dataset / benchmark 的论文。
- 提出关键概念、架构、训练范式或 evaluation protocol 的论文。
- survey 中反复出现的论文。

排序信号：

- citation count。
- yearly citation velocity。
- influential citation count。
- venue quality。
- method adoption。
- benchmark influence。
- dataset influence。
- conceptual influence。
- recency adjustment。
- human confirmation。

输出字段：

```json
{
  "paper": "paper metadata",
  "milestone_score": 0.0,
  "why_milestone": "中文解释",
  "evidence": ["source evidence"],
  "category": "problem_definition | method_paradigm | dataset | benchmark | system | theory",
  "risk": "为什么可能不是 milestone"
}
```

Human-in-the-loop：

- UI 允许用户把论文标记为 milestone / not milestone。
- 用户标记会影响当前 Field Map，但不改变外部事实。
- 被用户确认的 milestone 在 Obsidian 中以 `#milestone` 标记。

### 4.7 Technology Timeline

V2 必须生成领域技术演化时间线。

时间线维度：

- Problem evolution：问题定义如何变化。
- Method evolution：方法范式如何变化。
- Dataset evolution：数据集如何变化。
- Benchmark / metric evolution：评价方式如何变化。
- System / scale evolution：模型规模、数据规模、训练资源如何变化。
- Limitation evolution：未解决问题如何迁移。

时间线生成流程：

1. 以当前论文作为 seed。
2. 基于 references 找 foundational papers。
3. 基于 cited-by 找 follow-up papers。
4. 基于 benchmark/dataset 找横向相关论文。
5. 按年份排序。
6. 对每篇论文生成 mini report。
7. 聚合成 timeline event。
8. 标注 milestone / follow-up / branch。

Timeline event 字段：

```json
{
  "year": 2024,
  "paper": "paper metadata",
  "event_type": "milestone | follow_up | benchmark | survey",
  "problem": "解决的问题",
  "key_idea": "核心 idea",
  "pipeline": "方法 pipeline",
  "evaluation": "使用的数据集和 metric",
  "influence": "对后续工作的影响",
  "evidence": ["R1 evidence"],
  "reliability": "R1"
}
```

### 4.8 Field Map

V2 的 Field Map 是领域级产物，不是单篇论文报告。

Field Map 必须回答：

- 这个领域/任务的终极目标是什么？
- 当前已经达到什么水平？
- 主要任务定义有哪些？
- 常用数据集和 benchmark 是什么？
- 重要 metric 是什么？
- 有哪些 milestone papers？
- 有哪些主要方法范式？
- 技术如何随时间演变？
- 还有哪些重要问题未解决？
- 现阶段热点话题是什么？
- 哪些研究机会值得继续探索？

Field Map 结构：

- Field Summary。
- Task Taxonomy。
- Dataset / Benchmark Table。
- Milestone Papers。
- Timeline。
- Method Families。
- Evaluation Protocols。
- Open Problems。
- Recent Trends。
- Research Opportunities。
- Evidence Index。

Field Map 可靠性：

- Field Summary 可以包含 R1 + R2，但必须分层展示。
- 事实性内容必须是 R1。
- 趋势判断和研究机会必须是 R2。
- 用户应该可以隐藏 R2，只看 R1 facts。

### 4.9 Multi-paper Compare

V2 需要支持多论文对比，用于理解一个方法家族或 benchmark 上的差异。

对比维度：

- Task。
- Dataset。
- Benchmark / metric。
- Method family。
- Model scale。
- Input / output modality。
- Training compute。
- Key result。
- Strength。
- Limitation。
- Availability：code / data / model。

比较规则：

- 默认不把不同 setting 的数值直接排序。
- 如果 setting 不同，显示 comparison risk。
- 对同一 benchmark 和相同 protocol 的结果，可以显示 sortable table。
- 每个对比单元都能点击 evidence。

### 4.10 Research Insight / R2

V2 可以提供 R2 级研究洞察，但必须清晰隔离。

R2 输出类型：

- 领域趋势判断。
- 研究机会。
- 方法设计启发。
- 实验迭代建议。
- 故事线梳理。
- 论文写作 angle。

R2 约束：

- 必须显示 R2 badge。
- 必须显示“这是推断/建议，不是文献事实”。
- 如果 R2 基于 R0/R1 evidence 推导，需要列出参考 evidence。
- 不能把论坛评论、模型常识、趋势判断伪装成 R1。

## 5. UX Design

V2 采用三层结构：

```text
Library
  → Paper Workspace
  → Field Map Workspace
```

### 5.1 Library

Library 是入口和本地研究资产索引。

必须包含：

- Import PDF。
- Import arXiv。
- Import DOI / URL。
- Zotero import。
- Recent Papers。
- Processing Queue。
- Saved Reports。
- Saved Field Maps。
- Search / Filter。

Paper card 显示：

- 真实论文标题。
- 作者、年份、venue/arXiv。
- PDF path。
- 状态：queued / processing / completed / failed。
- Report 是否存在。
- Obsidian note 是否存在。
- Field Map 是否生成。
- Rerun Agent。
- Open Workspace。

### 5.2 Paper Workspace

Paper Workspace 推荐三栏：

```text
┌──────────────┬──────────────────────────────┬──────────────────────────┐
│ Paper Nav    │ PDF Reader                   │ Report / Agent Panel     │
│ - Library    │ - PDF.js                     │ - Reading Report         │
│ - Outline    │ - Evidence highlight         │ - Evidence Detail        │
│ - Sections   │ - Text selection             │ - Focused Q&A            │
│ - Field Map  │ - Page jump                  │ - R1 Related Work        │
└──────────────┴──────────────────────────────┴──────────────────────────┘
```

默认主视图：

- 如果 report 未完成：显示 task progress。
- 如果 report 已完成：右侧默认显示 Reading Report。
- 点击 evidence：中间 PDF 跳页并高亮。
- 选中 PDF 文本：右侧出现“解释选区 / 生成 claim / 加入笔记”。

### 5.3 Field Map Workspace

Field Map Workspace 面向领域理解。

布局：

```text
┌──────────────────────────────┬──────────────────────────┐
│ Field Map Canvas / Timeline  │ Evidence / Agent Panel   │
│ - Timeline                   │ - Selected paper         │
│ - Milestone graph            │ - Why milestone          │
│ - Method families            │ - Evidence               │
│ - Open problems              │ - Ask field question     │
└──────────────────────────────┴──────────────────────────┘
```

视图模式：

- Timeline view。
- Paper graph view。
- Table view。
- Open problems view。
- Benchmark view。

## 6. Agent Architecture

V2 采用多 Agent / 多模块协作，但 UI 不暴露复杂 Agent 名称。

### 6.1 Core Agents

- PDF Parser：机械解析 PDF、页码、文本 chunk、section、references。
- Metadata Agent：提取 title、authors、venue、year、arXiv、DOI。
- R0 Paper Agent：生成当前论文 Reading Report。
- Evidence Verifier Agent：检查 claim 是否有 evidence，定位 PDF page/bbox。
- Question Answer Agent：回答用户追问，保留 R0/R1/R2。
- Citation Explorer Agent：执行 references、cited-by、related papers 搜索。
- Benchmark Agent：查 task、dataset、metric、leaderboard。
- Milestone Agent：识别 milestone papers。
- Timeline Agent：整理技术演化。
- Field Map Agent：聚合领域地图。
- Research Insight Agent：生成 R2 趋势和研究机会。
- Obsidian Agent：渲染 Obsidian-native Markdown。

### 6.2 Agent Guardrails

规则代码允许做：

- 文件保存。
- PDF 下载。
- PDF 解析。
- 文本 chunk。
- 引用解析。
- SQLite 存储。
- API 调用。
- Markdown 渲染。
- JSON schema 校验。

规则代码不允许做：

- 推断论文任务。
- 总结方法。
- 判断 milestone。
- 生成 R2 research insight。
- 判断 benchmark 可比性。

这些必须由 Agent 完成，并输出结构化 JSON。

## 7. Data Model

核心对象：

- Paper。
- PaperVersion。
- PaperMetadata。
- ReadingReport。
- Claim。
- Evidence。
- CitationEdge。
- RelatedPaper。
- BenchmarkRecord。
- FieldMap。
- TimelineEvent。
- MilestonePaper。
- UserQuestion。
- ObsidianNote。
- AgentTask。

关键字段：

```json
{
  "paper": {
    "id": "uuid",
    "title": "paper title",
    "authors": [],
    "year": 2025,
    "venue": "arXiv",
    "arxiv_id": "2605.08063v1",
    "doi": null,
    "pdf_path": "...",
    "source_url": "...",
    "content_hash": "...",
    "status": "completed"
  }
}
```

```json
{
  "evidence": {
    "id": "uuid",
    "claim_id": "uuid",
    "source_type": "current_paper | external_paper | web",
    "source_paper_id": "uuid",
    "quote": "original quote",
    "page": 3,
    "section": "Method",
    "bbox": null,
    "url": null,
    "location_status": "exact | page_and_quote | quote_only | missing"
  }
}
```

## 8. API Requirements

V2 后端 API 应包含：

- `POST /api/papers/import`：本地 PDF。
- `POST /api/papers/import-arxiv`：arXiv URL / ID。
- `POST /api/papers/import-url`：DOI / OpenReview / Semantic Scholar URL。
- `GET /api/papers`：Library。
- `GET /api/papers/{id}`：paper metadata。
- `GET /api/papers/{id}/status`：任务状态。
- `GET /api/papers/{id}/report`：Reading Report。
- `POST /api/papers/{id}/rerun`：重跑 R0。
- `POST /api/papers/{id}/ask`：聚焦追问。
- `GET /api/papers/{id}/evidence/{evidence_id}`：证据定位。
- `POST /api/papers/{id}/r1-search`：触发 R1。
- `GET /api/papers/{id}/related`：相关论文。
- `POST /api/field-maps`：从 seed paper 生成 Field Map。
- `GET /api/field-maps/{id}`：读取 Field Map。
- `POST /api/field-maps/{id}/rerun`：重跑 Field Map。
- `POST /api/obsidian/export-paper`：导出单篇 note。
- `POST /api/obsidian/export-field-map`：导出领域地图。
- `GET /api/tasks`：任务队列。

长任务要求：

- V2 应支持 SSE 或 WebSocket 返回实时状态。
- 每个 task 有 stage、message、progress、error、started_at、finished_at。
- 用户可以 cancel / retry。

## 9. Storage Requirements

V2 存储分层：

- SQLite：metadata、tasks、claims、evidence、citation edges。
- Local files：PDF、report JSON、Field Map JSON、Markdown note。
- Cache：外部搜索结果、API response、paper metadata。
- Optional vector index：paper chunks、claim embeddings、field map retrieval。

去重策略：

优先级从高到低：

1. DOI。
2. arXiv ID。
3. Semantic Scholar paper ID / OpenAlex work ID。
4. PDF content hash。
5. normalized title + first author + year。

## 10. Obsidian Requirements

V2 的 Obsidian 导出包括两类 note。

### 10.1 Paper Note

包含：

- YAML frontmatter：title、authors、year、venue、arxiv、doi、tags、status。
- PDF link。
- Executive Summary。
- R0 Reading Report。
- Evidence Index。
- Focused Q&A。
- R1 Related Work。
- Follow-up Ideas。
- User annotations。

### 10.2 Field Map Note

包含：

- Field Summary。
- Milestone Papers。
- Timeline。
- Dataset / Benchmark Table。
- Open Problems。
- Recent Trends。
- Research Opportunities。
- Paper graph links。

Obsidian 语法：

- `[[paper title]]` 连接论文。
- `[[task name]]` 连接任务。
- `[[dataset name]]` 连接数据集。
- `#R0` / `#R1` / `#R2` 标签。
- callout 展示 warning、missing evidence、comparison risk。

## 11. Error Handling

V2 必须清晰处理：

- PDF 无法解析。
- arXiv 下载失败。
- DOI / URL 无法解析。
- Semantic Scholar / OpenAlex 限流。
- DeepSeek timeout。
- Agent 返回非 JSON。
- Report schema validation failed。
- Evidence quote 无法定位。
- 外部论文 PDF 无法获取。
- R1 搜索结果不足。
- citation graph 过大。
- Obsidian 导出路径不可写。

错误展示原则：

- Library、Workspace、Field Map 都要显示任务失败原因。
- 用户可以 retry。
- 部分失败不应阻塞全部结果，例如 R0 完成但 R1 失败时仍可阅读 R0。
- 失败信息要能进入 task log，方便调试。

## 12. Success Metrics

V2 成功标准：

- 用户导入论文后能自动得到真实标题、metadata 和中文 Reading Report。
- R0 report 中关键 claim 的 evidence 覆盖率达到可用水平。
- 用户能一键从 claim 跳回 PDF 原文。
- R1 能找到当前论文 references / cited-by / related papers 中的高相关论文。
- Field Map 能正确列出 milestone papers、timeline 和 open problems。
- 多论文比较能明确提示 comparison risk。
- Obsidian 导出的 note 能直接作为长期研究笔记使用。
- 用户能从一篇 seed paper 出发，在 30 分钟内获得一个可继续人工修正的领域地图。

## 13. Implementation Priority

建议 V2 拆成 5 个阶段。

### Phase 1: Evidence Workflow

- PDF.js 阅读器。
- page jump。
- quote fuzzy matching。
- evidence highlight。
- PDF 选区追问。

### Phase 2: Metadata And Import

- arXiv metadata。
- DOI / URL import。
- Semantic Scholar metadata。
- OpenReview import。
- Zotero read-only import。
- 真实标题去重和显示。

### Phase 3: Real R1 Search

- references parser。
- Semantic Scholar references / citations。
- OpenAlex fallback。
- Papers with Code search。
- R1 related work report。
- comparison risk。

### Phase 4: Field Map

- milestone detection。
- timeline。
- method families。
- dataset / benchmark table。
- open problems。
- Field Map Workspace。

### Phase 5: Knowledge Base And Research Insight

- Obsidian vault sync。
- Field Map note。
- multi-paper compare。
- R2 research opportunities。
- user curation feedback。

## 14. V2 Non-goals

V2 暂不做：

- 自动复现实验。
- 自动训练模型。
- 投稿级完整论文写作。
- 多人协作。
- 替代 Zotero 的完整文献管理。
- 付费数据库全文抓取。
- 不受限制地爬 Google Scholar。

## 15. Acceptance Checklist

V2 完成时应满足：

- [ ] 本地 PDF 导入。
- [ ] arXiv 链接 / ID 自动下载 PDF。
- [ ] DOI / OpenReview / Semantic Scholar URL 导入。
- [ ] Zotero read-only 导入。
- [ ] 真实论文标题显示。
- [ ] R0 Reading Report 完整覆盖 task、dataset、benchmark、method、model scale、input/output、compute、strength、limitation、related work claims。
- [ ] 每条 R0 claim 有 evidence。
- [ ] Evidence 可跳转 PDF page。
- [ ] Evidence quote 可高亮。
- [ ] 用户可选中 PDF 文本追问。
- [ ] Focused Q&A 持久化。
- [ ] R1 references search。
- [ ] R1 cited-by search。
- [ ] R1 benchmark / Papers with Code search。
- [ ] Milestone papers 自动识别。
- [ ] 技术演化 timeline。
- [ ] Field Map。
- [ ] Open problems。
- [ ] Recent trends。
- [ ] R2 research opportunities。
- [ ] 多论文对比。
- [ ] comparison risk 标注。
- [ ] Obsidian paper note。
- [ ] Obsidian field map note。
- [ ] 任务队列可取消、重试、恢复。

## 16. Relationship To Original SMLThoughts

V2 对原始需求的覆盖关系：

- `关键内容提取`：由 R0 Reading Report 和 Focused Q&A 完成。
- `信息可靠性分级`：由 R0/R1/R2 schema、UI badge、Evidence Verifier 和 Obsidian tags 完成。
- `R1 related works`：由 Citation Explorer、Benchmark Agent、Semantic Scholar/OpenAlex/Papers with Code 搜索完成。
- `milestone papers`：由 Milestone Agent 和 human-in-the-loop confirmation 完成。
- `技术发展脉络`：由 Timeline Agent 和 Field Map Workspace 完成。
- `重要问题与热点话题`：由 Field Map 的 Open Problems、Recent Trends、Research Opportunities 完成。
- `R2 研究视野`：由 Research Insight Agent 完成，并强制与 R0/R1 分离展示。

V2 的最终目标不是让 Agent 替用户做研究判断，而是把论文阅读、证据追溯、引用扩展、领域地图和知识沉淀变成一个可靠、可复查、可持续积累的研究工作流。

## 17. V2 Ships When

V2 进入“可发布”状态的最低要求：

- Section 15 中 R0 / Evidence / R1 / Milestone / Timeline / Field Map 主线全部勾选。
- 任意一篇 arXiv 链接导入后，30 分钟内可得到包含 milestone papers、timeline 与 open problems 的 Field Map 首版。
- Obsidian paper note 与 field map note 在导出后能直接被 Obsidian 打开，且 wikilink、tag、callout 渲染正确。
- 至少一次完整端到端测试：seed paper → R0 → R1 → milestone → timeline → field map → obsidian note。
- 长任务可取消、可重试；失败原因在 Library、Workspace、Field Map 三处都可见。

满足以上条件后，V2 即视为达到 PRD 锁定的开源发布门槛，后续以 patch / minor 版本继续演进。

