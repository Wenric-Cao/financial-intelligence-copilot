"""Historical-record tests use actual neutral fixtures, never AIA scores or gold."""

import csv
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pymupdf
import pytest

from financial_intelligence_copilot import evaluation_records
from financial_intelligence_copilot.chunking import EvidenceChunk
from financial_intelligence_copilot.evaluation import canonical_digest, run_cases
from financial_intelligence_copilot.indexing import build_index
from financial_intelligence_copilot.pdf_parser import DocumentMetadata, parse_pdf
from financial_intelligence_copilot.retrieval import LexicalRetriever

DOC_ID = "TEST-RECORD-2025"
QUOTE = "The Archive Board approves the records framework."


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_record(workspace: dict, *, refresh_digest: bool = True) -> None:
    run = workspace["run"]
    if refresh_digest:
        run["run_digest"] = canonical_digest(
            {key: value for key, value in run.items() if key != "run_digest"}
        )
    path = workspace["record_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run), encoding="utf-8")


@pytest.fixture
def recorded_workspace(tmp_path: Path) -> dict:
    """Generate real PDF bytes and a real neutral run, without an owner judgment."""
    raw = tmp_path / "data/raw"
    processed = tmp_path / "data/processed"
    raw.mkdir(parents=True)
    processed.mkdir()
    source = raw / "neutral_record.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text(
            (72, 72),
            "TEST FIXTURE ONLY - NOT A FINANCIAL REPORT\n"
            f"{QUOTE}\n"
            "The framework protects archive folders and reference labels.",
            fontsize=10,
        )
        document.save(source)
    parsed = parse_pdf(source, DocumentMetadata(DOC_ID, "Neutral Record Fixture", 2025))
    snapshot = processed / f"{DOC_ID}.pages.json"
    snapshot.write_text(json.dumps(parsed.to_dict()), encoding="utf-8")
    url = "https://example.invalid/neutral_record.pdf"
    manifest_row = {
        "doc_id": DOC_ID,
        "issuer": "Neutral Record Fixture",
        "fiscal_year": 2025,
        "language": "en",
        "source_url": url,
        "sha256": parsed.sha256,
        "local_filename": source.name,
    }
    manifest = tmp_path / "data/manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_row))
        writer.writeheader()
        writer.writerow(manifest_row)
    policy = {
        "schema_version": 1,
        "max_words": 180,
        "overlap_words": 30,
        "min_words": 8,
        "excluded_pdf_pages": {},
    }
    policy_path = tmp_path / "data/retrieval_policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    index = build_index(manifest, raw, processed, policy)
    index_path = processed / "retrieval-index.json"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    retriever = LexicalRetriever(EvidenceChunk(**item) for item in index["chunks"])
    quote_start = parsed.pages[0].text.index(QUOTE)
    fact = {
        "id": "TEST-ONLY-fact",
        "category": "simple_fact",
        "question": "Who approves the records framework?",
        "target_docs": [DOC_ID],
        "selected_doc_id": DOC_ID,
        "selected_fiscal_year": 2025,
        "answerable": True,
        "candidate_answer": "The Archive Board (neutral test proposal only).",
        "evidence": [
            {
                "doc_id": DOC_ID,
                "fiscal_year": 2025,
                "pdf_page": 1,
                "source_sha256": parsed.sha256,
                "source_url": url,
                "char_start": quote_start,
                "char_end": quote_start + len(QUOTE),
                "quote": QUOTE,
            }
        ],
        "expected_behavior": {"status": "extractive_evidence", "reason": None},
        "review_status": "pending_owner_review",
        "reviewer": None,
        "reviewed_at": None,
        "review_notes": "TEST ONLY neutral proposal; not approved gold or real company evidence.",
        "exposure": "development",
    }
    boundary = {
        **deepcopy(fact),
        "id": "TEST-ONLY-missing-subject",
        "category": "boundary",
        "question": "What is ZephyrQuartz?",
        "answerable": False,
        "candidate_answer": None,
        "evidence": [],
        "expected_behavior": {"status": "abstained", "reason": "no_matching_evidence"},
    }
    suite = {
        "schema_version": 1,
        "split": "development",
        "purpose": "TEST ONLY neutral historical record",
        "cases": [fact, boundary],
    }
    suite_path = tmp_path / "data/evaluation_cases.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("# TEST ONLY configuration bytes\n", encoding="utf-8")
    candidates = tmp_path / "data/kpi_candidates.json"
    candidates.write_text('{"schema_version": 1, "candidates": []}', encoding="utf-8")
    reviews = tmp_path / "data/kpi_reviews.json"
    reviews.write_text(
        '{"schema_version": 1, "candidate_reviews": [], "comparison_reviews": []}',
        encoding="utf-8",
    )
    dependencies = {
        "suite": digest(suite_path),
        "manifest": digest(manifest),
        "policy": digest(policy_path),
        "index": digest(index_path),
        f"raw/{DOC_ID}": digest(source),
        f"pages/{DOC_ID}": digest(snapshot),
        "data/kpi_candidates.json": digest(candidates),
        "data/kpi_reviews.json": digest(reviews),
        "pyproject.toml": digest(pyproject),
    }
    package = Path(evaluation_records.__file__).resolve().parent
    dependencies.update({f"code/{path.name}": digest(path) for path in package.glob("*.py")})
    dependencies["code/run_evaluation.py"] = digest(
        package.parents[1] / "scripts/run_evaluation.py"
    )
    run = run_cases(retriever, suite)
    run.update(dependency_fingerprints=dependencies, dependency_snapshot_valid=True)
    workspace = {
        "root": tmp_path,
        "run": run,
        "record_path": processed / "phase-8-evaluation.after-fix.json",
        "suite_path": suite_path,
        "retriever": retriever,
        "source": source,
    }
    save_record(workspace)
    return workspace


def test_absent_historical_record_returns_none_without_inventing_counts(tmp_path):
    assert evaluation_records.load_development_record(tmp_path) is None


def test_source_current_record_projects_frozen_denominators_and_no_semantic_scores(
    recorded_workspace,
):
    record = evaluation_records.load_development_record(recorded_workspace["root"])
    summary = recorded_workspace["run"]["summary"]
    assert record["case_count"] == 2
    assert record["completed_count"] == summary["completed_count"]
    assert record["behavior_matched"] == summary["expected_behavior"]["matched"]
    assert record["behavior_eligible"] == 2
    assert record["spans_checked"] == summary["source_spans"]["checked"]
    assert record["spans_total"] > 0
    assert record["page_hits_1"] == summary["proposed_page_hit_at_1"]["matched"]
    assert record["page_hit_eligible"] == 1
    assert record["code_snapshot_current"] is True
    assert record["approved_gold_count"] == record["human_scored_count"] == 0
    assert all(value is None for value in record["semantic_metrics"].values())
    assert record["run_digest"] == recorded_workspace["run"]["run_digest"]


def test_no_excerpt_run_preserves_zero_denominators_as_not_applicable(recorded_workspace):
    run = recorded_workspace["run"]
    suite = deepcopy(run["suite_snapshot"])
    suite["cases"] = suite["cases"][1:]
    recorded_workspace["suite_path"].write_text(json.dumps(suite), encoding="utf-8")
    new_run = run_cases(recorded_workspace["retriever"], suite)
    new_run.update(
        dependency_snapshot_valid=True,
        dependency_fingerprints=deepcopy(run["dependency_fingerprints"]),
    )
    new_run["dependency_fingerprints"]["suite"] = digest(recorded_workspace["suite_path"])
    recorded_workspace["run"] = new_run
    save_record(recorded_workspace)
    record = evaluation_records.load_development_record(recorded_workspace["root"])
    assert record["spans_checked"] == record["spans_total"] == 0
    assert record["page_hit_eligible"] == 0
    assert record["behavior_eligible"] == 1
    assert all(value is None for value in record["semantic_metrics"].values())


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("case_count",), 40),
        (("completed_count",), 0),
        (("error_count",), 1),
        (("error_count",), False),
        (("expected_behavior", "matched"), 0),
        (("expected_behavior", "eligible"), 1),
        (("source_spans", "checked"), 99),
        (("source_spans", "case_errors"), 1),
        (("proposed_page_hit_at_1", "eligible"), 2),
        (("proposed_page_hit_at_5", "matched"), 0),
        (("approved_gold_count",), 1),
        (("human_scored_count",), 1),
        (("semantic_metrics", "answer_correctness"), 1.0),
    ],
)
def test_fabricated_summary_counts_or_scores_fail_even_after_digest_refresh(
    recorded_workspace, path, value
):
    target = recorded_workspace["run"]["summary"]
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    save_record(recorded_workspace)
    with pytest.raises(ValueError, match="summary"):
        evaluation_records.load_development_record(recorded_workspace["root"])


@pytest.mark.parametrize("field", ["engineering_behavior_match", "proposed_page_hit_at_1"])
def test_summary_and_row_cannot_jointly_claim_false_behavior_or_page_hits(
    recorded_workspace, field
):
    run = recorded_workspace["run"]
    run["case_results"][0][field] = False
    if field == "engineering_behavior_match":
        run["summary"]["expected_behavior"]["matched"] -= 1
    else:
        run["summary"]["proposed_page_hit_at_1"]["matched"] -= 1
    save_record(recorded_workspace)
    with pytest.raises(ValueError):
        evaluation_records.load_development_record(recorded_workspace["root"])


@pytest.mark.parametrize(
    "relative",
    [
        "data/evaluation_cases.json",
        "data/manifest.csv",
        "data/raw/neutral_record.pdf",
        f"data/processed/{DOC_ID}.pages.json",
        "data/processed/retrieval-index.json",
        "data/retrieval_policy.json",
        "data/kpi_candidates.json",
        "data/kpi_reviews.json",
    ],
)
def test_changed_source_data_invalidates_the_historical_projection(recorded_workspace, relative):
    path = recorded_workspace["root"] / relative
    path.write_bytes(path.read_bytes() + b"\nTEST ONLY changed data bytes\n")
    with pytest.raises(ValueError, match="stale"):
        evaluation_records.load_development_record(recorded_workspace["root"])


def test_missing_recorded_source_is_a_friendly_validation_error(recorded_workspace):
    recorded_workspace["source"].unlink()
    with pytest.raises(ValueError, match="dependency is missing"):
        evaluation_records.load_development_record(recorded_workspace["root"])


def test_code_changes_mark_a_record_historical_without_invalidating_its_data(recorded_workspace):
    run = recorded_workspace["run"]
    run["dependency_fingerprints"]["code/answer.py"] = "0" * 64
    save_record(recorded_workspace)
    record = evaluation_records.load_development_record(recorded_workspace["root"])
    assert record["code_snapshot_current"] is False
    assert record["case_count"] == 2 and record["behavior_eligible"] == 2


def test_plotting_configuration_changes_are_not_stale_source_data(recorded_workspace):
    path = recorded_workspace["root"] / "pyproject.toml"
    path.write_text("# TEST ONLY extra plotting dependency configuration\n", encoding="utf-8")
    record = evaluation_records.load_development_record(recorded_workspace["root"])
    assert record["code_snapshot_current"] is False
    assert record["case_count"] == 2


@pytest.mark.parametrize("key", ["../../../outside", "code/../../outside.py", "raw/UNKNOWN"])
def test_unknown_dependency_keys_cannot_select_arbitrary_files(recorded_workspace, key):
    recorded_workspace["run"]["dependency_fingerprints"][key] = "0" * 64
    save_record(recorded_workspace)
    with pytest.raises(ValueError, match="untrusted path|unknown dependency"):
        evaluation_records.load_development_record(recorded_workspace["root"])


def test_recorded_manifest_cannot_point_source_validation_outside_raw_directory(recorded_workspace):
    root = recorded_workspace["root"]
    manifest = root / "data/manifest.csv"
    text = manifest.read_text(encoding="utf-8").replace("neutral_record.pdf", "../../outside.pdf")
    manifest.write_text(text, encoding="utf-8")
    recorded_workspace["run"]["dependency_fingerprints"]["manifest"] = digest(manifest)
    save_record(recorded_workspace)
    with pytest.raises(ValueError, match="allowed directory"):
        evaluation_records.load_development_record(root)


def test_source_hash_cannot_be_silently_dropped_from_a_resigned_record(recorded_workspace):
    recorded_workspace["run"]["dependency_fingerprints"].pop(f"raw/{DOC_ID}")
    save_record(recorded_workspace)
    with pytest.raises(ValueError, match="missing registered source dependencies"):
        evaluation_records.load_development_record(recorded_workspace["root"])


def test_invalid_outer_digest_is_rejected(recorded_workspace):
    recorded_workspace["run"]["notice"] = "TEST ONLY changed frozen record notice"
    save_record(recorded_workspace, refresh_digest=False)
    with pytest.raises(ValueError, match="digest"):
        evaluation_records.load_development_record(recorded_workspace["root"])


def test_case_membership_remains_bound_to_the_frozen_suite(recorded_workspace):
    recorded_workspace["run"]["case_results"].pop()
    save_record(recorded_workspace)
    with pytest.raises(ValueError, match="exactly once"):
        evaluation_records.load_development_record(recorded_workspace["root"])


def test_malformed_record_json_becomes_a_friendly_value_error(recorded_workspace):
    recorded_workspace["record_path"].write_text("TEST ONLY not JSON", encoding="utf-8")
    with pytest.raises(ValueError, match="Historical development record validation failed"):
        evaluation_records.load_development_record(recorded_workspace["root"])
