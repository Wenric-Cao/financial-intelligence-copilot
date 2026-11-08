"""Validate source excerpts from neutral fixtures, not real financial claims."""

import hashlib
import json
from dataclasses import replace

import pytest

from financial_intelligence_copilot.chunking import EvidenceChunk
from financial_intelligence_copilot.citations import CitationValidationError, validate_excerpt

DOC_ID = "NEUTRAL-FIXTURE-2024-EN"
ISSUER = "Neutral Test Fixture"
FISCAL_YEAR = 2024
SOURCE_URL = "https://example.invalid/neutral-citation-fixture.pdf"
SOURCE_HASH = hashlib.sha256(b"neutral citation fixture only").hexdigest()
PAGE_TEXT = (
    "TEST FIXTURE ONLY\n"
    "The café archive keeps paper folders and reference notes in a quiet reading room."
)
BASE_OFFSET = 97


def make_chunk(chunk_id: str, start: int, end: int, *, base: int = BASE_OFFSET) -> EvidenceChunk:
    """Preserve absolute page offsets despite using a small neutral text sample."""
    text = PAGE_TEXT[start:end]
    return EvidenceChunk(
        chunk_id=chunk_id,
        doc_id=DOC_ID,
        issuer=ISSUER,
        fiscal_year=FISCAL_YEAR,
        language="en",
        pdf_page=7,
        source_sha256=SOURCE_HASH,
        source_url=SOURCE_URL,
        char_start=base + start,
        char_end=base + end,
        raw_text=text,
        search_text=" ".join(text.split()),
    )


@pytest.fixture
def evidence() -> dict[str, EvidenceChunk]:
    return {
        "fixture-left": make_chunk("fixture-left", 0, PAGE_TEXT.index("reference") + 9),
        "fixture-right": make_chunk("fixture-right", PAGE_TEXT.index("paper"), len(PAGE_TEXT)),
    }


def paragraph_selection() -> dict:
    return {
        "evidence_ids": ["fixture-left", "fixture-right"],
        "char_start": BASE_OFFSET + PAGE_TEXT.index("The café"),
        "char_end": BASE_OFFSET + len(PAGE_TEXT),
    }


def validate(selection: dict, evidence: dict[str, EvidenceChunk], **kwargs):
    return validate_excerpt(
        selection, evidence=evidence, doc_id=DOC_ID, fiscal_year=FISCAL_YEAR, **kwargs
    )


def test_single_chunk_excerpt_is_derived_from_original_unicode_and_absolute_offsets(evidence):
    selection = {
        "evidence_ids": ["fixture-left"],
        "char_start": BASE_OFFSET + PAGE_TEXT.index("The café"),
        "char_end": BASE_OFFSET + PAGE_TEXT.index(" and reference"),
    }

    excerpt = validate(selection, evidence)

    assert excerpt.quote == "The café archive keeps paper folders"
    assert excerpt.evidence_ids == ("fixture-left",)
    assert excerpt.doc_id == DOC_ID
    assert excerpt.issuer == ISSUER
    assert excerpt.fiscal_year == FISCAL_YEAR
    assert excerpt.pdf_page == 7
    assert excerpt.source_url == SOURCE_URL
    assert excerpt.source_sha256 == SOURCE_HASH
    assert excerpt.char_start == selection["char_start"]
    assert excerpt.char_end == selection["char_end"]


def test_overlapping_chunks_cover_a_complete_sentence_without_rewriting(evidence):
    selection = paragraph_selection()

    excerpt = validate(selection, evidence)

    assert excerpt.quote == PAGE_TEXT[PAGE_TEXT.index("The café") :]
    assert isinstance(excerpt.evidence_ids, tuple)
    assert set(excerpt.evidence_ids) == {"fixture-left", "fixture-right"}
    assert excerpt.char_end - excerpt.char_start == len(excerpt.quote)
    serialized = json.loads(json.dumps(excerpt.to_dict()))
    assert serialized["quote"] == excerpt.quote
    assert serialized["pdf_page"] == 7
    assert serialized["source_sha256"] == SOURCE_HASH


def test_mapping_alias_cannot_relabel_an_indexed_evidence_id(evidence):
    evidence["fixture-left"] = replace(evidence["fixture-left"], chunk_id="different-source-id")
    with pytest.raises(CitationValidationError, match="identity"):
        validate(paragraph_selection(), evidence)


def test_adjacent_nonoverlapping_chunks_can_cover_a_contiguous_excerpt():
    split = PAGE_TEXT.index("reference")
    evidence = {
        "fixture-left": make_chunk("fixture-left", 0, split),
        "fixture-right": make_chunk("fixture-right", split, len(PAGE_TEXT)),
    }

    excerpt = validate(paragraph_selection(), evidence)

    assert excerpt.quote == PAGE_TEXT[PAGE_TEXT.index("The café") :]


def test_unknown_evidence_id_is_rejected_even_with_other_valid_sources(evidence):
    selection = paragraph_selection()
    selection["evidence_ids"].append("unknown-fixture-id")

    with pytest.raises(CitationValidationError):
        validate(selection, evidence)


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("doc_id", "OTHER-NEUTRAL-FIXTURE"),
        ("fiscal_year", 2025),
        ("issuer", "Another Neutral Test Fixture"),
        ("pdf_page", 8),
        ("source_sha256", hashlib.sha256(b"another neutral fixture version").hexdigest()),
        ("source_url", "https://example.invalid/different-neutral-fixture.pdf"),
    ],
)
def test_sources_from_different_documents_years_pages_or_versions_cannot_be_joined(
    evidence, field, wrong_value
):
    evidence["fixture-right"] = replace(evidence["fixture-right"], **{field: wrong_value})

    with pytest.raises(CitationValidationError):
        validate(paragraph_selection(), evidence)


def test_a_consistent_wrong_document_cannot_bypass_the_requested_scope(evidence):
    wrong_document = {
        key: replace(chunk, doc_id="OTHER-NEUTRAL-FIXTURE") for key, chunk in evidence.items()
    }

    with pytest.raises(CitationValidationError):
        validate(paragraph_selection(), wrong_document)


def test_missing_source_coverage_is_not_filled_by_guessing():
    evidence = {
        "fixture-left": make_chunk("fixture-left", 0, PAGE_TEXT.index("paper")),
        "fixture-right": make_chunk("fixture-right", PAGE_TEXT.index("reference"), len(PAGE_TEXT)),
    }

    with pytest.raises(CitationValidationError):
        validate(paragraph_selection(), evidence)


def test_overlapping_chunks_with_conflicting_original_text_are_rejected(evidence):
    right = evidence["fixture-right"]
    altered = "X" + right.raw_text[1:]
    evidence["fixture-right"] = replace(right, raw_text=altered, search_text=altered)

    with pytest.raises(CitationValidationError):
        validate(paragraph_selection(), evidence)


def test_chunk_text_length_must_match_its_declared_source_span(evidence):
    right = evidence["fixture-right"]
    evidence["fixture-right"] = replace(right, raw_text=right.raw_text + " Unmapped text.")

    with pytest.raises(CitationValidationError):
        validate(paragraph_selection(), evidence)


@pytest.mark.parametrize("payload_key", ["text", "quote"])
def test_caller_supplied_quote_text_is_rejected(evidence, payload_key):
    selection = {**paragraph_selection(), payload_key: "Caller-authored neutral text."}

    with pytest.raises(CitationValidationError):
        validate(selection, evidence)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("char_start", True),
        ("char_end", True),
        ("char_start", 1.0),
        ("char_end", 5.0),
        ("char_start", -1),
        ("char_end", len(PAGE_TEXT) + 1),
        ("char_end", 0),
    ],
)
def test_offsets_require_integer_nonempty_in_bounds_spans(field, invalid_value):
    evidence = {"whole-fixture": make_chunk("whole-fixture", 0, len(PAGE_TEXT), base=0)}
    selection = {
        "evidence_ids": ["whole-fixture"],
        "char_start": 0,
        "char_end": len(PAGE_TEXT),
        field: invalid_value,
    }

    with pytest.raises(CitationValidationError):
        validate(selection, evidence)


@pytest.mark.parametrize(
    "selection",
    [{}, {"evidence_ids": [], "char_start": 0, "char_end": 1}],
)
def test_empty_selections_cannot_produce_a_source_excerpt(evidence, selection):
    with pytest.raises(CitationValidationError):
        validate(selection, evidence)


def test_excerpt_length_limit_rejects_instead_of_silently_truncating(evidence):
    with pytest.raises(CitationValidationError):
        validate(paragraph_selection(), evidence, max_chars=20)
