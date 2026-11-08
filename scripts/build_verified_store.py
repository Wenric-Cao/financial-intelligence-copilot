"""Export explicitly confirmed KPI facts or revalidate an existing local store."""

import argparse
from pathlib import Path

from financial_intelligence_copilot.verified_store import (
    load_verified_store,
    write_verified_store,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="Create a new local reviewed-fact JSON store")
    mode.add_argument("--check", type=Path, help="Revalidate an existing store without writing")
    args = parser.parse_args()
    try:
        if args.output:
            payload = write_verified_store(args.root, args.output)
            action = "Exported"
        else:
            payload = load_verified_store(args.root, args.check)
            action = "Validated"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(
        f"{action} {len(payload['records'])}/{payload['candidate_count']} reviewed KPI facts. "
        "Only explicitly confirmed facts are included; pair comparability is separate."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
