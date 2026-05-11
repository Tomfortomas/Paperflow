"""Smoke tests for :class:`paperflow_tui.client.PaperflowClient`.

Uses :mod:`respx` to mock the FastAPI surface so the tests do not require
a running backend.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from paperflow_tui.client import PaperflowAPIError, PaperflowClient


@pytest.mark.asyncio
async def test_agent_status_parses_payload() -> None:
    async with PaperflowClient("http://test") as client:
        with respx.mock(base_url="http://test", assert_all_called=True) as mock:
            mock.get("/api/agent/status").respond(
                200,
                json={"configured": True, "mode": "deepseek", "model": "deepseek-v4-flash"},
            )
            status = await client.agent_status()

    assert status.configured is True
    assert status.mode == "deepseek"
    assert status.model == "deepseek-v4-flash"


@pytest.mark.asyncio
async def test_list_papers_returns_list() -> None:
    sample = [{"id": "abc", "title": "Paper", "status": {"stage": "completed"}}]
    async with PaperflowClient("http://test") as client:
        with respx.mock(base_url="http://test") as mock:
            mock.get("/api/papers").respond(200, json=sample)
            papers = await client.list_papers()
    assert papers == sample


@pytest.mark.asyncio
async def test_import_arxiv_posts_url() -> None:
    payload = {"id": "session-id", "paper": {"id": "pid", "title": "arxiv-2605.08063"}}
    async with PaperflowClient("http://test") as client:
        with respx.mock(base_url="http://test") as mock:
            route = mock.post("/api/papers/import-arxiv").respond(200, json=payload)
            result = await client.import_arxiv("https://arxiv.org/abs/2605.08063")
    assert route.called
    assert result == payload


@pytest.mark.asyncio
async def test_import_pdf_uploads_file(tmp_path: Path) -> None:
    pdf = tmp_path / "tiny.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    payload = {"id": "session", "paper": {"id": "pid", "title": "tiny"}}
    async with PaperflowClient("http://test") as client:
        with respx.mock(base_url="http://test") as mock:
            route = mock.post("/api/papers/import").respond(200, json=payload)
            result = await client.import_pdf(pdf)
    assert route.called
    assert result["paper"]["title"] == "tiny"


@pytest.mark.asyncio
async def test_get_report_round_trip() -> None:
    report = {
        "paper_id": "pid",
        "summary": [],
        "sections": [{"id": "s1", "title": "Task", "claims": []}],
        "related_work": [],
    }
    async with PaperflowClient("http://test") as client:
        with respx.mock(base_url="http://test") as mock:
            mock.get("/api/papers/pid/report").respond(200, json=report)
            got = await client.get_report("pid")
    assert got["sections"][0]["title"] == "Task"


@pytest.mark.asyncio
async def test_error_is_wrapped() -> None:
    async with PaperflowClient("http://test") as client:
        with respx.mock(base_url="http://test") as mock:
            mock.get("/api/papers").mock(side_effect=httpx.ConnectError("boom"))
            with pytest.raises(PaperflowAPIError):
                await client.list_papers()
