"""Streamlit workflows over neutral fixtures, not real AIA financial reports."""

import csv
import json
from copy import deepcopy
from pathlib import Path

import pymupdf
import pytest
from streamlit.testing.v1 import AppTest

from financial_intelligence_copilot import ui
from financial_intelligence_copilot.indexing import build_index
from financial_intelligence_copilot.kpi_reviews import make_review_packet
from financial_intelligence_copilot.pdf_parser import DocumentMetadata, parse_pdf

ARCHIVE_QUERY = "Who approves the records framework?"
BOARD_TEXT = "The Archive Board oversees archive stewardship and approves the records framework."
COUNCIL_TEXT = (
    "The Archive Council oversees archive stewardship and approves the records framework."
)


@pytest.fixture
def ui_workspace(tmp_path: Path) -> Path:
    """Use MVP routing labels with clearly synthetic, nonfinancial source content.

    AIA labels are required by the fixed-company UI. These tiny PDFs explicitly
    identify themselves as neutral test fixtures and make no real company claims.
    """
    raw = tmp_path / "data" / "raw"
    processed = tmp_path / "data" / "processed"
    raw.mkdir(parents=True)
    processed.mkdir()
    rows = []
    for year, governing_body in ((2024, COUNCIL_TEXT), (2025, BOARD_TEXT)):
        document_id = f"AIA-{year}-EN"
        source = raw / f"neutral_ui_fixture_{year}.pdf"
        with pymupdf.open() as document:
            cover = document.new_page()
            cover.insert_text((72, 72), "TEST FIXTURE ONLY - NOT AN OFFICIAL ANNUAL REPORT")
            page = document.new_page()
            page.insert_text(
                (72, 72),
                "TEST FIXTURE ONLY - NO REAL COMPANY CLAIMS\n\n"
                f"{governing_body}\n"
                "The records framework preserves paper folders and reading room labels.\n"
                "The archive stores literal <b>fixture markup</b> as plain reference text.\n"
                f"Neutral comparison amount: {10 if year == 2024 else 12}\n"
                f"Neutral comparison percent: {30 if year == 2024 else 33}%\n"
                "Neutral schema token 12 is included for review workflow tests.",
                fontsize=9,
            )
            document.save(source)
        parsed = parse_pdf(source, DocumentMetadata(document_id, "AIA Group Limited", year))
        (processed / f"{document_id}.pages.json").write_text(
            json.dumps(parsed.to_dict()), encoding="utf-8"
        )
        rows.append(
            {
                "doc_id": document_id,
                "issuer": "AIA Group Limited",
                "ticker": "1299.HK",
                "fiscal_year": year,
                "period_end": f"{year}-12-31",
                "language": "en",
                "source_url": f"https://example.invalid/neutral-ui-fixture-{year}.pdf",
                "date_downloaded": "",
                "sha256": parsed.sha256,
                "local_filename": source.name,
                "notes": "Generated neutral UI fixture; not downloaded or real company evidence.",
            }
        )
    manifest = tmp_path / "data" / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    policy = {
        "schema_version": 1,
        "max_words": 180,
        "overlap_words": 30,
        "min_words": 8,
        "excluded_pdf_pages": {
            f"AIA-{year}-EN": {"1": "Explicit neutral test fixture cover"} for year in (2024, 2025)
        },
    }
    (tmp_path / "data" / "retrieval_policy.json").write_text(json.dumps(policy), encoding="utf-8")
    index = build_index(manifest, raw, processed, policy)
    (processed / "retrieval-index.json").write_text(json.dumps(index), encoding="utf-8")
    return tmp_path


def app_for(root: Path) -> AppTest:
    script = (
        "from pathlib import Path\n"
        "from financial_intelligence_copilot.ui import run_app\n"
        f"run_app(root=Path({str(root)!r}))\n"
    )
    return AppTest.from_string(script, default_timeout=10).run()


def button(app: AppTest, label: str):
    return next(item for item in app.button if item.label == label)


def submit(app: AppTest, question: str = ARCHIVE_QUERY) -> AppTest:
    app.text_area(key="question").set_value(question)
    button(app, "Find evidence").click().run()
    assert not app.exception
    return app


def response(app: AppTest):
    try:
        return app.session_state["_response"]
    except KeyError:
        return None


def rendered_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for category in ("text", "code", "markdown", "caption", "info", "warning", "error")
        for element in getattr(app, category)
    )


def test_ui_defaults_and_unavailable_financial_workflows_are_explicit(ui_workspace):
    app = app_for(ui_workspace)

    assert not app.exception
    company = next(item for item in app.selectbox if item.label == "Company")
    assert company.value == "AIA Group Limited"
    assert company.options == ["AIA Group Limited"]
    assert company.disabled
    assert app.selectbox(key="fiscal_year").value == 2025
    assert [tab.label for tab in app.tabs] == [
        "Ask the Annual Report",
        "Financial KPIs",
        "Year-over-Year",
        "About & Evaluation",
    ]
    assert button(app, "Find evidence")
    assert button(app, "Recheck local sources")
    assert "Verified financial KPIs are not available yet." in rendered_text(app)
    assert "Year-over-year analysis is pending verified, comparable KPI inputs." in rendered_text(
        app
    )
    assert not response(app)


def test_ui_submission_displays_exact_source_text_and_physical_page(ui_workspace):
    app = submit(app_for(ui_workspace))

    assert response(app)["status"] == "extractive_evidence"
    assert any(item.value == BOARD_TEXT for item in app.code)
    assert "PDF page 2" in rendered_text(app)
    assert all(item["fiscal_year"] == 2025 for item in response(app)["excerpts"])
    assert all(item["doc_id"] == "AIA-2025-EN" for item in response(app)["excerpts"])
    assert all(item["pdf_page"] == 2 for item in response(app)["excerpts"])


def test_changing_year_clears_previous_answer_before_another_submission(ui_workspace):
    app = submit(app_for(ui_workspace))
    assert BOARD_TEXT in rendered_text(app)

    app.selectbox(key="fiscal_year").set_value(2024).run()

    assert not app.exception
    assert not response(app)
    assert BOARD_TEXT not in rendered_text(app)
    submit(app)
    assert any(item.value == COUNCIL_TEXT for item in app.code)
    assert all(item["fiscal_year"] == 2024 for item in response(app)["excerpts"])
    assert all(item["doc_id"] == "AIA-2024-EN" for item in response(app)["excerpts"])
    assert BOARD_TEXT not in rendered_text(app)


def test_checkout_without_local_reports_fails_closed(tmp_path):
    app = app_for(tmp_path)

    assert not app.exception
    available_submit = [item for item in app.button if item.label == "Find evidence"]
    if available_submit and not available_submit[0].disabled:
        submit(app)
    assert any("Local data is unavailable" in item.value for item in app.error)
    assert not response(app)
    assert BOARD_TEXT not in rendered_text(app)
    assert COUNCIL_TEXT not in rendered_text(app)


def test_source_change_clears_old_response_and_rejects_unverified_snapshot(ui_workspace):
    app = submit(app_for(ui_workspace))
    assert BOARD_TEXT in rendered_text(app)
    snapshot = ui_workspace / "data" / "processed" / "AIA-2025-EN.pages.json"
    saved = json.loads(snapshot.read_text(encoding="utf-8"))
    saved["pages"][1]["text"] = saved["pages"][1]["text"].replace("Archive Board", "Archive Orbis")
    snapshot.write_text(json.dumps(saved), encoding="utf-8")

    app.run()

    assert not app.exception
    assert not response(app)
    assert BOARD_TEXT not in rendered_text(app)
    available_submit = [item for item in app.button if item.label == "Find evidence"]
    if available_submit and not available_submit[0].disabled:
        submit(app)
    assert any("Could not verify local sources" in item.value for item in app.error)
    assert not response(app)
    assert BOARD_TEXT not in rendered_text(app)


def test_source_markup_is_rendered_as_literal_code(ui_workspace):
    app = submit(app_for(ui_workspace), "What does the archive store as plain reference text?")

    assert response(app)["status"] == "extractive_evidence"
    assert any("<b>fixture markup</b>" in item.value for item in app.code)
    assert all("<b>fixture markup</b>" not in item.value for item in app.markdown)


def write_neutral_candidate(root: Path):
    """Schema-routing quantity only, explicitly not a real company financial value."""
    with (root / "data/manifest.csv").open(newline="", encoding="utf-8") as handle:
        source = next(row for row in csv.DictReader(handle) if row["fiscal_year"] == "2025")
    page = json.loads((root / "data/processed/AIA-2025-EN.pages.json").read_text())["pages"][1]
    text = page["text"]
    start = text.index("12")
    row_start = text.rfind("\n", 0, start) + 1
    row_end = text.find("\n", start)
    if row_end == -1:
        row_end = len(text)
    record = {
        "candidate_id": "TEST-UI-2025-VONB",
        "issuer": "AIA Group Limited",
        "fiscal_year": 2025,
        "metric_code": "VONB",
        "metric_name": "Neutral schema quantity - test only",
        "value": "12",
        "currency": "USD",
        "unit": "million",
        "period_start": "2025-01-01",
        "period_end": "2025-12-31",
        "scope": "Neutral UI schema fixture, not company evidence",
        "basis": "Neutral schema routing",
        "comparability_status": "needs_owner_review",
        "comparability_notes": "Test fixture only; no financial conclusion.",
        "source_doc_id": "AIA-2025-EN",
        "source_sha256": source["sha256"],
        "source_pdf_page": 2,
        "source_char_start": start,
        "source_char_end": start + 2,
        "source_snippet": "12",
        "source_row_start": row_start,
        "source_row_end": row_end,
        "source_row_snippet": text[row_start:row_end],
        "source_url": source["source_url"],
        "verified": False,
        "review_status": "pending_owner_review",
        "reviewer": None,
        "reviewed_at": None,
        "definition_pages": [],
    }
    path = root / "data/kpi_candidates.json"
    path.write_text(json.dumps({"schema_version": 1, "candidates": [record]}), encoding="utf-8")
    return path


def test_candidate_ui_is_pending_review_without_approval_controls(ui_workspace):
    path = write_neutral_candidate(ui_workspace)
    app = app_for(ui_workspace)
    assert not app.exception
    assert "Pending owner review - these values are not verified financial data." in rendered_text(
        app
    )
    assert "Neutral schema quantity - test only" in rendered_text(app)
    assert app.session_state["_kpi_candidates"][0]["verified"] is False
    assert json.loads(path.read_text())["candidates"][0]["verified"] is False
    assert all("approve" not in item.label.lower() for item in app.button)
    assert "Year-over-year analysis is pending verified, comparable KPI inputs." in rendered_text(
        app
    )


def test_changed_candidate_value_cannot_reuse_previous_ui_values(ui_workspace):
    path = write_neutral_candidate(ui_workspace)
    app = app_for(ui_workspace)
    assert "Neutral schema quantity - test only" in rendered_text(app)
    data = json.loads(path.read_text())
    data["candidates"][0]["value"] = "13"
    path.write_text(json.dumps(data), encoding="utf-8")
    app.run()
    assert not app.exception
    assert any("KPI candidate validation failed" in item.value for item in app.error)
    assert "Neutral schema quantity - test only" not in rendered_text(app)


def write_neutral_comparison_inputs(root: Path, *, confirmed: bool) -> None:
    """Use test-only source quantities and review decisions inside the temporary workspace."""
    template = json.loads(write_neutral_candidate(root).read_text())["candidates"][0]
    with (root / "data/manifest.csv").open(newline="", encoding="utf-8") as handle:
        sources = {int(row["fiscal_year"]): row for row in csv.DictReader(handle)}
    records = []
    for year in (2024, 2025):
        source = sources[year]
        page = json.loads((root / f"data/processed/AIA-{year}-EN.pages.json").read_text())["pages"][
            1
        ]
        text = page["text"]
        for code, prefix, token in (
            ("VONB", "Neutral comparison amount:", "10" if year == 2024 else "12"),
            ("VONB_MARGIN", "Neutral comparison percent:", "30%" if year == 2024 else "33%"),
        ):
            row_start = text.index(prefix)
            row_end = text.find("\n", row_start)
            if row_end < 0:
                row_end = len(text)
            start = text.index(token, row_start, row_end)
            record = deepcopy(template)
            record.update(
                candidate_id=f"TEST-UI-{year}-{code}",
                fiscal_year=year,
                metric_code=code,
                metric_name=f"Neutral {code} comparison fixture - not company evidence",
                value=token.rstrip("%"),
                currency=None if code == "VONB_MARGIN" else "USD",
                unit="percent" if code == "VONB_MARGIN" else "million",
                period_start=f"{year}-01-01",
                period_end=f"{year}-12-31",
                source_doc_id=f"AIA-{year}-EN",
                source_sha256=source["sha256"],
                source_char_start=start,
                source_char_end=start + len(token),
                source_snippet=token,
                source_row_start=row_start,
                source_row_end=row_end,
                source_row_snippet=text[row_start:row_end],
                source_url=source["source_url"],
            )
            records.append(record)
    (root / "data/kpi_candidates.json").write_text(
        json.dumps({"schema_version": 1, "candidates": records}), encoding="utf-8"
    )
    packet = make_review_packet(records)
    if confirmed:
        for collection, decision in (
            ("candidate_reviews", "confirmed"),
            ("comparison_reviews", "comparable"),
        ):
            for review in packet[collection]:
                review.update(
                    decision=decision,
                    reviewer="Neutral UI Test Reviewer - not a real owner decision",
                    reviewed_at="2026-11-08T00:00:00+08:00",
                    notes="TEST FIXTURE ONLY: recorded decision for neutral schema quantities.",
                    checks=dict.fromkeys(review["checks"], True),
                )
    (root / "data/kpi_reviews.json").write_text(json.dumps(packet), encoding="utf-8")


def comparison_metrics(app: AppTest) -> dict[str, str]:
    return {item.label: item.value for item in app.metric}


def comparison_chart(app: AppTest) -> dict:
    charts = app.get("plotly_chart")
    assert len(charts) == 1
    assert charts[0].key == "reviewed-comparison-chart"
    return json.loads(charts[0].proto.spec)


def test_pending_neutral_pair_has_no_calculation_or_plotly_chart(ui_workspace):
    write_neutral_comparison_inputs(ui_workspace, confirmed=False)

    app = app_for(ui_workspace)

    assert not app.exception
    assert "Comparison readiness" in [item.value for item in app.subheader]
    assert "Year-over-year analysis is pending verified, comparable KPI inputs." in rendered_text(
        app
    )
    assert not app.get("plotly_chart")
    assert "Absolute change" not in comparison_metrics(app)
    assert "Percentage-point change" not in comparison_metrics(app)


def test_confirmed_neutral_amount_pair_displays_guarded_changes_and_source_levels(ui_workspace):
    write_neutral_comparison_inputs(ui_workspace, confirmed=True)
    candidate_path = ui_workspace / "data/kpi_candidates.json"
    original_candidate_bytes = candidate_path.read_bytes()

    app = app_for(ui_workspace)

    assert not app.exception
    assert comparison_metrics(app)["Absolute change"] == "2 USD million"
    assert comparison_metrics(app)["Percentage change"] == "20.00%"
    chart = comparison_chart(app)
    assert chart["data"][0]["x"] == ["FY2024", "FY2025"]
    assert chart["data"][0]["y"] == [10, 12]
    assert "Fact confirmations recorded: 4" in [item.value for item in app.success]
    assert candidate_path.read_bytes() == original_candidate_bytes
    assert all(
        record["verified"] is False for record in json.loads(original_candidate_bytes)["candidates"]
    )


def test_neutral_percentage_pair_uses_percentage_points_and_percent_levels(ui_workspace):
    write_neutral_comparison_inputs(ui_workspace, confirmed=True)
    app = app_for(ui_workspace)

    app.selectbox(key="comparison_metric").set_value(
        "TEST-UI-2024-VONB_MARGIN:TEST-UI-2025-VONB_MARGIN"
    ).run()

    assert not app.exception
    metrics = comparison_metrics(app)
    assert metrics["Percentage-point change"] == "3 pp"
    assert "Percentage change" not in metrics and "Absolute change" not in metrics
    chart = comparison_chart(app)
    assert chart["data"][0]["x"] == ["FY2024", "FY2025"]
    assert chart["data"][0]["y"] == [30, 33]
    assert chart["data"][0]["text"] == ["30%", "33%"]


@pytest.mark.parametrize("change", ["pending", "delete", "reject", "stale", "malformed"])
def test_review_changes_remove_previously_displayed_calculations_and_chart(ui_workspace, change):
    write_neutral_comparison_inputs(ui_workspace, confirmed=True)
    app = app_for(ui_workspace)
    assert comparison_metrics(app)["Percentage change"] == "20.00%"
    assert app.get("plotly_chart")
    path = ui_workspace / "data/kpi_reviews.json"
    packet = json.loads(path.read_text())
    if change == "delete":
        path.unlink()
    elif change == "malformed":
        path.write_text("{deliberately invalid neutral review JSON", encoding="utf-8")
    elif change == "stale":
        candidate_path = ui_workspace / "data/kpi_candidates.json"
        dataset = json.loads(candidate_path.read_text())
        dataset["candidates"][0]["comparability_notes"] = "Changed neutral review context."
        candidate_path.write_text(json.dumps(dataset), encoding="utf-8")
    else:
        if change == "pending":
            for review in packet["comparison_reviews"]:
                review.update(
                    decision="pending",
                    reviewer=None,
                    reviewed_at=None,
                    notes="",
                    checks=dict.fromkeys(review["checks"]),
                )
        else:
            for review in packet["candidate_reviews"]:
                review.update(
                    decision="rejected",
                    notes="TEST ONLY: reject this neutral fixture quantity.",
                    checks=dict.fromkeys(review["checks"], False),
                )
        path.write_text(json.dumps(packet), encoding="utf-8")

    app.run()

    assert not app.exception
    assert not app.get("plotly_chart")
    assert not {"Absolute change", "Percentage change", "Percentage-point change"}.intersection(
        comparison_metrics(app)
    )
    if change in {"stale", "malformed"}:
        assert any("Comparison validation failed" in item.value for item in app.error)
    else:
        assert (
            "Year-over-year analysis is pending verified, comparable KPI inputs."
            in rendered_text(app)
        )


def test_cached_review_revision_race_hides_confirmed_inputs_and_chart(ui_workspace, monkeypatch):
    write_neutral_comparison_inputs(ui_workspace, confirmed=True)
    app = app_for(ui_workspace)
    assert app.get("plotly_chart")
    original_fingerprint = ui.workspace_fingerprint
    calls = 0

    def changed_after_initial_snapshot(root, documents):
        nonlocal calls
        calls += 1
        current = original_fingerprint(root, documents)
        return current if calls == 1 else "changed-after-initial-rerun-snapshot"

    monkeypatch.setattr(ui, "workspace_fingerprint", changed_after_initial_snapshot)

    app.run()

    assert not app.exception
    assert not app.get("plotly_chart")
    assert all("Fact confirmations recorded" not in item.value for item in app.success)
    assert any("KPI candidate validation failed" in item.value for item in app.error)
    assert any("Comparison validation failed" in item.value for item in app.error)


def test_historical_evaluation_projection_is_labeled_and_clears_after_reader_failure(
    ui_workspace, monkeypatch
):
    projection = {
        "started_at": "2026-10-31T00:00:00+00:00",
        "run_id": "TEST-ONLY-HISTORICAL-PROJECTION",
        "run_digest": "f" * 64,
        "case_count": 40,
        "completed_count": 40,
        "error_count": 0,
        "behavior_matched": 40,
        "behavior_eligible": 40,
        "spans_checked": 12,
        "spans_total": 12,
        "span_case_errors": 0,
        "page_hits_1": 15,
        "page_hits_5": 21,
        "page_hit_eligible": 28,
        "approved_gold_count": 0,
        "human_scored_count": 0,
        "semantic_metrics": dict.fromkeys(
            (
                "answer_correctness",
                "citation_relevance",
                "numerical_correctness",
                "abstention_correctness",
            )
        ),
        "code_snapshot_current": False,
    }
    monkeypatch.setattr(ui, "load_development_record", lambda root: projection)
    app = app_for(ui_workspace)

    assert not app.exception
    table_text = "\n".join(item.value.to_string(index=False) for item in app.dataframe)
    assert all(value in table_text for value in ("40/40", "12/12", "21/28"))
    assert "0 approved gold answers and 0 human-scored cases" in rendered_text(app)
    assert any("earlier code/configuration snapshot" in item.value for item in app.warning)
    assert "Current UI behavior is not a fresh evaluation run." in rendered_text(app)

    def unreadable_record(root):
        raise ValueError("Deliberate neutral historical-record validation failure")

    monkeypatch.setattr(ui, "load_development_record", unreadable_record)
    app.run()

    assert not app.exception
    assert any("Evaluation record validation failed" in item.value for item in app.error)
    table_text = "\n".join(item.value.to_string(index=False) for item in app.dataframe)
    assert all(value not in table_text for value in ("40/40", "12/12", "21/28"))
