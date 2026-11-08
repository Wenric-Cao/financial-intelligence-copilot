"""Evaluation CLI checks over actual neutral TEST ONLY PDFs, never real AIA data."""

import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

from financial_intelligence_copilot.indexing import build_index
from financial_intelligence_copilot.pdf_parser import DocumentMetadata, parse_pdf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts/run_evaluation.py"
DOC_ID = "TEST-2025-EN"
ARCHIVE_FACT = "The Archive Board oversees archive stewardship and approves the records framework."
RATING_FIELDS = {
    "answer_correctness",
    "citation_relevance",
    "numerical_correctness",
    "abstention_correctness",
}


def json_digest(payload: dict) -> str:
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@pytest.fixture
def evaluation_workspace(tmp_path: Path) -> dict:
    """Build a real local source/index chain for clearly labeled archive fixtures."""
    raw = tmp_path / "data/raw"
    processed = tmp_path / "data/processed"
    raw.mkdir(parents=True)
    processed.mkdir()
    source = raw / "neutral_archive_test_only.pdf"
    with pymupdf.open() as document:
        cover = document.new_page()
        cover.insert_text((72, 72), "TEST ONLY NEUTRAL FIXTURE - NOT A FINANCIAL REPORT")
        page = document.new_page()
        page.insert_text(
            (72, 72),
            "TEST ONLY - NO REAL COMPANY OR FINANCIAL CLAIMS\n\n"
            f"{ARCHIVE_FACT}\n"
            "The records framework preserves paper folders and reading room labels.\n",
            fontsize=9,
        )
        document.save(source)
    parsed = parse_pdf(source, DocumentMetadata(DOC_ID, "Neutral Archive Test Fixture", 2025))
    (processed / f"{DOC_ID}.pages.json").write_text(json.dumps(parsed.to_dict()), encoding="utf-8")
    source_url = "https://example.invalid/neutral-archive-test-only.pdf"
    row = {
        "doc_id": DOC_ID,
        "issuer": "Neutral Archive Test Fixture",
        "ticker": "TEST",
        "fiscal_year": 2025,
        "period_end": "2025-12-31",
        "language": "en",
        "source_url": source_url,
        "date_downloaded": "",
        "sha256": parsed.sha256,
        "local_filename": source.name,
        "notes": "Generated locally for testing; not downloaded and not real financial data.",
    }
    manifest = tmp_path / "data/manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    policy = {
        "schema_version": 1,
        "max_words": 180,
        "overlap_words": 30,
        "min_words": 8,
        "excluded_pdf_pages": {DOC_ID: {"1": "Explicit TEST ONLY fixture cover"}},
    }
    (tmp_path / "data/retrieval_policy.json").write_text(json.dumps(policy), encoding="utf-8")
    index = build_index(manifest, raw, processed, policy)
    (processed / "retrieval-index.json").write_text(json.dumps(index), encoding="utf-8")

    page_text = parsed.pages[1].text
    start = page_text.index(ARCHIVE_FACT)
    base = {
        "target_docs": [DOC_ID],
        "selected_doc_id": DOC_ID,
        "selected_fiscal_year": 2025,
        "review_status": "pending_owner_review",
        "reviewer": None,
        "reviewed_at": None,
        "review_notes": "TEST ONLY neutral development proposal; no approved gold answer.",
        "exposure": "development",
    }
    suite = {
        "schema_version": 1,
        "split": "development",
        "category_counts": {"simple_fact": 1, "boundary": 1},
        "cases": [
            {
                **base,
                "id": "neutral-archive-fact",
                "category": "simple_fact",
                "question": "Who approves the records framework?",
                "answerable": True,
                "candidate_answer": "The Archive Board.",
                "evidence": [
                    {
                        "doc_id": DOC_ID,
                        "fiscal_year": 2025,
                        "pdf_page": 2,
                        "source_sha256": parsed.sha256,
                        "char_start": start,
                        "char_end": start + len(ARCHIVE_FACT),
                        "quote": ARCHIVE_FACT,
                        "source_url": source_url,
                    }
                ],
                "expected_behavior": {"status": "extractive_evidence", "reason": None},
            },
            {
                **base,
                "id": "neutral-missing-marker",
                "category": "boundary",
                "question": "What is ZephyrQuartz?",
                "answerable": False,
                "candidate_answer": None,
                "evidence": [],
                "expected_behavior": {"status": "abstained", "reason": "no_matching_evidence"},
            },
        ],
    }
    suite_path = tmp_path / "data/evaluation_cases.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    return {
        "root": tmp_path,
        "source": source,
        "source_sha256": parsed.sha256,
        "page_text": page_text,
        "suite": suite,
        "suite_path": suite_path,
        "output": processed / "neutral-evaluation-run.json",
        "review_output": processed / "neutral-evaluation-review.json",
    }


def cli_arguments(workspace: dict) -> list[str]:
    return [
        "--root",
        str(workspace["root"]),
        "--output",
        str(workspace["output"]),
        "--review-output",
        str(workspace["review_output"]),
    ]


def run_cli(workspace: dict):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *cli_arguments(workspace)],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_runs_actual_neutral_pdf_chain_preserving_unscored_cases_and_refuses_overwrite(
    evaluation_workspace,
):
    workspace = evaluation_workspace
    completed = run_cli(workspace)
    assert completed.returncode == 0, completed.stderr
    run = json.loads(workspace["output"].read_text(encoding="utf-8"))
    review = json.loads(workspace["review_output"].read_text(encoding="utf-8"))
    assert run["suite_snapshot"] == workspace["suite"]
    assert run["suite_digest"] == json_digest(workspace["suite"])
    assert run["run_digest"] == json_digest(
        {key: value for key, value in run.items() if key != "run_digest"}
    )
    assert [row["case_id"] for row in run["case_results"]] == [
        case["id"] for case in workspace["suite"]["cases"]
    ]
    assert run["model_api_calls"] == 0
    assert run["provider_cost"] is None
    assert run["dependency_snapshot_valid"] is True
    assert run["environment"]["python"] and run["environment"]["PyMuPDF"]
    assert run["suite_source_validation_seconds"] >= 0
    assert run["startup_index_verification_seconds"] >= 0

    fingerprints = run["dependency_fingerprints"]
    assert {
        "suite",
        "manifest",
        "policy",
        "index",
        f"raw/{DOC_ID}",
        f"pages/{DOC_ID}",
        "code/evaluation.py",
        "code/run_evaluation.py",
    }.issubset(fingerprints)
    assert fingerprints[f"raw/{DOC_ID}"] == workspace["source_sha256"]
    assert fingerprints["suite"] == hashlib.sha256(workspace["suite_path"].read_bytes()).hexdigest()
    assert all(len(value) == 64 for value in fingerprints.values())

    summary = run["summary"]
    assert summary["case_count"] == summary["completed_count"] == 2
    assert summary["error_count"] == summary["diagnostic_retrieval_error_count"] == 0
    assert summary["approved_gold_count"] == summary["human_scored_count"] == 0
    assert summary["semantic_metrics"] == dict.fromkeys(RATING_FIELDS)
    assert summary["expected_behavior"] == {"matched": 2, "eligible": 2}
    assert summary["source_spans"]["case_errors"] == 0
    assert summary["source_spans"]["total"] >= 1
    assert summary["source_spans"]["checked"] == summary["source_spans"]["total"]

    fact, missing = run["case_results"]
    assert fact["response"]["status"] == "extractive_evidence"
    assert fact["retrieval_hits"]
    assert fact["proposed_evidence"] == workspace["suite"]["cases"][0]["evidence"]
    for excerpt in fact["response"]["excerpts"]:
        assert excerpt["doc_id"] == DOC_ID
        assert excerpt["pdf_page"] == 2
        assert excerpt["source_sha256"] == workspace["source_sha256"]
        assert (
            excerpt["quote"] == workspace["page_text"][excerpt["char_start"] : excerpt["char_end"]]
        )
    assert missing["response"]["status"] == "abstained"
    assert missing["response"]["excerpts"] == []
    assert missing["document_answerability_proposal"] is False
    assert missing["proposed_page_hit_at_1"] is None
    assert missing["proposed_page_hit_at_5"] is None
    for case, row in zip(workspace["suite"]["cases"], run["case_results"], strict=True):
        assert row["case_digest"] == json_digest(case)
        assert row["response_digest"] == json_digest(row["response"])
        assert row["error"] is None
        assert row["source_span_check"]["errors"] == []
        assert all(seconds >= 0 for seconds in row["latency"].values())

    assert review["run_id"] == run["run_id"]
    assert review["run_digest"] == run["run_digest"]
    assert review["suite_digest"] == run["suite_digest"]
    assert len(review["reviews"]) == 2
    for row, judgment in zip(run["case_results"], review["reviews"], strict=True):
        for field in ("case_id", "case_digest", "response_digest", "response"):
            assert judgment[field] == row[field]
        assert judgment["ratings"] == dict.fromkeys(RATING_FIELDS)
        assert judgment["reviewer"] is None and judgment["reviewed_at"] is None
        assert judgment["gold_review"] == {
            "status": "pending",
            "reviewer": None,
            "reviewed_at": None,
            "notes": "",
        }

    original_run = workspace["output"].read_bytes()
    original_review = workspace["review_output"].read_bytes()
    second = run_cli(workspace)
    assert second.returncode == 2
    assert "Output already exists" in second.stderr
    assert workspace["output"].read_bytes() == original_run
    assert workspace["review_output"].read_bytes() == original_review


@pytest.mark.parametrize("tamper", ["raw_pdf", "evidence_span"])
def test_cli_rejects_invalid_source_evidence_without_publishing_either_output(
    evaluation_workspace, tamper
):
    workspace = evaluation_workspace
    if tamper == "raw_pdf":
        with workspace["source"].open("ab") as handle:
            handle.write(b"\n% TEST ONLY changed source bytes\n")
    else:
        proposed = workspace["suite"]["cases"][0]["evidence"][0]
        proposed["char_start"] += 1
        proposed["char_end"] += 1
        workspace["suite_path"].write_text(json.dumps(workspace["suite"]), encoding="utf-8")
    completed = run_cli(workspace)
    assert completed.returncode == 2
    expected_error = "raw PDF hash mismatch" if tamper == "raw_pdf" else "actual PDF source span"
    assert expected_error in completed.stderr
    assert not workspace["output"].exists()
    assert not workspace["review_output"].exists()


def test_cli_does_not_publish_a_run_if_dependency_fingerprints_change(
    evaluation_workspace, monkeypatch, capsys
):
    """Exercise the CLI guard with real fixture execution and a changed snapshot."""
    spec = importlib.util.spec_from_file_location("neutral_evaluation_cli_test_module", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.dependency_fingerprints
    calls = []

    def changed_snapshot(root, suite):
        result = original(root, suite)
        calls.append(result)
        if len(calls) == 2:
            result["code/evaluation.py"] = "0" * 64
        return result

    monkeypatch.setattr(module, "dependency_fingerprints", changed_snapshot)
    with pytest.raises(SystemExit) as error:
        module.main(cli_arguments(evaluation_workspace))
    assert error.value.code == 2
    assert len(calls) == 2
    assert "dependencies changed during execution" in capsys.readouterr().err
    assert not evaluation_workspace["output"].exists()
    assert not evaluation_workspace["review_output"].exists()
