<div align="center">

<img src="./assets/paperflow_banner.png" alt="Paperflow banner" width="720" />

# Paperflow

**Evidence-first paper reading + citation-aware search + field map + Obsidian knowledge base.**

A local-first paper-reading workbench for AI researchers and engineers.
Powered by DeepSeek-backed agents, every generated claim is graded **R0 / R1 / R2** and traced back to the paper whenever possible.

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-red.svg)](./LICENSE)
[![Research-only](https://img.shields.io/badge/use-research%20only-orange.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?logo=react&logoColor=61DAFB)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Obsidian](https://img.shields.io/badge/Obsidian-7C3AED?logo=obsidian&logoColor=white)](https://obsidian.md/)

</div>

---

## Why Paperflow

Reading papers is not a one-shot summarization task. It is a continuous workflow of:

- judging the task, dataset, benchmark, model and compute behind a paper,
- backtracking each conclusion to the exact place in the PDF,
- walking out from one paper to its references, cited-by and related work,
- saving the result into a personal knowledge base you can keep extending.

Paperflow turns that workflow into a local-first, evidence-graded research IDE.

It is opinionated:

- **Report first, chat second.** You open a paper and see a structured Reading Report, not a blank chatbox.
- **Every claim is graded.** R0 = grounded in the current paper, R1 = grounded in external papers, R2 = inference / opinion.
- **Evidence is the product.** Every fact tries to carry a quote, page and section, and can jump back into the PDF when location data is available.
- **Local-first by default.** PDFs, report JSON, SQLite metadata, and Obsidian notes live on your disk.

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
- `POST /api/papers/{paper_id}/chat` returns structured steps, messages, reliability, answer claim, and evidence.
- Selected claim/evidence/page/quote can be passed into the Agent chat so answers stay grounded in the current report.
- Runtime Agent configuration in the web UI: update local DeepSeek API key, switch model, and change report timeout.

### Literature Context And Field Maps

- Metadata import via arXiv, CrossRef, Semantic Scholar, OpenReview, and Zotero.
- Content-hash + DOI + arXiv-ID deduplication.
- Six-lane R1 search: seed, backward, forward, benchmark, survey, and recent.
- Field Map generation: milestones, timeline, task taxonomy, datasets, benchmarks, method families, open problems, trends, and R2 opportunities.
- Multi-paper comparison and R2 research insights with Obsidian export.

---

## Quickstart

> Requirements: Python 3.9+, Node.js 18+, and a DeepSeek API key for real Agent parsing.

### Fastest Path

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

### Manual Backend

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

### Manual Web Frontend

```bash
cd paperflow/frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### Typical Workflow

1. Import a local PDF or paste an arXiv URL.
2. Watch the Agent move from PDF parsing to dynamic partial reports.
3. Read the first key findings while the report continues to fill in.
4. Open the completed Reading Report and inspect R0 / R1 / R2 claims.
5. Click a claim to inspect evidence in the right rail.
6. Ask focused Agent questions grounded in the selected claim or evidence.
7. Save or update the Obsidian note.

---

## DeepSeek Configuration

Paperflow currently supports DeepSeek as the Agent API provider.
The backend reads credentials in this order:

1. `DEEPSEEK_API_KEY` environment variable.
2. `api_key` in the config file.

The config file path is `DEEPSEEK_CONFIG_PATH` when set, otherwise `~/.deepseek/config.toml`.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | Yes | none | DeepSeek API key used by the backend PaperAgent. |
| `DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com/beta` | DeepSeek-compatible chat completions endpoint root. |
| `DEEPSEEK_MODEL` | No | `deepseek-v4-flash` | Model used for Reading Report generation. |
| `DEEPSEEK_REPORT_READ_TIMEOUT` | No | `90` | Read timeout in seconds for report generation. Increase this for long PDFs or slow model responses. |
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

## TUI

Paperflow also ships a Textual-based terminal UI that talks to the same backend.

```bash
cd paperflow/backend && . .venv/bin/activate
pip install -e ../tui

# Make sure the backend is running, then in another terminal:
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

## Reliability Model

| Level | Meaning | Examples |
| --- | --- | --- |
| **R0** | Strictly grounded in the current paper. Numbers must not be inferred or compared across settings. | "The model is trained on 8xA100 for 72 hours." |
| **R1** | Grounded in another paper / source fetched through external search. Source paper, venue, year, and URL should be recorded. | "This benchmark was introduced in paper X." |
| **R2** | Inference, trend judgement, or research opinion. Always shown with an R2 badge. | "This direction is likely to converge with diffusion priors." |

Reliability is rendered as a UI badge, persisted in JSON, embedded as `#R0` / `#R1` / `#R2` tags in Obsidian notes, and enforced inside the PaperAgent prompt contract.

---

## Reading Report Schema

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
├── LICENSE
├── assets/
│   └── paperflow_banner.png
├── design_docs/                         ← local design / PRD notes, not required at runtime
└── paperflow/
    ├── run-dev.sh                       ← starts backend + frontend
    ├── backend/                         ← FastAPI + PaperAgent harness
    │   ├── app/
    │   ├── tests/
    │   └── pyproject.toml
    ├── frontend/                        ← React + Vite + TypeScript web client
    │   ├── src/
    │   └── package.json
    └── tui/                             ← Textual terminal client
        ├── paperflow_tui/
        └── tests/
```

User data is stored under `paperflow/backend/paperflow_data/` and is git-ignored by default.

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

- Improve PDF parsing fidelity for sections, tables, references, and equations.
- Add stronger evidence-location checks and PDF highlighting.
- Extend the Obsidian renderer for Field Maps, R2 callouts, and citation graph links.
- Add end-to-end tests for import -> report -> Agent chat -> Obsidian export.

Please keep PRs aligned with the reliability contract: every UI surface that produces a fact should be expressible as R0 / R1 / R2 with evidence.

---

## License

Paperflow is released under the [**PolyForm Noncommercial License 1.0.0**](./LICENSE).

This means:

- You may freely use, copy, modify, and distribute Paperflow for any noncommercial purpose, including academic research, teaching, personal study, hobby projects, and use inside charitable, educational, government, or public research organizations.
- You may not use Paperflow for any commercial purpose, including hosting it as a paid service, embedding it inside a commercial product, or using it as part of a for-profit company's internal tooling, without a separate commercial license.
- Forks and derivative works must keep this license and the `Required Notice` line in [`LICENSE`](./LICENSE).
- The software is provided as is, without warranty of any kind.

For commercial use, please open an issue on the [GitHub repository](https://github.com/shiml20/PaperFlow) to discuss a commercial license.

Copyright © 2026 shiml20 and Paperflow contributors.

---

## Acknowledgements

- Agent integration is built against the DeepSeek API and reuses configuration written by the DeepSeek-TUI CLI when present.
- PDF parsing is powered by [PyMuPDF](https://github.com/pymupdf/PyMuPDF).
- The frontend is built with [Vite](https://vitejs.dev/) and [React](https://react.dev/).

If Paperflow is useful to your research workflow, a star is the kindest signal.

---

## Status

Paperflow currently ships two front-ends on top of the same backend agent harness:

- **Web**: React + Vite + TypeScript, report-first Workspace, PDF viewer, Agent rail, and Obsidian export.
- **TUI**: Textual + httpx, keyboard-driven Library / Workspace / R0-R1-R2 / Evidence / Q&A flow.

### V1.1

- [x] Library-first home with status tracking (`queued` -> `processing` -> `completed` / `failed`)
- [x] DeepSeek-backed PaperAgent generating R0 Reading Reports
- [x] R0 / R1 / R2 reliability badges in UI and data model
- [x] Evidence quote, page, and section per claim
- [x] Background agent task with persistent reports
- [x] Obsidian-native paper note export
- [x] Focused Q&A around dataset / benchmark / method / compute / limitations

### V2

- [x] **Evidence Workflow**: PyMuPDF block parser, evidence verification, PDF.js page jump, bbox highlight, and select-to-ask.
- [x] **Metadata & Import**: arXiv, CrossRef, Semantic Scholar, OpenReview, Zotero, and DOI/arXiv/content-hash deduplication.
- [x] **Real R1 Search**: six-lane related-work search over Semantic Scholar, OpenAlex fallback, Papers with Code, and local references.
- [x] **Field Map**: milestones, timeline, task taxonomy, datasets, benchmarks, method families, open problems, trends, and R2 opportunities.
- [x] **Compare + R2 + Task Queue**: multi-paper compare, research insights, Field Map Obsidian export, cancel/retry/resume task APIs.

### V3

- [x] Formal Agent Conversation rail replacing the old focused Q&A area.
- [x] Paper-scoped chat API: `POST /api/papers/{paper_id}/chat`.
- [x] Evidence-aware chat inputs: selected claim, evidence, page, quote, and section.
- [x] Right-rail information architecture for Agent status, config, evidence, chat, and Obsidian export.

### V3.5

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
