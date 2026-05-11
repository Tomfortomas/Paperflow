# Paperflow V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable Paperflow V1 MVP that imports PDFs, creates paper sessions, generates evidence-aware reading reports through a DeepSeek-compatible agent workflow, and presents a Library-first / Report-first web UI.

**Architecture:** Create a new `paperflow/` app with a FastAPI backend and a React/Vite frontend. The backend owns storage, PDF parsing, report generation, task status, and Obsidian-native note writing; the frontend consumes REST APIs and renders the paper library, workspace, report cards, evidence badges, and chat-style focused questions.

**Tech Stack:** Python 3 + FastAPI + PyMuPDF + Pydantic + pytest; React + TypeScript + Vite + Vitest; SQLite/local files for persistence.

---

## File Structure

- `paperflow/backend/`: FastAPI app, domain models, SQLite/file storage, PDF parser, report service, Obsidian renderer, DeepSeek client stub.
- `paperflow/backend/tests/`: pytest coverage for report schema, storage, PDF session creation, Obsidian note rendering, and focused questions.
- `paperflow/frontend/`: Vite React app implementing Library-first and Report-first UI.
- `paperflow/frontend/src/`: typed API client, React components, and Vitest tests.
- `paperflow/README.md`: run instructions and DeepSeek API configuration.

## Milestones

### Task 1: Backend Domain And Storage

- [ ] Write failing tests for paper session creation, claim/evidence serialization, and library listing.
- [ ] Implement Pydantic models for `Paper`, `PaperSession`, `Claim`, `Evidence`, `ReadingReport`, `RelatedWorkItem`, and `TaskStatus`.
- [ ] Implement local storage with SQLite metadata and file paths under `paperflow_data/`.
- [ ] Verify tests pass.

### Task 2: PDF Import And Report Pipeline

- [ ] Write failing tests for importing a PDF fixture and producing a session with parsed pages.
- [ ] Implement `PdfParser` using PyMuPDF with a text fallback for tests.
- [ ] Implement `ReportService` that creates deterministic report cards when DeepSeek API is not configured.
- [ ] Implement task statuses for parse, R0 report, R1 related work, and completed.
- [ ] Verify tests pass.

### Task 3: Obsidian-native Note Rendering

- [ ] Write failing tests for frontmatter, wikilinks, callouts, reliability badges, and evidence index rendering.
- [ ] Implement Markdown renderer and note persistence.
- [ ] Verify tests pass.

### Task 4: FastAPI Runtime API

- [ ] Write failing API tests for importing a paper, listing papers, reading a report, asking a focused question, and exporting the Obsidian note.
- [ ] Implement REST endpoints and CORS for the frontend.
- [ ] Verify tests pass.

### Task 5: Frontend Library-first UI

- [ ] Write failing component tests for the Library page: import card, recent papers, task status, saved reports.
- [ ] Implement React components and API client.
- [ ] Verify tests pass.

### Task 6: Frontend Report-first Workspace

- [ ] Write failing component tests for report sections, R0/R1/R2 badges, evidence details, related work, and focused question panel.
- [ ] Implement workspace components.
- [ ] Verify tests pass.

### Task 7: End-to-end Smoke Flow

- [ ] Run backend tests.
- [ ] Run frontend tests.
- [ ] Start backend and frontend locally.
- [ ] Smoke-check PDF import, report display, evidence expansion, focused question, and Obsidian note generation.
