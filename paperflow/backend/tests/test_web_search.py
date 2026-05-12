from __future__ import annotations

import httpx
import respx

from app.web_search import DuckDuckGoSearchClient, parse_duckduckgo_html


def test_parse_duckduckgo_html_extracts_results() -> None:
    html = """
    <html><body>
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpaper">Paper result</a>
      <a class="result__snippet">A useful snippet about the paper.</a>
      <a class="result__a" href="https://example.org/blog">Blog result</a>
      <div class="result__snippet">Another snippet.</div>
    </body></html>
    """

    results = parse_duckduckgo_html(html, limit=5)

    assert len(results) == 2
    assert results[0].title == "Paper result"
    assert results[0].url == "https://example.com/paper"
    assert results[0].snippet == "A useful snippet about the paper."
    assert results[1].url == "https://example.org/blog"


@respx.mock
def test_duckduckgo_search_client_degrades_to_empty_results_on_failure() -> None:
    respx.get("https://duckduckgo.com/html/").mock(side_effect=httpx.ConnectError("offline"))

    results = DuckDuckGoSearchClient().search("paperflow web search", limit=3)

    assert results == []
