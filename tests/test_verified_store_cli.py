"""Exercise local store commands with labeled neutral PDFs and actual subprocesses."""

import json
import subprocess
import sys
from pathlib import Path

from financial_intelligence_copilot.kpi_reviews import make_review_packet

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_verified_store.py"


def run_cli(workspace, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(workspace["root"]), *map(str, args)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def record_fixture_reviews(workspace, decision):
    packet = make_review_packet(workspace["records"])
    if decision == "confirmed":
        for review in packet["candidate_reviews"]:
            review.update(
                decision="confirmed",
                reviewer="TEST ONLY neutral fixture reviewer",
                reviewed_at="2026-11-08T12:00:00+08:00",
                notes="Explicit fixture decision over nonfinancial counts only.",
                checks=dict.fromkeys(review["checks"], True),
            )
    path = workspace["root"] / "data/kpi_reviews.json"
    path.write_text(json.dumps(packet), encoding="utf-8")
    return path


def test_pending_export_and_check_preserve_input_files(verified_workspace):
    workspace = verified_workspace
    review_path = record_fixture_reviews(workspace, "pending")
    original_candidates = workspace["candidate_path"].read_bytes()
    original_reviews = review_path.read_bytes()
    output = workspace["root"] / "data/processed/pending-store.json"
    result = run_cli(workspace, "--output", output)
    assert result.returncode == 0, result.stderr
    assert "Exported 0/2" in result.stdout
    payload = json.loads(output.read_text())
    assert payload["records"] == [] and payload["verified_count"] == 0
    checked = run_cli(workspace, "--check", output)
    assert checked.returncode == 0, checked.stderr
    assert "Validated 0/2" in checked.stdout
    assert workspace["candidate_path"].read_bytes() == original_candidates
    assert review_path.read_bytes() == original_reviews


def test_fact_confirmation_export_does_not_approve_pairs_and_refuses_overwrite(verified_workspace):
    workspace = verified_workspace
    review_path = record_fixture_reviews(workspace, "confirmed")
    output = workspace["root"] / "confirmed-store.json"
    result = run_cli(workspace, "--output", output)
    assert result.returncode == 0, result.stderr
    assert "Exported 2/2" in result.stdout
    before = output.read_bytes()
    payload = json.loads(before)
    assert all(row["verified"] is True for row in payload["records"])
    assert all(row["comparability_status"] == "needs_owner_review" for row in payload["records"])
    packet = json.loads(review_path.read_text())
    assert all(row["decision"] == "pending" for row in packet["comparison_reviews"])
    repeated = run_cli(workspace, "--output", output)
    assert repeated.returncode == 2
    assert output.read_bytes() == before
    assert run_cli(workspace, "--check", output).returncode == 0


def test_revoked_review_rejects_saved_store_without_modification(verified_workspace):
    workspace = verified_workspace
    record_fixture_reviews(workspace, "confirmed")
    output = workspace["root"] / "former-confirmed-store.json"
    assert run_cli(workspace, "--output", output).returncode == 0
    before = output.read_bytes()
    record_fixture_reviews(workspace, "pending")
    result = run_cli(workspace, "--check", output)
    assert result.returncode == 2
    assert output.read_bytes() == before


def test_source_missing_fails_before_export_and_check(verified_workspace):
    workspace = verified_workspace
    output = workspace["root"] / "source-checked-store.json"
    assert run_cli(workspace, "--output", output).returncode == 0
    next((workspace["root"] / "data/raw").glob("*.pdf")).unlink()
    rejected = workspace["root"] / "must-not-exist.json"
    result = run_cli(workspace, "--output", rejected)
    assert result.returncode == 2
    assert not rejected.exists()
    assert run_cli(workspace, "--check", output).returncode == 2


def test_cli_requires_one_action(verified_workspace):
    workspace = verified_workspace
    assert run_cli(workspace).returncode == 2
    path = workspace["root"] / "unused.json"
    assert run_cli(workspace, "--output", path, "--check", path).returncode == 2
    assert not path.exists()
