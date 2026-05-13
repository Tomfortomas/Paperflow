# Paperflow Status

Paperflow currently ships two front-ends on top of the same backend agent harness.

- **Web**: React + Vite + TypeScript, report-first Workspace, PDF viewer, Agent rail, and Obsidian export.
- **TUI**: Textual + httpx, keyboard-driven Library / Workspace / R0-R1-R2 / Evidence / Q&A flow.

## Versioning Policy

Paperflow is currently in the `v0.1` line. Features that previously appeared as `v0.2` to `v0.7` are now treated as part of the first public `v0.1` release.

Future small feature releases should use patch versions such as `v0.1.1`, `v0.1.2`, and `v0.1.3`. Do not bump to `v0.2` or higher unless the project intentionally defines a new broader release line.

## v0.1

- [x] Public-facing README narrative for an evidence-first agentic paper workspace.
- [x] README-ready demo visuals for import, evidence highlight, Agent chat, reliability model, and Obsidian export.
- [x] PDF search and quote matching with segmented text highlights.
- [x] Responsive PDF toolbar for narrower IDE / Cursor workspace panes.
- [x] Landing page and HTML README copy aligned with the public product story.
- [x] Replace serial full-report generation with a staged Agent pipeline: fast paper briefing, parallel chunk extraction, coordinator deduplication, and final synthesis.
- [x] Share the same paper briefing with every chunk agent so parallel extraction stays globally consistent and avoids repeated claims.
- [x] Preserve partial reports during extraction while the final coordinator pass merges duplicates, fills missing required sections conservatively, and keeps exact evidence quotes.
- [x] Add richer generation status messages for briefing, parallel chunk extraction, per-chunk completion, and coordinator synthesis.
- [x] Render PDF pages at device-pixel-ratio resolution so text stays sharp on Retina and large displays.
- [x] Add continuous PDF scrolling with toolbar controls for direct page jump and zoom presets.
- [x] Move the PDF into an independent Workspace pane that becomes a left column on large screens.
- [x] Keep evidence-driven PDF opening: clicking evidence opens the PDF pane, jumps to the page, and scrolls the highlight into view when bbox data exists.
- [x] Chunked full-paper Reading Reports over bounded DeepSeek chunks.
- [x] Dynamic partial reports so the first key findings appear before full completion.
- [x] Coverage-aware UI such as `full-paper coverage 50%` and `full-paper coverage 100% · 8 chunks`.
- [x] Live parsing metrics while generation is still running.
- [x] Transparent Agent progress for extraction, request preparation, model wait, coverage, and persistence.
- [x] Runtime Agent configuration for local API key, model, and report timeout.
- [x] Persist Agent chat threads in SQLite and restore the latest transcript when the Workspace opens.
- [x] Upgrade chat answers to a DeepSeek-backed chat agent over report + selected evidence + R1 cache, with a report-grounded fallback.
- [x] Surface report and chat work through the task lifecycle; report import/rerun now runs through the task queue wrapper and chat records completed task snapshots.
- [x] Add SSE streaming for Agent chat step/final events, with frontend stream consumption and final transcript sync.
- [x] Deepen PDF evidence interactions: evidence detail can open the PDF viewer, jump to the evidence page, and reuse bbox highlights when available.
- [x] Add Agent-enriched Field Map / lineage graph edges with source type, rationale, confidence, and UI labels that distinguish Agent suggestions from rule-derived relations.
- [x] Formal Agent Conversation rail replacing the old focused Q&A area.
- [x] Paper-scoped chat API: `POST /api/papers/{paper_id}/chat`.
- [x] Evidence-aware chat inputs: selected claim, evidence, page, quote, and section.
- [x] Right-rail information architecture for Agent status, config, evidence, chat, and Obsidian export.
- [x] Evidence Workflow: PyMuPDF block parser, evidence verification, PDF.js page jump, bbox highlight, and select-to-ask.
- [x] Metadata & Import: arXiv, CrossRef, Semantic Scholar, OpenReview, Zotero, and DOI/arXiv/content-hash deduplication.
- [x] Real R1 Search: six-lane related-work search over Semantic Scholar, OpenAlex fallback, Papers with Code, and local references.
- [x] Field Map: milestones, timeline, task taxonomy, datasets, benchmarks, method families, open problems, trends, and R2 opportunities.
- [x] Compare + R2 + Task Queue: multi-paper compare, research insights, Field Map Obsidian export, cancel/retry/resume task APIs.
- [x] Library-first home with status tracking (`queued` -> `processing` -> `completed` / `failed`).
- [x] DeepSeek-backed PaperAgent generating R0 Reading Reports.
- [x] R0 / R1 / R2 reliability badges in UI and data model.
- [x] Evidence quote, page, and section per claim.
- [x] Background agent task with persistent reports.
- [x] Obsidian-native paper note export.
- [x] Focused Q&A around dataset / benchmark / method / compute / limitations.
