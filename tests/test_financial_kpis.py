"""KPI-schema tests use neutral, generated samples, never real financial amounts."""

import csv
import io
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest

from financial_intelligence_copilot.financial_kpis import (
    candidate_csv,
    load_candidates,
    parse_reported_value,
)
from financial_intelligence_copilot.pdf_parser import DocumentMetadata, parse_pdf

ISSUER = "Neutral Schema Fixture"


def source_fields(parsed, year: int, row_prefix: str, token: str) -> dict:
    """Locate a test marker within actual native PDF text and its complete row."""
    text = parsed.pages[0].text
    row = next(line for line in text.splitlines() if line.startswith(row_prefix))
    row_start = text.index(row)
    start = text.index(token, row_start, row_start + len(row))
    return {
        "source_doc_id": f"TEST-{year}-EN",
        "source_sha256": parsed.sha256,
        "source_pdf_page": 1,
        "source_char_start": start,
        "source_char_end": start + len(token),
        "source_snippet": token,
        "source_row_start": row_start,
        "source_row_end": row_start + len(row),
        "source_row_snippet": row,
        "source_url": f"https://example.invalid/neutral-schema-{year}.pdf",
    }


def candidate(metric: str, year: int, value: str, source: dict) -> dict:
    percent = metric == "VONB_MARGIN"
    return {
        "candidate_id": f"neutral-{year}-{metric.lower()}",
        "issuer": ISSUER,
        "fiscal_year": year,
        "metric_code": metric,
        "metric_name": "Neutral percentage schema sample" if percent else "Neutral amount sample",
        "value": value,
        "currency": None if percent else "USD",
        "unit": "percent" if percent else "million",
        "period_start": f"{year}-01-01",
        "period_end": f"{year}-12-31",
        "scope": "Neutral schema fixture only",
        "basis": "Synthetic validation sample, not a real company disclosure",
        "comparability_status": "needs_owner_review",
        "comparability_notes": "A reviewer must assess real definitions before any calculation.",
        **source,
        "verified": False,
        "review_status": "pending_owner_review",
        "reviewer": None,
        "reviewed_at": None,
        "definition_pages": [],
    }


def save_candidates(workspace: dict) -> None:
    (workspace["root"] / "data/kpi_candidates.json").write_text(
        json.dumps({"schema_version": 1, "candidates": workspace["records"]}), encoding="utf-8"
    )


@pytest.fixture
def candidate_workspace(tmp_path: Path) -> dict:
    """Generate labeled nonfinancial PDFs and truthful fixture-file provenance."""
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    manifest_rows, parsed_documents = [], {}
    for year, amount, percentage in ((2024, "1,234", "12.5%"), (2025, "2,345", "15.0%")):
        source = raw / f"neutral_schema_{year}.pdf"
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text(
                (72, 72),
                "TEST FIXTURE ONLY - NOT A FINANCIAL REPORT\n"
                "Neutral schema units: USD million / percent\n"
                f"Neutral amount marker: {amount} | prior marker: 1,234\n"
                f"Neutral percentage marker: {percentage}\n"
                "Neutral alternate prior marker: 1,111\n",
                fontsize=10,
            )
            document.save(source)
        parsed = parse_pdf(source, DocumentMetadata(f"TEST-{year}-EN", ISSUER, year))
        parsed_documents[year] = parsed
        manifest_rows.append(
            {
                "doc_id": f"TEST-{year}-EN",
                "issuer": ISSUER,
                "ticker": "TEST",
                "fiscal_year": year,
                "period_end": f"{year}-12-31",
                "language": "en",
                "source_url": f"https://example.invalid/neutral-schema-{year}.pdf",
                "date_downloaded": "",
                "sha256": parsed.sha256,
                "local_filename": source.name,
                "notes": "Generated neutral schema fixture. No real financial information.",
            }
        )
    with (tmp_path / "data/manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)
    records = [
        candidate(
            "VONB",
            2024,
            "1234",
            source_fields(parsed_documents[2024], 2024, "Neutral amount marker:", "1,234"),
        ),
        candidate(
            "VONB_MARGIN",
            2024,
            "12.5",
            source_fields(parsed_documents[2024], 2024, "Neutral percentage marker:", "12.5%"),
        ),
        candidate(
            "VONB",
            2025,
            "2345",
            source_fields(parsed_documents[2025], 2025, "Neutral amount marker:", "2,345"),
        ),
    ]
    records[2]["prior_year_comparative"] = {
        **source_fields(parsed_documents[2025], 2025, "Neutral amount marker:", "1,234"),
        "reported_fiscal_year": 2024,
        "value": "1234",
    }
    text = parsed_documents[2024].pages[0].text
    header = "Neutral schema units: USD million / percent"
    records[0]["source_header"] = {
        "char_start": text.index(header),
        "char_end": text.index(header) + len(header),
        "text": header,
    }
    workspace = {
        "root": tmp_path,
        "records": records,
        "alternate_prior": source_fields(
            parsed_documents[2025], 2025, "Neutral alternate prior marker:", "1,111"
        ),
    }
    save_candidates(workspace)
    return workspace


def test_missing_candidate_file_returns_no_candidates(tmp_path):
    assert load_candidates(tmp_path) == []


def test_valid_candidates_keep_decimal_values_pending_review_and_exact_sources(candidate_workspace):
    records = load_candidates(candidate_workspace["root"])

    assert len(records) == 3
    assert records[0]["value"] == Decimal("1234")
    assert records[1]["value"] == Decimal("12.5")
    assert records[1]["unit"] == "percent" and records[1]["currency"] is None
    for record in records:
        assert isinstance(record["value"], Decimal)
        assert record["verified"] is False
        assert record["review_status"] == "pending_owner_review"
        assert record["comparability_status"] == "needs_owner_review"
        assert record["reviewer"] is None and record["reviewed_at"] is None
        assert record["source_row_start"] <= record["source_char_start"]
        assert record["source_char_end"] <= record["source_row_end"]
        start = record["source_char_start"] - record["source_row_start"]
        end = record["source_char_end"] - record["source_row_start"]
        assert record["source_row_snippet"][start:end] == record["source_snippet"]


def test_grouped_negative_and_percent_tokens_are_parsed_without_float_rounding():
    assert parse_reported_value("1,234.50", "million") == Decimal("1234.50")
    assert parse_reported_value("-1,234.50", "million") == Decimal("-1234.50")
    assert parse_reported_value("+1,234.50", "million") == Decimal("1234.50")
    assert parse_reported_value("(1,234.50)", "million") == Decimal("-1234.50")
    assert parse_reported_value("  ( 1,234.50 )  ", "million") == Decimal("-1234.50")
    assert parse_reported_value("12.5%", "percent") == Decimal("12.5")


@pytest.mark.parametrize("token", ["-", "–", "", "n/a", "NaN", "Infinity", "1,23"])
def test_missing_nonfinite_or_malformed_tokens_do_not_turn_into_numbers(token):
    with pytest.raises(ValueError):
        parse_reported_value(token, "million")


def test_percentage_sign_is_required_and_cannot_be_used_for_a_monetary_token():
    with pytest.raises(ValueError):
        parse_reported_value("12.5", "percent")
    with pytest.raises(ValueError):
        parse_reported_value("12.5%", "million")
    with pytest.raises(ValueError):
        parse_reported_value("(12.5%)%", "percent")


def test_candidate_value_cannot_disagree_with_the_source_token(candidate_workspace):
    candidate_workspace["records"][0]["value"] = "1235"
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


@pytest.mark.parametrize("token", ["234", "1"])
def test_partial_monetary_token_cannot_be_promoted_to_a_different_number(
    candidate_workspace, token
):
    record = candidate_workspace["records"][0]
    start = record["source_char_start"] + record["source_snippet"].index(token)
    record.update(
        value=token,
        source_snippet=token,
        source_char_start=start,
        source_char_end=start + len(token),
    )
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError, match="complete numeric token"):
        load_candidates(candidate_workspace["root"])


@pytest.mark.parametrize("token", ["2.5%", "5%"])
def test_partial_percent_token_cannot_be_promoted_to_a_different_percentage(
    candidate_workspace, token
):
    record = candidate_workspace["records"][1]
    start = record["source_char_start"] + record["source_snippet"].index(token)
    record.update(
        value=token[:-1],
        source_snippet=token,
        source_char_start=start,
        source_char_end=start + len(token),
    )
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError, match="complete numeric token"):
        load_candidates(candidate_workspace["root"])


def test_numeric_boundary_check_uses_stripped_token_edges(candidate_workspace):
    record = candidate_workspace["records"][0]
    # Include following whitespace so a raw end-character check alone would
    # overlook that the start still sits inside the grouped original token.
    record.update(
        value="234",
        source_snippet="234 ",
        source_char_start=record["source_char_start"] + 2,
        source_char_end=record["source_char_end"] + 1,
    )
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError, match="complete numeric token"):
        load_candidates(candidate_workspace["root"])


def test_changed_pdf_bytes_are_rejected_even_if_pdf_still_opens(candidate_workspace):
    source = candidate_workspace["root"] / "data/raw/neutral_schema_2024.pdf"
    with source.open("ab") as handle:
        handle.write(b"\n% changed neutral fixture bytes\n")

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


@pytest.mark.parametrize("field", ["source_sha256", "source_snippet", "source_row_snippet"])
def test_forged_source_identity_or_text_is_rejected(candidate_workspace, field):
    wrong = "f" * 64 if field == "source_sha256" else "Altered neutral fixture content"
    candidate_workspace["records"][0][field] = wrong
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


def test_source_token_must_be_inside_the_claimed_row(candidate_workspace):
    record, unrelated_row = candidate_workspace["records"][:2]
    for field in ("source_row_start", "source_row_end", "source_row_snippet"):
        record[field] = unrelated_row[field]
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("source_doc_id", "UNKNOWN-NEUTRAL-DOCUMENT"),
        ("fiscal_year", 2025),
        ("issuer", "Another Neutral Fixture"),
        ("source_url", "https://example.invalid/unrelated-neutral-source.pdf"),
    ],
)
def test_candidate_cannot_borrow_another_document_year_or_source(
    candidate_workspace, field, wrong_value
):
    candidate_workspace["records"][0][field] = wrong_value
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [("currency", "HKD"), ("currency", None), ("unit", "billion")],
)
def test_monetary_metric_rejects_incompatible_currency_or_unit(
    candidate_workspace, field, wrong_value
):
    candidate_workspace["records"][0][field] = wrong_value
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


def test_percentage_metric_cannot_claim_a_currency(candidate_workspace):
    candidate_workspace["records"][1]["currency"] = "USD"
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("verified", True),
        ("review_status", "approved"),
        ("reviewer", "A fictional reviewer"),
        ("reviewed_at", "2024-01-01T00:00:00Z"),
        ("comparability_status", "comparable"),
    ],
)
def test_candidate_loader_cannot_forge_approval_or_comparability(
    candidate_workspace, field, wrong_value
):
    candidate_workspace["records"][0][field] = wrong_value
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


@pytest.mark.parametrize("field", ["source_pdf_page", "source_char_start", "source_row_end"])
def test_float_or_boolean_source_coordinates_are_not_accepted_as_integers(
    candidate_workspace, field
):
    record = candidate_workspace["records"][0]
    record[field] = True if field == "source_pdf_page" else float(record[field])
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


def test_page_beyond_the_pdf_is_rejected(candidate_workspace):
    candidate_workspace["records"][0]["source_pdf_page"] = 2
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


def test_duplicate_metric_year_is_rejected_even_with_a_different_candidate_id(candidate_workspace):
    duplicate = deepcopy(candidate_workspace["records"][0])
    duplicate["candidate_id"] = "different-neutral-id"
    candidate_workspace["records"].append(duplicate)
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


def test_optional_table_header_must_match_native_source_text(candidate_workspace):
    candidate_workspace["records"][0]["source_header"]["text"] = "Changed neutral header"
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


@pytest.mark.parametrize(
    "references",
    [
        None,
        {"pdf_page": 1, "topic": "A mapping instead of a list"},
        ["An unstructured reference"],
        [{"pdf_page": 1}],
        [{"pdf_page": 1, "topic": " \n\t "}],
        [{"pdf_page": 1, "topic": 42}],
    ],
)
def test_malformed_definition_references_are_rejected_before_ui_rendering(
    candidate_workspace, references
):
    candidate_workspace["records"][0]["definition_pages"] = references
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError, match="reference"):
        load_candidates(candidate_workspace["root"])


def test_well_formed_definition_page_is_preserved_as_pending_review_metadata(candidate_workspace):
    reference = {"pdf_page": 1, "topic": "Neutral schema-unit explanation"}
    candidate_workspace["records"][0]["definition_pages"] = [reference]
    save_candidates(candidate_workspace)

    records = load_candidates(candidate_workspace["root"])

    assert records[0]["definition_pages"] == [reference]
    assert records[0]["verified"] is False
    assert records[0]["review_status"] == "pending_owner_review"


def test_prior_comparative_uses_the_current_report_but_compares_the_original_year(
    candidate_workspace,
):
    records = load_candidates(candidate_workspace["root"])
    current = next(r for r in records if r["fiscal_year"] == 2025)
    prior = current["prior_year_comparative"]

    assert prior["reported_fiscal_year"] == 2024
    assert prior["source_doc_id"] == "TEST-2025-EN"
    assert prior["value"] == Decimal("1234")
    assert current["comparative_matches_original"] is True


def test_source_backed_comparative_mismatch_is_preserved_for_review(candidate_workspace):
    current = candidate_workspace["records"][2]
    current["prior_year_comparative"] = {
        **candidate_workspace["alternate_prior"],
        "reported_fiscal_year": 2024,
        "value": "1111",
    }
    save_candidates(candidate_workspace)

    records = load_candidates(candidate_workspace["root"])
    current = next(r for r in records if r["fiscal_year"] == 2025)

    assert current["prior_year_comparative"]["value"] == Decimal("1111")
    assert current["comparative_matches_original"] is False
    assert current["comparability_status"] == "needs_owner_review"
    assert current["verified"] is False


def test_comparative_cannot_be_sourced_from_the_original_report_instead(candidate_workspace):
    original = candidate_workspace["records"][0]
    candidate_workspace["records"][2]["prior_year_comparative"].update(
        {key: value for key, value in original.items() if key.startswith("source_")}
    )
    save_candidates(candidate_workspace)

    with pytest.raises(ValueError):
        load_candidates(candidate_workspace["root"])


def test_csv_export_preserves_review_status_decimal_value_and_provenance(candidate_workspace):
    records = load_candidates(candidate_workspace["root"])

    exported = list(csv.DictReader(io.StringIO(candidate_csv(records))))

    assert len(exported) == len(records)
    monetary = next(r for r in exported if r["candidate_id"] == "neutral-2024-vonb")
    assert Decimal(monetary["value"]) == Decimal("1234")
    assert monetary["verified"].lower() == "false"
    assert monetary["review_status"] == "pending_owner_review"
    assert monetary["source_doc_id"] == "TEST-2024-EN"
    assert monetary["source_pdf_page"] == "1"
    assert monetary["source_url"] == "https://example.invalid/neutral-schema-2024.pdf"
