"""CLI integration uses generated TEST ONLY counts, not real financial data."""

import csv
import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_comparison_readiness.py"


@pytest.fixture
def source_workspace(tmp_path: Path) -> dict:
    """Write actual neutral PDFs and truthful hashes for the real source loader."""
    raw_dir = tmp_path / "data/raw"
    raw_dir.mkdir(parents=True)
    rows, candidates = [], []
    for year, count in ((2024, "10"), (2025, "12")):
        source = raw_dir / f"neutral_count_{year}.pdf"
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text(
                (72, 72),
                "TEST ONLY - NOT A FINANCIAL REPORT\n"
                "Neutral archive counts; no company financial claims.\n"
                "Schema routing units: USD million\n"
                f"Neutral fixture count: {count}\n",
                fontsize=10,
            )
            document.save(source)
        with pymupdf.open(source) as document:
            text = document[0].get_text("text", sort=True)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        document_id = f"TEST-COUNT-{year}"
        url = f"https://example.invalid/neutral-count-{year}.pdf"
        row_start = text.index("Neutral fixture count:")
        row_end = text.find("\n", row_start)
        if row_end == -1:
            row_end = len(text)
        token_start = text.index(count, row_start, row_end)
        header = "Schema routing units: USD million"
        header_start = text.index(header)
        candidates.append(
            {
                "candidate_id": f"TEST-COUNT-{year}-VONB",
                "issuer": "Neutral Archive Fixture",
                "fiscal_year": year,
                "metric_code": "VONB",
                "metric_name": "Neutral count with schema-only metric routing",
                "value": count,
                "currency": "USD",
                "unit": "million",
                "period_start": f"{year}-01-01",
                "period_end": f"{year}-12-31",
                "period_basis": "Neutral annual schema fixture",
                "scope": "Neutral archive fixture only",
                "basis": "TEST ONLY schema routing, not a financial disclosure",
                "comparability_status": "needs_owner_review",
                "comparability_notes": "Neutral nonfinancial counts for CLI testing only.",
                "source_doc_id": document_id,
                "source_sha256": digest,
                "source_pdf_page": 1,
                "source_char_start": token_start,
                "source_char_end": token_start + len(count),
                "source_snippet": count,
                "source_row_start": row_start,
                "source_row_end": row_end,
                "source_row_snippet": text[row_start:row_end],
                "source_header": {
                    "char_start": header_start,
                    "char_end": header_start + len(header),
                    "text": header,
                },
                "source_url": url,
                "verified": False,
                "review_status": "pending_owner_review",
                "reviewer": None,
                "reviewed_at": None,
                "definition_pages": [],
            }
        )
        rows.append(
            {
                "doc_id": document_id,
                "issuer": "Neutral Archive Fixture",
                "ticker": "TEST",
                "fiscal_year": year,
                "period_end": f"{year}-12-31",
                "language": "en",
                "source_url": url,
                "date_downloaded": "",
                "sha256": digest,
                "local_filename": source.name,
                "notes": "Generated TEST ONLY neutral fixture; not downloaded company data.",
            }
        )
    with (tmp_path / "data/manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    candidate_path = tmp_path / "data/kpi_candidates.json"
    candidate_path.write_text(
        json.dumps({"schema_version": 1, "candidates": candidates}), encoding="utf-8"
    )
    return {"root": tmp_path, "records": candidates, "candidate_path": candidate_path}


def run_cli(workspace: dict, mode: str, destination: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(workspace["root"]), mode, str(destination)],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def initialize_packet(workspace: dict, *, decided: bool = False) -> Path:
    path = workspace["root"] / "data/kpi_reviews.json"
    initialized = run_cli(workspace, "--init-review", path)
    assert initialized.returncode == 0, initialized.stderr
    if decided:
        packet = json.loads(path.read_text(encoding="utf-8"))
        for reviews, decision in (
            (packet["candidate_reviews"], "confirmed"),
            (packet["comparison_reviews"], "comparable"),
        ):
            for review in reviews:
                review.update(
                    decision=decision,
                    reviewer="TEST ONLY neutral fixture reviewer",
                    reviewed_at="2026-10-30T12:30:00+08:00",
                    notes="Recorded test-only decision over nonfinancial counts.",
                    checks=dict.fromkeys(review["checks"], True),
                )
        path.write_text(json.dumps(packet), encoding="utf-8")
    return path


def test_cli_rechecks_real_fixture_sources_and_keeps_pending_until_explicit_test_reviews(
    source_workspace,
):
    root = source_workspace["root"]
    packet_path = initialize_packet(source_workspace)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert len(packet["candidate_reviews"]) == 2
    assert len(packet["comparison_reviews"]) == 1
    for review in packet["candidate_reviews"] + packet["comparison_reviews"]:
        assert review["decision"] == "pending"
        assert review["reviewer"] is None and review["reviewed_at"] is None
        assert all(value is None for value in review["checks"].values())

    pending_path = root / "pending-result.json"
    pending = run_cli(source_workspace, "--output", pending_path)
    assert pending.returncode == 0, pending.stderr
    pending_payload = json.loads(pending_path.read_text(encoding="utf-8"))
    assert pending_payload["fact_confirmed_count"] == 0
    assert pending_payload["calculated_count"] == 0
    blocked = pending_payload["results"][0]
    assert blocked["status"] == "needs_review" and blocked["reasons"]
    for key in ("absolute_change", "percentage_change", "percentage_point_change"):
        assert blocked[key] is None
    assert "previous_value" not in blocked and "current_value" not in blocked

    pending_bytes = pending_path.read_bytes()
    overwrite = run_cli(source_workspace, "--output", pending_path)
    assert overwrite.returncode == 2
    assert "already exists" in overwrite.stderr
    assert pending_path.read_bytes() == pending_bytes

    for reviews, decision in (
        (packet["candidate_reviews"], "confirmed"),
        (packet["comparison_reviews"], "comparable"),
    ):
        for review in reviews:
            review.update(
                decision=decision,
                reviewer="TEST ONLY neutral fixture reviewer",
                reviewed_at="2026-10-30T12:30:00+08:00",
                notes="Recorded test-only decision over nonfinancial counts.",
                checks=dict.fromkeys(review["checks"], True),
            )
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    calculated_path = root / "calculated-neutral-result.json"
    calculated = run_cli(source_workspace, "--output", calculated_path)
    assert calculated.returncode == 0, calculated.stderr
    payload = json.loads(calculated_path.read_text(encoding="utf-8"))
    assert payload["fact_confirmed_count"] == 2
    assert payload["calculated_count"] == 1
    result = payload["results"][0]
    assert result["status"] == "calculated"
    assert Decimal(result["absolute_change"]) == Decimal("2")
    assert Decimal(result["percentage_change"]) == Decimal("20")
    for key, record in zip(
        ("previous_source", "current_source"), source_workspace["records"], strict=True
    ):
        for field in (
            "candidate_id",
            "source_doc_id",
            "source_pdf_page",
            "source_sha256",
            "source_url",
        ):
            assert result[key][field] == record[field]
    unchanged = json.loads(source_workspace["candidate_path"].read_text(encoding="utf-8"))
    assert all(record["verified"] is False for record in unchanged["candidates"])
    assert not (root / "data/verified_kpis.csv").exists()


def test_cli_source_tamper_and_stale_metadata_fail_without_result_file(source_workspace):
    root = source_workspace["root"]
    initialize_packet(source_workspace, decided=True)
    source = root / "data/raw/neutral_count_2024.pdf"
    original_pdf = source.read_bytes()
    source.write_bytes(original_pdf + b"\nTEST ONLY changed bytes\n")
    failed_pdf_path = root / "must-not-exist-source.json"
    failed_pdf = run_cli(source_workspace, "--output", failed_pdf_path)
    assert failed_pdf.returncode == 2
    assert "hash mismatch" in failed_pdf.stderr
    assert not failed_pdf_path.exists()

    source.write_bytes(original_pdf)
    candidate_path = source_workspace["candidate_path"]
    records = json.loads(candidate_path.read_text(encoding="utf-8"))
    records["candidates"][0]["scope"] = "Changed neutral archive scope after review"
    candidate_path.write_text(json.dumps(records), encoding="utf-8")
    failed_digest_path = root / "must-not-exist-stale.json"
    failed_digest = run_cli(source_workspace, "--output", failed_digest_path)
    assert failed_digest.returncode == 2
    assert "Stale candidate review digest" in failed_digest.stderr
    assert not failed_digest_path.exists()
