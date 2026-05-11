"""Textual TUI for Paperflow.

Screens:

* :class:`LibraryScreen` — paper library + agent status + import + rerun.
* :class:`WorkspaceScreen` — two-column Report-first workspace with R0/R1/R2
  badges, evidence detail, focused Q&A, and Obsidian export.
* :class:`ImportPdfScreen` / :class:`ImportArxivScreen` / :class:`AskScreen` —
  modal prompts.

The TUI never imports the agent code directly. All work goes through
:class:`paperflow_tui.client.PaperflowClient`, mirroring how DeepSeek-TUI keeps
its ``tui`` crate as a thin client over the ``app-server`` crate.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
    Tree,
)
from textual.widgets.tree import TreeNode

from paperflow_tui.client import AgentStatus, PaperflowAPIError, PaperflowClient


# --------------------------------------------------------------------- helpers


RELIABILITY_STYLE = {
    "R0": "bold green",
    "R1": "bold cyan",
    "R2": "bold yellow",
}


STAGE_STYLE = {
    "queued": "dim",
    "processing": "yellow",
    "completed": "green",
    "failed": "bold red",
}


def reliability_badge(reliability: str) -> Text:
    style = RELIABILITY_STYLE.get(reliability, "white")
    return Text(f"[{reliability}]", style=style)


def stage_badge(stage: str) -> Text:
    style = STAGE_STYLE.get(stage, "white")
    return Text(stage, style=style)


def _render_r1_label(item: Dict[str, Any]) -> str:
    """Build a compact one-line label for an R1 RelatedWorkItem."""

    title = item.get("title") or "(untitled)"
    bits: List[str] = [title]
    meta_bits: List[str] = []
    authors = item.get("authors") or []
    if isinstance(authors, list) and authors:
        meta_bits.append(authors[0] + (" et al." if len(authors) > 1 else ""))
    year = item.get("year")
    if year:
        meta_bits.append(str(year))
    venue = item.get("venue")
    if venue:
        meta_bits.append(str(venue))
    cites = item.get("citation_count")
    if cites:
        meta_bits.append(f"{cites} cites")
    if meta_bits:
        bits.append(f"  ·  {' / '.join(meta_bits)}")
    relation = item.get("relation")
    if relation:
        bits.append(f"  ({relation})")
    return "".join(bits)


_LOCATION_LABEL = {
    "exact": "located precisely",
    "page_and_quote": "located by page + paragraph",
    "quote_only": "no PDF location",
    "missing": "missing evidence",
}


def evidence_lines(evidence: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for ev in evidence:
        bits: List[str] = []
        if ev.get("page") is not None:
            bits.append(f"p.{ev['page']}")
        if ev.get("section"):
            bits.append(str(ev["section"]))
        if ev.get("source"):
            bits.append(str(ev["source"]))
        bbox = ev.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            x0, y0, x1, y1 = bbox
            bits.append(f"bbox=({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f})")
        location = ev.get("location_status")
        if location:
            bits.append(_LOCATION_LABEL.get(location, location))
        header = " · ".join(bits) if bits else "evidence"
        out.append(f"[{header}]")
        quote = (ev.get("quote") or "").strip()
        if quote:
            out.append(f"  \u201c{quote}\u201d")
    return out


# --------------------------------------------------------------------- modals


class ImportPdfScreen(ModalScreen[Optional[Path]]):
    """Prompt for a local PDF path."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel", show=True),
        Binding("enter", "submit", "Import", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Label("Import local PDF", id="modal-title")
            yield Label("Enter an absolute or ~-relative PDF path.", id="modal-hint")
            yield Input(placeholder="/path/to/paper.pdf", id="pdf-input")

    def on_mount(self) -> None:
        self.query_one("#pdf-input", Input).focus()

    @on(Input.Submitted)
    def _on_submit(self, event: Input.Submitted) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        value = self.query_one("#pdf-input", Input).value.strip()
        self.dismiss(Path(value).expanduser() if value else None)


class ImportArxivScreen(ModalScreen[Optional[str]]):
    """Prompt for an arXiv URL or ID."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel", show=True),
        Binding("enter", "submit", "Import", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Label("Import arXiv URL or ID", id="modal-title")
            yield Label(
                "Examples: https://arxiv.org/abs/2605.08063  ·  2605.08063  ·  arXiv:2605.08063v1",
                id="modal-hint",
            )
            yield Input(placeholder="https://arxiv.org/abs/...", id="arxiv-input")

    def on_mount(self) -> None:
        self.query_one("#arxiv-input", Input).focus()

    @on(Input.Submitted)
    def _on_submit(self, event: Input.Submitted) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        value = self.query_one("#arxiv-input", Input).value.strip()
        self.dismiss(value or None)


class ImportUrlScreen(ModalScreen[Optional[str]]):
    """Prompt for any auto-classified URL (arXiv / DOI / S2 / OpenReview)."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel", show=True),
        Binding("enter", "submit", "Import", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Label("Import paper URL or DOI", id="modal-title")
            yield Label(
                "arXiv / DOI / Semantic Scholar / OpenReview — Paperflow detects the right source.",
                id="modal-hint",
            )
            yield Input(placeholder="https://… or 10.x/…", id="url-input")

    def on_mount(self) -> None:
        self.query_one("#url-input", Input).focus()

    @on(Input.Submitted)
    def _on_submit(self, event: Input.Submitted) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        value = self.query_one("#url-input", Input).value.strip()
        self.dismiss(value or None)


class AskScreen(ModalScreen[Optional[str]]):
    """Prompt for a focused question."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel", show=True),
        Binding("enter", "submit", "Ask", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Label("Ask the PaperAgent a focused question", id="modal-title")
            yield Label(
                "Examples: What is the dataset? · What benchmark is used? · What are the limitations?",
                id="modal-hint",
            )
            yield Input(placeholder="Type your question…", id="question-input")

    def on_mount(self) -> None:
        self.query_one("#question-input", Input).focus()

    @on(Input.Submitted)
    def _on_submit(self, event: Input.Submitted) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        value = self.query_one("#question-input", Input).value.strip()
        self.dismiss(value or None)


# --------------------------------------------------------------------- screens


class LibraryScreen(Screen):
    """Library-first home: agent status + paper table + import actions."""

    BINDINGS = [
        Binding("i", "import_pdf", "Import PDF", show=True),
        Binding("a", "import_arxiv", "Import arXiv", show=True),
        Binding("u", "import_url", "Import URL", show=True),
        Binding("z", "import_zotero", "Zotero", show=True),
        Binding("o,enter", "open_paper", "Open", show=True),
        Binding("r", "rerun", "Rerun Agent", show=True),
        Binding("R", "refresh", "Refresh", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="header-bar")
        table = DataTable(id="library-table", zebra_stripes=True, cursor_type="row")
        table.add_columns("ID", "Title", "Authors", "Year", "Venue", "Source", "Status", "Note")
        yield table
        yield Static("", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_agent_status()
        await self.refresh_library()
        self.set_interval(3.0, self._poll_library)

    # ---------------- status

    async def refresh_agent_status(self) -> None:
        bar = self.query_one("#header-bar", Static)
        client: PaperflowClient = self.app.client
        try:
            status = await client.agent_status()
            bar.update(self._render_agent_status(status, client.base_url))
        except PaperflowAPIError as exc:
            bar.update(Text(f"Backend unreachable at {client.base_url} — {exc}", style="bold red"))

    def _render_agent_status(self, status: AgentStatus, base_url: str) -> Text:
        text = Text()
        text.append("Agent: ", style="bold")
        if status.configured:
            text.append(f"{status.mode}", style="bold green")
            if status.model:
                text.append(f" · {status.model}", style="green")
        else:
            text.append("missing-key", style="bold red")
        text.append("   ")
        text.append("Backend: ", style="bold")
        text.append(base_url, style="cyan")
        text.append("   ")
        text.append(
            "[i] PDF  [a] arXiv  [u] URL/DOI  [z] Zotero  [o] Open  [r] Rerun  [R] Refresh  [q] Quit",
            style="dim",
        )
        return text

    async def _poll_library(self) -> None:
        await self.refresh_library(preserve_cursor=True)

    async def refresh_library(self, *, preserve_cursor: bool = False) -> None:
        table = self.query_one("#library-table", DataTable)
        client: PaperflowClient = self.app.client
        try:
            papers = await client.list_papers()
        except PaperflowAPIError as exc:
            self._set_status(Text(str(exc), style="bold red"))
            return

        cursor_row = table.cursor_row if preserve_cursor else 0
        table.clear()
        self.app.papers = papers
        for paper in papers:
            paper_id = str(paper.get("id", ""))
            short_id = paper_id[:8] if paper_id else "—"
            title = str(paper.get("title") or "(untitled)")
            metadata = paper.get("metadata") or {}
            authors = metadata.get("authors") or []
            if isinstance(authors, list) and authors:
                authors_label = ", ".join(authors[:2]) + ("…" if len(authors) > 2 else "")
            else:
                authors_label = "—"
            year_label = str(metadata.get("year") or "—")
            venue_label = str(metadata.get("venue") or "—")
            source_type = metadata.get("source_type") or "—"
            external_id = (
                f"arXiv:{metadata.get('arxiv_id')}"
                if metadata.get("arxiv_id")
                else (f"DOI:{metadata.get('doi')}" if metadata.get("doi") else None)
            )
            source_label = external_id or str(source_type)
            status = paper.get("status") or {}
            stage = str(status.get("stage", "unknown"))
            note = "✓" if paper.get("note_path") else "—"
            table.add_row(
                short_id,
                title,
                authors_label,
                year_label,
                venue_label,
                source_label,
                stage_badge(stage),
                note,
                key=paper_id,
            )
        try:
            if cursor_row < table.row_count:
                table.move_cursor(row=cursor_row)
        except Exception:
            pass
        self._set_status(Text(f"{len(papers)} papers · auto-refresh every 3s", style="dim"))

    def _set_status(self, text: Text | str) -> None:
        self.query_one("#status-bar", Static).update(text)

    # ---------------- actions

    def _selected_paper(self) -> Optional[Dict[str, Any]]:
        table = self.query_one("#library-table", DataTable)
        if table.row_count == 0:
            return None
        try:
            row_key = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key
        except Exception:
            return None
        paper_id = row_key.value if row_key else None
        if not paper_id:
            return None
        return next((p for p in self.app.papers if str(p.get("id")) == paper_id), None)

    async def action_import_pdf(self) -> None:
        path = await self.app.push_screen_wait(ImportPdfScreen())
        if not path:
            return
        self._set_status(Text(f"Uploading {path.name} …", style="yellow"))
        try:
            session = await self.app.client.import_pdf(path)
        except PaperflowAPIError as exc:
            self._set_status(Text(str(exc), style="bold red"))
            return
        self._set_status(
            Text(f"Imported {path.name} → paper id {session.get('paper', {}).get('id', '?')[:8]}…", style="green")
        )
        await self.refresh_library()

    async def action_import_arxiv(self) -> None:
        value = await self.app.push_screen_wait(ImportArxivScreen())
        if not value:
            return
        self._set_status(Text(f"Downloading {value} from arXiv …", style="yellow"))
        try:
            session = await self.app.client.import_arxiv(value)
        except PaperflowAPIError as exc:
            self._set_status(Text(str(exc), style="bold red"))
            return
        self._set_status(
            Text(f"Imported {value} → paper id {session.get('paper', {}).get('id', '?')[:8]}…", style="green")
        )
        await self.refresh_library()

    async def action_import_url(self) -> None:
        value = await self.app.push_screen_wait(ImportUrlScreen())
        if not value:
            return
        self._set_status(Text(f"Fetching metadata for {value} …", style="yellow"))
        try:
            session = await self.app.client.import_url(value)
        except PaperflowAPIError as exc:
            self._set_status(Text(str(exc), style="bold red"))
            return
        self._set_status(
            Text(
                f"Imported {session.get('paper', {}).get('title') or value} "
                f"({session.get('paper', {}).get('id', '?')[:8]}…)",
                style="green",
            )
        )
        await self.refresh_library()

    async def action_import_zotero(self) -> None:
        self._set_status(Text("Reading local Zotero library …", style="yellow"))
        try:
            result = await self.app.client.import_zotero()
        except PaperflowAPIError as exc:
            self._set_status(Text(str(exc), style="bold red"))
            return
        imported = int(result.get("imported", 0))
        if imported == 0:
            self._set_status(Text("Zotero library is empty or has no PDF attachments.", style="yellow"))
            return
        self._set_status(Text(f"Imported {imported} papers from Zotero.", style="green"))
        await self.refresh_library()

    async def action_open_paper(self) -> None:
        paper = self._selected_paper()
        if not paper:
            self._set_status(Text("No paper selected.", style="bold red"))
            return
        await self.app.push_screen(WorkspaceScreen(paper=paper))

    async def action_rerun(self) -> None:
        paper = self._selected_paper()
        if not paper:
            self._set_status(Text("No paper selected.", style="bold red"))
            return
        try:
            await self.app.client.rerun(str(paper["id"]))
        except PaperflowAPIError as exc:
            self._set_status(Text(str(exc), style="bold red"))
            return
        self._set_status(Text(f"Queued rerun for {paper.get('title')}", style="yellow"))
        await self.refresh_library(preserve_cursor=True)

    async def action_refresh(self) -> None:
        await self.refresh_agent_status()
        await self.refresh_library(preserve_cursor=True)


class WorkspaceScreen(Screen):
    """Two-column Report-first workspace for a single paper."""

    BINDINGS = [
        Binding("b,escape", "back", "Back", show=True),
        Binding("a", "ask", "Ask", show=True),
        Binding("c", "copy_quote", "Copy quote", show=True),
        Binding("1", "run_r1_search", "R1 search", show=True),
        Binding("s", "save_obsidian", "Save Obsidian", show=True),
        Binding("r", "rerun", "Rerun Agent", show=True),
        Binding("R", "refresh", "Refresh", show=True),
    ]

    def __init__(self, paper: Dict[str, Any]) -> None:
        super().__init__()
        self.paper = paper
        self.report: Optional[Dict[str, Any]] = None
        self._claim_index: Dict[int, Tuple[str, Dict[str, Any]]] = {}
        self._selected_claim: Optional[Dict[str, Any]] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="header-bar")
        with Horizontal(id="workspace-root"):
            with Vertical(id="report-column"):
                yield Label("Reading Report", classes="panel-title")
                tree: Tree = Tree("(loading)", id="report-tree")
                tree.show_root = False
                tree.guide_depth = 3
                yield tree
            with Vertical(id="side-column"):
                yield Label("Evidence Detail", classes="panel-title")
                yield Static("Select a claim in the tree on the left.", id="evidence-panel")
                yield Label("Focused Q&A", classes="panel-title")
                yield RichLog(id="qa-log", highlight=False, markup=True, wrap=True)
                yield Static("[a] Ask · [s] Save Obsidian · [r] Rerun · [R] Refresh · [b] Back", classes="dim")
        yield Static("", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        self._render_header()
        await self.load_report()
        self.set_interval(2.5, self._poll_until_completed)

    def _render_header(self) -> None:
        text = Text()
        text.append("Paper: ", style="bold")
        text.append(str(self.paper.get("title") or "(untitled)"), style="cyan")
        text.append("   ")
        status = self.paper.get("status") or {}
        text.append("Stage: ", style="bold")
        text.append(stage_badge(str(status.get("stage", "unknown"))))
        self.query_one("#header-bar", Static).update(text)

    def _set_status(self, text: Text | str) -> None:
        self.query_one("#status-bar", Static).update(text)

    async def _poll_until_completed(self) -> None:
        if not self.report or not self.report.get("sections"):
            await self.load_report()
        else:
            await self._refresh_stage()

    async def _refresh_stage(self) -> None:
        try:
            status = await self.app.client.get_status(str(self.paper["id"]))
        except PaperflowAPIError:
            return
        self.paper["status"] = status
        self._render_header()

    async def load_report(self) -> None:
        client: PaperflowClient = self.app.client
        paper_id = str(self.paper["id"])

        try:
            status = await client.get_status(paper_id)
        except PaperflowAPIError as exc:
            self._set_status(Text(str(exc), style="bold red"))
            return
        self.paper["status"] = status
        self._render_header()

        if status.get("stage") != "completed":
            self._set_status(
                Text(
                    f"Agent is {status.get('stage', 'working')}: {status.get('message', '')}",
                    style="yellow",
                )
            )
            tree = self.query_one("#report-tree", Tree)
            tree.reset(label="(waiting for agent)")
            return

        try:
            self.report = await client.get_report(paper_id)
        except PaperflowAPIError as exc:
            self._set_status(Text(str(exc), style="bold red"))
            return

        self._populate_tree(self.report)
        self._set_status(Text(f"Report loaded · {len(self.report.get('sections') or [])} sections", style="dim"))

    def _populate_tree(self, report: Dict[str, Any]) -> None:
        tree = self.query_one("#report-tree", Tree)
        tree.reset(label=str(report.get("paper_title") or self.paper.get("title") or "Paper"))
        tree.show_root = True
        self._claim_index = {}

        # Executive summary.
        summary_node = tree.root.add("Executive Summary", expand=True)
        for claim in report.get("summary") or []:
            node = summary_node.add_leaf(self._claim_label(claim))
            self._claim_index[node.id] = ("Executive Summary", claim)

        # Detailed sections.
        for section in report.get("sections") or []:
            section_node = tree.root.add(str(section.get("title") or "Section"), expand=False)
            for claim in section.get("claims") or []:
                node = section_node.add_leaf(self._claim_label(claim))
                self._claim_index[node.id] = (str(section.get("title")), claim)

        # R1 related work.
        related = report.get("related_work") or []
        if related:
            rw_node = tree.root.add(f"R1 Related Work ({len(related)})", expand=False)
            for item in related:
                claim_like = {
                    "id": item.get("id"),
                    "text": _render_r1_label(item),
                    "reliability": item.get("reliability", "R1"),
                    "evidence": item.get("evidence") or [],
                    "uncertainty": item.get("comparison_risk"),
                }
                node = rw_node.add_leaf(self._claim_label(claim_like))
                self._claim_index[node.id] = ("R1 Related Work", claim_like)

        tree.root.expand()

    def _claim_label(self, claim: Dict[str, Any]) -> Text:
        reliability = str(claim.get("reliability", "R2"))
        text = Text()
        text.append_text(reliability_badge(reliability))
        text.append(" ")
        text.append(str(claim.get("text") or "").strip().replace("\n", " "))
        return text

    @on(Tree.NodeSelected)
    def _on_node_selected(self, event: Tree.NodeSelected) -> None:
        node: TreeNode = event.node
        entry = self._claim_index.get(node.id)
        panel = self.query_one("#evidence-panel", Static)
        if not entry:
            panel.update("No claim selected.")
            self._selected_claim = None
            return
        section_title, claim = entry
        self._selected_claim = claim
        body = self._render_claim_detail(section_title, claim)
        panel.update(body)

    def _render_claim_detail(self, section_title: str, claim: Dict[str, Any]) -> Text:
        body = Text()
        body.append("Section: ", style="bold")
        body.append(f"{section_title}\n", style="cyan")
        body.append("Reliability: ", style="bold")
        body.append_text(reliability_badge(str(claim.get("reliability", "R2"))))
        body.append("\n\n")
        body.append("Claim:\n", style="bold")
        body.append(f"{(claim.get('text') or '').strip()}\n\n")
        evidence = claim.get("evidence") or []
        body.append("Evidence:\n", style="bold")
        if not evidence:
            body.append("  (no evidence attached)\n", style="dim red")
        else:
            for line in evidence_lines(evidence):
                body.append(f"{line}\n")
        uncertainty = claim.get("uncertainty")
        if uncertainty:
            body.append("\nUncertainty: ", style="bold yellow")
            body.append(f"{uncertainty}\n")
        return body

    # ---------------- actions

    async def action_back(self) -> None:
        await self.app.pop_screen()

    @work(exclusive=True)
    async def _do_ask(self, question: str) -> None:
        log = self.query_one("#qa-log", RichLog)
        log.write(f"[bold cyan]you[/bold cyan] » {question}")
        try:
            answer = await self.app.client.ask(str(self.paper["id"]), question)
        except PaperflowAPIError as exc:
            log.write(f"[bold red]error[/bold red] {exc}")
            return
        reliability = str(answer.get("reliability", "R2"))
        style = RELIABILITY_STYLE.get(reliability, "white")
        log.write(f"[{style}]agent [{reliability}][/] {answer.get('text', '').strip()}")
        for line in evidence_lines(answer.get("evidence") or []):
            log.write(f"  [dim]{line}[/dim]")

    async def action_ask(self) -> None:
        if (self.paper.get("status") or {}).get("stage") != "completed":
            self._set_status(Text("Wait for the report to finish before asking.", style="yellow"))
            return
        question = await self.app.push_screen_wait(AskScreen())
        if not question:
            return
        self._do_ask(question)

    async def action_save_obsidian(self) -> None:
        try:
            result = await self.app.client.export_obsidian(str(self.paper["id"]))
        except PaperflowAPIError as exc:
            self._set_status(Text(str(exc), style="bold red"))
            return
        self._set_status(Text(f"Obsidian note saved → {result.get('note_path')}", style="green"))

    async def action_rerun(self) -> None:
        try:
            await self.app.client.rerun(str(self.paper["id"]))
        except PaperflowAPIError as exc:
            self._set_status(Text(str(exc), style="bold red"))
            return
        self._set_status(Text("Rerun queued. Polling for status …", style="yellow"))
        await self.load_report()

    async def action_refresh(self) -> None:
        await self.load_report()

    async def action_run_r1_search(self) -> None:
        """Phase 3: run the backend's R1 pipeline and refresh the report tree."""

        if (self.paper.get("status") or {}).get("stage") != "completed":
            self._set_status(Text("Wait for the report to finish before running R1.", style="yellow"))
            return
        self._set_status(Text("Running R1 search (references + citations + benchmark…) …", style="yellow"))
        try:
            payload = await self.app.client.run_r1_search(str(self.paper["id"]))
        except PaperflowAPIError as exc:
            self._set_status(Text(f"R1 search failed: {exc}", style="bold red"))
            return
        items = payload.get("items") or []
        if self.report is not None:
            self.report["related_work"] = items
            self._populate_tree(self.report)
        trace = payload.get("query_trace") or []
        self._set_status(
            Text(
                f"R1 search done · {len(items)} candidates across {len(trace)} traced lanes.",
                style="green",
            )
        )

    def action_copy_quote(self) -> None:
        """Copy the selected claim's first evidence quote to the OS clipboard."""

        claim = self._selected_claim
        if not claim:
            self._set_status(Text("Select a claim first to copy its quote.", style="yellow"))
            return
        evidence = (claim.get("evidence") or [None])[0]
        quote = (evidence or {}).get("quote") if evidence else None
        if not quote:
            self._set_status(Text("No evidence quote available for that claim.", style="yellow"))
            return
        try:
            self.app.copy_to_clipboard(quote)
        except Exception as exc:  # pragma: no cover — depends on host clipboard
            self._set_status(Text(f"Clipboard copy failed: {exc}", style="bold red"))
            return
        preview = quote[:60] + ("…" if len(quote) > 60 else "")
        self._set_status(Text(f"Copied quote → \"{preview}\"", style="green"))


# --------------------------------------------------------------------- App


class PaperflowTUI(App[None]):
    """Top-level Textual app."""

    CSS_PATH = "styles.tcss"
    TITLE = "Paperflow TUI"
    SUB_TITLE = "Evidence-first paper reading · R0 · R1 · R2"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
    ]

    def __init__(self, base_url: str = "http://127.0.0.1:8000") -> None:
        super().__init__()
        self.client = PaperflowClient(base_url=base_url)
        self.papers: List[Dict[str, Any]] = []

    async def on_mount(self) -> None:
        await self.push_screen(LibraryScreen())

    async def on_unmount(self) -> None:
        try:
            await self.client.aclose()
        except Exception:
            pass

    async def push_screen_wait(self, screen: ModalScreen[Any]) -> Any:
        """Compat shim — older Textual versions use ``push_screen_wait`` with a name,
        newer versions return the result directly. We always go through ``wait_for_dismiss``
        via an asyncio.Future to keep behavior identical across supported versions."""
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()

        def _set(value: Any) -> None:
            if not future.done():
                future.set_result(value)

        self.push_screen(screen, _set)
        return await future
