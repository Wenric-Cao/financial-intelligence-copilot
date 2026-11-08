"""Read a frozen development run without turning its counts into live accuracy."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from financial_intelligence_copilot.evaluation import (
    SEMANTIC_FIELDS,
    canonical_digest,
    make_review_packet,
)

RECORD_PATH = Path("data/processed/phase-8-evaluation.after-fix.json")
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
CORE_DATA = {
    "suite": Path("data/evaluation_cases.json"),
    "manifest": Path("data/manifest.csv"),
    "policy": Path("data/retrieval_policy.json"),
    "index": Path("data/processed/retrieval-index.json"),
}
OPTIONAL_DATA = ("data/kpi_candidates.json", "data/kpi_reviews.json")


def _inside(path: Path, base: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(base.resolve()):
        raise ValueError("An evaluation record dependency leaves its allowed directory")
    return resolved


def _file_digest(path: Path, base: Path) -> str:
    path = _inside(path, base)
    if not path.is_file():
        raise ValueError("A recorded evaluation dependency is missing")
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _count(value) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Evaluation counts must be nonnegative integers")
    return value


def _same_json(actual, expected) -> None:
    if canonical_digest({"value": actual}) != canonical_digest({"value": expected}):
        raise ValueError("Evaluation summary differs from its frozen case results")


def _validate_counts(run: dict) -> None:
    rows = run["case_results"]
    cases = {case["id"]: case for case in run["suite_snapshot"]["cases"]}
    for row in rows:
        case = cases[row["case_id"]]
        if row["category"] != case["category"]:
            raise ValueError("Evaluation result category differs from its frozen case")
        response, error = row["response"], row["error"]
        if error is not None and not isinstance(error, dict):
            raise ValueError("Evaluation error must be a structured record")
        if response is None and error is None:
            raise ValueError("A completed evaluation case needs a recorded response")
        behavior = bool(
            response is not None
            and response.get("status") == case["expected_behavior"]["status"]
            and response.get("reason") == case["expected_behavior"]["reason"]
        )
        _same_json(row["engineering_behavior_match"], behavior)
        spans = row["source_span_check"]
        checked, total = _count(spans["checked"]), _count(spans["total"])
        if (
            checked > total
            or not isinstance(spans["errors"], list)
            or any(not isinstance(message, str) for message in spans["errors"])
        ):
            raise ValueError("Evaluation span counts or errors are malformed")
        if error is None and isinstance(response.get("excerpts"), list):
            _same_json(total, len(response["excerpts"]))
        diagnostic = row["retrieval_error"]
        if diagnostic is not None and (
            not isinstance(diagnostic, dict)
            or diagnostic.get("kind") not in {"expected_scope_rejection", "unexpected_error"}
        ):
            raise ValueError("Evaluation diagnostic error is malformed")
        expected_pages = {
            (item["doc_id"], item["fiscal_year"], item["pdf_page"])
            for item in case["evidence"]
            if item["doc_id"] == case["selected_doc_id"]
        }
        eligible = len(case["target_docs"]) == 1 and bool(expected_pages)
        pages = [
            (hit["doc_id"], hit["fiscal_year"], hit["pdf_page"]) for hit in row["retrieval_hits"]
        ]
        for rank in (1, 5):
            hit = bool(set(pages[:rank]) & expected_pages) if eligible else None
            _same_json(row[f"proposed_page_hit_at_{rank}"], hit)

    summary = run["summary"]
    expected = {
        "case_count": len(rows),
        "completed_count": sum(row["error"] is None for row in rows),
        "error_count": sum(row["error"] is not None for row in rows),
        "diagnostic_retrieval_error_count": sum(row["retrieval_error"] is not None for row in rows),
        "unexpected_diagnostic_error_count": sum(
            row["retrieval_error"] is not None
            and row["retrieval_error"]["kind"] == "unexpected_error"
            for row in rows
        ),
        "category_counts": dict(Counter(case["category"] for case in cases.values())),
        "response_status_counts": dict(
            Counter(
                row["response"].get("status", "invalid_response")
                for row in rows
                if row["response"] is not None
            )
        ),
        "expected_behavior": {
            "matched": sum(row["engineering_behavior_match"] for row in rows),
            "eligible": len(rows),
        },
        "source_spans": {
            "checked": sum(row["source_span_check"]["checked"] for row in rows),
            "total": sum(row["source_span_check"]["total"] for row in rows),
            "case_errors": sum(bool(row["source_span_check"]["errors"]) for row in rows),
        },
        "approved_gold_count": 0,
        "human_scored_count": 0,
        "semantic_metrics": dict.fromkeys(SEMANTIC_FIELDS),
    }
    for rank in (1, 5):
        key = f"proposed_page_hit_at_{rank}"
        expected[key] = {
            "matched": sum(row[key] is True for row in rows),
            "eligible": sum(row[key] is not None for row in rows),
        }
    for key, value in expected.items():
        _same_json(summary[key], value)


def _validate_dependencies(root: Path, run: dict) -> bool:
    dependencies = run["dependency_fingerprints"]
    if not isinstance(dependencies, dict) or any(
        not isinstance(key, str)
        or not isinstance(digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        for key, digest in dependencies.items()
    ):
        raise ValueError("Evaluation dependency fingerprints are malformed")
    if not set(CORE_DATA).issubset(dependencies):
        raise ValueError("Evaluation record is missing core source dependencies")
    data_paths = {key: _inside(root / relative, root) for key, relative in CORE_DATA.items()}
    if _file_digest(data_paths["manifest"], root) != dependencies["manifest"]:
        raise ValueError("Historical evaluation manifest is stale")
    with data_paths["manifest"].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    seen = set()
    for row in rows:
        doc_id = row["doc_id"]
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", doc_id) is None or doc_id in seen:
            raise ValueError("Evaluation manifest has invalid or duplicate document IDs")
        seen.add(doc_id)
        raw = _inside(root / "data/raw", root)
        processed = _inside(root / "data/processed", root)
        data_paths[f"raw/{doc_id}"] = _inside(raw / row["local_filename"], raw)
        data_paths[f"pages/{doc_id}"] = _inside(processed / f"{doc_id}.pages.json", processed)
    if not rows or not set(data_paths).issubset(dependencies):
        raise ValueError("Evaluation record is missing registered source dependencies")
    for key in OPTIONAL_DATA:
        if key in dependencies:
            data_paths[key] = _inside(root / key, root)
    for key, path in data_paths.items():
        if _file_digest(path, root) != dependencies[key]:
            raise ValueError(f"Historical evaluation source data is stale: {key}")
    current_suite = json.loads(data_paths["suite"].read_text(encoding="utf-8"))
    if canonical_digest(current_suite) != run["suite_digest"]:
        raise ValueError("Historical evaluation suite snapshot differs from current source data")

    code_keys = {key for key in dependencies if key.startswith("code/")}
    if any(re.fullmatch(r"code/[A-Za-z_][A-Za-z0-9_]*\.py", key) is None for key in code_keys):
        raise ValueError("Evaluation code fingerprint has an untrusted path")
    allowed = set(data_paths) | code_keys | {"pyproject.toml"}
    if set(dependencies) - allowed:
        raise ValueError("Evaluation record contains an unknown dependency")
    current_code = {f"code/{path.name}" for path in PACKAGE_ROOT.glob("*.py")}
    current_code.add("code/run_evaluation.py")
    code_current = code_keys == current_code
    for key in code_keys:
        if key == "code/run_evaluation.py":
            path, base = PROJECT_ROOT / "scripts/run_evaluation.py", PROJECT_ROOT
        else:
            path, base = PACKAGE_ROOT / key.removeprefix("code/"), PACKAGE_ROOT
        try:
            code_current &= _file_digest(path, base) == dependencies[key]
        except (OSError, ValueError):
            code_current = False
    if "pyproject.toml" in dependencies:
        try:
            code_current &= (
                _file_digest(root / "pyproject.toml", root) == dependencies["pyproject.toml"]
            )
        except (OSError, ValueError):
            code_current = False
    return code_current


def load_development_record(root: Path) -> dict | None:
    """Project a frozen run only when its data dependencies still match.

    Code/configuration changes mark the record historical; source-data changes
    reject it. Digests establish content identity, not reviewer authentication or
    semantic correctness. No evaluation is rerun and no missing score is inferred.
    """
    root = Path(root).resolve()
    path = _inside(root / RECORD_PATH, root)
    if not path.exists():
        return None
    try:
        run = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(run, dict)
            or type(run.get("schema_version")) is not int
            or run["schema_version"] != 1
            or run.get("kind") != "local_extractive_development_evaluation"
            or run.get("mode") != "local_extractive"
            or run.get("dependency_snapshot_valid") is not True
            or type(run.get("model_api_calls")) is not int
            or run["model_api_calls"] != 0
            or run.get("provider_cost") is not None
            or not isinstance(run.get("run_id"), str)
            or not run["run_id"].strip()
        ):
            raise ValueError("Unsupported historical local-extractive evaluation record")
        started = datetime.fromisoformat(run["started_at"])
        if started.tzinfo is None or started.utcoffset() is None:
            raise ValueError("Evaluation start time must include its timezone")
        make_review_packet(run)
        _validate_counts(run)
        code_current = _validate_dependencies(root, run)
        summary = run["summary"]
        return {
            "started_at": run["started_at"],
            "run_id": run["run_id"],
            "run_digest": run["run_digest"],
            "case_count": summary["case_count"],
            "completed_count": summary["completed_count"],
            "error_count": summary["error_count"],
            "behavior_matched": summary["expected_behavior"]["matched"],
            "behavior_eligible": summary["expected_behavior"]["eligible"],
            "spans_checked": summary["source_spans"]["checked"],
            "spans_total": summary["source_spans"]["total"],
            "span_case_errors": summary["source_spans"]["case_errors"],
            "page_hits_1": summary["proposed_page_hit_at_1"]["matched"],
            "page_hits_5": summary["proposed_page_hit_at_5"]["matched"],
            "page_hit_eligible": summary["proposed_page_hit_at_1"]["eligible"],
            "approved_gold_count": 0,
            "human_scored_count": 0,
            "semantic_metrics": dict.fromkeys(SEMANTIC_FIELDS),
            "code_snapshot_current": code_current,
        }
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"Historical development record validation failed: {exc}") from exc
