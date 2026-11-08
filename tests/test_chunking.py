"""Page-preserving chunks from neutral test text, never real financial evidence."""

import hashlib

import pytest

from financial_intelligence_copilot.chunking import chunk_page, normalize_search_text

FIXTURE_HASH = hashlib.sha256(b"neutral chunking test fixture only").hexdigest()
FIXTURE_URL = "https://example.invalid/neutral-test-fixture.pdf"


def make_page(text: str, *, pdf_page: int = 7, status: str = "ok") -> dict:
    """Use explicit fixture metadata with physical and printed pages differing."""
    return {
        "doc_id": "TEST-FIXTURE-2024-EN",
        "issuer": "Neutral Test Fixture",
        "fiscal_year": 2024,
        "language": "en",
        "pdf_page": pdf_page,
        "text": text,
        "status": status,
        "error": None,
    }


def test_chunks_keep_exact_original_substrings_and_physical_page():
    original = (
        "TEST FIXTURE ONLY\nPrinted page 1\n"
        "The café archive contains neutral descriptions of paper folders and shelves.\n"
        "A second paragraph describes labels, storage boxes, and a reading room. "
        "These words are test content and make no annual report claims."
    )
    page = make_page(original)

    chunks = chunk_page(
        page,
        source_sha256=FIXTURE_HASH,
        source_url=FIXTURE_URL,
        max_words=12,
        overlap_words=3,
        min_words=3,
    )

    assert len(chunks) >= 2
    assert page["text"] == original
    assert [chunk.char_start for chunk in chunks] == sorted(chunk.char_start for chunk in chunks)
    for chunk in chunks:
        assert 0 <= chunk.char_start < chunk.char_end <= len(original)
        assert chunk.raw_text == original[chunk.char_start : chunk.char_end]
        assert chunk.pdf_page == 7
        assert chunk.doc_id == page["doc_id"]
        assert chunk.issuer == page["issuer"]
        assert chunk.fiscal_year == 2024
        assert chunk.language == "en"
        assert chunk.source_sha256 == FIXTURE_HASH
        assert chunk.source_url == FIXTURE_URL
        assert chunk.search_text == normalize_search_text(chunk.raw_text)
    assert "Printed page 1" in " ".join(chunk.raw_text for chunk in chunks)


def test_chunk_ids_are_repeatable_and_distinguish_source_page_and_bytes():
    page = make_page("Neutral fixture text about archive labels and reading room shelves.")
    kwargs = {"source_sha256": FIXTURE_HASH, "source_url": FIXTURE_URL}

    first = chunk_page(page, **kwargs)
    again = chunk_page(page, **kwargs)
    other_page = chunk_page({**page, "pdf_page": 8}, **kwargs)
    other_source = chunk_page(
        page,
        source_sha256=hashlib.sha256(b"another neutral fixture version").hexdigest(),
        source_url=FIXTURE_URL,
    )

    assert first
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in again]
    assert len({chunk.chunk_id for chunk in first}) == len(first)
    assert {chunk.chunk_id for chunk in first}.isdisjoint(chunk.chunk_id for chunk in other_page)
    assert {chunk.chunk_id for chunk in first}.isdisjoint(chunk.chunk_id for chunk in other_source)


@pytest.mark.parametrize(
    ("status", "text"),
    [
        ("empty_text", ""),
        ("extraction_error", "Do not use stale text from a failed extraction."),
        ("ok", " \n\t "),
    ],
)
def test_empty_or_failed_pages_do_not_become_evidence(status: str, text: str):
    assert (
        chunk_page(
            make_page(text, status=status),
            source_sha256=FIXTURE_HASH,
            source_url=FIXTURE_URL,
        )
        == []
    )


def test_skipping_an_empty_page_does_not_renumber_later_evidence():
    text = "Neutral fixture words describe archive shelves labels folders and reading rooms."
    pages = [
        make_page(text, pdf_page=1),
        make_page("", pdf_page=2, status="empty_text"),
        make_page(text, pdf_page=3),
    ]

    chunks = [
        chunk
        for page in pages
        for chunk in chunk_page(page, source_sha256=FIXTURE_HASH, source_url=FIXTURE_URL)
    ]

    assert {chunk.pdf_page for chunk in chunks} == {1, 3}
    assert all(chunk.pdf_page != 2 for chunk in chunks)


def test_search_cleanup_preserves_original_evidence_and_meaningful_punctuation():
    original = (
        "Neutral fixture\nContents .............. Alpha "
        "\ufffd\ufffd\ufffd section\t notes v1.2 café."
    )
    page = make_page(original)

    chunks = chunk_page(page, source_sha256=FIXTURE_HASH, source_url=FIXTURE_URL)

    assert len(chunks) == 1
    assert chunks[0].raw_text == original
    assert page["text"] == original
    normalized = chunks[0].search_text
    assert "\ufffd" not in normalized
    assert "........" not in normalized
    assert "\n" not in normalized and "\t" not in normalized
    assert "  " not in normalized
    assert "v1.2" in normalized
    assert "café." in normalized
    assert "Alpha" in normalized and "section" in normalized


@pytest.mark.parametrize(
    "override",
    [
        {"max_words": 0},
        {"max_words": -1},
        {"overlap_words": -1},
        {"overlap_words": 12},
        {"overlap_words": 13},
        {"min_words": 0},
        {"min_words": 13},
    ],
)
def test_invalid_window_settings_are_rejected(override: dict):
    settings = {"max_words": 12, "overlap_words": 2, "min_words": 3, **override}

    with pytest.raises(ValueError):
        chunk_page(
            make_page("Neutral fixture text about paper labels and archive shelves."),
            source_sha256=FIXTURE_HASH,
            source_url=FIXTURE_URL,
            **settings,
        )
