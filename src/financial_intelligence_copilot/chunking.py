"""Create deterministic, page-bounded evidence chunks without rewriting sources."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

CHUNKING_VERSION = "page-words-v1"


@dataclass(frozen=True)
class EvidenceChunk:
    """An exact source substring and its separate normalized search text."""

    chunk_id: str
    doc_id: str
    issuer: str
    fiscal_year: int
    language: str
    pdf_page: int
    source_sha256: str
    source_url: str
    char_start: int
    char_end: int
    raw_text: str
    search_text: str


def normalize_search_text(text: str) -> str:
    """Normalize search input only; callers must retain original evidence text."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"\ufffd+|\.{3,}", " ", normalized)
    return " ".join(normalized.split())


def chunk_page(
    page: dict,
    *,
    source_sha256: str,
    source_url: str,
    max_words: int = 180,
    overlap_words: int = 30,
    min_words: int = 8,
) -> list[EvidenceChunk]:
    """Split one physical page at word boundaries, with exact character offsets.

    These are whitespace-delimited words, not LLM tokens. Windows never cross a
    PDF page. Empty/failed pages are not indexed and are never renumbered.
    """
    for name, value in (
        ("max_words", max_words),
        ("overlap_words", overlap_words),
        ("min_words", min_words),
    ):
        if type(value) is not int:
            raise ValueError(f"{name} must be an integer")
    if max_words < 1 or not 0 <= overlap_words < max_words:
        raise ValueError("Require max_words > 0 and 0 <= overlap_words < max_words")
    if not 1 <= min_words <= max_words:
        raise ValueError("Require 1 <= min_words <= max_words")
    if page["status"] != "ok" or not page["text"].strip():
        return []

    words = list(re.finditer(r"\S+", page["text"]))
    if len(words) < min_words:
        return []
    chunks = []
    step = max_words - overlap_words
    for start in range(0, len(words), step):
        end = min(start + max_words, len(words))
        # A short final window is already covered by the preceding window.
        if start and end - start <= overlap_words:
            break
        char_start, char_end = words[start].start(), words[end - 1].end()
        raw_text = page["text"][char_start:char_end]
        identity = (
            f"{CHUNKING_VERSION}|{source_sha256}|{page['doc_id']}|{page['pdf_page']}|"
            f"{char_start}|{char_end}|{raw_text}"
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
        chunks.append(
            EvidenceChunk(
                chunk_id=f"{page['doc_id']}:p{page['pdf_page']}:{digest}",
                doc_id=page["doc_id"],
                issuer=page["issuer"],
                fiscal_year=page["fiscal_year"],
                language=page["language"],
                pdf_page=page["pdf_page"],
                source_sha256=source_sha256,
                source_url=source_url,
                char_start=char_start,
                char_end=char_end,
                raw_text=raw_text,
                search_text=normalize_search_text(raw_text),
            )
        )
        if end == len(words):
            break
    return chunks
