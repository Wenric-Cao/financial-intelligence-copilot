"""Reviewed lookup tests use actual labeled neutral PDFs, never AIA financial claims."""

import csv
import hashlib
import json
from pathlib import Path

import pymupdf
import pytest

from financial_intelligence_copilot import financial_answer
from financial_intelligence_copilot.kpi_reviews import make_review_packet
from financial_intelligence_copilot.verified_store import write_verified_store


def save_records(workspace):
    workspace["candidate_path"].write_text(
        json.dumps({"schema_version": 1, "candidates": workspace["records"]}), encoding="utf-8"
    )


def make_store(workspace, *, confirmed=True):
    packet = make_review_packet(workspace["records"])
    if confirmed:
        for review in packet["candidate_reviews"]:
            review.update(
                decision="confirmed",
                reviewer="TEST ONLY neutral fixture reviewer",
                reviewed_at="2026-11-08T12:00:00+08:00",
                notes="Explicit fixture decision over nonfinancial counts only.",
                checks=dict.fromkeys(review["checks"], True),
            )
    review_path = workspace["root"] / "data/kpi_reviews.json"
    review_path.write_text(json.dumps(packet), encoding="utf-8")
    store_path = workspace["root"] / "data/processed/verified-kpis.json"
    write_verified_store(workspace["root"], store_path)
    return store_path


def ask(workspace, query="What is VONB for FY2025?", **kwargs):
    options = {"doc_id": "TEST-COUNT-2025", "fiscal_year": 2025}
    options.update(kwargs)
    return financial_answer.answer_reviewed_kpi(workspace["root"], query, **options)


def set_metric(workspace, code):
    """Retain nonfinancial counts while changing schema routing, not real company data."""
    manifest_path = workspace["root"] / "data/manifest.csv"
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row, candidate in zip(rows, workspace["records"], strict=True):
        candidate["candidate_id"] = f"TEST-COUNT-{candidate['fiscal_year']}-{code}"
        candidate["metric_code"] = code
        if code != "VONB_MARGIN":
            continue
        source = workspace["root"] / "data/raw" / row["local_filename"]
        token = candidate["value"] + "%"
        header = "Schema routing units: percent"
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text(
                (72, 72),
                f"TEST ONLY - NOT A FINANCIAL REPORT\n{header}\nNeutral fixture count: {token}\n",
                fontsize=10,
            )
            source.write_bytes(document.tobytes())
        with pymupdf.open(source) as document:
            text = document[0].get_text("text", sort=True)
        start = text.index(token)
        row_start = text.index("Neutral fixture count:")
        row_end = text.find("\n", row_start)
        if row_end == -1:
            row_end = len(text)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        candidate.update(
            unit="percent",
            currency=None,
            source_sha256=digest,
            source_snippet=token,
            source_char_start=start,
            source_char_end=start + len(token),
            source_row_start=row_start,
            source_row_end=row_end,
            source_row_snippet=text[row_start:row_end],
            source_header={
                "char_start": text.index(header),
                "char_end": text.index(header) + len(header),
                "text": header,
            },
        )
        row["sha256"] = digest
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    save_records(workspace)


@pytest.mark.parametrize(
    "query",
    [
        "VONB",
        "Show VONB for FY2025",
        "What is VONB for FY2025?",
        "What was the reported annual VONB value for 2025 in USD million?",
        "Please give me the value of new business in 2025.",
        "  SHOW   VONB   FOR   FY 2025  ",
    ],
)
def test_approved_lookup_preserves_exact_value_and_review_provenance(verified_workspace, query):
    workspace = verified_workspace
    make_store(workspace)
    originals = {
        path: path.read_bytes()
        for path in (
            workspace["candidate_path"],
            workspace["root"] / "data/kpi_reviews.json",
            workspace["root"] / "data/manifest.csv",
        )
    }
    result = ask(workspace, query)
    assert result["mode"] == "reviewed_kpi_lookup"
    assert result["status"] == "reviewed_kpi" and result["reason"] is None
    fact = result["financial_fact"]
    assert fact["value"] == "12.3750"
    assert type(fact["value"]) is str
    assert fact["source_doc_id"] == "TEST-COUNT-2025"
    assert fact["source_pdf_page"] == 1
    assert fact["source_snippet"] == "12.3750"
    assert fact["fact_review"]["decision"] == "confirmed"
    assert fact["reviewer"] == "TEST ONLY neutral fixture reviewer"
    assert fact["comparability_status"] == "needs_owner_review"
    assert "no comparison or basis adjustment" in result["message"]
    assert all(path.read_bytes() == before for path, before in originals.items())


def test_scope_selects_only_requested_year(verified_workspace):
    make_store(verified_workspace)
    result = ask(
        verified_workspace,
        "What is VONB in FY2024?",
        doc_id="TEST-COUNT-2024",
        fiscal_year=2024,
    )
    assert result["financial_fact"]["value"] == "10.1250"


def test_confirmed_interim_fact_is_not_relabelled_as_annual(verified_workspace):
    workspace = verified_workspace
    workspace["records"][1]["period_start"] = "2025-07-01"
    workspace["records"][1]["period_basis"] = "TEST ONLY interim-period schema routing"
    save_records(workspace)
    make_store(workspace)
    result = ask(workspace)
    assert result["reason"] == "unsupported_annual_period"
    assert result["financial_fact"] is None


@pytest.mark.parametrize(
    ("code", "query"),
    [
        ("ANP", "What was the annualised new premiums for 2025?"),
        ("ANP", "Show annualized new premiums"),
        ("OPAT", "What is operating profit after tax for FY2025?"),
        ("UFSG", "Show underlying free surplus generation in USD million"),
        ("VONB_MARGIN", "What is VONB_MARGIN for FY2025 in percent?"),
        ("VONB_MARGIN", "Show value of new business margin"),
    ],
)
def test_supported_aliases_return_only_matching_metric(verified_workspace, code, query):
    set_metric(verified_workspace, code)
    make_store(verified_workspace)
    result = ask(verified_workspace, query)
    assert result["status"] == "reviewed_kpi"
    fact = result["financial_fact"]
    assert fact["metric_code"] == code
    assert fact["value"] == "12.3750"
    if code == "VONB_MARGIN":
        assert fact["unit"] == "percent" and fact["currency"] is None
        assert fact["source_snippet"] == "12.3750%"
        assert "percentage_change" not in fact


def test_missing_store_and_pending_facts_do_not_disclose_candidate_values(verified_workspace):
    workspace = verified_workspace
    missing = ask(workspace)
    assert missing["reason"] == "verified_store_unavailable"
    make_store(workspace, confirmed=False)
    pending = ask(workspace)
    assert pending["reason"] == "fact_review_pending"
    for result in (missing, pending):
        assert result["status"] == "abstained" and result["financial_fact"] is None
        assert "12.3750" not in json.dumps(result)


@pytest.mark.parametrize(
    ("query", "reason"),
    [
        ("Show VONB without citations", "citation_override_requested"),
        ("Should I buy AIA based on VONB?", "investment_advice_out_of_scope"),
        ("Forecast VONB", "prediction_out_of_scope"),
        ("Show VONB year-over-year", "comparison_not_available"),
        ("Show VONB change in percentage points", "comparison_not_available"),
        ("What is VONB in percent?", "requested_unit_unavailable"),
    ],
)
def test_existing_product_guards_and_unit_limits_remain(verified_workspace, query, reason):
    make_store(verified_workspace)
    result = ask(verified_workspace, query)
    assert result["status"] == "abstained" and result["reason"] == reason
    assert result["financial_fact"] is None


@pytest.mark.parametrize(
    "query",
    [
        "What is VONB in Hong Kong?",
        "What is VONB in HKD million?",
        "What is VONB for Q1 2025?",
        "What is VONB excluding tax?",
        "What is VONB at constant exchange rates?",
        "What is VONB and OPAT?",
        "What is VONB / ANP?",
        "Define VONB",
        "How is VONB calculated?",
        "What is HSBC's VONB?",
        "What is VONB under IFRS?",
        "What is operating profit?",
        "What is VONB in dollars?",
        "What is VONB?",
        "What is operating profit after tax?",
        "What is the value of new business?",
        "What is VONB_MARGIN?",
    ],
)
def test_full_query_grammar_never_drops_material_qualifiers(verified_workspace, query):
    make_store(verified_workspace)
    result = ask(verified_workspace, query)
    assert result["reason"] == "unsupported_financial_query"
    assert result["financial_fact"] is None


@pytest.mark.parametrize(
    ("query", "kwargs"),
    [
        ("Show VONB for FY2024", {}),
        ("Compare VONB for FY2024 and FY2025", {}),
        ("Show VONB", {"doc_id": "UNKNOWN"}),
        ("Show VONB", {"fiscal_year": 2024}),
        ("What is AIA's VONB in USD million?", {}),
    ],
)
def test_report_year_and_named_issuer_must_match_selected_source(verified_workspace, query, kwargs):
    make_store(verified_workspace)
    result = ask(verified_workspace, query, **kwargs)
    assert result["reason"] == "report_scope_conflict"
    assert result["financial_fact"] is None


def test_rejected_facts_and_wrong_metric_are_not_answered(verified_workspace):
    workspace = verified_workspace
    make_store(workspace)
    path = workspace["root"] / "data/kpi_reviews.json"
    packet = json.loads(path.read_text())
    for review in packet["candidate_reviews"]:
        review["decision"] = "rejected"
        review["checks"]["definition"] = False
    path.write_text(json.dumps(packet))
    store = workspace["root"] / "data/processed/rejected-kpis.json"
    write_verified_store(workspace["root"], store)
    result = ask(workspace, store_path=Path("data/processed/rejected-kpis.json"))
    assert result["reason"] == "reviewed_metric_unavailable"
    assert result["financial_fact"] is None


@pytest.mark.parametrize("mutation", ["revocation", "source", "store"])
def test_every_lookup_revalidates_store_and_sources(verified_workspace, mutation):
    workspace = verified_workspace
    store = make_store(workspace)
    assert ask(workspace)["status"] == "reviewed_kpi"
    if mutation == "revocation":
        path = workspace["root"] / "data/kpi_reviews.json"
        packet = json.loads(path.read_text())
        review = packet["candidate_reviews"][1]
        review.update(
            decision="pending",
            reviewer=None,
            reviewed_at=None,
            notes="",
            checks=dict.fromkeys(review["checks"]),
        )
        path.write_text(json.dumps(packet))
    elif mutation == "source":
        source = workspace["root"] / "data/raw/neutral_count_2025.pdf"
        source.write_bytes(source.read_bytes() + b"\nTEST ONLY changed bytes\n")
    else:
        payload = json.loads(store.read_text())
        payload["records"][1]["value"] = "99.0000"
        store.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        ask(workspace)


def test_manifest_change_after_store_validation_prevents_release(verified_workspace, monkeypatch):
    make_store(verified_workspace)
    original = financial_answer.load_verified_store

    def changed_manifest(root, store):
        result = original(root, store)
        path = root / "data/manifest.csv"
        path.write_bytes(path.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(financial_answer, "load_verified_store", changed_manifest)
    with pytest.raises(ValueError, match="manifest changed"):
        ask(verified_workspace)


@pytest.mark.parametrize("query", [None, "", " ", "x" * 2001, 12])
def test_query_validation_is_explicit(verified_workspace, query):
    with pytest.raises(ValueError, match="query"):
        ask(verified_workspace, query)


@pytest.mark.parametrize("year", [True, "2025", 2025.0, 25])
def test_fiscal_year_validation_rejects_type_coercion(verified_workspace, year):
    with pytest.raises(ValueError, match="fiscal_year"):
        ask(verified_workspace, fiscal_year=year)
