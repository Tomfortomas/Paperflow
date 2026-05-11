"""Tests for Phase 2 metadata fetchers and URL classification."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.metadata import (
    MetadataError,
    classify_url,
    dedup_key_from_metadata,
    fetch_arxiv_metadata,
    fetch_crossref_metadata,
    fetch_metadata_from_url,
    fetch_openreview_metadata,
    fetch_semantic_scholar_metadata,
    normalize_title,
    pdf_url_from_metadata,
)
from app.models import ImportSourceType, PaperMetadata


# --------------------------------------------------------------- classify_url


@pytest.mark.parametrize(
    "raw, expected_type, expected_id",
    [
        ("https://arxiv.org/abs/2605.08063", ImportSourceType.ARXIV, "2605.08063"),
        ("https://arxiv.org/abs/2605.08063v1", ImportSourceType.ARXIV, "2605.08063v1"),
        ("arXiv:2605.08063v1", ImportSourceType.ARXIV, "2605.08063v1"),
        ("2605.08063", ImportSourceType.ARXIV, "2605.08063"),
        ("https://arxiv.org/pdf/2605.08063v1.pdf", ImportSourceType.ARXIV, "2605.08063v1"),
        ("10.1145/3580305.3599800", ImportSourceType.DOI, "10.1145/3580305.3599800"),
        ("https://doi.org/10.1145/3580305.3599800", ImportSourceType.DOI, "10.1145/3580305.3599800"),
        (
            "https://www.semanticscholar.org/paper/Attention-Is-All-You-Need/" + "a" * 40,
            ImportSourceType.SEMANTIC_SCHOLAR,
            "a" * 40,
        ),
        (
            "https://openreview.net/forum?id=AbCdEf123",
            ImportSourceType.OPENREVIEW,
            "AbCdEf123",
        ),
    ],
)
def test_classify_url_dispatches_correctly(raw: str, expected_type: ImportSourceType, expected_id: str) -> None:
    parsed = classify_url(raw)
    assert parsed.source_type is expected_type
    assert parsed.identifier == expected_id
    assert parsed.source_url


def test_classify_url_rejects_garbage() -> None:
    with pytest.raises(MetadataError):
        classify_url("not a paper url")


# --------------------------------------------------------------- arXiv fetcher


_ARXIV_ATOM = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom' xmlns:arxiv='http://arxiv.org/schemas/atom'>
  <entry>
    <id>http://arxiv.org/abs/2605.08063v1</id>
    <title>An Evidence-Aware Paper Reading Agent</title>
    <summary>This paper introduces Paperflow, a local-first IDE for evidence-aware paper reading.</summary>
    <published>2026-04-12T17:55:33Z</published>
    <author><name>Mingliang Shi</name></author>
    <author><name>Coauthor Two</name></author>
    <arxiv:journal_ref>NeurIPS 2026</arxiv:journal_ref>
    <arxiv:doi>10.48550/arXiv.2605.08063</arxiv:doi>
  </entry>
</feed>
"""


@respx.mock
def test_fetch_arxiv_metadata_parses_atom_feed() -> None:
    respx.get("https://export.arxiv.org/api/query").mock(
        return_value=httpx.Response(200, text=_ARXIV_ATOM)
    )
    meta = fetch_arxiv_metadata("2605.08063v1")

    assert meta.title == "An Evidence-Aware Paper Reading Agent"
    assert meta.authors == ["Mingliang Shi", "Coauthor Two"]
    assert meta.year == 2026
    assert meta.venue == "NeurIPS 2026"
    assert meta.arxiv_id == "2605.08063v1"
    assert meta.doi == "10.48550/arxiv.2605.08063"
    assert meta.source_type is ImportSourceType.ARXIV
    assert meta.source_url == "https://arxiv.org/abs/2605.08063v1"
    assert meta.abstract and meta.abstract.startswith("This paper introduces Paperflow")


@respx.mock
def test_fetch_arxiv_metadata_raises_on_empty_response() -> None:
    respx.get("https://export.arxiv.org/api/query").mock(
        return_value=httpx.Response(200, text="<feed xmlns='http://www.w3.org/2005/Atom'></feed>")
    )
    with pytest.raises(MetadataError):
        fetch_arxiv_metadata("0000.00000")


# --------------------------------------------------------------- CrossRef


_CROSSREF_PAYLOAD = {
    "message": {
        "title": ["Reading the Paper Reading Agent"],
        "author": [
            {"given": "Alice", "family": "Liu"},
            {"given": "Bob", "family": "Chen"},
        ],
        "issued": {"date-parts": [[2025, 6, 1]]},
        "container-title": ["ACM Transactions on Information Systems"],
        "abstract": "<jats:p>An <jats:italic>evidence-first</jats:italic> reading assistant.</jats:p>",
    }
}


@respx.mock
def test_fetch_crossref_metadata_normalises_authors_and_strips_jats() -> None:
    respx.get("https://api.crossref.org/works/10.1145/foo.bar").mock(
        return_value=httpx.Response(200, json=_CROSSREF_PAYLOAD)
    )
    meta = fetch_crossref_metadata("10.1145/foo.bar")
    assert meta.title == "Reading the Paper Reading Agent"
    assert meta.authors == ["Alice Liu", "Bob Chen"]
    assert meta.year == 2025
    assert meta.venue == "ACM Transactions on Information Systems"
    assert meta.doi == "10.1145/foo.bar"
    assert meta.abstract == "An evidence-first reading assistant."
    assert meta.source_type is ImportSourceType.DOI


# --------------------------------------------------------------- Semantic Scholar


_S2_PAYLOAD = {
    "paperId": "abc123def4",
    "title": "Retrieval-Augmented Paper Agents",
    "authors": [{"name": "X. Wang"}, {"name": "Y. Zhang"}],
    "year": 2024,
    "venue": "ICLR",
    "externalIds": {"ArXiv": "2401.12345", "DOI": "10.5555/iclr.2024.1"},
    "abstract": "Abstract here.",
}


@respx.mock
def test_fetch_semantic_scholar_metadata_extracts_external_ids() -> None:
    respx.get("https://api.semanticscholar.org/graph/v1/paper/abc123def4").mock(
        return_value=httpx.Response(200, json=_S2_PAYLOAD)
    )
    meta = fetch_semantic_scholar_metadata("abc123def4")
    assert meta.semantic_scholar_id == "abc123def4"
    assert meta.arxiv_id == "2401.12345"
    assert meta.doi == "10.5555/iclr.2024.1"
    assert meta.venue == "ICLR"
    assert meta.source_type is ImportSourceType.SEMANTIC_SCHOLAR


# --------------------------------------------------------------- OpenReview


_OPENREVIEW_PAYLOAD = {
    "notes": [
        {
            "id": "abcd1234",
            "cdate": 1709251200000,  # 2024-03-01 UTC
            "content": {
                "title": {"value": "Decoding-Time R0 Verifier"},
                "authors": {"value": ["A. One", "B. Two"]},
                "abstract": {"value": "We verify R0 claims at decoding time."},
                "venue": {"value": "ICLR 2024"},
            },
        }
    ]
}


@respx.mock
def test_fetch_openreview_metadata_handles_v2_value_dict() -> None:
    respx.get("https://api2.openreview.net/notes").mock(
        return_value=httpx.Response(200, json=_OPENREVIEW_PAYLOAD)
    )
    meta = fetch_openreview_metadata("abcd1234")
    assert meta.title == "Decoding-Time R0 Verifier"
    assert meta.authors == ["A. One", "B. Two"]
    assert meta.year == 2024
    assert meta.venue == "ICLR 2024"
    assert meta.openreview_id == "abcd1234"
    assert meta.source_type is ImportSourceType.OPENREVIEW


# --------------------------------------------------------------- combined


@respx.mock
def test_fetch_metadata_from_url_dispatches_to_arxiv() -> None:
    respx.get("https://export.arxiv.org/api/query").mock(
        return_value=httpx.Response(200, text=_ARXIV_ATOM)
    )
    meta = fetch_metadata_from_url("https://arxiv.org/abs/2605.08063v1")
    assert meta.arxiv_id == "2605.08063v1"
    assert meta.source_type is ImportSourceType.ARXIV


@respx.mock
def test_fetch_metadata_from_url_dispatches_to_crossref_for_doi() -> None:
    respx.get("https://api.crossref.org/works/10.1145/foo.bar").mock(
        return_value=httpx.Response(200, json=_CROSSREF_PAYLOAD)
    )
    meta = fetch_metadata_from_url("https://doi.org/10.1145/foo.bar")
    assert meta.doi == "10.1145/foo.bar"


def test_pdf_url_from_metadata_prefers_arxiv() -> None:
    meta_arxiv = PaperMetadata(arxiv_id="2605.08063v1", source_type=ImportSourceType.ARXIV)
    assert pdf_url_from_metadata(meta_arxiv) == "https://arxiv.org/pdf/2605.08063v1.pdf"
    meta_or = PaperMetadata(openreview_id="abcd", source_type=ImportSourceType.OPENREVIEW)
    assert pdf_url_from_metadata(meta_or) == "https://openreview.net/pdf?id=abcd"
    meta_doi = PaperMetadata(doi="10.1145/foo", source_type=ImportSourceType.DOI)
    assert pdf_url_from_metadata(meta_doi) is None


# --------------------------------------------------------------- dedup keys


def test_dedup_key_prefers_content_hash_then_doi_then_arxiv() -> None:
    full = PaperMetadata(
        title="x",
        authors=["A. Y"],
        year=2024,
        arxiv_id="2401.12345v1",
        doi="10.1/abc",
        content_hash="sha",
    )
    assert dedup_key_from_metadata(full) == ("content_hash", "sha")

    without_hash = full.model_copy(update={"content_hash": None})
    assert dedup_key_from_metadata(without_hash) == ("doi", "10.1/abc")

    without_doi = without_hash.model_copy(update={"doi": None})
    # arXiv version should be stripped so identifiers across versions dedup together.
    assert dedup_key_from_metadata(without_doi) == ("arxiv_id", "2401.12345")

    title_only = PaperMetadata(title="Some Paper (v2)", authors=["Alice Liu"], year=2024)
    assert dedup_key_from_metadata(title_only) == (
        "title_author_year",
        "some paper|liu|2024",
    )


def test_normalize_title_strips_versions_and_punctuation() -> None:
    assert normalize_title("My Paper Title (v2)") == "my paper title"
    assert normalize_title("Long Title.") == "long title"
    assert normalize_title("  Spaces   Everywhere v3 ") == "spaces everywhere"
