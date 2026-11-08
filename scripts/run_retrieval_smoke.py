"""Measure engineering page hits; this is not answer or citation correctness."""

import argparse
import json
from pathlib import Path
from time import perf_counter

from financial_intelligence_copilot.retrieval import load_retriever


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=Path("data/retrieval_cases.json"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Output already exists; choose another path")
        data = json.loads(args.cases.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1 or not data.get("cases"):
            raise ValueError("Unsupported or empty smoke-case file")
        started = perf_counter()
        retriever = load_retriever(args.index)
        load_seconds = perf_counter() - started
        records = []
        for case in data["cases"]:
            started = perf_counter()
            hits = retriever.search(
                case["question"],
                doc_id=case["doc_id"],
                fiscal_year=case["fiscal_year"],
                top_k=args.top_k,
            )
            seconds = perf_counter() - started
            pages = [hit.chunk.pdf_page for hit in hits]
            assert all(
                hit.chunk.doc_id == case["doc_id"] and hit.chunk.fiscal_year == case["fiscal_year"]
                for hit in hits
            ), "Scope leakage detected"
            expected = set(case["expected_pdf_pages"])
            records.append(
                {
                    **case,
                    "retrieved_pdf_pages": pages,
                    "page_hit_at_1": bool(expected.intersection(pages[:1])),
                    "page_hit_at_k": bool(expected.intersection(pages)),
                    "query_seconds": seconds,
                    "hits": [hit.to_dict() for hit in hits],
                }
            )
        result = {
            "kind": "engineering_page_hit_smoke_test",
            "notice": (
                "Owner review pending. Not answer accuracy, citation accuracy, "
                "or the 40-question evaluation."
            ),
            "top_k": args.top_k,
            "case_count": len(records),
            "hits_at_1": sum(record["page_hit_at_1"] for record in records),
            "hits_at_k": sum(record["page_hit_at_k"] for record in records),
            "index_load_seconds": load_seconds,
            "cases": records,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(
            f"Engineering page hits: top 1 = {result['hits_at_1']}/{len(records)}; "
            f"top {args.top_k} = {result['hits_at_k']}/{len(records)}. Owner review pending."
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
