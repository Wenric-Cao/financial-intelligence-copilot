"""Validate candidate provenance and export a pending-review sheet, without approval."""

import argparse
import json
from pathlib import Path

from financial_intelligence_copilot.financial_kpis import candidate_csv, load_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.csv.exists():
        parser.error("Output already exists; choose new filenames")
    records = load_candidates(args.root)
    if not records:
        parser.error("No candidates are registered")
    summary = {
        "kind": "kpi_candidate_source_check",
        "candidate_count": len(records),
        "verified_count": sum(item["verified"] for item in records),
        "prior_year_comparatives_checked": sum(
            bool(item.get("prior_year_comparative")) for item in records
        ),
        "prior_values_matching_original": sum(
            item.get("comparative_matches_original", False) for item in records
        ),
        "owner_review_pending": True,
        "yoy_calculated": False,
        "notice": (
            "Source tokens match local PDFs; definitions, column meaning "
            "and comparability need owner review."
        ),
        "candidates": [
            {
                "candidate_id": item["candidate_id"],
                "value": str(item["value"]),
                "currency": item["currency"],
                "unit": item["unit"],
                "source_pdf_page": item["source_pdf_page"],
                "verified": False,
            }
            for item in records
        ],
    }
    for path in (args.output, args.csv):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    with args.csv.open("x", newline="", encoding="utf-8") as handle:
        handle.write(candidate_csv(records))
    print(
        f"Source-checked {len(records)} candidates; {summary['verified_count']} verified. "
        "Owner review pending."
    )
    print(
        f"Prior comparative matches: {summary['prior_values_matching_original']}/"
        f"{summary['prior_year_comparatives_checked']}; no YoY calculated."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
