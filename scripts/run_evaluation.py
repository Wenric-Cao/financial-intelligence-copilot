"""Run a source-checked development suite and export pending human judgments."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from time import perf_counter

from financial_intelligence_copilot.evaluation import (
    canonical_digest,
    load_suite,
    make_review_packet,
    run_cases,
)
from financial_intelligence_copilot.retrieval import load_retriever


def dependency_fingerprints(root: Path, suite: Path) -> dict:
    """Record actual source/cache/config/code bytes before and after execution."""
    paths = {
        "suite": suite,
        "manifest": root / "data/manifest.csv",
        "policy": root / "data/retrieval_policy.json",
        "index": root / "data/processed/retrieval-index.json",
    }
    for name in ("pyproject.toml", "data/kpi_candidates.json", "data/kpi_reviews.json"):
        if (root / name).is_file():
            paths[name] = root / name
    with paths["manifest"].open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for label, base, relative in (
                ("raw", root / "data/raw", row["local_filename"]),
                ("pages", root / "data/processed", row["doc_id"] + ".pages.json"),
            ):
                source = (base / relative).resolve()
                if not source.is_relative_to(base.resolve()):
                    raise ValueError("Evaluation dependency leaves its registered data directory")
                paths[f"{label}/{row['doc_id']}"] = source
    package = Path(__file__).resolve().parents[1] / "src/financial_intelligence_copilot"
    for path in package.glob("*.py"):
        paths[f"code/{path.name}"] = path
    paths["code/run_evaluation.py"] = Path(__file__).resolve()
    result = {}
    for name, path in sorted(paths.items()):
        with path.open("rb") as handle:
            result[name] = hashlib.file_digest(handle, "sha256").hexdigest()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--suite", type=Path, default=Path("data/evaluation_cases.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.resolve() == args.review_output.resolve():
        parser.error("Run and review outputs must be distinct files")
    if args.output.exists() or args.review_output.exists():
        parser.error("Output already exists; choose new filenames")
    root = args.root.resolve()
    suite_path = args.suite if args.suite.is_absolute() else root / args.suite
    try:
        before = dependency_fingerprints(root, suite_path)
        start = perf_counter()
        suite = load_suite(suite_path, root)
        suite_validation_seconds = perf_counter() - start
        start = perf_counter()
        retriever = load_retriever(
            root / "data/processed/retrieval-index.json",
            manifest_path=root / "data/manifest.csv",
            raw_dir=root / "data/raw",
            pages_dir=root / "data/processed",
            policy_path=root / "data/retrieval_policy.json",
        )
        startup_verification_seconds = perf_counter() - start
        run = run_cases(retriever, suite)
        after = dependency_fingerprints(root, suite_path)
        if before != after:
            raise ValueError("Evaluation dependencies changed during execution; run not published")
        run["dependency_fingerprints"] = before
        run["suite_source_validation_seconds"] = suite_validation_seconds
        run["startup_index_verification_seconds"] = startup_verification_seconds
        run["dependency_snapshot_valid"] = True
        run["run_digest"] = canonical_digest(
            {key: value for key, value in run.items() if key != "run_digest"}
        )
        review = make_review_packet(run)
        for path, payload in ((args.output, run), (args.review_output, review)):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.write("\n")
        summary = run["summary"]
        print(
            f"Completed {summary['completed_count']}/{summary['case_count']} cases; "
            f"{summary['error_count']} runtime errors."
        )
        print(
            f"Engineering behavior matches: {summary['expected_behavior']['matched']}/"
            f"{summary['expected_behavior']['eligible']}."
        )
        spans = summary["source_spans"]
        span_result = (
            f"{spans['checked']}/{spans['total']}" if spans["total"] else "N/A (no excerpts)"
        )
        print(
            f"Literal source spans: {span_result}; {spans['case_errors']} cases with span errors. "
            "Semantic scores unavailable (0 approved gold, 0 human-scored cases)."
        )
        return int(
            summary["error_count"] > 0
            or summary["source_spans"]["case_errors"] > 0
            or summary["unexpected_diagnostic_error_count"] > 0
        )
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
