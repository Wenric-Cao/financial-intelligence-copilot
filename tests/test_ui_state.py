"""Workspace state safety using neutral byte fixtures, not financial reports."""

import csv
import json
import os
from pathlib import Path

import pytest

from financial_intelligence_copilot.ui_state import (
    engineering_record,
    official_pdf_link,
    read_documents,
    workspace_fingerprint,
)


@pytest.fixture
def workspace(tmp_path: Path):
    raw, processed = tmp_path / "data/raw", tmp_path / "data/processed"
    raw.mkdir(parents=True)
    processed.mkdir()
    fields = ["doc_id", "issuer", "fiscal_year", "language", "source_url", "local_filename"]
    rows = [
        dict(
            zip(
                fields,
                [
                    f"AIA-{year}-EN",
                    "AIA Group Limited",
                    str(year),
                    "en",
                    "https://example.invalid/neutral-fixture.pdf",
                    f"neutral-{year}.pdf",
                ],
                strict=True,
            )
        )
        for year in (2024, 2025)
    ]
    with (tmp_path / "data/manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        (raw / row["local_filename"]).write_bytes(b"NEUTRAL FINGERPRINT FIXTURE ONLY")
        (processed / f"{row['doc_id']}.pages.json").write_text("neutral page-byte fixture")
    (processed / "retrieval-index.json").write_text("neutral index-byte fixture")
    (tmp_path / "data/retrieval_policy.json").write_text("neutral policy-byte fixture")
    return tmp_path


def test_actual_bytes_invalidate_revision_even_with_same_size_and_timestamp(workspace):
    documents = read_documents(workspace)
    before = workspace_fingerprint(workspace, documents)
    target = workspace / "data/raw/neutral-2025.pdf"
    original_stat = target.stat()
    data = target.read_bytes()
    target.write_bytes(b"X" + data[1:])
    os.utime(target, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    assert target.stat().st_size == original_stat.st_size
    assert workspace_fingerprint(workspace, documents) != before


def test_missing_local_file_fails_instead_of_reusing_a_revision(workspace):
    documents = read_documents(workspace)
    (workspace / "data/processed/retrieval-index.json").unlink()
    with pytest.raises(FileNotFoundError, match="Missing local data file"):
        workspace_fingerprint(workspace, documents)


def test_optional_run_record_does_not_invent_scores(workspace):
    assert engineering_record(workspace) is None
    record = workspace / "data/processed/phase-4-checks.reviewed.json"
    record.write_text(json.dumps({"source_probe_count": "unverified"}))
    with pytest.raises(ValueError, match="invalid count"):
        engineering_record(workspace)


def test_source_links_preserve_resource_but_use_physical_page_fragment():
    assert official_pdf_link("https://example.invalid/report.pdf?lang=en#old", 64) == (
        "https://example.invalid/report.pdf?lang=en#page=64"
    )
    for url in ("javascript:alert(1)", "https://username:password@example.invalid/report.pdf"):
        with pytest.raises(ValueError, match="HTTPS"):
            official_pdf_link(url, 1)
    with pytest.raises(ValueError, match="positive"):
        official_pdf_link("https://example.invalid/report.pdf", True)


def test_raw_symlink_cannot_expand_workspace_file_access(workspace, tmp_path):
    source = workspace / "data/raw/neutral-2025.pdf"
    source.unlink()
    source.symlink_to(workspace.parent / "outside-report.pdf")
    with pytest.raises(ValueError, match="outside"):
        read_documents(workspace)


def test_duplicate_fiscal_year_inventory_is_rejected(workspace):
    manifest = workspace / "data/manifest.csv"
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows([rows[0], rows[0]])
    with pytest.raises(ValueError, match="one report for each"):
        read_documents(workspace)


@pytest.mark.parametrize(
    "relative",
    [
        "data/kpi_reviews.json",
        "data/evaluation_cases.json",
        "data/processed/phase-8-evaluation.after-fix.json",
        "pyproject.toml",
    ],
)
def test_review_record_add_edit_and_removal_invalidate_revision(workspace, relative):
    documents = read_documents(workspace)
    absent = workspace_fingerprint(workspace, documents)
    target = workspace / relative
    target.write_text("initial", encoding="utf-8")
    original_stat = target.stat()
    added = workspace_fingerprint(workspace, documents)
    assert added != absent
    target.write_text("changed", encoding="utf-8")
    os.utime(target, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    assert target.stat().st_size == original_stat.st_size
    assert workspace_fingerprint(workspace, documents) != added
    target.unlink()
    assert workspace_fingerprint(workspace, documents) == absent
