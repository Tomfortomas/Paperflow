<div align="center">

<img src="./assets/paperflow_banner.png" alt="Paperflow banner" width="720" />

# Paperflow

**证据优先的论文研读台：阅读报告、引用检索、领域地图、Obsidian 知识库。**

Paperflow 是一个面向 AI 研究者和工程师的本地优先论文工作台。
它使用 DeepSeek-backed Agent 生成结构化阅读报告，并把每个生成结论标记为 **R0 / R1 / R2**，尽可能追溯到 PDF 原文证据。

[English](./README.md) · [中文](./README.zh-CN.md) · [项目首页](./index.html)

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-red.svg)](./LICENSE)
[![Research-only](https://img.shields.io/badge/use-research%20only-orange.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?logo=react&logoColor=61DAFB)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Obsidian](https://img.shields.io/badge/Obsidian-7C3AED?logo=obsidian&logoColor=white)](https://obsidian.md/)

</div>

---

## Paperflow 是什么

Paperflow 把读论文变成一个可追溯、可积累的本地研究流程：

- 导入本地 PDF 或 arXiv 链接。
- 生成结构化 Reading Report，而不是一次性摘要。
- 用 R0 / R1 / R2 标记每个 claim 的可靠性。
- 点击 claim / evidence 回到 PDF 原文位置。
- 在右侧 Agent 对话区基于报告、选中证据、R1 缓存继续追问。
- 保存为 Obsidian 友好的本地知识库笔记。

产品原则很简单：**先报告，后聊天；没有证据，就不假装确定。**

---

## News

- **2026-05-12 — v0.6 完成。** 报告生成升级为快速 briefing → 并行 chunk 抽取 → coordinator 合并综合，在减少等待时间的同时保留全局一致性和证据追踪。
- **2026-05-12 — v0.5 完成。** Workspace 支持高清连续滚动 PDF pane、页码跳转、缩放控件、证据居中滚动，以及大屏三栏阅读布局。
- **2026-05-12 — v0.4 完成。** Agent Chat 已持久化，支持 SSE 对话流，evidence 可打开 PDF 并跳页，Field Map 关系边加入 Agent enrichment 元数据。
- **2026-05-12 — v0.3 发布。** Workspace 右侧升级为正式 Agent 对话栏，包含 transcript、process cards、status、composer 和 paper-scoped chat API。
- **2026-05-12 — v0.2 完成。** Evidence workflow、metadata import、R1 search、Field Map、compare、R2 insights、task queue 全部落地。
- **2026-05-12 — 项目首页加入仓库。** 可通过 [`index.html`](./index.html) 查看轻量 landing page。

---

## 快速开始

> 需要 Python 3.9+、Node.js 18+，以及用于真实 Agent 解析的 DeepSeek API Key。

```bash
git clone https://github.com/shiml20/PaperFlow.git
cd PaperFlow

export DEEPSEEK_API_KEY="your-deepseek-api-key"
cd paperflow
./run-dev.sh --install
```

然后打开 `http://127.0.0.1:5173`，导入 PDF 或 arXiv URL，进入 Workspace。

如果依赖已经安装过：

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
cd paperflow
./run-dev.sh
```

---

## 如何使用

1. 导入本地 PDF，或粘贴 arXiv URL。
2. 等待 Agent 从 PDF 解析进入动态部分报告。
3. 首个 chunk 完成后先看关键发现，完整报告会继续补全。
4. 打开 Reading Report，检查 R0 / R1 / R2 claim。
5. 点击 claim 或 evidence，查看原文证据和 PDF 位置。
6. 在右侧 Agent 对话区基于当前论文继续追问。
7. 保存或更新 Obsidian 笔记。

---

## DeepSeek 配置

Paperflow 当前只支持 DeepSeek 作为 Agent API provider。
最快方式是设置 `DEEPSEEK_API_KEY`。

| 变量 | 必需 | 默认值 | 作用 |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | 是 | 无 | 后端 PaperAgent 使用的 DeepSeek API Key。 |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com/beta` | DeepSeek-compatible chat completions endpoint root。 |
| `DEEPSEEK_MODEL` | 否 | `deepseek-v4-flash` | Reading Report 默认模型。 |
| `DEEPSEEK_REPORT_READ_TIMEOUT` | 否 | `90` | 报告生成 read timeout，单位秒。 |
| `DEEPSEEK_CONFIG_PATH` | 否 | `~/.deepseek/config.toml` | 自定义配置文件路径。 |

配置文件示例：

```toml
api_key = "your-deepseek-api-key"
base_url = "https://api.deepseek.com/beta"
model = "deepseek-v4-flash"
```

旧 DeepSeek-TUI 配置里的 `default_text_model` 不会覆盖 Paperflow 的默认报告模型。除非显式设置 `DEEPSEEK_MODEL` 或 `model`，否则默认使用 `deepseek-v4-flash`。

没有 DeepSeek Key 时，后端会报告 `Agent not configured`，无法生成真实 R0/R1 Reading Report。

---

## 手动运行

### 后端

```bash
cd paperflow/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'

export DEEPSEEK_API_KEY="your-key"
export DEEPSEEK_MODEL="deepseek-v4-flash"
export DEEPSEEK_REPORT_READ_TIMEOUT="90"

uvicorn app.main:app --reload
```

### Web 前端

```bash
cd paperflow/frontend
npm install
npm run dev
```

打开 `http://localhost:5173`。

### TUI

Paperflow 也提供 Textual 终端 UI，连接同一个后端。

```bash
cd paperflow/backend && . .venv/bin/activate
pip install -e ../tui

paperflow-tui
# 或
PAPERFLOW_BASE_URL=http://127.0.0.1:8000 paperflow-tui
# 或
python -m paperflow_tui
```

常用快捷键：

| 位置 | 按键 | 动作 |
| --- | --- | --- |
| Library | `i` | 导入本地 PDF |
| Library | `a` | 导入 arXiv URL / ID |
| Library | `o` / `Enter` | 打开选中论文 Workspace |
| Library | `r` | 重新运行 PaperAgent |
| Library | `R` | 刷新 library 和 agent status |
| Workspace | `j` / `k` / arrows | 导航 claims |
| Workspace | `Enter` | 查看 evidence |
| Workspace | `a` | 提出 R0 / R1 / R2 聚焦问题 |
| Workspace | `1` | 运行 R1 related-work search |
| Workspace | `2` | 打开 Field Map |
| Workspace | `s` | 保存 / 更新 Obsidian 笔记 |
| Workspace | `b` / `Esc` | 返回 Library |

---

## 核心功能

### 动态 Reading Report

- **长论文分 chunk 读取**：不再只截取 PDF 前面一段。
- **动态部分报告**：首个 chunk 完成后立即保存，读者可以先看关键发现。
- **覆盖率感知 UI**：显示 `覆盖全文 50%`、`覆盖全文 100% · 8 chunks` 等状态。
- **实时解析指标**：生成中 elapsed time 会动态更新，tokens、coverage、chunk count 会随部分报告刷新。
- **透明过程输出**：展示 PDF 文本抽取、DeepSeek 请求准备、模型等待、chunk 覆盖、报告落盘、失败状态。

### 证据优先 Workspace

- R0 / R1 / R2 可靠性标签进入 UI 和数据模型。
- claim 尽量携带 evidence quote、page、section、bbox 和 `location_status`。
- PDF.js 阅读器支持跳页、bbox highlight、选区追问。
- 右侧 evidence detail 面板展示当前 claim 的证据。
- Obsidian-native Markdown 导出支持 frontmatter、wikilinks、callouts、reliability tags。

### Agent 对话区

- 右侧正式 Agent panel：transcript、process cards、status、composer。
- Chat transcript 持久化到 SQLite，Workspace 打开时自动恢复。
- `/chat` 使用 DeepSeek chat agent，读取 report + selected evidence + R1 cache，并保留 report-grounded fallback。
- `/chat/stream` 提供 SSE step/final events。
- Web UI 可运行时更新本地 DeepSeek API Key、切换模型、调整报告 timeout。

### 文献脉络与 Field Map

- 支持 arXiv、CrossRef、Semantic Scholar、OpenReview、Zotero metadata import。
- 基于 content hash + DOI + arXiv ID 去重。
- 六路 R1 search：seed、backward、forward、benchmark、survey、recent。
- Field Map 包含 milestones、timeline、task taxonomy、datasets、benchmarks、method families、open problems、trends、R2 opportunities。
- Field Map / lineage graph edge 带 Agent enrichment：source type、rationale、confidence、UI label。
- 支持多论文 compare、R2 research insights 和 Obsidian export。

---

## 可靠性模型

| 等级 | 含义 | 示例 |
| --- | --- | --- |
| **R0** | 严格来自当前论文。数字不能跨设置推断或比较。 | "The model is trained on 8xA100 for 72 hours." |
| **R1** | 来自其他论文 / 外部来源，需要记录来源论文、venue、year、URL。 | "This benchmark was introduced in paper X." |
| **R2** | 推断、趋势判断、研究观点，必须带 R2 标签。 | "This direction is likely to converge with diffusion priors." |

可靠性不是附加 metadata，而是 UI badge、JSON 持久化、Obsidian `#R0` / `#R1` / `#R2` 标签和 Agent prompt contract 的核心。

---

## 架构

Paperflow 有两个前端，共用同一个后端 Agent harness：

```text
┌──────────────────────────────┐                ┌──────────────────────────────────┐
│  Web Frontend (React + Vite) │                │  Backend (FastAPI)               │
│  - Library-first home        │ ─── REST ───► │  - PaperStorage (SQLite + files) │
│  - Report-first Workspace    │                │  - PDF parser (PyMuPDF)          │
│  - Agent rail + evidence     │                │  - ReportService                 │
│  - PDF viewer                │                │  - PaperAgent (DeepSeek client)  │
└──────────────────────────────┘                └──────────────┬───────────────────┘
                                                               │
┌──────────────────────────────┐                               │
│  TUI (Textual + httpx)       │ ─── REST ────────────────────►│
│  - Same Library + Workspace  │                               │
│  - R0/R1/R2 badges           │                               │
│  - Keyboard-driven           │                               │
└──────────────────────────────┘                               ▼
                                                 ┌──────────────────────────┐
                                                 │  Local Data              │
                                                 │  - PDFs                  │
                                                 │  - report JSON           │
                                                 │  - Obsidian vault notes  │
                                                 │  - SQLite metadata       │
                                                 └──────────────────────────┘
```

Agent harness 只在后端。Web 前端和 TUI 都是薄 HTTP client。

**技术栈：** Python 3.9+ · FastAPI · Pydantic · PyMuPDF · httpx · pytest · React · TypeScript · Vite · Vitest · Textual · Rich · SQLite · DeepSeek API。

---

## 数据与 Schema

用户数据存放在 `paperflow/backend/paperflow_data/`，默认 git-ignored。

每个 R0 claim 的基本结构：

```json
{
  "id": "claim-id",
  "text": "中文解释 / English explanation",
  "reliability": "R0",
  "evidence": [
    {
      "source": "paper.pdf",
      "quote": "verbatim quote from the PDF",
      "page": 3,
      "section": "Method",
      "bbox": null,
      "location_status": "page_and_quote"
    }
  ],
  "uncertainty": null
}
```

完整 Reading Report 覆盖 metadata、executive summary、task、dataset、benchmark/metric、method、model scale、input/output、compute/training、key results、strengths、limitations、related-work claims 和 evidence index。

---

## 仓库结构

```text
PaperFlow/
├── README.md
├── README.zh-CN.md
├── index.html
├── LICENSE
├── assets/
│   ├── README.html                       ← GitHub Pages 友好的 README 页面
│   ├── favicon.svg
│   └── paperflow_banner.png
├── design_docs/                         ← 本地设计 / PRD 笔记
└── paperflow/
    ├── run-dev.sh                       ← 启动 backend + frontend
    ├── backend/                         ← FastAPI + PaperAgent harness
    ├── frontend/                        ← React + Vite + TypeScript web client
    └── tui/                             ← Textual terminal client
```

---

## 测试

```bash
# Backend
cd paperflow/backend
. .venv/bin/activate
pytest -q

# Frontend
cd ../frontend
npm test
npm run build

# TUI
cd ../tui
pytest -q
```

---

## 贡献

Paperflow 还在早期，但 reliability contract 已经稳定。适合优先贡献的方向：

- 提升 PDF 解析质量：section、table、reference、equation。
- 加强 evidence 定位与 PDF highlight。
- 扩展 Obsidian renderer：Field Map note、R2 callout、citation graph link。
- 增加 import -> report -> Agent chat -> Obsidian export 的端到端测试。

请保持 PR 与可靠性契约一致：任何产生事实的 UI 表面，都应该能表示为 R0 / R1 / R2 并带证据。

---

## License

Paperflow 使用 [**PolyForm Noncommercial License 1.0.0**](./LICENSE)。

- 可自由用于非商业目的，包括学术研究、教学、个人学习、公益 / 教育 / 政府 / 公共研究组织内部使用。
- 未经单独商业授权，不可用于商业目的，包括付费托管、嵌入商业产品、公司内部生产工具等。
- fork 和衍生作品必须保留该 license 和 [`LICENSE`](./LICENSE) 中的 `Required Notice`。
- 软件按现状提供，不含任何担保。

商业使用请在 [GitHub repository](https://github.com/shiml20/PaperFlow) 开 issue 讨论商业授权。

Copyright © 2026 shiml20 and Paperflow contributors.

---

## 致谢

- Agent integration 基于 DeepSeek API，并可复用 DeepSeek-TUI CLI 写入的配置。
- PDF parsing 基于 [PyMuPDF](https://github.com/pymupdf/PyMuPDF)。
- 前端基于 [Vite](https://vitejs.dev/) 和 [React](https://react.dev/)。
- Prompt 设计受到彭思达开源科研经验文档 [pengsida/learning_research](https://github.com/pengsida/learning_research) 的启发。

如果 Paperflow 对你的研究流程有帮助，欢迎 star。

---

## Status

Paperflow 当前有两个前端，共用同一个后端 Agent harness：

- **Web**：React + Vite + TypeScript，report-first Workspace、PDF viewer、Agent rail、Obsidian export。
- **TUI**：Textual + httpx，键盘驱动 Library / Workspace / R0-R1-R2 / Evidence / Q&A flow。

### v0.1

- [x] Library-first home with status tracking (`queued` -> `processing` -> `completed` / `failed`)
- [x] DeepSeek-backed PaperAgent generating R0 Reading Reports
- [x] R0 / R1 / R2 reliability badges in UI and data model
- [x] Evidence quote, page, and section per claim
- [x] Background agent task with persistent reports
- [x] Obsidian-native paper note export
- [x] Focused Q&A around dataset / benchmark / method / compute / limitations

### v0.2

- [x] **Evidence Workflow**：PyMuPDF block parser、evidence verification、PDF.js page jump、bbox highlight、select-to-ask。
- [x] **Metadata & Import**：arXiv、CrossRef、Semantic Scholar、OpenReview、Zotero、DOI/arXiv/content-hash dedup。
- [x] **Real R1 Search**：Semantic Scholar、OpenAlex fallback、Papers with Code、本地 references 的六路 related-work search。
- [x] **Field Map**：milestones、timeline、task taxonomy、datasets、benchmarks、method families、open problems、trends、R2 opportunities。
- [x] **Compare + R2 + Task Queue**：多论文 compare、research insights、Field Map Obsidian export、cancel/retry/resume task APIs。

### v0.3

- [x] 正式 Agent Conversation rail，替代旧 focused Q&A 区域。
- [x] Paper-scoped chat API：`POST /api/papers/{paper_id}/chat`。
- [x] Evidence-aware chat inputs：selected claim、evidence、page、quote、section。
- [x] 右侧 rail 信息架构：Agent status、config、evidence、chat、Obsidian export。

### v0.4

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

### v0.5

- [x] PDF 页面按 device-pixel-ratio 渲染，Retina 和大屏下文字更清晰。
- [x] PDF 支持连续滚动阅读，toolbar 支持直接输入页码跳转，并提供 `Fit`、`100%`、`125%`、`150%` 缩放预设。
- [x] PDF 从报告流中独立成 Workspace pane，大屏下变成左侧栏。
- [x] 保留 evidence-driven PDF 打开逻辑：点击 evidence 会打开 PDF pane、跳到对应页，并在有 bbox 时把高亮滚到视野中。

### v0.6

- [x] 将串行全文报告生成替换为分阶段 Agent pipeline：快速 paper briefing、并行 chunk 抽取、coordinator 去重合并、最终综合。
- [x] 所有 chunk agent 共享同一份 paper briefing，让并行抽取仍保持全局一致，并减少重复 claim。
- [x] 并行抽取过程中继续保存 partial report，最终由 coordinator 合并重复、保守补齐缺失 section，并保留精确 evidence quote。
- [x] 增加更细的生成状态：briefing、并行 chunk 抽取、单个 chunk 完成、coordinator synthesis。
