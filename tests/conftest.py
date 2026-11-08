"""Shared neutral PDF fixtures for source-bound reviewed-store tests."""

import csv
import hashlib
import json
from pathlib import Path

import pymupdf
import pytest


@pytest.fixture
def verified_workspace(tmp_path: Path) -> dict:
    """Use actual neutral PDFs; these counts are never company financial claims."""
    raw_dir = tmp_path / "data/raw"
    raw_dir.mkdir(parents=True)
    rows, candidates = [], []
    for year, count in ((2024, "10.1250"), (2025, "12.3750")):
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
                "comparability_notes": "Neutral nonfinancial counts for persistence testing only.",
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
