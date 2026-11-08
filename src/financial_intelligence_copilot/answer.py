"""Local verbatim report excerpts with scoped citations and conservative refusals."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

from financial_intelligence_copilot.chunking import EvidenceChunk, normalize_search_text
from financial_intelligence_copilot.citations import CitationValidationError, validate_excerpt
from financial_intelligence_copilot.retrieval import (
    LexicalRetriever,
    ReportScopeError,
    load_retriever,
    tokenize,
)

NOTICE = (
    "Verbatim report excerpts, not an LLM-generated or verified financial answer. "
    "Relevance and completeness require review. "
    "Research demonstration only - not investment advice."
)
INSUFFICIENT = "Not enough information in selected documents"
QUESTION_WORDS = frozenset(
    "body sets role areas covered divide model arrangements measures support "
    "disclose disclosed described give tell please show explain summarize summarise "
    "information regarding".split()
)
INSTRUCTION_PATTERN = (
    r"ignore\b.{0,70}\b(?:instructions?|citations?|evidence|documents?|requirements?)\b"
    r"|(?:fabricate|invent|make up)\b.{0,60}\b(?:citations?|sources?|pages?|facts?)\b"
    r"|(?:without|omit|remove)\b.{0,25}\b(?:citations?|sources?|evidence)\b"
    r"|pretend\b.{0,50}\b(?:page|source|report)\b"
)


def request_limitation(query: str) -> tuple[str, str] | None:
    """Explicit product boundaries, not a comprehensive intent classifier."""
    # Treat metadata-style separators as word boundaries for intent checks only.
    # The caller retains the original query, and source quotations stay intact.
    intent_query = query.replace("_", " ")
    rules = (
        (
            INSTRUCTION_PATTERN,
            "citation_override_requested",
            "Citation rules cannot be overridden; no invented sources or page labels are allowed.",
        ),
        (
            r"\bshould i\b.{0,30}\b(?:buy|sell|invest|trade)\b|\bprice target\b"
            r"|\brecommend\b.{0,40}\b(?:stock|buy|sell|portfolio|investment)\b",
            "investment_advice_out_of_scope",
            "Investment recommendations are outside this research demonstration.",
        ),
        (
            r"\b(?:predict|forecast)\b|\bwhat will\b.{0,70}\b(?:be|price|earn|profit)\b",
            "prediction_out_of_scope",
            "This application does not predict future financial values or share prices.",
        ),
        (
            r"\byoy\b|year.over.year|percentage points?|\bcompare\b.{0,100}\b(?:fy)?20\d{2}\b"
            r"|\bchange\b.{0,100}\b(?:from|between)\b.{0,25}\b(?:fy)?20\d{2}\b",
            "comparison_not_available",
            "This extractive question workflow does not calculate comparisons. "
            "Use Year-over-Year to inspect review readiness and any approved comparisons.",
        ),
        (
            r"\b(?:vonb|opat|ufsg|anp|eps|revenue|profit|dividend|assets|liabilities)\b"
            r"|value of new business|free surplus generation|operating profit|new premiums?"
            r"|earnings per share|embedded value|solvency ratio|profit margin",
            "verified_kpi_unavailable",
            "Verified KPI answers are not available yet in this extractive question workflow. "
            "Use Financial KPIs to inspect candidates and recorded fact reviews.",
        ),
    )
    for pattern, reason, message in rules:
        if re.search(pattern, intent_query, flags=re.I | re.S):
            return reason, message
    return None


def _terms(text: str, fiscal_year: int) -> set[str]:
    terms = set(tokenize(normalize_search_text(text))) - QUESTION_WORDS
    terms -= {str(fiscal_year), f"fy{fiscal_year}"}
    return {
        term[:-1] if term.endswith("s") and not term.endswith("ss") and len(term) > 4 else term
        for term in terms
    }


def _regions(chunks: list[EvidenceChunk]) -> list[tuple[int, str]]:
    """Join only matching overlapping source spans; never invent missing whitespace."""
    regions: list[tuple[int, str]] = []
    for chunk in sorted(chunks, key=lambda item: (item.char_start, item.char_end)):
        if not regions or chunk.char_start > regions[-1][0] + len(regions[-1][1]):
            regions.append((chunk.char_start, chunk.raw_text))
            continue
        start, text = regions[-1]
        overlap = min(start + len(text), chunk.char_end) - chunk.char_start
        offset = chunk.char_start - start
        if text[offset : offset + overlap] != chunk.raw_text[:overlap]:
            raise CitationValidationError("Overlapping page context conflicts")
        if chunk.char_end > start + len(text):
            regions[-1] = (start, text + chunk.raw_text[overlap:])
    return regions


def _sentence_spans(text: str, query_terms: set[str], definition: bool):
    """Candidate source spans; punctuation heuristics do not prove grammatical completeness."""
    spans, start = [], 0
    endings = list(re.finditer(r"[.!?](?=\s|$)", text))
    for match in endings:
        prefix = text[max(0, match.end() - 6) : match.end()].lower()
        if any(prefix.endswith(abbreviation) for abbreviation in ("e.g.", "i.e.", "mr.", "dr.")):
            continue
        end = match.end()
        part = text[start:end]
        breaks = list(re.finditer(r"\n[ \t]*\n", part))
        left = start + (breaks[-1].end() if breaks else 0)
        while left < end and text[left].isspace():
            left += 1
        spans.append((left, end, 0.0))
        start = end
    if definition:
        # Generic glossary-row shape, not a hard-coded report page or answer.
        for term in query_terms:
            for match in re.finditer(rf"\b{re.escape(term)}[ \t]{{2,}}(?:a|an|the)\b", text, re.I):
                left = text.rfind("\n", 0, match.start()) + 1
                while left < len(text) and text[left].isspace():
                    left += 1
                ending = next((m.end() for m in endings if m.start() >= match.end()), None)
                if ending:
                    spans.append((left, ending, 2.0))
    return spans


def _covering_ids(chunks: list[EvidenceChunk], start: int, end: int) -> list[str]:
    selected, position = [], start
    while position < end:
        eligible = [chunk for chunk in chunks if chunk.char_start <= position < chunk.char_end]
        if not eligible:
            raise CitationValidationError("No continuous source coverage for selected excerpt")
        chosen = max(eligible, key=lambda chunk: (chunk.char_end, chunk.chunk_id))
        selected.append(chosen.chunk_id)
        position = min(end, chosen.char_end)
    return selected


def _select_excerpts(retriever, hits, query: str, doc_id: str, fiscal_year: int, limit: int):
    page_ranks = {hit.chunk.pdf_page: rank for rank, hit in enumerate(hits)}
    pool = {
        chunk.chunk_id: chunk
        for chunk in retriever.chunks
        if chunk.doc_id == doc_id
        and chunk.fiscal_year == fiscal_year
        and chunk.pdf_page in page_ranks
    }
    query_terms = _terms(query, fiscal_year)
    scoped = [
        chunk
        for chunk in retriever.chunks
        if chunk.doc_id == doc_id and chunk.fiscal_year == fiscal_year
    ]
    frequency = Counter()
    vocabulary = set()
    for chunk in scoped:
        terms = _terms(chunk.search_text, fiscal_year)
        vocabulary.update(terms)
        frequency.update(query_terms.intersection(terms))
    # Missing distinctive names must not be hidden by generic risk/product matches.
    for name in re.findall(r"\b[A-Z][A-Za-z0-9]*\b", query):
        if re.fullmatch(r"FY\d{4}", name):
            continue
        if _terms(name, fiscal_year) - vocabulary:
            return [], pool
    unknown = query_terms - vocabulary
    denominator = len(query_terms) + len(unknown)
    definition = bool(re.search(r"\bwhat (?:is|are)\b|\bdefine\b|\bmeaning of\b", query, re.I))
    candidates = []
    for page, rank in page_ranks.items():
        chunks = [chunk for chunk in pool.values() if chunk.pdf_page == page]
        regions = _regions(chunks)
        page_terms = set().union(*(_terms(text, fiscal_year) for _, text in regions))
        # A transparent conservative lexical heuristic, not an answerability score.
        if not denominator or len(query_terms.intersection(page_terms)) / denominator < 0.65:
            continue
        for base, text in regions:
            for left, right, bonus in _sentence_spans(text, query_terms, definition):
                raw = text[left:right]
                if (
                    not 30 <= len(raw) <= 1600
                    or "\ufffd" in raw
                    or re.search(r"\S[ \t]{40,}\S", raw)
                    or re.search(INSTRUCTION_PATTERN, raw, re.I | re.S)
                    or len(tokenize(raw)) < 5
                ):
                    continue
                matches = query_terms.intersection(_terms(raw, fiscal_year))
                if not matches:
                    continue
                score = sum(math.log(1 + len(scoped) / (1 + frequency[term])) for term in matches)
                candidates.append((score + bonus, rank, base + left, base + right, page, chunks))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    excerpts = []
    strongest = candidates[0][0] if candidates else 0
    selected_page = candidates[0][4] if candidates else None
    for score, _, start, end, page, chunks in candidates:
        # Keep the offline response focused on one selected source page. This is
        # an evidence excerpt mode, not a comprehensive multi-page synthesis.
        if page != selected_page:
            continue
        # Do not pad a short response with weak, tangential matches.
        if score < strongest * 0.65:
            continue
        if any(
            item.pdf_page == page and start < item.char_end and end > item.char_start
            for item in excerpts
        ):
            continue
        selection = {
            "evidence_ids": _covering_ids(chunks, start, end),
            "char_start": start,
            "char_end": end,
        }
        excerpts.append(
            validate_excerpt(selection, evidence=pool, doc_id=doc_id, fiscal_year=fiscal_year)
        )
        if len(excerpts) == limit:
            break
    return excerpts, pool


def answer_question(
    retriever: LexicalRetriever,
    query: str,
    *,
    doc_id: str,
    fiscal_year: int,
    top_k: int = 5,
    max_excerpts: int = 3,
) -> dict:
    """Return exact report excerpts or a reasoned abstention, without any model call."""
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("query must contain 1-2000 characters")
    if type(max_excerpts) is not int or not 1 <= max_excerpts <= 3:
        raise ValueError("max_excerpts must be an integer between 1 and 3")
    result = {
        "mode": "local_extractive",
        "status": "abstained",
        "query": query,
        "scope": {"doc_id": doc_id, "fiscal_year": fiscal_year},
        "message": INSUFFICIENT,
        "reason": "no_matching_evidence",
        "notice": NOTICE,
        "excerpts": [],
        "retrieval_context": {
            "primary_evidence_ids": [],
            "expanded_evidence_ids": [],
            "selected_pdf_page": None,
        },
    }
    try:
        hits = retriever.search(query, doc_id=doc_id, fiscal_year=fiscal_year, top_k=top_k)
    except ReportScopeError as exc:
        result.update(reason="report_scope_conflict", message=str(exc))
        return result
    limitation = request_limitation(query)
    if limitation:
        result.update(reason=limitation[0], message=limitation[1])
        return result
    if not hits:
        return result
    result["retrieval_context"]["primary_evidence_ids"] = [hit.chunk.chunk_id for hit in hits]
    try:
        excerpts, pool = _select_excerpts(retriever, hits, query, doc_id, fiscal_year, max_excerpts)
    except CitationValidationError:
        result.update(
            reason="citation_validation_failed",
            message="Source consistency checks failed; no excerpt was released.",
        )
        return result
    result["retrieval_context"]["expanded_evidence_ids"] = sorted(pool)
    if not excerpts:
        result["reason"] = "insufficient_quotable_evidence"
        return result
    result.update(
        status="extractive_evidence",
        reason=None,
        message="Selected-page report excerpts; completeness has not been established.",
        excerpts=[excerpt.to_dict() for excerpt in excerpts],
    )
    result["retrieval_context"]["selected_pdf_page"] = excerpts[0].pdf_page
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--fiscal-year", type=int, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.exists():
            raise ValueError("Output already exists; choose another path")
        retriever = load_retriever(args.index)
        response = answer_question(
            retriever,
            args.query,
            doc_id=args.doc_id,
            fiscal_year=args.fiscal_year,
            top_k=args.top_k,
        )
        serialized = json.dumps(response, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(serialized)
            print(f"Saved {response['status']} response to {args.output}")
        else:
            print(serialized, end="")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
