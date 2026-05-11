"""External clients for the R1 search pipeline.

Each client is intentionally narrow — it answers exactly the questions the
:mod:`app.r1_search` orchestrator needs, returns a normalised
:class:`R1Candidate` dataclass, and degrades to an empty list on upstream
failure. This way one broken vendor never breaks the whole search.

Clients exposed here:

* :class:`SemanticScholarClient` — references / citations / TLDR / search.
* :class:`OpenAlexClient` — work lookup by DOI/arXiv, references, cited_by.
* :class:`PapersWithCodeClient` — task / dataset / leaderboard lookup.

All three are mockable with :mod:`respx` (see ``tests/test_r1_clients.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx


# ---------------------------------------------------------------- common type


@dataclass
class R1Candidate:
    """One R1 candidate, normalised across vendors."""

    title: str
    source: str  # vendor + lane, e.g. ``semanticscholar:references``
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    openalex_id: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    tldr: Optional[str] = None
    citation_count: Optional[int] = None
    influential_citation_count: Optional[int] = None
    relation: Optional[str] = None  # one-liner like "cited reference" / "follow-up"

    def fingerprint(self) -> str:
        """Identity for dedup. Prefers DOI → arXiv id → S2 id → normalised title."""

        if self.doi:
            return f"doi:{self.doi.lower()}"
        if self.arxiv_id:
            return f"arxiv:{self.arxiv_id.lower()}"
        if self.semantic_scholar_id:
            return f"s2:{self.semantic_scholar_id}"
        if self.openalex_id:
            return f"oa:{self.openalex_id}"
        normalised = (self.title or "").lower().strip()
        return f"title:{normalised}"


# ---------------------------------------------------------------- Semantic Scholar


class SemanticScholarClient:
    """Thin client over the Semantic Scholar Graph API.

    Endpoints used:
    * ``/paper/{paper_id}`` — for the seed paper's S2 id and externalIds.
    * ``/paper/{paper_id}/references`` — for backward citations.
    * ``/paper/{paper_id}/citations`` — for forward citations.
    * ``/paper/search?query=…`` — for "Recent" and "Survey" lanes.
    """

    BASE = "https://api.semanticscholar.org/graph/v1"

    def __init__(
        self,
        *,
        client: Optional[httpx.Client] = None,
        api_key: Optional[str] = None,
        timeout: float = 20.0,
    ) -> None:
        self._client = client
        self._owns_client = client is None
        self._timeout = timeout
        self._headers = {"x-api-key": api_key} if api_key else {}

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout, headers=self._headers)
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    # --------------- single-paper lookup

    def resolve(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """Return the raw paper record for any S2-resolvable id."""

        fields = "paperId,title,authors.name,year,venue,externalIds,abstract,tldr,citationCount,influentialCitationCount"
        try:
            response = self._http().get(f"{self.BASE}/paper/{paper_id}", params={"fields": fields})
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None

    # --------------- backward / forward citations

    def references(self, paper_id: str, *, limit: int = 50) -> List[R1Candidate]:
        return self._citation_list(paper_id, "references", lane="references", limit=limit)

    def citations(self, paper_id: str, *, limit: int = 50) -> List[R1Candidate]:
        return self._citation_list(paper_id, "citations", lane="citations", limit=limit)

    def _citation_list(self, paper_id: str, endpoint: str, *, lane: str, limit: int) -> List[R1Candidate]:
        fields = "title,authors.name,year,venue,externalIds,tldr,citationCount,influentialCitationCount"
        try:
            response = self._http().get(
                f"{self.BASE}/paper/{paper_id}/{endpoint}",
                params={"fields": fields, "limit": min(limit, 100)},
            )
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError:
            return []

        out: List[R1Candidate] = []
        for entry in data.get("data") or []:
            nested = entry.get(endpoint[:-1])  # 'references' → 'referenced' would be wrong; use field below
            paper = entry.get("citedPaper") or entry.get("citingPaper") or nested or entry
            cand = _from_s2_paper(paper, lane=lane)
            if cand is not None:
                out.append(cand)
        return out

    # --------------- search

    def search(self, query: str, *, limit: int = 20, lane: str = "search") -> List[R1Candidate]:
        fields = "title,authors.name,year,venue,externalIds,tldr,citationCount,influentialCitationCount"
        try:
            response = self._http().get(
                f"{self.BASE}/paper/search",
                params={"query": query[:500], "limit": min(limit, 100), "fields": fields},
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError:
            return []

        candidates = [
            _from_s2_paper(item, lane=lane) for item in data.get("data") or []
        ]
        return [c for c in candidates if c is not None]


def _from_s2_paper(paper: Dict[str, Any], *, lane: str) -> Optional[R1Candidate]:
    if not paper or not paper.get("title"):
        return None
    external = paper.get("externalIds") or {}
    tldr_obj = paper.get("tldr") or {}
    return R1Candidate(
        title=paper.get("title") or "",
        source=f"semanticscholar:{lane}",
        authors=[a.get("name") for a in paper.get("authors") or [] if a.get("name")],
        year=paper.get("year"),
        venue=paper.get("venue"),
        doi=(external.get("DOI") or "").lower() or None,
        arxiv_id=external.get("ArXiv"),
        semantic_scholar_id=paper.get("paperId"),
        url=f"https://www.semanticscholar.org/paper/{paper.get('paperId')}" if paper.get("paperId") else None,
        tldr=tldr_obj.get("text") if isinstance(tldr_obj, dict) else None,
        citation_count=paper.get("citationCount"),
        influential_citation_count=paper.get("influentialCitationCount"),
        relation=_relation_for_lane(lane),
    )


# ---------------------------------------------------------------- OpenAlex


class OpenAlexClient:
    """Fallback client when Semantic Scholar is rate-limited or empty."""

    BASE = "https://api.openalex.org"

    def __init__(self, *, client: Optional[httpx.Client] = None, timeout: float = 20.0) -> None:
        self._client = client
        self._owns_client = client is None
        self._timeout = timeout

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def resolve_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        return self._resolve(f"works/doi:{doi}")

    def resolve_by_arxiv(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        return self._resolve(f"works/arxiv:{arxiv_id}")

    def _resolve(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            response = self._http().get(f"{self.BASE}/{path}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None

    def cited_by(self, work_id: str, *, limit: int = 25) -> List[R1Candidate]:
        try:
            response = self._http().get(
                f"{self.BASE}/works",
                params={"filter": f"cites:{work_id}", "per-page": min(limit, 50)},
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError:
            return []
        return [c for c in (_from_openalex(item, lane="citations") for item in data.get("results") or []) if c is not None]

    def references_of(self, work: Dict[str, Any], *, limit: int = 25) -> List[R1Candidate]:
        ref_ids = (work or {}).get("referenced_works") or []
        if not ref_ids:
            return []
        ref_ids = ref_ids[:limit]
        out: List[R1Candidate] = []
        try:
            response = self._http().get(
                f"{self.BASE}/works",
                params={"filter": "openalex_id:" + "|".join(_short_oa_id(rid) for rid in ref_ids), "per-page": min(len(ref_ids), 50)},
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError:
            return []
        for item in data.get("results") or []:
            cand = _from_openalex(item, lane="references")
            if cand is not None:
                out.append(cand)
        return out


def _short_oa_id(rid: str) -> str:
    # OpenAlex IDs come as "https://openalex.org/W12345". The filter wants just "W12345".
    return rid.rsplit("/", 1)[-1]


def _from_openalex(item: Dict[str, Any], *, lane: str) -> Optional[R1Candidate]:
    if not item or not item.get("title"):
        return None
    ids = item.get("ids") or {}
    authors = []
    for auth in item.get("authorships") or []:
        author = (auth or {}).get("author") or {}
        if author.get("display_name"):
            authors.append(author["display_name"])
    venue = (item.get("primary_location") or {}).get("source") or {}
    return R1Candidate(
        title=item.get("title") or "",
        source=f"openalex:{lane}",
        authors=authors,
        year=item.get("publication_year"),
        venue=venue.get("display_name") if isinstance(venue, dict) else None,
        doi=(item.get("doi") or "").replace("https://doi.org/", "").lower() or None,
        openalex_id=_short_oa_id(item.get("id", "")) or None,
        url=item.get("id"),
        citation_count=item.get("cited_by_count"),
        relation=_relation_for_lane(lane),
    )


# ---------------------------------------------------------------- Papers with Code


class PapersWithCodeClient:
    """Tiny PwC client — answers ``which benchmark / dataset / task is this on?``."""

    BASE = "https://paperswithcode.com/api/v1"

    def __init__(self, *, client: Optional[httpx.Client] = None, timeout: float = 20.0) -> None:
        self._client = client
        self._owns_client = client is None
        self._timeout = timeout

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def find_paper(self, title: str) -> Optional[Dict[str, Any]]:
        try:
            response = self._http().get(f"{self.BASE}/papers", params={"title": title[:200]})
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError:
            return None
        results = data.get("results") or []
        return results[0] if results else None

    def benchmark_neighbors(self, paper: Dict[str, Any], *, limit: int = 10) -> List[R1Candidate]:
        """Given a PwC paper, surface other papers sharing its tasks / datasets."""

        if not paper:
            return []
        paper_id = paper.get("id")
        if not paper_id:
            return []
        try:
            tasks = self._http().get(f"{self.BASE}/papers/{paper_id}/tasks").json() or {}
        except httpx.HTTPError:
            tasks = {}
        candidate_ids: List[str] = []
        for task in (tasks.get("results") or [])[:3]:
            task_id = task.get("id")
            if not task_id:
                continue
            try:
                neighbors = self._http().get(f"{self.BASE}/tasks/{task_id}/papers", params={"limit": limit}).json() or {}
            except httpx.HTTPError:
                continue
            for entry in neighbors.get("results") or []:
                if entry.get("id") and entry["id"] != paper_id:
                    candidate_ids.append(entry["id"])
            if len(candidate_ids) >= limit:
                break

        out: List[R1Candidate] = []
        for pid in candidate_ids[:limit]:
            try:
                detail = self._http().get(f"{self.BASE}/papers/{pid}").json()
            except httpx.HTTPError:
                continue
            cand = _from_pwc(detail, lane="benchmark")
            if cand is not None:
                out.append(cand)
        return out


def _from_pwc(item: Dict[str, Any], *, lane: str) -> Optional[R1Candidate]:
    if not item or not item.get("title"):
        return None
    return R1Candidate(
        title=item.get("title") or "",
        source=f"paperswithcode:{lane}",
        authors=[author for author in (item.get("authors") or []) if author],
        year=int(item["published"][:4]) if item.get("published") else None,
        venue=item.get("proceeding"),
        arxiv_id=item.get("arxiv_id"),
        doi=(item.get("doi") or "").lower() or None,
        url=item.get("url_abs"),
        abstract=item.get("abstract"),
        relation=_relation_for_lane(lane),
    )


# ---------------------------------------------------------------- helpers


def _relation_for_lane(lane: str) -> str:
    return {
        "references": "cited reference",
        "citations": "cites this paper",
        "search": "search result",
        "benchmark": "shares task / dataset",
        "survey": "survey or review",
        "recent": "recent related work",
    }.get(lane, lane)
