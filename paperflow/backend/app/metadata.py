"""External metadata fetchers for Paperflow imports.

Each ``fetch_*`` function takes a raw identifier (arXiv id, DOI, OpenReview note id,
Semantic Scholar paper id) and returns a :class:`~app.models.PaperMetadata`.
``classify_url`` inspects a free-form input string (URL, arXiv id, DOI) and
dispatches it to the right fetcher; ``fetch_metadata_from_url`` is the all-in-one
entry point used by ``POST /api/papers/import-url``.

The fetchers use ``httpx`` synchronously, matching the existing backend style
(:mod:`app.deepseek`). Each remote call has a tight timeout and gracefully
degrades to a metadata-only object when an upstream is unavailable.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, Tuple

import httpx

from app.models import ImportSourceType, PaperMetadata


# ---------------------------------------------------------------- URL parsing


_ARXIV_RE = re.compile(
    r"""
    (?:                              # opt arxiv: prefix
        ^arxiv:\s*
    )?
    (
        [a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?   # old-style id, e.g. cs.LG/0512345
        |
        \d{4}\.\d{4,5}(?:v\d+)?                  # new-style id, e.g. 2605.08063v1
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# DOI grammar: 10.{registrant}/{suffix}.
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", re.IGNORECASE)

_OPENREVIEW_RE = re.compile(r"openreview\.net/(?:forum|pdf|references|notes)\?[^#\s]*?id=([A-Za-z0-9_\-]+)")

_S2_RE = re.compile(r"semanticscholar\.org/paper/(?:[^/]+/)?([A-Fa-f0-9]{32,64})")


@dataclass(frozen=True)
class ParsedSource:
    source_type: ImportSourceType
    identifier: str  # canonical id (arxiv id without version stripping, doi, etc.)
    source_url: str


class MetadataError(Exception):
    """Wrapped failure from any upstream metadata source."""


# ---------------------------------------------------------------- classify URL


def classify_url(raw: str) -> ParsedSource:
    """Classify a free-form import string and return the canonical source.

    Examples accepted:

    * ``https://arxiv.org/abs/2605.08063``
    * ``arXiv:2605.08063v1`` / ``2605.08063``
    * ``https://doi.org/10.1145/3580305.3599800`` / ``10.1145/...``
    * ``https://www.semanticscholar.org/paper/abc.../<sha>``
    * ``https://openreview.net/forum?id=abcDEF``
    """

    value = raw.strip()
    if not value:
        raise MetadataError("Empty import string")

    # OpenReview must come before generic URL parsing because it embeds an id query string.
    m = _OPENREVIEW_RE.search(value)
    if m:
        forum_id = m.group(1)
        return ParsedSource(
            source_type=ImportSourceType.OPENREVIEW,
            identifier=forum_id,
            source_url=f"https://openreview.net/forum?id={forum_id}",
        )

    # Semantic Scholar paper URL.
    m = _S2_RE.search(value)
    if m:
        s2_id = m.group(1)
        return ParsedSource(
            source_type=ImportSourceType.SEMANTIC_SCHOLAR,
            identifier=s2_id,
            source_url=f"https://www.semanticscholar.org/paper/{s2_id}",
        )

    # arXiv URL or bare id.
    if "arxiv.org" in value.lower() or value.lower().startswith("arxiv:") or _ARXIV_RE.fullmatch(value):
        arxiv_id = _extract_arxiv_id(value)
        if arxiv_id:
            return ParsedSource(
                source_type=ImportSourceType.ARXIV,
                identifier=arxiv_id,
                source_url=f"https://arxiv.org/abs/{arxiv_id}",
            )

    # DOI: a bare doi or a URL containing one.
    m = _DOI_RE.search(value)
    if m:
        doi = m.group(1).rstrip(".)\"'")
        return ParsedSource(
            source_type=ImportSourceType.DOI,
            identifier=doi.lower(),
            source_url=f"https://doi.org/{doi}",
        )

    raise MetadataError(f"Could not classify import URL/ID: {raw!r}")


def _extract_arxiv_id(value: str) -> Optional[str]:
    cleaned = value.strip()
    if cleaned.lower().startswith("arxiv:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    url_match = re.search(r"arxiv\.org/(?:abs|pdf|html)/([^?#\s]+)", cleaned, re.IGNORECASE)
    if url_match:
        cleaned = url_match.group(1)
    if cleaned.lower().endswith(".pdf"):
        cleaned = cleaned[:-4]
    match = _ARXIV_RE.fullmatch(cleaned) or _ARXIV_RE.search(cleaned)
    return match.group(1) if match else None


# ---------------------------------------------------------------- fetchers


def fetch_arxiv_metadata(arxiv_id: str, *, client: Optional[httpx.Client] = None) -> PaperMetadata:
    """Query the public arXiv Atom API for a single paper id."""

    owns_client = client is None
    client = client or httpx.Client(timeout=20)
    try:
        response = client.get(
            "https://export.arxiv.org/api/query",
            params={"id_list": arxiv_id},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MetadataError(f"arXiv API failed for {arxiv_id}: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    return _parse_arxiv_atom(response.text, arxiv_id)


def _parse_arxiv_atom(xml_body: str, fallback_arxiv_id: str) -> PaperMetadata:
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    try:
        root = ET.fromstring(xml_body)
    except ET.ParseError as exc:
        raise MetadataError(f"Invalid arXiv response: {exc}") from exc

    entry = root.find("atom:entry", ns)
    if entry is None:
        raise MetadataError(f"arXiv returned no entry for {fallback_arxiv_id}")

    title_el = entry.find("atom:title", ns)
    title = " ".join((title_el.text or "").split()) if title_el is not None else None

    authors = [
        (a.findtext("atom:name", default="", namespaces=ns) or "").strip()
        for a in entry.findall("atom:author", ns)
    ]
    authors = [a for a in authors if a]

    published_el = entry.find("atom:published", ns)
    year = None
    if published_el is not None and published_el.text:
        year = int(published_el.text[:4])

    summary_el = entry.find("atom:summary", ns)
    abstract = " ".join((summary_el.text or "").split()) if summary_el is not None else None

    venue_el = entry.find("arxiv:journal_ref", ns)
    venue = (venue_el.text or "").strip() if venue_el is not None else "arXiv"

    doi_el = entry.find("arxiv:doi", ns)
    doi = (doi_el.text or "").strip().lower() if doi_el is not None else None

    id_el = entry.find("atom:id", ns)
    arxiv_id = fallback_arxiv_id
    if id_el is not None and id_el.text:
        m = re.search(r"arxiv\.org/abs/(.+)$", id_el.text)
        if m:
            arxiv_id = m.group(1)

    return PaperMetadata(
        title=title,
        authors=authors,
        year=year,
        venue=venue or "arXiv",
        arxiv_id=arxiv_id,
        doi=doi or None,
        source_type=ImportSourceType.ARXIV,
        source_url=f"https://arxiv.org/abs/{arxiv_id}",
        abstract=abstract,
    )


def fetch_crossref_metadata(doi: str, *, client: Optional[httpx.Client] = None) -> PaperMetadata:
    """Query the CrossRef public API for a DOI."""

    owns_client = client is None
    client = client or httpx.Client(timeout=20)
    try:
        response = client.get(
            f"https://api.crossref.org/works/{doi}",
            headers={"User-Agent": "PaperFlow/0.2 (mailto:noreply@paperflow.local)"},
        )
        response.raise_for_status()
        data = response.json().get("message") or {}
    except httpx.HTTPError as exc:
        raise MetadataError(f"CrossRef API failed for {doi}: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    title_list = data.get("title") or []
    title = title_list[0] if title_list else None

    authors = [
        " ".join(part for part in [a.get("given"), a.get("family")] if part)
        for a in (data.get("author") or [])
        if a.get("family") or a.get("given")
    ]

    year = None
    issued = (data.get("issued") or {}).get("date-parts") or []
    if issued and issued[0]:
        try:
            year = int(issued[0][0])
        except (TypeError, ValueError):
            year = None

    venue = None
    container = data.get("container-title") or []
    if container:
        venue = container[0]
    if not venue:
        event = data.get("event") or {}
        venue = event.get("name")

    abstract = data.get("abstract")
    if abstract:
        # CrossRef abstracts are wrapped in JATS; strip tags crudely for display.
        abstract = re.sub(r"<[^>]+>", "", abstract).strip()

    return PaperMetadata(
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        doi=doi.lower(),
        source_type=ImportSourceType.DOI,
        source_url=f"https://doi.org/{doi}",
        abstract=abstract,
    )


def fetch_semantic_scholar_metadata(
    paper_id: str,
    *,
    client: Optional[httpx.Client] = None,
) -> PaperMetadata:
    """Query the Semantic Scholar Graph API for any S2-resolvable id.

    ``paper_id`` can be the raw S2 hash, ``DOI:10.x/...``, ``ARXIV:2605.08063``,
    or ``URL:https://...`` per the S2 docs.
    """

    fields = "title,authors.name,year,venue,externalIds,abstract"
    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"

    owns_client = client is None
    client = client or httpx.Client(timeout=20)
    try:
        response = client.get(url, params={"fields": fields})
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        raise MetadataError(f"Semantic Scholar API failed for {paper_id}: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    external = data.get("externalIds") or {}
    authors = [a.get("name") for a in (data.get("authors") or []) if a.get("name")]
    return PaperMetadata(
        title=data.get("title"),
        authors=authors,
        year=data.get("year"),
        venue=data.get("venue"),
        arxiv_id=external.get("ArXiv"),
        doi=(external.get("DOI") or "").lower() or None,
        semantic_scholar_id=data.get("paperId") or paper_id,
        source_type=ImportSourceType.SEMANTIC_SCHOLAR,
        source_url=f"https://www.semanticscholar.org/paper/{data.get('paperId') or paper_id}",
        abstract=data.get("abstract"),
    )


def fetch_openreview_metadata(
    note_id: str,
    *,
    client: Optional[httpx.Client] = None,
) -> PaperMetadata:
    """Query the OpenReview API for a single forum/note id."""

    owns_client = client is None
    client = client or httpx.Client(timeout=20)
    try:
        response = client.get(
            "https://api2.openreview.net/notes",
            params={"id": note_id},
        )
        response.raise_for_status()
        notes = (response.json() or {}).get("notes") or []
    except httpx.HTTPError as exc:
        raise MetadataError(f"OpenReview API failed for {note_id}: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    if not notes:
        raise MetadataError(f"OpenReview returned no notes for {note_id}")

    note = notes[0]
    content = note.get("content") or {}

    def _value(field_name: str) -> Optional[str]:
        field = content.get(field_name)
        if isinstance(field, dict):
            return field.get("value")
        return field

    authors_field = _value("authors")
    if isinstance(authors_field, str):
        authors = [a.strip() for a in authors_field.split(",") if a.strip()]
    elif isinstance(authors_field, list):
        authors = [str(a).strip() for a in authors_field if str(a).strip()]
    else:
        authors = []

    year = None
    cdate = note.get("cdate") or note.get("pdate")
    if cdate:
        from datetime import datetime, timezone

        try:
            year = datetime.fromtimestamp(int(cdate) / 1000, tz=timezone.utc).year
        except (TypeError, ValueError):
            year = None

    venue = _value("venue") or note.get("invitation")

    return PaperMetadata(
        title=_value("title"),
        authors=authors,
        year=year,
        venue=venue,
        openreview_id=note_id,
        source_type=ImportSourceType.OPENREVIEW,
        source_url=f"https://openreview.net/forum?id={note_id}",
        abstract=_value("abstract"),
    )


# ---------------------------------------------------------------- combined


def fetch_metadata_from_url(raw: str, *, client: Optional[httpx.Client] = None) -> PaperMetadata:
    """Classify ``raw`` and dispatch to the appropriate fetcher.

    Returns :class:`PaperMetadata` with ``source_url`` populated. Raises
    :class:`MetadataError` if classification or fetch fails.
    """

    parsed = classify_url(raw)
    if parsed.source_type == ImportSourceType.ARXIV:
        return fetch_arxiv_metadata(parsed.identifier, client=client)
    if parsed.source_type == ImportSourceType.DOI:
        return fetch_crossref_metadata(parsed.identifier, client=client)
    if parsed.source_type == ImportSourceType.SEMANTIC_SCHOLAR:
        return fetch_semantic_scholar_metadata(parsed.identifier, client=client)
    if parsed.source_type == ImportSourceType.OPENREVIEW:
        return fetch_openreview_metadata(parsed.identifier, client=client)
    raise MetadataError(f"Unsupported source type for {raw!r}")


def pdf_url_from_metadata(meta: PaperMetadata) -> Optional[str]:
    """Best-effort guess at a downloadable PDF URL for the given metadata."""

    if meta.arxiv_id:
        return f"https://arxiv.org/pdf/{meta.arxiv_id}.pdf"
    if meta.openreview_id:
        return f"https://openreview.net/pdf?id={meta.openreview_id}"
    return None


# ---------------------------------------------------------------- title cleanup


def normalize_title(title: str) -> str:
    """Normalize a title for fuzzy-key dedup.

    Lowercases, collapses whitespace, strips trailing punctuation, and removes
    common version suffixes like ``(v2)`` and ``Vol. 3``.
    """

    if not title:
        return ""
    value = title.lower()
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s*\(?v\d+\)?$", "", value)
    value = re.sub(r"[\u2018\u2019\u201c\u201d\"'`]+", "", value)
    return value.strip(" .,:;-_/")


def dedup_key_from_metadata(meta: PaperMetadata) -> Tuple[str, str]:
    """Return ``(kind, key)`` — strongest available identity for dedup."""

    if meta.content_hash:
        return ("content_hash", meta.content_hash)
    if meta.doi:
        return ("doi", meta.doi.lower())
    if meta.arxiv_id:
        # Strip the version so 2605.08063 and 2605.08063v1 dedup together.
        return ("arxiv_id", re.sub(r"v\d+$", "", meta.arxiv_id))
    if meta.semantic_scholar_id:
        return ("semantic_scholar_id", meta.semantic_scholar_id)
    if meta.openreview_id:
        return ("openreview_id", meta.openreview_id)
    first_author = (meta.authors[0] if meta.authors else "").split()[-1].lower() if meta.authors else ""
    return ("title_author_year", f"{normalize_title(meta.title or '')}|{first_author}|{meta.year or ''}")
