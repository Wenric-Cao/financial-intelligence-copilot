"""Local workspace validation and byte fingerprints for UI cache invalidation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def read_documents(root: Path) -> list[dict]:
    """Read the fixed AIA MVP inventory, without claiming source or KPI verification."""
    with (root / "data/manifest.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"doc_id", "issuer", "fiscal_year", "language", "source_url", "local_filename"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("The source manifest is missing required fields.")
        documents = list(reader)
    if len(documents) != 2:
        raise ValueError("Register both AIA FY2024 and FY2025 reports in the source manifest.")
    for item in documents:
        year = int(item["fiscal_year"])
        if (
            year not in (2024, 2025)
            or item["doc_id"] != f"AIA-{year}-EN"
            or item["issuer"] != "AIA Group Limited"
            or item["language"] != "en"
        ):
            raise ValueError("The current interface supports AIA FY2024/FY2025 English reports.")
        item["fiscal_year"] = year
        official_pdf_link(item["source_url"], 1)
        source = (root / "data/raw" / item["local_filename"]).resolve()
        if not item["local_filename"] or not source.is_relative_to((root / "data/raw").resolve()):
            raise ValueError("A source filename points outside the local report directory.")
    if {item["fiscal_year"] for item in documents} != {2024, 2025}:
        raise ValueError("Source records must contain one report for each fiscal year.")
    return sorted(documents, key=lambda item: item["fiscal_year"], reverse=True)


def workspace_fingerprint(root: Path, documents: list[dict]) -> str:
    """Hash actual bytes on each UI rerun, including changes with unchanged timestamps."""
    paths = [
        root / "data/manifest.csv",
        root / "data/retrieval_policy.json",
        root / "data/processed/retrieval-index.json",
    ]
    for relative in (
        "data/kpi_candidates.json",
        "data/kpi_reviews.json",
        "data/evaluation_cases.json",
        "data/processed/phase-8-evaluation.after-fix.json",
        "pyproject.toml",
    ):
        optional = root / relative
        if optional.exists():
            paths.append(optional)
    for item in documents:
        paths.extend(
            [
                root / "data/raw" / item["local_filename"],
                root / "data/processed" / f"{item['doc_id']}.pages.json",
            ]
        )
    fingerprint = hashlib.sha256()
    for path in sorted(paths):
        resolved = path.resolve()
        if not resolved.is_relative_to(root.resolve()):
            raise ValueError("A local data path points outside the project workspace.")
        if not path.is_file():
            raise FileNotFoundError(f"Missing local data file: {path.relative_to(root)}")
        fingerprint.update(str(path.relative_to(root)).encode("utf-8"))
        with path.open("rb") as handle:
            fingerprint.update(hashlib.file_digest(handle, "sha256").digest())
    return fingerprint.hexdigest()


def official_pdf_link(url: str, pdf_page: int) -> str:
    """Link to the original official resource, never serve a local report copy."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Source links must use HTTPS and contain no credentials.")
    if type(pdf_page) is not int or pdf_page < 1:
        raise ValueError("PDF page must be a positive physical page number.")
    return urlunsplit(parsed._replace(fragment=f"page={pdf_page}"))


def engineering_record(root: Path) -> dict | None:
    """Read an optional recorded development run; never invent missing scores."""
    path = root / "data/processed/phase-4-checks.reviewed.json"
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    for key in (
        "source_probe_count",
        "boundary_probe_count",
        "boundary_behaviors_matched",
        "exact_page_spans_checked",
    ):
        if type(record.get(key)) is not int or record[key] < 0:
            raise ValueError("The local development record has invalid count fields.")
    return record
