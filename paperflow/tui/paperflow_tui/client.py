"""Async HTTP client over the Paperflow FastAPI backend.

The TUI never talks to the PaperAgent or storage directly. All operations
go through the same REST API the React/Vite frontend uses. This keeps the
agent harness on the server and the TUI as a thin client — matching the
``app-server`` / ``tui`` separation in DeepSeek-TUI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


class PaperflowAPIError(Exception):
    """Wrapped HTTPX error with a human-friendly message."""


@dataclass(frozen=True)
class AgentStatus:
    configured: bool
    mode: str
    model: Optional[str]


class PaperflowClient:
    """Thin async client over the Paperflow REST API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "PaperflowClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    async def _get(self, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.get(path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise PaperflowAPIError(f"GET {path} failed: {exc}") from exc

    async def _post(self, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.post(path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise PaperflowAPIError(f"POST {path} failed: {exc}") from exc

    # ------------------------------------------------------------------ agent

    async def agent_status(self) -> AgentStatus:
        data = await self._get("/api/agent/status")
        return AgentStatus(
            configured=bool(data.get("configured")),
            mode=str(data.get("mode", "unknown")),
            model=data.get("model"),
        )

    # ------------------------------------------------------------------ library

    async def list_papers(self) -> List[Dict[str, Any]]:
        return await self._get("/api/papers")

    async def get_status(self, paper_id: str) -> Dict[str, Any]:
        return await self._get(f"/api/papers/{paper_id}/status")

    async def get_report(self, paper_id: str) -> Dict[str, Any]:
        return await self._get(f"/api/papers/{paper_id}/report")

    # ------------------------------------------------------------------ import

    async def import_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        path = Path(pdf_path).expanduser().resolve()
        if not path.is_file():
            raise PaperflowAPIError(f"PDF not found: {path}")
        files = {"file": (path.name, path.read_bytes(), "application/pdf")}
        return await self._post("/api/papers/import", files=files)

    async def import_arxiv(self, url_or_id: str) -> Dict[str, Any]:
        return await self._post(
            "/api/papers/import-arxiv",
            json={"url": url_or_id.strip()},
            timeout=120.0,
        )

    async def import_url(self, url: str) -> Dict[str, Any]:
        """Import any URL Paperflow can auto-classify (arXiv/DOI/S2/OpenReview)."""

        return await self._post(
            "/api/papers/import-url",
            json={"url": url.strip()},
            timeout=120.0,
        )

    async def import_zotero(self, item_key: Optional[str] = None) -> Dict[str, Any]:
        """Import everything (or one item) from the local Zotero library."""

        payload: Dict[str, Any] = {}
        if item_key:
            payload["item_key"] = item_key
        return await self._post(
            "/api/papers/import-zotero",
            json=payload,
            timeout=300.0,
        )

    async def preview_zotero(self) -> List[Dict[str, Any]]:
        return await self._get("/api/zotero/preview")

    # ------------------------------------------------------------------ agent ops

    async def rerun(self, paper_id: str) -> Dict[str, Any]:
        return await self._post(f"/api/papers/{paper_id}/rerun")

    async def ask(self, paper_id: str, question: str) -> Dict[str, Any]:
        return await self._post(
            f"/api/papers/{paper_id}/ask",
            json={"question": question},
            timeout=60.0,
        )

    async def export_obsidian(self, paper_id: str) -> Dict[str, Any]:
        return await self._post(f"/api/papers/{paper_id}/export-obsidian")
