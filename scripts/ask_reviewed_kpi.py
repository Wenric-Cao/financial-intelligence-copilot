"""Look up one explicitly reviewed annual KPI from a revalidated local store."""

import argparse
import json
from pathlib import Path

from financial_intelligence_copilot.financial_answer import answer_reviewed_kpi


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--fiscal-year", required=True, type=int)
    parser.add_argument("--query", required=True)
    parser.add_argument(
        "--store", type=Path, help="Optional reviewed-store path; relative paths use --root"
    )
    parser.add_argument("--output", type=Path, help="Optional new response JSON; stdout by default")
    args = parser.parse_args()
    try:
        if args.output:
            if args.output.exists():
                raise FileExistsError(
                    "Output already exists; preserve it and choose a new filename"
                )
            destination = args.output.resolve()
            protected = {
                (args.root / relative).resolve()
                for relative in (
                    "data/kpi_candidates.json",
                    "data/kpi_reviews.json",
                    "data/manifest.csv",
                    "data/processed/verified-kpis.json",
                )
            }
            if args.store:
                active_store = args.store if args.store.is_absolute() else args.root / args.store
                protected.add(active_store.resolve())
            if destination in protected or destination.is_relative_to(
                (args.root / "data/raw").resolve()
            ):
                raise ValueError("Output path must not replace KPI inputs, the store or raw data")
        response = answer_reviewed_kpi(
            args.root,
            args.query,
            doc_id=args.doc_id,
            fiscal_year=args.fiscal_year,
            store_path=args.store,
        )
        serialized = json.dumps(response, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
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
