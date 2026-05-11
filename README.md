<div align="center">

# PaperFlow

**Evidence-first paper reading + citation-aware search + field map + Obsidian knowledge base.**

A local-first paper-reading workbench for AI researchers and engineers.
Powered by DeepSeek-backed agents, every claim is graded R0 / R1 / R2 and can be traced back to the PDF.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?logo=react&logoColor=61DAFB)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Obsidian](https://img.shields.io/badge/Obsidian-7C3AED?logo=obsidian&logoColor=white)](https://obsidian.md/)

</div>

---

## Why PaperFlow

Reading papers as a researcher is not a one-shot summarization task. It is a continuous workflow of:

- judging the task, dataset, benchmark, model and compute behind a paper,
- backtracking each conclusion to the exact place in the PDF,
- walking out from one paper to its references, cited-by, related work and field map,
- and saving the result into a personal knowledge base you can keep extending.

**PaperFlow turns that workflow into a local-first, evidence-graded research IDE.**

It is opinionated:

- **Report first, chat second.** You open a paper and see a structured Reading Report, not a blank chatbox.
- **Every claim is graded.** R0 = grounded in the current paper, R1 = grounded in external papers, R2 = inference / opinion. The grade is a first-class citizen of the UI, the data model, and the Obsidian export.
- **Evidence is the product.** Every fact tries to carry a quote, page and section — and tries to jump back into the PDF.
- **Local-first knowledge base.** PDFs, report JSON, Markdown notes and Field Map JSON all live on your disk and sync to an Obsidian-friendly vault.

---

## Highlights

| Capability | Status |
| --- | --- |
| Import local PDFs and arXiv URLs/IDs | Shipped (V1 / V1.1) |
| DeepSeek-backed PaperAgent generating R0 Reading Report | Shipped (V1) |
| R0 / R1 / R2 reliability badges in UI and data model | Shipped (V1) |
| Evidence quote, page and section per claim | Shipped (V1) |
| Library-first home with status tracking (`queued` → `processing` → `completed` / `failed`) | Shipped (V1.1) |
| Two-column Report-first Workspace | Shipped (V1.1) |
| Background agent task, no UI blocking on import | Shipped (V1.1) |
| Persistent report — survives backend restart | Shipped (V1.1) |
| Obsidian-native paper note (frontmatter, wikilinks, callouts, reliability tags) | Shipped (V1.1) |
| De-dup by filename / arXiv ID — re-import replaces in place | Shipped (V1.1) |
| Focused Q&A around dataset / benchmark / method / compute / limitations | Shipped (V1.1) |
| Full PDF.js viewer with evidence highlight + page jump | Planned (V2 Phase 1) |
| Real R1 search over Semantic Scholar / OpenAlex / Papers with Code | Planned (V2 Phase 3) |
| Milestone papers + technology timeline | Planned (V2 Phase 4) |
| Field Map workspace (problem ↔ method ↔ dataset ↔ benchmark ↔ open problems) | Planned (V2 Phase 4) |
| Multi-paper compare with comparison-risk warning | Planned (V2 Phase 5) |
| R2 research insight & opportunity surface | Planned (V2 Phase 5) |

For the full V2 design contract see [`Paperflow_V2_PRD.md`](./Paperflow_V2_PRD.md).

---

## Architecture

```text
┌──────────────────────────────┐        ┌──────────────────────────────────┐
│  Frontend (React + Vite)     │  REST  │  Backend (FastAPI)               │
│  - Library-first home        │ <────> │  - PaperStorage (SQLite + files) │
│  - Report-first Workspace    │        │  - PDF parser (PyMuPDF)          │
│  - Reliability badges        │        │  - ReportService                 │
│  - Evidence Detail panel     │        │  - PaperAgent (DeepSeek client)  │
│  - Focused Q&A               │        │  - Obsidian-native renderer     │
└──────────────────────────────┘        └──────────────┬───────────────────┘
                                                       │
                                                       ▼
                                         ┌──────────────────────────┐
                                         │  Local Data (paperflow_data/)
                                         │  - PDFs                  │
                                         │  - report JSON           │
                                         │  - Obsidian vault notes  │
                                         │  - SQLite metadata       │
                                         └──────────────────────────┘
```

**Tech stack:** Python 3.9+ · FastAPI · Pydantic · PyMuPDF · httpx · pytest · React · TypeScript · Vite · Vitest · SQLite · DeepSeek API.

---

## Quickstart

> Requirements: Python 3.9+, Node.js 18+, and (optionally) a DeepSeek API key for full Agent capability.

### 1. Clone

```bash
git clone https://github.com/shiml20/PaperFlow.git
cd PaperFlow
```

### 2. Backend

```bash
cd paperflow/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'

# Optional: enable the real DeepSeek-backed PaperAgent
export DEEPSEEK_API_KEY="your-key"
export DEEPSEEK_MODEL="deepseek-v4-flash"

uvicorn app.main:app --reload
```

PaperFlow also reuses keys stored at `~/.deepseek/config.toml`
(or whatever path `DEEPSEEK_CONFIG_PATH` points to), so a key saved by
`deepseek auth set --provider deepseek` is picked up automatically.

Without a DeepSeek key the backend uses a clearly-marked development fallback.
That fallback is **only** for local UI smoke-testing — real R0/R1 extraction always
goes through the DeepSeek-backed PaperAgent.

Run the backend tests:

```bash
cd paperflow/backend
. .venv/bin/activate
pytest -q
```

### 3. Frontend

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

A full Reading Report covers: paper metadata, executive summary, task, dataset, benchmark/metric, method, model scale, input/output, compute/training, key results, strengths, limitations, related-work claims, theory/methodology insights, and an evidence index. See [`Paperflow_V2_PRD.md` §4.3](./Paperflow_V2_PRD.md) for the canonical schema.

---

## Roadmap

PaperFlow ships through three PRD generations:

- **V1 — [`Paperflow_V1_PRD.md`](./Paperflow_V1_PRD.md)** — Library-first home, evidence-aware R0 Reading Report, lightweight R1 context, Obsidian-native note. *Shipped.*
- **V1.1 — [`Paperflow_V1_1_PRD.md`](./Paperflow_V1_1_PRD.md)** — Two-column Report-first Workspace, durable storage, background tasks, status badges, agent config surface. *Shipped.*
- **V2 — [`Paperflow_V2_PRD.md`](./Paperflow_V2_PRD.md)** — Full PDF evidence workflow, real R1 over Semantic Scholar / OpenAlex / Papers with Code, milestone detection, technology timeline, Field Map workspace, multi-paper compare, R2 research insight. *In progress.*

V2 is planned in five phases:

1. **Evidence workflow** — PDF.js reader, quote fuzzy match, evidence highlight, selection-driven Q&A.
2. **Metadata & import** — arXiv, DOI, Semantic Scholar, OpenReview, Zotero read-only.
3. **Real R1 search** — references parser, Semantic Scholar references/citations, OpenAlex fallback, Papers with Code, comparison-risk surfacing.
4. **Field Map** — milestone detection, timeline, method families, dataset/benchmark table, open problems, Field Map Workspace.
5. **Knowledge base & R2** — Obsidian vault sync, Field Map note, multi-paper compare, research opportunities, user curation.

Original product thinking and traceability back to first principles live in [`SMLThoughts.md`](./SMLThoughts.md), [`SMLThoughts_V1_status.md`](./SMLThoughts_V1_status.md) and [`SMLThoughts_with_suggestions.md`](./SMLThoughts_with_suggestions.md).

---

## Repository Layout

```text
PaperFlow/
├── README.md                            ← you are here
├── LICENSE                              ← MIT
├── Paperflow_V1_PRD.md                  ← V1 product spec  (shipped)
├── Paperflow_V1_1_PRD.md                ← V1.1 product spec (shipped)
├── Paperflow_V2_PRD.md                  ← V2 product spec  (in progress, locked design)
├── Paperflow_V1_IMPLEMENTATION_PLAN.md  ← V1 task plan
├── SMLThoughts.md                       ← original requirements
├── SMLThoughts_V1_status.md             ← V1 coverage of original requirements
├── SMLThoughts_with_suggestions.md      ← annotated requirements
└── paperflow/                           ← runnable V1.1 implementation
    ├── README.md
    ├── backend/                         ← FastAPI + PaperAgent
    │   ├── app/                         ← models, storage, report service, agent, obsidian
    │   ├── tests/                       ← pytest
    │   └── pyproject.toml
    └── frontend/                        ← React + Vite + TypeScript
        ├── src/                         ← App, API client, types, components
        ├── public/
        └── package.json
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
- Wire one of the V2 external sources (Semantic Scholar, OpenAlex, Papers with Code) end-to-end.
- Extend the Obsidian renderer (Field Map note, R2 callout, citation graph links).
- Add end-to-end tests for the V1.1 import → report → focused-question → Obsidian flow.

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

[MIT](./LICENSE) © 2026 shiml20 and PaperFlow contributors.

---

## Acknowledgements

- The reliability grading model (R0 / R1 / R2) and the field-map framing originated in [`SMLThoughts.md`](./SMLThoughts.md).
- Agent integration is built against the DeepSeek API and reuses configuration written by the DeepSeek-TUI CLI when present.
- PDF parsing is powered by [PyMuPDF](https://github.com/pymupdf/PyMuPDF).
- The frontend is built with [Vite](https://vitejs.dev/) and [React](https://react.dev/).

If PaperFlow is useful to your research workflow, a star is the kindest signal.
