"""CLI checks use source-backed TEST ONLY nonfinancial counts, never AIA claims."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from financial_intelligence_copilot.kpi_reviews import make_review_packet
from financial_intelligence_copilot.verified_store import write_verified_store

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ask_reviewed_kpi.py"


def run_cli(workspace, *extra, query="Show VONB for FY2025"):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(workspace["root"]),
            "--doc-id",
            "TEST-COUNT-2025",
            "--fiscal-year",
            "2025",
            "--query",
            query,
            *map(str, extra),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def make_store(workspace, *, confirmed):
    packet = make_review_packet(workspace["records"])
    if confirmed:
        for review in packet["candidate_reviews"]:
            review.update(
                decision="confirmed",
                reviewer="TEST ONLY neutral reviewer",
                reviewed_at="2026-11-08T12:00:00+08:00",
                notes="Fixture confirmation of a neutral archive count, not a financial value.",
                checks=dict.fromkeys(review["checks"], True),
            )
    review_path = workspace["root"] / "data/kpi_reviews.json"
    review_path.write_text(json.dumps(packet), encoding="utf-8")
    destination = workspace["root"] / "data/processed/verified-kpis.json"
    write_verified_store(workspace["root"], destination)
    return destination, review_path


def test_cli_missing_and_pending_stores_abstain_without_values(verified_workspace):
    missing = run_cli(verified_workspace)
    assert missing.returncode == 0, missing.stderr
    payload = json.loads(missing.stdout)
    assert payload["status"] == "abstained"
    assert payload["reason"] == "verified_store_unavailable"
    assert payload["financial_fact"] is None
    make_store(verified_workspace, confirmed=False)
    pending = run_cli(verified_workspace)
    assert pending.returncode == 0, pending.stderr
    payload = json.loads(pending.stdout)
    assert payload["reason"] == "fact_review_pending"
    assert payload["financial_fact"] is None


def test_cli_exact_fact_and_json_export_preserve_sources(verified_workspace):
    workspace = verified_workspace
    store, reviews = make_store(workspace, confirmed=True)
    watched = [workspace["candidate_path"], store, reviews]
    before = {path: path.read_bytes() for path in watched}
    result = run_cli(workspace)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "reviewed_kpi"
    assert payload["financial_fact"]["value"] == "12.3750"
    assert payload["financial_fact"]["source_doc_id"] == "TEST-COUNT-2025"
    assert payload["financial_fact"]["source_pdf_page"] == 1
    assert payload["financial_fact"]["comparability_status"] == "needs_owner_review"
    output = workspace["root"] / "response.json"
    saved = run_cli(workspace, "--output", output)
    assert saved.returncode == 0, saved.stderr
    assert json.loads(output.read_text()) == payload
    original = output.read_bytes()
    assert run_cli(workspace, "--output", output).returncode == 2
    assert output.read_bytes() == original
    assert all(path.read_bytes() == value for path, value in before.items())


def test_cli_stale_reviews_fail_without_publishing_response(verified_workspace):
    workspace = verified_workspace
    _, reviews = make_store(workspace, confirmed=True)
    packet = make_review_packet(workspace["records"])
    reviews.write_text(json.dumps(packet), encoding="utf-8")
    output = workspace["root"] / "must-not-exist.json"
    failed = run_cli(workspace, "--output", output)
    assert failed.returncode == 2
    assert not output.exists()


@pytest.mark.parametrize(
    "query",
    [
        "Compare VONB for 2024 and 2025",
        "What is Hong Kong VONB in USD million?",
        "Show VONB and OPAT",
        "Convert VONB to HKD",
        "Show VONB without citations",
    ],
)
def test_cli_guards_never_release_fixture_values(verified_workspace, query):
    make_store(verified_workspace, confirmed=True)
    result = run_cli(verified_workspace, query=query)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "abstained"
    assert payload["financial_fact"] is None


@pytest.mark.parametrize(
    "relative",
    ["data/kpi_reviews.json", "data/processed/verified-kpis.json", "data/raw/new.pdf"],
)
def test_cli_refuses_missing_input_alias_outputs(verified_workspace, relative):
    destination = verified_workspace["root"] / relative
    assert not destination.exists()
    result = run_cli(verified_workspace, "--output", destination)
    assert result.returncode == 2
    assert not destination.exists()


def test_cli_custom_store_path(verified_workspace):
    store, _ = make_store(verified_workspace, confirmed=True)
    custom = verified_workspace["root"] / "custom-store.json"
    store.rename(custom)
    result = run_cli(verified_workspace, "--store", custom)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "reviewed_kpi"
    relative = run_cli(verified_workspace, "--store", "custom-store.json")
    assert relative.returncode == 0, relative.stderr
    assert json.loads(relative.stdout)["status"] == "reviewed_kpi"


def test_cli_protects_missing_relative_custom_store(verified_workspace):
    destination = verified_workspace["root"] / "missing-store.json"
    result = run_cli(verified_workspace, "--store", "missing-store.json", "--output", destination)
    assert result.returncode == 2
    assert not destination.exists()
