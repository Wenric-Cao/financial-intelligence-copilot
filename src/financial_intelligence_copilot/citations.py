"""Resolve quote selections from exact, scoped source spans; accept no answer text."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from financial_intelligence_copilot.chunking import EvidenceChunk


class CitationValidationError(ValueError):
    """A selection cannot be reconstructed from its stated source evidence."""


@dataclass(frozen=True)
class SourceExcerpt:
    evidence_ids: tuple[str, ...]
    issuer: str
    doc_id: str
    fiscal_year: int
    pdf_page: int
    source_url: str
    source_sha256: str
    char_start: int
    char_end: int
    quote: str

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "page_label": f"PDF page {self.pdf_page}",
            "verification_status": "exact_source_span_only_not_financial_verification",
        }


def validate_excerpt(
    selection: dict,
    *,
    evidence: Mapping[str, EvidenceChunk],
    doc_id: str,
    fiscal_year: int,
    max_chars: int = 1600,
) -> SourceExcerpt:
    """Derive a quote from source IDs and absolute physical-page text offsets.

    Multiple chunks may support a single quote only on the same physical page
    with the same issuer, year, source hash, and URL. They must cover every
    character and agree wherever they overlap. No supplied quote or claim text
    is trusted. This proves source identity, not relevance or completeness.
    """
    if not isinstance(selection, dict) or set(selection) != {
        "evidence_ids",
        "char_start",
        "char_end",
    }:
        raise CitationValidationError("Selection must contain only evidence IDs and source offsets")
    ids = selection["evidence_ids"]
    if (
        not isinstance(ids, list)
        or not ids
        or len(ids) > 8
        or any(not isinstance(item, str) or not item for item in ids)
        or len(set(ids)) != len(ids)
    ):
        raise CitationValidationError("Evidence IDs must be a non-empty unique list")
    if type(fiscal_year) is not int or type(max_chars) is not int or max_chars < 1:
        raise CitationValidationError("Invalid year or quote-length limit")
    start, end = selection["char_start"], selection["char_end"]
    if type(start) is not int or type(end) is not int or not 0 <= start < end:
        raise CitationValidationError("Quote offsets must be increasing non-negative integers")
    if end - start > max_chars:
        raise CitationValidationError("Quote exceeds the configured length limit")
    try:
        chunks = [evidence[item] for item in ids]
    except KeyError as exc:
        raise CitationValidationError("Unknown evidence ID") from exc

    first = chunks[0]
    identity = (
        first.doc_id,
        first.issuer,
        first.fiscal_year,
        first.pdf_page,
        first.source_sha256,
        first.source_url,
    )
    if first.doc_id != doc_id or first.fiscal_year != fiscal_year:
        raise CitationValidationError("Evidence does not belong to the selected document/year")
    characters: list[str | None] = [None] * (end - start)
    for evidence_id, chunk in zip(ids, chunks, strict=True):
        if evidence_id != chunk.chunk_id:
            raise CitationValidationError("Evidence ID does not match the indexed chunk identity")
        if (
            (
                chunk.doc_id,
                chunk.issuer,
                chunk.fiscal_year,
                chunk.pdf_page,
                chunk.source_sha256,
                chunk.source_url,
            )
            != identity
            or type(chunk.pdf_page) is not int
            or chunk.pdf_page < 1
            or type(chunk.fiscal_year) is not int
        ):
            raise CitationValidationError("Evidence sources disagree on document/page identity")
        if (
            type(chunk.char_start) is not int
            or type(chunk.char_end) is not int
            or chunk.char_start < 0
            or chunk.char_end <= chunk.char_start
            or not isinstance(chunk.raw_text, str)
            or len(chunk.raw_text) != chunk.char_end - chunk.char_start
        ):
            raise CitationValidationError("Evidence text length does not match its source span")
        left, right = max(start, chunk.char_start), min(end, chunk.char_end)
        if left >= right:
            raise CitationValidationError("An evidence ID does not intersect the selected quote")
        for offset in range(left, right):
            char = chunk.raw_text[offset - chunk.char_start]
            current = characters[offset - start]
            if current is not None and current != char:
                raise CitationValidationError("Overlapping evidence text conflicts")
            characters[offset - start] = char
    if any(char is None for char in characters):
        raise CitationValidationError("Evidence leaves a gap in the quote's source coverage")
    quote = "".join(char for char in characters if char is not None)
    if not quote.strip():
        raise CitationValidationError("A quote must contain non-whitespace source text")
    return SourceExcerpt(
        tuple(ids),
        first.issuer,
        doc_id,
        fiscal_year,
        first.pdf_page,
        first.source_url,
        first.source_sha256,
        start,
        end,
        quote,
    )
