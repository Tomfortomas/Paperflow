<div align="center">

# PaperFlow

**Evidence-first paper reading + citation-aware search + field map + Obsidian knowledge base.**

A local-first paper-reading workbench for AI researchers and engineers.
Powered by DeepSeek-backed agents — every claim is graded **R0 / R1 / R2** and can be traced back to the PDF.

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-red.svg)](./LICENSE)
[![Research-only](https://img.shields.io/badge/use-research%20only-orange.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?logo=react&logoColor=61DAFB)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Obsidian](https://img.shields.io/badge/Obsidian-7C3AED?logo=obsidian&logoColor=white)](https://obsidian.md/)

</div>

---

## Why PaperFlow

Reading papers is not a one-shot summarization task. It is a continuous workflow of:

- judging the task, dataset, benchmark, model and compute behind a paper,
- backtracking each conclusion to the exact place in the PDF,
- walking out from one paper to its references, cited-by and related work,
- saving the result into a personal knowledge base you can keep extending.

**PaperFlow turns that workflow into a local-first, evidence-graded research IDE.**

It is opinionated:

- **Report first, chat second.** You open a paper and see a structured Reading Report, not a blank chatbox.
- **Every claim is graded.** R0 = grounded in the current paper, R1 = grounded in external papers, R2 = inference / opinion. The grade is a first-class citizen of the UI, the data model, and the Obsidian export.
- **Evidence is the product.** Every fact tries to carry a quote, page and section — and tries to jump back into the PDF.
- **Local-first knowledge base.** PDFs, report JSON, and Markdown notes live on your disk and sync to an Obsidian-friendly vault.

---

## Status

PaperFlow currently ships **two front-ends** on top of the same V1.1 backend agent harness:

- **Web** — React + Vite + TypeScript, two-column Report-first Workspace.
- **TUI** — Textual + httpx, keyboard-driven, same Library / Workspace / R0-R1-R2 / Evidence / Q&A / Obsidian flow inside your terminal.

V1.1 workbench features:

- Library-first home with status tracking (`queued` → `processing` → `completed` / `failed`)
- DeepSeek-backed PaperAgent generating R0 Reading Reports
- R0 / R1 / R2 reliability badges in UI and data model
- Evidence quote, page and section per claim
- Two-column Report-first Workspace with Evidence Detail side panel
- Background agent task (no UI blocking on import)
- Persistent report — survives backend restart
- Obsidian-native paper note (frontmatter, wikilinks, callouts, reliability tags)
- Focused Q&A around dataset / benchmark / method / compute / limitations

V2 progress (in active rollout):

- [x] **Phase 2 — Metadata & Import**: real `authors / year / venue / DOI / arXiv ID` populated via arXiv, CrossRef, Semantic Scholar, OpenReview APIs; new `POST /api/papers/import-url` auto-detects source; read-only Zotero importer (`POST /api/papers/import-zotero`); content-hash + DOI + arXiv-ID dedup; metadata chips on Library cards (web + TUI)
- [x] **Phase 1 — Evidence Workflow**: PyMuPDF block-level parser with section guesses; `EvidenceVerifier` fuzzy-matches every agent quote to page + bbox + `location_status`; PDF.js viewer with page jump, bbox highlight, and select-to-ask; TUI evidence panel surfaces bbox + status; new endpoints `GET /api/papers/{id}/pdf`, `GET /api/papers/{id}/chunks`, `POST /api/papers/{id}/ask-selection`
- [x] **Phase 3 — Real R1 Search**: six-lane pipeline (seed → backward → forward → benchmark → survey → recent) over Semantic Scholar Graph API, OpenAlex (fallback), and Papers with Code, plus a regex-based local references parser; each candidate carries author / year / venue / DOI / arXiv / citation counts and a `comparison_risk` note; new endpoints `POST /api/papers/{id}/r1-search` and `GET /api/papers/{id}/related`; web and TUI show a richer Related Work panel with the per-lane query trace.
- [x] **Phase 4 — Field Map**: heuristic Milestone Agent scores R1 candidates on citations / velocity / venue / category, Timeline aggregator orders milestones + follow-ups chronologically, Field Map aggregator yields task taxonomy, datasets/benchmarks, metrics, method families, open problems (from R0 limitations), recent trends (R2) and research opportunities (R2); new endpoints `POST /api/field-maps`, `GET /api/field-maps/{id}`, `POST /api/field-maps/{id}/rerun`, `GET /api/field-maps`; web Workspace gains a Field Map section, TUI gets a dedicated Field Map screen (`2` to open).
- [x] **Phase 5 — Compare + R2 + Cancel/Retry/Resume**: `POST /api/compare` pivots two or more papers across Task / Dataset / Benchmark / Method / Compute / Result / Limitations / Availability with per-cell evidence and per-row `comparison_risk`; `POST /api/field-maps/{id}/insights` runs the Research Insight Agent (R2 only — trends, opportunities, method-angle, story, writing-scaffold); `POST /api/field-maps/{id}/export-obsidian` writes a `#milestone` / `#R2`-tagged note for the field map; new task queue (`GET /api/tasks`, `GET /api/tasks/{id}`, `POST /api/tasks/{id}/cancel`, `POST /api/tasks/{id}/retry`) persists status snapshots, recovers them on restart (any `running` task is flipped to `failed` so you can retry), and supports cooperative cancellation via a shared `threading.Event`.

---

## Architecture

PaperFlow ships two front-ends sharing the same backend agent harness:

```text
┌──────────────────────────────┐                ┌──────────────────────────────────┐
│  Web Frontend (React + Vite) │                │  Backend (FastAPI)               │
│  - Library-first home        │ ─── REST ───► │  - PaperStorage (SQLite + files) │
│  - Report-first Workspace    │                │  - PDF parser (PyMuPDF)          │
│  - Reliability badges        │                │  - ReportService                 │
│  - Evidence Detail panel     │                │  - PaperAgent (DeepSeek client)  │
│  - Focused Q&A               │                │  - Obsidian-native renderer      │
└──────────────────────────────┘                └──────────────┬───────────────────┘
                                                               │
┌──────────────────────────────┐                               │
│  TUI (Textual + httpx)       │ ─── REST ────────────────────►│
│  - Same Library + Workspace  │                               │
│  - R0/R1/R2 badges in terminal│                              │
│  - Keyboard-driven           │                               │
└──────────────────────────────┘                               ▼
                                                 ┌──────────────────────────┐
                                                 │  Local Data (paperflow_data/)
                                                 │  - PDFs                  │
                                                 │  - report JSON           │
                                                 │  - Obsidian vault notes  │
                                                 │  - SQLite metadata       │
                                                 └──────────────────────────┘
```

The agent harness — PaperAgent + ReportService + DeepSeekClient — lives only in the backend, just like the `app-server` / `tui` separation in [DeepSeek-TUI](https://github.com/Hmbown/DeepSeek-TUI). Both the web frontend and the TUI are thin HTTP clients.

**Tech stack:** Python 3.9+ · FastAPI · Pydantic · PyMuPDF · httpx · pytest · React · TypeScript · Vite · Vitest · Textual · Rich · SQLite · DeepSeek API.

---

## Quickstart

> Requirements: Python 3.9+, Node.js 18+, and a DeepSeek API key for real Agent parsing.

### 1. Clone

```bash
git clone https://github.com/shiml20/PaperFlow.git
cd PaperFlow
```

### 2. Fastest API Setup (DeepSeek)

PaperFlow currently supports DeepSeek as the Agent API provider. The fastest path
for a new user is to export one environment variable before starting the app:

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
cd paperflow
./run-dev.sh --install
```

Then open `http://127.0.0.1:5173`, import a PDF or arXiv URL, and wait for the
Reading Report to finish.

If dependencies are already installed, use:

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
cd paperflow
./run-dev.sh
```

### 3. DeepSeek Configuration

The backend reads DeepSeek credentials from the environment first, then falls
back to a config file:

1. `DEEPSEEK_API_KEY` environment variable.
2. `api_key` in the config file.

The config file path is `DEEPSEEK_CONFIG_PATH` when set, otherwise
`~/.deepseek/config.toml`.

Supported environment variables:

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | Yes | none | DeepSeek API key used by the backend PaperAgent. |
| `DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com/beta` | DeepSeek-compatible chat completions endpoint root. |
| `DEEPSEEK_MODEL` | No | `deepseek-v4-flash` | Model used for Reading Report generation. |
| `DEEPSEEK_REPORT_READ_TIMEOUT` | No | `45` | Read timeout in seconds for report generation. Increase this for long PDFs or slow model responses. |
| `DEEPSEEK_CONFIG_PATH` | No | `~/.deepseek/config.toml` | Alternate config file path. |

Example config file:

```toml
api_key = "your-deepseek-api-key"
base_url = "https://api.deepseek.com/beta"
model = "deepseek-v4-flash"
```

`default_text_model` is also accepted as a fallback model key for compatibility
with existing DeepSeek config files.

Without a DeepSeek key, the backend reports `Agent not configured` and cannot
produce a real R0/R1 Reading Report.

### 4. Backend

```bash
cd paperflow/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'

# Enable the real DeepSeek-backed PaperAgent
export DEEPSEEK_API_KEY="your-key"
export DEEPSEEK_MODEL="deepseek-v4-flash"
# Optional for long PDFs or slow model responses
export DEEPSEEK_REPORT_READ_TIMEOUT="90"

uvicorn app.main:app --reload
```

Run the backend tests:

```bash
cd paperflow/backend
. .venv/bin/activate
pytest -q
```

### 5. Web Frontend

```bash
cd paperflow/frontend
npm install
npm run dev
```

Run the frontend tests:

```bash
cd paperflow/frontend
npm test
```

Open `http://localhost:5173` in your browser, then:

1. Click **Import PDF** or paste an arXiv URL.
2. Wait for the Agent task to move from `processing` → `completed`.
3. Open the paper to see the two-column Report-first Workspace.
4. Click any claim to see its evidence in the right panel.
5. Ask a focused question — the answer is still graded R0 / R1 / R2.
6. Click **Save Obsidian Note** to drop a Markdown file into the local vault.

### 6. TUI (Terminal UI)

If you prefer a keyboard-driven workflow, PaperFlow ships a Textual-based TUI
that talks to the same backend.

```bash
# Install into the backend's venv (TUI shares httpx with the backend)
cd paperflow/backend && . .venv/bin/activate
pip install -e ../tui

# Make sure the backend is running, then in another terminal:
paperflow-tui
# or
PAPERFLOW_BASE_URL=http://127.0.0.1:8000 paperflow-tui
# or
python -m paperflow_tui
```

Keyboard bindings:

| Where | Key | Action |
| --- | --- | --- |
| Library | `i` | Import a local PDF |
| Library | `a` | Import an arXiv URL / ID |
| Library | `o` / `Enter` | Open the selected paper's Workspace |
| Library | `r` | Re-run the PaperAgent on a paper |
| Library | `R` | Refresh library + agent status |
| Library | `q` | Quit |
| Workspace | `j` / `k` / `↑` / `↓` | Navigate claims in the Reading Report tree |
| Workspace | `Enter` | Inspect a claim's evidence on the right panel |
| Workspace | `a` | Ask a focused question — answer is graded R0 / R1 / R2 |
| Workspace | `c` | Copy the selected claim's quote to the clipboard |
| Workspace | `1` | Run the six-lane R1 related-work search |
| Workspace | `2` | Open the Field Map screen (milestones / timeline / open problems) |
| Field Map | `g` | Generate or re-run the Field Map for this paper |
| Field Map | `i` | Generate R2 Research Insights |
| Field Map | `o` | Save the Field Map Obsidian note |
| Field Map | `b` / `Esc` | Back to Workspace |
| Workspace | `s` | Save / update the Obsidian note |
| Workspace | `r` | Re-run agent for this paper |
| Workspace | `b` / `Esc` | Back to Library |

Run the TUI client tests (uses `respx` to mock the backend):

```bash
cd paperflow/tui
pytest -q
```

---

## Reliability Model (R0 / R1 / R2)

| Level | Meaning | Examples |
| --- | --- | --- |
| **R0** | Strictly grounded in the current paper. Numbers must not be inferred or compared across settings. | "The model is trained on 8×A100 for 72 hours." |
| **R1** | Grounded in another paper / source, fetched through external search. The source paper, venue, year and URL must be recorded. | "This benchmark was introduced in *paper X (NeurIPS 2024)*." |
| **R2** | Inference, trend judgement, or research opinion. Always shown with an R2 badge. | "This direction is likely to converge with diffusion priors in the next year." |

Reliability is not just metadata. It is rendered as a UI badge, persisted in JSON, embedded as `#R0` / `#R1` / `#R2` tags in the Obsidian note, and enforced inside the PaperAgent prompt contract.

---

## Reading Report Schema (R0)

Every R0 claim looks like:

```json
{
  "id": "claim-id",
  "text": "中文解释 / English explanation",
  "reliability": "R0",
  "source": "current_paper",
  "evidence": [
    {
      "quote": "verbatim quote from the PDF",
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

A full Reading Report covers: paper metadata, executive summary, task, dataset, benchmark/metric, method, model scale, input/output, compute/training, key results, strengths, limitations, related-work claims, theory/methodology insights, and an evidence index.

---

## Repository Layout

```text
PaperFlow/
├── README.md                            ← you are here
├── LICENSE                              ← MIT
├── .gitignore
└── paperflow/                           ← runnable V1.1 implementation
    ├── README.md
    ├── backend/                         ← FastAPI + PaperAgent harness
    │   ├── app/                         ← models, storage, report service, agent, obsidian
    │   ├── tests/                       ← pytest
    │   └── pyproject.toml
    ├── frontend/                        ← React + Vite + TypeScript web client
    │   ├── src/                         ← App, API client, types, components
    │   ├── public/
    │   └── package.json
    └── tui/                             ← Textual + httpx terminal client
        ├── paperflow_tui/               ← app, client, screens, styles.tcss
        ├── tests/                       ← respx-mocked client tests
        └── pyproject.toml
```

User data (PDFs, generated reports, Obsidian vault) is stored under `paperflow/backend/paperflow_data/` and is git-ignored by default — your library never leaks into the repo.

---

## Configuration

PaperFlow reads its DeepSeek configuration in this order:

1. Environment variables — `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL`.
2. A TOML config at `DEEPSEEK_CONFIG_PATH` (if set).
3. The standard DeepSeek-TUI config at `~/.deepseek/config.toml`.

If none of those provide a key, the backend reports `agent.status = "missing-key"` and the UI surfaces an **Agent not configured** banner. The development fallback is intentionally limited so users cannot mistake stub data for real R0 extraction.

---

## Contributing

PaperFlow is early but the contract is stable. Good first contributions:

- Improve PDF parsing fidelity (sections, tables, references).
- Wire one of the external sources (Semantic Scholar, OpenAlex, Papers with Code) end-to-end.
- Extend the Obsidian renderer (Field Map note, R2 callout, citation graph links).
- Add end-to-end tests for the import → report → focused-question → Obsidian flow.

Before opening a PR:

```bash
# Backend
cd paperflow/backend && . .venv/bin/activate && pytest -q

# Frontend
cd paperflow/frontend && npm test
```

Please keep PRs aligned with the reliability contract: every UI surface that produces a fact must be expressible as R0 / R1 / R2 with evidence.

---

## License

PaperFlow is released under the [**PolyForm Noncommercial License 1.0.0**](./LICENSE).

This means:

- **You may freely use, copy, modify, and distribute PaperFlow** for any **noncommercial** purpose — including academic research, teaching, personal study, hobby projects, and use inside charitable, educational, government, or public research organizations.
- **You may not use PaperFlow for any commercial purpose** — including but not limited to: hosting it as a paid service, embedding it inside a commercial product, or using it as part of a for-profit company's internal tooling — without a separate commercial license.
- Forks and derivative works must keep this license and the `Required Notice` line that appears at the top of [`LICENSE`](./LICENSE).
- The software is provided **as is**, without warranty of any kind.

If you would like to use PaperFlow commercially, please open an issue on the [GitHub repository](https://github.com/shiml20/PaperFlow) to discuss a commercial license.

Copyright © 2026 shiml20 and PaperFlow contributors.

---

## Acknowledgements

- Agent integration is built against the DeepSeek API and reuses configuration written by the DeepSeek-TUI CLI when present.
- PDF parsing is powered by [PyMuPDF](https://github.com/pymupdf/PyMuPDF).
- The frontend is built with [Vite](https://vitejs.dev/) and [React](https://react.dev/).

If PaperFlow is useful to your research workflow, a star is the kindest signal.
