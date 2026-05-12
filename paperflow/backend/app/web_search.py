"""Lightweight web search helpers for Agent chat.

The default implementation uses DuckDuckGo's HTML endpoint so Paperflow can
offer optional web context without requiring another API key. It is deliberately
best-effort: failures return an empty result set and chat falls back to local
paper context.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import httpx


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str = ""


class DuckDuckGoSearchClient:
    """Tiny, dependency-free client over DuckDuckGo HTML search."""

    endpoint = "https://duckduckgo.com/html/"

    def search(self, query: str, limit: int = 5) -> List[WebSearchResult]:
        query = " ".join(query.split())
        if not query:
            return []
        try:
            response = httpx.get(
                self.endpoint,
                params={"q": query},
                headers={"User-Agent": "Paperflow/0.1 (+local research assistant)"},
                timeout=httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=3.0),
            )
            response.raise_for_status()
        except Exception:
            return []
        return parse_duckduckgo_html(response.text, limit=limit)


def parse_duckduckgo_html(html: str, *, limit: int = 5) -> List[WebSearchResult]:
    parser = _DuckDuckGoParser()
    parser.feed(html or "")
    return parser.results[: max(0, limit)]


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: List[WebSearchResult] = []
        self._capture: Optional[str] = None
        self._buffer: List[str] = []
        self._pending_url: Optional[str] = None
        self._pending_title: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        class_name = attrs_dict.get("class", "")
        if tag == "a" and "result__a" in class_name:
            self._pending_url = _normalise_duckduckgo_url(attrs_dict.get("href", ""))
            self._capture = "title"
            self._buffer = []
        elif "result__snippet" in class_name:
            self._capture = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._capture:
            return
        value = " ".join("".join(self._buffer).split())
        if self._capture == "title" and tag == "a":
            self._pending_title = unescape(value)
            if self._pending_url:
                self.results.append(
                    WebSearchResult(title=self._pending_title, url=self._pending_url)
                )
        elif self._capture == "snippet":
            snippet = unescape(value)
            if snippet and self.results:
                previous = self.results[-1]
                if not previous.snippet:
                    self.results[-1] = WebSearchResult(
                        title=previous.title,
                        url=previous.url,
                        snippet=snippet,
                    )
        self._capture = None
        self._buffer = []


def _normalise_duckduckgo_url(raw: str) -> str:
    value = unescape(raw or "").strip()
    if value.startswith("//"):
        value = f"https:{value}"
    parsed = urlparse(value)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return value
