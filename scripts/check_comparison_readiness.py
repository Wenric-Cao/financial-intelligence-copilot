"""Prepare pending owner reviews or audit comparison readiness against actual PDF sources."""

import argparse
import json
from decimal import Decimal
from pathlib import Path

from financial_intelligence_copilot.kpi_reviews import (
    comparison_results,
    load_review_state,
    prepare_review_packet,
)


def decimal_json(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError("Unsupported result value")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--init-review", type=Path, help="Write an all-pending review packet")
    mode.add_argument("--output", type=Path, help="Write source-checked comparison readiness")
    args = parser.parse_args()
    output = args.init_review or args.output
    if output.exists():
        parser.error("Output already exists; preserve it and choose a new filename")
    try:
        if args.init_review:
            payload = prepare_review_packet(args.root)
            if not payload["candidate_reviews"]:
                raise ValueError("No local KPI candidates are registered")
            message = (
                f"Prepared {len(payload['candidate_reviews'])} pending fact reviews and "
                f"{len(payload['comparison_reviews'])} pending pair reviews. No approval recorded."
            )
        else:
            state = load_review_state(args.root)
            results = comparison_results(state)
            if not state["candidates"]:
                raise ValueError("No local KPI candidates are registered")
            calculated = sum(item["status"] == "calculated" for item in results)
            payload = {
                "kind": "source_checked_comparison_readiness",
                "review_packet_present": state["packet_present"],
                "candidate_count": len(state["candidates"]),
                "fact_confirmed_count": sum(
                    item["decision"] == "confirmed" for item in state["packet"]["candidate_reviews"]
                ),
                "pair_count": len(results),
                "calculated_count": calculated,
                "results": results,
                "notice": (
                    "Review decisions are local owner records, not authenticated signatures. "
                    "Calculation is gated by source checks, fact confirmation, explicit pair "
                    "comparability and structural rules. No verified store is written."
                ),
            }
            message = (
                f"Source-checked {len(state['candidates'])} candidates; "
                f"{payload['fact_confirmed_count']} facts confirmed. "
                f"Calculated {calculated}/{len(results)} annual pairs."
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, default=decimal_json, indent=2, ensure_ascii=False)
            handle.write("\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
