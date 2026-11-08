"""Lexical evidence isolation using neutral fixtures, not annual-report answers."""

import hashlib

import pytest

from financial_intelligence_copilot.chunking import EvidenceChunk
from financial_intelligence_copilot.retrieval import LexicalRetriever


def make_chunk(
    chunk_id: str,
    text: str,
    *,
    fiscal_year: int = 2024,
    pdf_page: int = 1,
    doc_id: str | None = None,
) -> EvidenceChunk:
    """Build explicitly fake provenance without claiming a real report citation."""
    document_id = doc_id or f"TEST-FIXTURE-{fiscal_year}-EN"
    return EvidenceChunk(
        chunk_id=chunk_id,
        doc_id=document_id,
        issuer="Neutral Test Fixture",
        fiscal_year=fiscal_year,
        language="en",
        pdf_page=pdf_page,
        source_sha256=hashlib.sha256(document_id.encode()).hexdigest(),
        source_url="https://example.invalid/neutral-test-fixture.pdf",
        char_start=0,
        char_end=len(text),
        raw_text=text,
        search_text=text,
    )


@pytest.fixture
def chunks() -> list[EvidenceChunk]:
    return [
        make_chunk(
            "older-archive", "Archive stewardship preserves paper folders and shelf labels."
        ),
        make_chunk("older-room", "A reading room provides tables and lamps.", pdf_page=2),
        make_chunk(
            "newer-archive",
            "Archive stewardship archive stewardship archive stewardship comet.",
            fiscal_year=2025,
        ),
    ]


def test_requested_document_and_year_are_hard_evidence_boundaries(chunks):
    retriever = LexicalRetriever(chunks)

    older_hits = retriever.search(
        "archive stewardship comet", doc_id="TEST-FIXTURE-2024-EN", fiscal_year=2024
    )
    newer_hits = retriever.search(
        "archive stewardship", doc_id="TEST-FIXTURE-2025-EN", fiscal_year=2025
    )

    assert older_hits and newer_hits
    assert {hit.chunk.chunk_id for hit in older_hits} == {"older-archive"}
    assert all(hit.chunk.doc_id == "TEST-FIXTURE-2024-EN" for hit in older_hits)
    assert all(hit.chunk.fiscal_year == 2024 for hit in older_hits)
    assert all(hit.chunk.doc_id == "TEST-FIXTURE-2025-EN" for hit in newer_hits)
    assert all(hit.chunk.fiscal_year == 2025 for hit in newer_hits)


def test_other_year_does_not_change_scoped_scores(chunks):
    selected_only = LexicalRetriever([chunk for chunk in chunks if chunk.fiscal_year == 2024])
    with_other_year = LexicalRetriever(chunks)
    scope = {"doc_id": "TEST-FIXTURE-2024-EN", "fiscal_year": 2024}

    baseline = selected_only.search("archive stewardship", **scope)
    combined = with_other_year.search("archive stewardship", **scope)

    assert [hit.chunk.chunk_id for hit in baseline] == [hit.chunk.chunk_id for hit in combined]
    assert [hit.score for hit in baseline] == pytest.approx([hit.score for hit in combined])


@pytest.mark.parametrize(
    ("doc_id", "fiscal_year"),
    [
        ("UNKNOWN-TEST-DOCUMENT", 2024),
        ("TEST-FIXTURE-2024-EN", 2025),
        ("TEST-FIXTURE-2024-EN", 2027),
    ],
)
def test_unknown_or_inconsistent_scope_is_rejected(chunks, doc_id, fiscal_year):
    with pytest.raises(ValueError):
        LexicalRetriever(chunks).search("archive", doc_id=doc_id, fiscal_year=fiscal_year)


def test_no_term_overlap_returns_no_evidence_instead_of_falling_back(chunks):
    result = LexicalRetriever(chunks).search(
        "unmentionedquasar", doc_id="TEST-FIXTURE-2024-EN", fiscal_year=2024
    )

    assert result == []


def test_result_explains_matches_and_retains_exact_evidence(chunks):
    hits = LexicalRetriever(chunks).search(
        "ARCHIVE stewardship", doc_id="TEST-FIXTURE-2024-EN", fiscal_year=2024
    )

    assert hits
    assert hits[0].chunk == chunks[0]
    assert hits[0].score > 0
    assert set(hits[0].matched_terms) == {"archive", "stewardship"}
    assert hits[0].chunk.raw_text == chunks[0].raw_text
    assert hits[0].chunk.pdf_page == 1


def test_multiple_chunks_on_one_page_do_not_crowd_out_another_page():
    retriever = LexicalRetriever(
        [
            make_chunk("first-page-a", "Archive archive archive preservation."),
            make_chunk("first-page-b", "Archive archive stewardship."),
            make_chunk("second-page", "Archive labels.", pdf_page=2),
        ]
    )
    scope = {"doc_id": "TEST-FIXTURE-2024-EN", "fiscal_year": 2024}

    hits = retriever.search("archive", top_k=5, **scope)

    assert len(hits) == 2
    assert {hit.chunk.pdf_page for hit in hits} == {1, 2}
    assert len(retriever.search("archive", top_k=1, **scope)) == 1


@pytest.mark.parametrize("query", ["", " \n\t "])
def test_empty_queries_are_rejected(chunks, query):
    with pytest.raises(ValueError):
        LexicalRetriever(chunks).search(query, doc_id="TEST-FIXTURE-2024-EN", fiscal_year=2024)


@pytest.mark.parametrize("top_k", [0, -1, 1.5, True])
def test_invalid_result_limits_are_rejected(chunks, top_k):
    with pytest.raises(ValueError):
        LexicalRetriever(chunks).search(
            "archive", doc_id="TEST-FIXTURE-2024-EN", fiscal_year=2024, top_k=top_k
        )
