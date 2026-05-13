<div align="center">

<img src="./assets/paperflow_banner.png" alt="Paperflow banner" width="720" />

# Paperflow

**Evidence-first AI paper workspace.**  
**证据优先的 AI 论文工作台。**

Read papers, verify claims, ask an Agent with context, and save durable research knowledge.
Paperflow is not a generic PDF reader: every generated claim is labeled **R0 / R1 / R2** and traced back to PDF evidence whenever possible.

用于阅读论文、核验证据、追问 Agent、沉淀知识。Paperflow 不是普通 PDF 阅读器：每个生成结论都带 **R0 / R1 / R2** 可靠性标记，并尽可能回到 PDF 原文证据。

[English](./README.md) · [中文](./README.zh-CN.md) · [Landing Page](./index.html)

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-red.svg)](./LICENSE)
[![Research-only](https://img.shields.io/badge/use-research%20only-orange.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?logo=react&logoColor=61DAFB)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Obsidian](https://img.shields.io/badge/Obsidian-7C3AED?logo=obsidian&logoColor=white)](https://obsidian.md/)

</div>

---

## Core Workflow

```mermaid
flowchart LR
  importPdf["Import PDF or arXiv 导入论文"] --> readingReport["Agent Reading Report 阅读报告"]
  readingReport --> evidenceHighlight["PDF Evidence Highlight 证据高亮"]
  evidenceHighlight --> agentChat["Chat with R0/R1/Web Context 追问 Agent"]
  agentChat --> obsidianExport["Export to Obsidian 沉淀笔记"]
```

Paperflow turns a paper into a reliability-labeled workspace: structured report first, evidence-backed claims second, paper-aware chat third, durable notes last.

Paperflow 把一篇论文变成可追溯的研究工作台：先生成结构化报告，再核验 PDF 证据，然后带着证据追问 Agent，最后沉淀到 Obsidian。

---

## Product Demo Strip

<table>
  <tr>
    <td width="20%"><img src="./assets/demo/01-import-to-report.png" alt="Import to Reading Report / 导入到阅读报告" /></td>
    <td width="20%"><img src="./assets/demo/02-claim-to-evidence.png" alt="Claim to PDF Evidence / 结论跳转到 PDF 证据" /></td>
    <td width="20%"><img src="./assets/demo/03-agent-chat.png" alt="Ask with Evidence / 带着证据追问" /></td>
    <td width="20%"><img src="./assets/demo/04-reliability-model.png" alt="R0/R1/R2 Reliability / 可靠性分级" /></td>
    <td width="20%"><img src="./assets/demo/05-obsidian-export.png" alt="Export to Obsidian / 导出到 Obsidian" /></td>
  </tr>
  <tr>
    <td><strong>Import to Report</strong><br />导入到阅读报告</td>
    <td><strong>Claim to Evidence</strong><br />结论跳转证据</td>
    <td><strong>Ask with Evidence</strong><br />带证据追问</td>
    <td><strong>R0/R1/R2</strong><br />可靠性分级</td>
    <td><strong>Obsidian Export</strong><br />沉淀到知识库</td>
  </tr>
</table>


---

## Quick Demo

Use one paper to see the full loop:

1. Import a local PDF or paste an arXiv URL.
2. Let the Agent generate a structured Reading Report.
3. Click a reliability-labeled claim.
4. Jump to the supporting PDF page and highlight the evidence.
5. Ask the Agent: "What evidence supports this limitation?"
6. Save or update the Obsidian note.

中文流程：

1. 导入本地 PDF，或粘贴 arXiv URL。
2. 等待 Agent 生成结构化阅读报告。
3. 点击带可靠性标记的结论。
4. 跳转到 PDF 原文页并高亮支持证据。
5. 追问 Agent："这条 limitation 的证据是什么？"
6. 保存或更新 Obsidian 笔记。

---

## Why Paperflow Is Different

- **R0/R1/R2 reliability model / 可靠性分级**: separates paper-grounded facts, external context, and higher-level inference.
- **PDF evidence grounding / PDF 证据定位**: claims can jump back to the PDF page and highlight supporting text.
- **Agent chat with paper + web/model context / 带上下文的 Agent 对话**: chat is grounded in the report, selected evidence, R1 cache, and optional web/model knowledge.
- **Local-first research memory / 本地优先研究记忆**: PDFs, report JSON, SQLite metadata, and Obsidian notes stay under local project data.
- **Obsidian export / 知识库沉淀**: reading outputs become durable knowledge, not disposable chat history.

The product stance is simple: **report first, chat second, evidence always**.  
产品原则很简单：**先报告，后聊天；始终回到证据。**

---

## News

- **2026-05-13 — v0.7 released.** Paperflow now presents a public-facing evidence-first AI paper workspace: bilingual README narrative, PDF evidence highlighting, responsive PDF search, Agent chat grounding, local-first research memory, and Obsidian export.

---

## Quickstart

> Requirements: Python 3.9+, Node.js 18+, and a DeepSeek API key for real Agent parsing.

```bash
git clone https://github.com/shiml20/PaperFlow.git
cd PaperFlow

export DEEPSEEK_API_KEY="your-deepseek-api-key"
cd paperflow
./run-dev.sh --install
```

Then open `http://127.0.0.1:5173`, import a PDF or arXiv URL, and open the Workspace.

If dependencies are already installed:

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
cd paperflow
./run-dev.sh
```

---

## How To Use

1. Import a local PDF or paste an arXiv URL.
2. Watch the Agent move from PDF parsing to dynamic partial reports.
3. Read the first key findings while the full report continues to fill in.
4. Open the completed Reading Report and inspect R0 / R1 / R2 claims.
5. Click a claim or evidence item to inspect source text and PDF location.
6. Ask the Agent a focused question grounded in the current paper.
7. Save or update the Obsidian note.

---

## DeepSeek Setup

Paperflow currently supports DeepSeek as the Agent API provider.
The fastest setup is `DEEPSEEK_API_KEY`.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | Yes | none | DeepSeek API key used by the backend PaperAgent. |
| `DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com/beta` | DeepSeek-compatible chat completions endpoint root. |
| `DEEPSEEK_MODEL` | No | `deepseek-v4-flash` | Model used for Reading Report generation. |
| `DEEPSEEK_REPORT_READ_TIMEOUT` | No | `90` | Read timeout in seconds for report generation. |
| `DEEPSEEK_CONFIG_PATH` | No | `~/.deepseek/config.toml` | Alternate config file path. |

Example config file:

```toml
api_key = "your-deepseek-api-key"
base_url = "https://api.deepseek.com/beta"
model = "deepseek-v4-flash"
```

`default_text_model` from older DeepSeek-TUI config files is ignored for Paperflow's report model. This keeps the Paperflow default on `deepseek-v4-flash` unless `DEEPSEEK_MODEL` or `model` is set explicitly.

Without a DeepSeek key, the backend reports `Agent not configured` and cannot produce a real R0/R1 Reading Report.

---

## Manual Run

### Backend

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

### Web Frontend

```bash
cd paperflow/frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### TUI

Paperflow also ships a Textual-based terminal UI that talks to the same backend.

```bash
cd paperflow/backend && . .venv/bin/activate
pip install -e ../tui

paperflow-tui
# or
PAPERFLOW_BASE_URL=http://127.0.0.1:8000 paperflow-tui
# or
python -m paperflow_tui
```

Useful bindings:

| Where | Key | Action |
| --- | --- | --- |
| Library | `i` | Import a local PDF |
| Library | `a` | Import an arXiv URL / ID |
| Library | `o` / `Enter` | Open the selected paper's Workspace |
| Library | `r` | Re-run the PaperAgent |
| Library | `R` | Refresh library + agent status |
| Workspace | `j` / `k` / arrows | Navigate claims |
| Workspace | `Enter` | Inspect evidence |
| Workspace | `a` | Ask a focused R0 / R1 / R2 question |
| Workspace | `1` | Run R1 related-work search |
| Workspace | `2` | Open Field Map |
| Workspace | `s` | Save / update Obsidian note |
| Workspace | `b` / `Esc` | Back to Library |

---

## Core Features

### Dynamic Reading Reports

- **Chunked full-paper reading**: long PDFs are split into bounded chunks instead of being summarized from only the first text window.
- **Dynamic partial reports**: the first completed chunk is saved immediately, so readers can see key findings before the whole paper finishes.
- **Coverage-aware generation**: the UI shows progress such as `覆盖全文 50%`, then `覆盖全文 100% · 8 chunks` when all chunks are covered.
- **Live parsing metrics**: elapsed time keeps ticking while generation is running; tokens, coverage, and chunk count update as new partial reports arrive.
- **Transparent process output**: the Workspace shows PDF text extraction, DeepSeek request preparation, model wait, chunk coverage, report persistence, and failure states.

### Evidence-First Workspace

- R0 / R1 / R2 reliability badges in the UI and data model.
- Evidence quote, page, section, bbox, and `location_status` for claims when available.
- PDF.js reader with page jump, bbox highlight, and select-to-ask.
- Right-side evidence detail panel for selected claims.
- Obsidian-native Markdown export with frontmatter, wikilinks, callouts, and reliability tags.

### Agent Conversation

- A formal right-rail Agent panel with transcript, process cards, status, and composer.
- Chat transcripts are persisted in SQLite and restored when the Workspace opens.
- `/chat` is backed by a DeepSeek chat agent over report + selected evidence + R1 cache, with a report-grounded fallback.
- `/chat/stream` provides SSE step/final events for the frontend.
- Runtime Agent configuration in the web UI: update local DeepSeek API key, switch model, and change report timeout.

### Literature Context And Field Maps

- Metadata import via arXiv, CrossRef, Semantic Scholar, OpenReview, and Zotero.
- Content-hash + DOI + arXiv-ID deduplication.
- Six-lane R1 search: seed, backward, forward, benchmark, survey, and recent.
- Field Map generation: milestones, timeline, task taxonomy, datasets, benchmarks, method families, open problems, trends, and R2 opportunities.
- Agent-enriched Field Map / lineage graph edges with source type, rationale, confidence, and UI labels.
- Multi-paper comparison and R2 research insights with Obsidian export.

---

## Reliability Model

| Level | Meaning | Examples |
| --- | --- | --- |
| **R0** | Strictly grounded in the current paper. Numbers must not be inferred or compared across settings. | "The model is trained on 8xA100 for 72 hours." |
| **R1** | Grounded in another paper / source fetched through external search. Source paper, venue, year, and URL should be recorded. | "This benchmark was introduced in paper X." |
| **R2** | Inference, trend judgement, or research opinion. Always shown with an R2 badge. | "This direction is likely to converge with diffusion priors." |

Reliability is rendered as a UI badge, persisted in JSON, embedded as `#R0` / `#R1` / `#R2` tags in Obsidian notes, and enforced inside the PaperAgent prompt contract.

---

## Architecture

Paperflow ships two front-ends sharing the same backend agent harness:

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

The agent harness lives only in the backend. Both the web frontend and the TUI are thin HTTP clients.

**Tech stack:** Python 3.9+ · FastAPI · Pydantic · PyMuPDF · httpx · pytest · React · TypeScript · Vite · Vitest · Textual · Rich · SQLite · DeepSeek API.

---

## Data And Schema

User data is stored under the project-level `data/` directory and is git-ignored by default.
This single location is used no matter whether the backend is started from the repository root,
`paperflow/`, or `paperflow/backend/`. Set `PAPERFLOW_DATA_DIR` only if you intentionally want
to override the local data root.

Every R0 claim follows this shape:

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

A full Reading Report covers paper metadata, executive summary, task, dataset, benchmark/metric, method, model scale, input/output, compute/training, key results, strengths, limitations, related-work claims, and an evidence index.

---

## Repository Layout

```text
PaperFlow/
├── README.md
├── README.zh-CN.md
├── index.html
├── LICENSE
├── assets/
│   ├── README.html                       ← GitHub Pages-friendly README
│   ├── favicon.svg
│   └── paperflow_banner.png
├── data/                                 ← local user data, git-ignored
├── design_docs/                         ← local design / PRD notes
└── paperflow/
    ├── run-dev.sh                       ← starts backend + frontend
    ├── backend/                         ← FastAPI + PaperAgent harness
    ├── frontend/                        ← React + Vite + TypeScript web client
    └── tui/                             ← Textual terminal client
```

---

## Testing

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

## Contributing

Paperflow is early, but the reliability contract is stable. Good first contributions:

- **Field timelines and domain maps**: curate timelines, milestones, method families, datasets, benchmarks, and open problems for specific research areas.
- **Friendlier interaction design**: improve the reading flow, evidence navigation, PDF highlight experience, Agent chat UX, keyboard shortcuts, and onboarding.
- **Other improvements**: parsing fidelity, evidence-location checks, Obsidian rendering, tests, docs, localization, and small reliability-focused fixes.

Please keep PRs aligned with the reliability contract: every UI surface that produces a fact should be expressible as R0 / R1 / R2 with evidence.

---

## License

Paperflow is released under the [**PolyForm Noncommercial License 1.0.0**](./LICENSE).

- You may freely use, copy, modify, and distribute Paperflow for noncommercial purposes.
- You may not use Paperflow for commercial purposes without a separate commercial license.
- Forks and derivative works must keep this license and the `Required Notice` line in [`LICENSE`](./LICENSE).
- The software is provided as is, without warranty of any kind.

For commercial use, please open an issue on the [GitHub repository](https://github.com/shiml20/PaperFlow) to discuss a commercial license.

Copyright © 2026 shiml20 and Paperflow contributors.

---

## Acknowledgements

- Agent integration is built against the DeepSeek API and reuses configuration written by the DeepSeek-TUI CLI when present.
- PDF parsing is powered by [PyMuPDF](https://github.com/pymupdf/PyMuPDF).
- The frontend is built with [Vite](https://vitejs.dev/) and [React](https://react.dev/).
- The prompt design was inspired by Peng Sida's open research-learning notes, [pengsida/learning_research](https://github.com/pengsida/learning_research).

If Paperflow is useful to your research workflow, a star is the kindest signal.

---

## Status

For release history and milestone details, see [`STATUS.md`](./STATUS.md).
