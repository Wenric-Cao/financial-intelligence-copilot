"""Source-backed KPI review candidates, kept separate from verified financial data."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pymupdf

METRIC_UNITS = {
    "VONB": ("USD", "million"),
    "ANP": ("USD", "million"),
    "OPAT": ("USD", "million"),
    "UFSG": ("USD", "million"),
    "VONB_MARGIN": (None, "percent"),
}


def parse_reported_value(token: str, unit: str) -> Decimal:
    """Parse one reported token; missing/dash is never silently treated as zero."""
    if not isinstance(token, str) or unit not in {"million", "percent"}:
        raise ValueError("Unsupported reported value or unit")
    text = token.strip()
    if text.count("%") > 1:
        raise ValueError("Reported number contains multiple percent symbols")
    percent = text.endswith("%")
    if percent:
        text = text[:-1].strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
        if text.startswith(("-", "+")):
            raise ValueError("Ambiguous sign in reported value")
    if text.endswith("%"):
        percent = True
        text = text[:-1].strip()
    if percent != (unit == "percent"):
        raise ValueError("Reported percent symbol does not match the declared unit")
    if not re.fullmatch(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", text):
        raise ValueError("Missing or invalid reported number; no value was inferred")
    value = Decimal(text.replace(",", ""))
    return -value if negative else value


def _stored_value(value) -> Decimal:
    if not isinstance(value, str) or not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        raise ValueError("Candidate value must be a plain decimal string")
    return Decimal(value)


def _span(text: str, start, end, expected: str) -> None:
    if (
        type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= len(text)
        or not isinstance(expected, str)
        or text[start:end] != expected
    ):
        raise ValueError("Candidate source span does not match the original PDF text")


def _numeric_token_boundaries(text: str, start: int, end: int, token: str) -> None:
    """Reject a partial number even when it is an exact source substring.

    Check the stripped token's actual source edges, rather than allowing supplied
    surrounding whitespace to hide a decimal, sign, grouping mark, or percent.
    Spaces between separate table cells remain valid delimiters.
    """
    left = start + len(token) - len(token.lstrip())
    right = end - (len(token) - len(token.rstrip()))
    number_marks = ".,%+-()\N{MINUS SIGN}"
    for adjacent in (text[left - 1] if left else "", text[right] if right < len(text) else ""):
        if adjacent and (adjacent.isdecimal() or adjacent in number_marks):
            raise ValueError("Candidate source span must contain the complete numeric token")
    # Parenthesized negative values may have internal whitespace. Selecting only
    # their inner digits must not turn a negative reported value into a positive.
    if text[:left].rstrip().endswith("(") and text[right:].lstrip().startswith(")"):
        raise ValueError("Candidate source span omits the reported negative parentheses")


def load_candidates(root: Path) -> list[dict]:
    """Check decimal values and raw-PDF provenance, never approve a financial fact.

    Column interpretation, definitions, scope, tax basis, and comparability still
    require owner review. No promotion or growth calculation is performed here.
    """
    root = Path(root).resolve()
    path = root / "data/kpi_candidates.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or type(payload.get("schema_version")) is not int
        or payload["schema_version"] != 1
        or not isinstance(payload.get("candidates"), list)
    ):
        raise ValueError("Invalid KPI candidate dataset schema")
    with (root / "data/manifest.csv").open(newline="", encoding="utf-8") as handle:
        manifest = list(csv.DictReader(handle))
    sources = {item["doc_id"]: item for item in manifest}
    if len(sources) != len(manifest):
        raise ValueError("Duplicate source documents in manifest")

    documents, page_text = {}, {}

    def source_page(record: dict) -> tuple[str, dict]:
        document_id = record["source_doc_id"]
        if document_id not in sources:
            raise ValueError("Unknown candidate source document")
        metadata = sources[document_id]
        if document_id not in documents:
            raw_root = root / "data/raw"
            source = (raw_root / metadata["local_filename"]).resolve()
            if not source.is_relative_to(raw_root.resolve()):
                raise ValueError("Candidate source path leaves the raw-data directory")
            with source.open("rb") as handle:
                actual_hash = hashlib.file_digest(handle, "sha256").hexdigest()
            if actual_hash != metadata["sha256"]:
                raise ValueError("Candidate source PDF hash mismatch")
            try:
                document = pymupdf.open(source)
            except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
                raise ValueError("Cannot read the candidate source PDF") from exc
            documents[document_id] = document
            if not document.is_pdf or document.needs_pass:
                raise ValueError("Candidate source must be an unlocked PDF")
        document = documents[document_id]
        page = record["source_pdf_page"]
        if type(page) is not int or not 1 <= page <= document.page_count:
            raise ValueError("Candidate PDF page must be a valid physical integer page")
        if record["source_sha256"] != metadata["sha256"]:
            raise ValueError("Candidate source hash does not match its registered PDF")
        if record["source_url"] != metadata["source_url"]:
            raise ValueError("Candidate source URL does not match the manifest")
        key = (document_id, page)
        if key not in page_text:
            try:
                page_text[key] = document.load_page(page - 1).get_text("text", sort=True)
            except (RuntimeError, ValueError) as exc:
                raise ValueError("Cannot extract the candidate source page") from exc
        return page_text[key], metadata

    def checked_cell(record: dict, unit: str) -> dict:
        text, _ = source_page(record)
        _span(
            text, record["source_char_start"], record["source_char_end"], record["source_snippet"]
        )
        _span(
            text, record["source_row_start"], record["source_row_end"], record["source_row_snippet"]
        )
        if not (
            record["source_row_start"]
            <= record["source_char_start"]
            < record["source_char_end"]
            <= record["source_row_end"]
        ):
            raise ValueError("Candidate token must lie inside its cited table row")
        value = _stored_value(record["value"])
        if parse_reported_value(record["source_snippet"], unit) != value:
            raise ValueError("Candidate value differs from the reported source token")
        _numeric_token_boundaries(
            text, record["source_char_start"], record["source_char_end"], record["source_snippet"]
        )
        if record.get("source_header"):
            header = record["source_header"]
            _span(text, header["char_start"], header["char_end"], header["text"])
        return {**record, "value": value}

    candidates, ids, metric_years = [], set(), set()
    try:
        for record in payload["candidates"]:
            if not isinstance(record, dict):
                raise ValueError("Each candidate must be a structured record")
            if (
                record.get("verified") is not False
                or record.get("review_status") != "pending_owner_review"
                or record.get("reviewer") is not None
                or record.get("reviewed_at") is not None
                or record.get("comparability_status") != "needs_owner_review"
            ):
                raise ValueError(
                    "Candidate records must remain unverified and pending owner review"
                )
            year = record["fiscal_year"]
            if type(year) is not int:
                raise ValueError("Candidate fiscal year must be an integer")
            code = record["metric_code"]
            if (
                code not in METRIC_UNITS
                or (record["currency"], record["unit"]) != METRIC_UNITS[code]
            ):
                raise ValueError("Candidate metric unit or currency is inconsistent")
            for name in (
                "candidate_id",
                "issuer",
                "metric_name",
                "scope",
                "basis",
                "comparability_notes",
            ):
                if not isinstance(record[name], str) or not record[name].strip():
                    raise ValueError(f"Candidate {name} must be non-empty")
            key = (record["issuer"], year, code)
            if record["candidate_id"] in ids or key in metric_years:
                raise ValueError("Duplicate candidate ID or metric-year")
            ids.add(record["candidate_id"])
            metric_years.add(key)
            start, end = (
                date.fromisoformat(record["period_start"]),
                date.fromisoformat(record["period_end"]),
            )
            if start > end or end.year != year:
                raise ValueError("Candidate period is inconsistent with its fiscal year")
            checked = checked_cell(record, record["unit"])
            source_metadata = sources[record["source_doc_id"]]
            if (source_metadata["issuer"], int(source_metadata["fiscal_year"])) != (
                record["issuer"],
                year,
            ):
                raise ValueError("Candidate issuer/year differs from its source report")
            references = record.get("definition_pages", [])
            if not isinstance(references, list):
                raise ValueError("Definition references must be a list")
            for reference in references:
                if not isinstance(reference, dict):
                    raise ValueError("Each definition reference must be a structured record")
                page = reference.get("pdf_page")
                if (
                    type(page) is not int
                    or not 1 <= page <= documents[record["source_doc_id"]].page_count
                    or not isinstance(reference.get("topic"), str)
                    or not reference["topic"].strip()
                ):
                    raise ValueError(
                        "Definition references need a valid PDF page and non-empty topic"
                    )
            prior = record.get("prior_year_comparative")
            if prior:
                if (
                    type(prior["reported_fiscal_year"]) is not int
                    or prior["reported_fiscal_year"] != year - 1
                    or prior["source_doc_id"] != record["source_doc_id"]
                ):
                    raise ValueError(
                        "Prior comparative must identify its period and current source report"
                    )
                checked["prior_year_comparative"] = checked_cell(prior, record["unit"])
            candidates.append(checked)
        originals = {
            (item["issuer"], item["fiscal_year"], item["metric_code"]): item for item in candidates
        }
        for item in candidates:
            if prior := item.get("prior_year_comparative"):
                previous = originals.get(
                    (item["issuer"], prior["reported_fiscal_year"], item["metric_code"])
                )
                item["comparative_matches_original"] = (
                    previous is not None and prior["value"] == previous["value"]
                )
    except (KeyError, TypeError) as exc:
        raise ValueError("KPI candidate record is missing or has invalid fields") from exc
    finally:
        for document in documents.values():
            document.close()
    return sorted(candidates, key=lambda item: (item["fiscal_year"], item["metric_code"]))


def candidate_csv(records: list[dict]) -> str:
    """Export a review sheet; never convert a candidate into a verified record."""
    fields = [
        "candidate_id",
        "issuer",
        "fiscal_year",
        "metric_code",
        "metric_name",
        "value",
        "currency",
        "unit",
        "period_start",
        "period_end",
        "scope",
        "basis",
        "comparability_status",
        "comparability_notes",
        "source_doc_id",
        "source_pdf_page",
        "source_snippet",
        "source_char_start",
        "source_char_end",
        "source_sha256",
        "source_url",
        "verified",
        "review_status",
        "reviewer",
        "reviewed_at",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for item in records:
        row = {key: item.get(key) for key in fields}
        if row["verified"] is not False or row["review_status"] != "pending_owner_review":
            raise ValueError("Only unverified review candidates may be exported")
        for key, value in row.items():
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) and key != "value":
                row[key] = "'" + value
        row.update(verified="false", reviewer="", reviewed_at="")
        writer.writerow(row)
    return buffer.getvalue()
