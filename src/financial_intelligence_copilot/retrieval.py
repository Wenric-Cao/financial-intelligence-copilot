"""Local BM25 evidence retrieval with explicit document and report-year scope."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from financial_intelligence_copilot.chunking import EvidenceChunk
from financial_intelligence_copilot.indexing import build_index

# Ignore question scaffolding and issuer/report labels that otherwise match
# nearly every page footer. No stemming or semantic query expansion is used.
STOP_WORDS = frozenset(
    "a an and are as at be been by can describe describes did do does for from has "
    "have how in into is it its of on or say says that the their this to was were "
    "what when where which who why with would according about under aia annual "
    "report reports group".split()
)


class ReportScopeError(ValueError):
    """The requested document/year scope is absent or conflicts with the question."""


def tokenize(text: str) -> list[str]:
    """English lexical baseline; numeric terms and short acronyms are retained."""
    return [term for term in re.findall(r"[a-z0-9]+", text.lower()) if term not in STOP_WORDS]


@dataclass(frozen=True)
class SearchHit:
    chunk: EvidenceChunk
    score: float
    matched_terms: tuple[str, ...]

    def to_dict(self) -> dict:
        """Expose a source card, not a generated answer or verified KPI."""
        return {
            "evidence_id": self.chunk.chunk_id,
            "issuer": self.chunk.issuer,
            "doc_id": self.chunk.doc_id,
            "fiscal_year": self.chunk.fiscal_year,
            "pdf_page": self.chunk.pdf_page,
            "page_label": f"PDF page {self.chunk.pdf_page}",
            "source_url": self.chunk.source_url,
            "source_sha256": self.chunk.source_sha256,
            "char_start": self.chunk.char_start,
            "char_end": self.chunk.char_end,
            "source_excerpt": self.chunk.raw_text,
            "score": round(self.score, 6),
            "matched_terms": list(self.matched_terms),
            "verification_status": "candidate_evidence_only",
        }


class LexicalRetriever:
    """Rank matching chunks within one explicitly selected report.

    BM25 corpus statistics are computed after filtering. At most one chunk per
    physical page is returned, so top_k means up to top_k distinct evidence pages.
    Scores are ranking values, not calibrated confidence or answer correctness.
    """

    def __init__(self, chunks):
        self.chunks = tuple(chunks)
        ids = [chunk.chunk_id for chunk in self.chunks]
        if len(set(ids)) != len(ids):
            raise ValueError("Index contains duplicate evidence IDs")
        self.scopes: dict[str, tuple[str, int]] = {}
        for chunk in self.chunks:
            scope = (chunk.issuer, chunk.fiscal_year)
            if self.scopes.setdefault(chunk.doc_id, scope) != scope:
                raise ValueError("A document ID must identify exactly one issuer and fiscal year")
        self.terms = {chunk.chunk_id: Counter(tokenize(chunk.search_text)) for chunk in self.chunks}

    def search(
        self, query: str, *, doc_id: str, fiscal_year: int, top_k: int = 5
    ) -> list[SearchHit]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if type(top_k) is not int or not 1 <= top_k <= 50:
            raise ValueError("top_k must be an integer between 1 and 50")
        if type(fiscal_year) is not int:
            raise ValueError("fiscal_year must be an integer")
        if doc_id not in self.scopes or self.scopes[doc_id][1] != fiscal_year:
            raise ReportScopeError(
                "Unknown document or fiscal year does not match the selected report"
            )
        report_years = {
            int(match)
            for pattern in (
                r"\b(?:FY\s*|fiscal\s+year\s+)(\d{4})\s+(?:annual\s+)?report\b",
                r"\b(\d{4})\s+(?:annual\s+)?report\b",
                r"\bannual\s+report\s+(?:for\s+)?(\d{4})\b",
            )
            for match in re.findall(pattern, query, flags=re.I)
        }
        if report_years - {fiscal_year}:
            raise ReportScopeError(
                "Query references a different report year; select the matching report. "
                "Cross-report questions are not supported by this single-report baseline."
            )

        scoped = [
            chunk
            for chunk in self.chunks
            if chunk.doc_id == doc_id and chunk.fiscal_year == fiscal_year
        ]
        query_terms = set(tokenize(query)) - {str(fiscal_year), f"fy{fiscal_year}"}
        if not query_terms:
            return []
        counts = [self.terms[chunk.chunk_id] for chunk in scoped]
        lengths = [sum(count.values()) for count in counts]
        average_length = sum(lengths) / len(lengths) if lengths else 0
        if not average_length:
            return []
        document_frequency = Counter()
        for count in counts:
            document_frequency.update(query_terms.intersection(count))

        ranked = []
        for chunk, count, length in zip(scoped, counts, lengths, strict=True):
            matches = tuple(sorted(query_terms.intersection(count)))
            score = 0.0
            for term in matches:
                frequency = count[term]
                idf = math.log(
                    1
                    + (len(scoped) - document_frequency[term] + 0.5)
                    / (document_frequency[term] + 0.5)
                )
                score += (
                    idf
                    * frequency
                    * 2.5
                    / (frequency + 1.5 * (0.25 + 0.75 * length / average_length))
                )
            if score > 0:
                ranked.append(SearchHit(chunk, score, matches))

        ranked.sort(key=lambda hit: (-hit.score, hit.chunk.pdf_page, hit.chunk.chunk_id))
        hits, seen_pages = [], set()
        for hit in ranked:
            if hit.chunk.pdf_page not in seen_pages:
                hits.append(hit)
                seen_pages.add(hit.chunk.pdf_page)
            if len(hits) == top_k:
                break
        return hits


def load_retriever(
    path: str | Path,
    *,
    manifest_path: str | Path = "data/manifest.csv",
    raw_dir: str | Path = "data/raw",
    pages_dir: str | Path = "data/processed",
    policy_path: str | Path = "data/retrieval_policy.json",
) -> LexicalRetriever:
    """Verify a local cache against current sources before using its evidence.

    Rebuilding at load time favors auditability over startup speed for this small
    corpus. A loaded retriever can serve many queries in memory. A future cache
    optimization must preserve these source and policy invalidation checks.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("index_kind") != "local-bm25":
        raise ValueError("Unsupported retrieval index format")
    policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    fresh = build_index(manifest_path, raw_dir, pages_dir, policy)
    canonical_options = {"sort_keys": True, "separators": (",", ":"), "allow_nan": False}
    if json.dumps(data, **canonical_options) != json.dumps(fresh, **canonical_options):
        raise ValueError("Index does not match current sources or policy; rebuild and review it")
    return LexicalRetriever(EvidenceChunk(**record) for record in fresh["chunks"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--pages-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--policy", type=Path, default=Path("data/retrieval_policy.json"))
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--fiscal-year", type=int, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.exists():
            raise ValueError("Output already exists; choose another path")
        retriever = load_retriever(
            args.index,
            manifest_path=args.manifest,
            raw_dir=args.raw_dir,
            pages_dir=args.pages_dir,
            policy_path=args.policy,
        )
        hits = retriever.search(
            args.query, doc_id=args.doc_id, fiscal_year=args.fiscal_year, top_k=args.top_k
        )
        result = {
            "status": "candidate_evidence" if hits else "no_evidence",
            "query": args.query,
            "scope": {"doc_id": args.doc_id, "fiscal_year": args.fiscal_year},
            "notice": "Candidate evidence only; no generated answer or verified financial figures.",
            "hits": [hit.to_dict() for hit in hits],
        }
        serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(serialized)
            print(f"Saved {len(hits)} candidate evidence pages to {args.output}")
        else:
            print(serialized, end="")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
