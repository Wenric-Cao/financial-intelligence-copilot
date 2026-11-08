"""Neutral chart-unit fixtures, without real AIA values or financial authorization."""

import hashlib
from copy import deepcopy
from decimal import Decimal

import pytest

from financial_intelligence_copilot.ui_charts import comparison_figure


def neutral_result(previous="1234.5000", current="1469.6250", percent=False):
    """Use metric codes as routing labels for neutral geometry, not company facts.

    Source fields are explicitly test metadata. Actual source and review checks
    are the caller's responsibility and are exercised in separate integration tests.
    """
    sources = []
    for year, value, page in ((2024, previous, 7), (2025, current, 9)):
        token = format(Decimal(value), ",f") + ("%" if percent else "")
        sources.append(
            {
                "candidate_id": f"TEST-NEUTRAL-{year}-QUANTITY",
                "source_doc_id": f"TEST-NEUTRAL-{year}-EN",
                "fiscal_year": year,
                "period_start": f"{year}-01-01",
                "period_end": f"{year}-12-31",
                "source_pdf_page": page,
                "source_sha256": hashlib.sha256(f"TEST ONLY {year}".encode()).hexdigest(),
                "source_url": f"https://example.invalid/neutral-chart-test-{year}.pdf",
                "source_snippet": token,
                "source_char_start": 100,
                "source_char_end": 100 + len(token),
            }
        )
    return {
        "status": "calculated",
        "metric_code": "VONB_MARGIN" if percent else "VONB",
        "currency": None if percent else "USD",
        "unit": "percent" if percent else "million",
        "previous_value": Decimal(previous),
        "current_value": Decimal(current),
        "previous_source": sources[0],
        "current_source": sources[1],
        "scope": "TEST ONLY neutral geometry",
        "basis": "TEST ONLY reported-level routing",
    }


@pytest.mark.parametrize("status", ["needs_review", "pending", "rejected", None])
def test_pending_or_unavailable_comparisons_cannot_produce_a_figure(status):
    result = neutral_result()
    result["status"] = status
    with pytest.raises(ValueError, match="calculated guarded"):
        comparison_figure(result)


def test_monetary_chart_preserves_exact_labels_original_units_and_both_sources():
    result = neutral_result()
    saved = deepcopy(result)
    figure = comparison_figure(result)
    assert len(figure.data) == 1
    bars = figure.data[0]
    assert list(bars.x) == ["FY2024", "FY2025"]
    assert list(bars.y) == [1234.5, 1469.625]
    assert list(bars.text) == ["1,234.5000", "1,469.6250"]
    assert figure.layout.xaxis.type == "category"
    assert list(figure.layout.xaxis.categoryarray) == ["FY2024", "FY2025"]
    assert figure.layout.yaxis.title.text == "USD million"
    assert figure.layout.yaxis.ticksuffix == ""
    assert "USD million" in bars.hovertemplate
    assert "Reported level: %{customdata[0]}" in bars.hovertemplate
    assert "PDF page %{customdata[3]}" in bars.hovertemplate
    assert "FY%{customdata[1]}" in bars.hovertemplate
    for index, source in enumerate((result["previous_source"], result["current_source"])):
        point = list(bars.customdata[index])
        assert point[0] == bars.text[index]
        assert point[1:6] == [
            source["fiscal_year"],
            source["source_doc_id"],
            source["source_pdf_page"],
            source["period_start"],
            source["period_end"],
        ]
        assert point[6:] == [source["source_url"], source["source_sha256"]]
    assert result == saved


def test_percent_levels_are_not_scaled_as_fractions_or_labeled_as_growth():
    result = neutral_result("12.50", "15.00", percent=True)
    figure = comparison_figure(result)
    bars = figure.data[0]
    assert list(bars.y) == [12.5, 15.0]
    assert list(bars.text) == ["12.50%", "15.00%"]
    assert figure.layout.yaxis.title.text == "percent"
    assert figure.layout.yaxis.ticksuffix == "%"
    assert figure.layout.yaxis.tickformat is None
    assert "USD" not in bars.hovertemplate
    assert "percentage change" not in bars.hovertemplate.lower()
    assert "percentage points" not in bars.hovertemplate.lower()
    assert "CER" not in figure.layout.title.text


def test_ratio_outputs_are_not_recomputed_or_substituted_for_reported_levels():
    result = neutral_result("80", "100")
    result.update(
        absolute_change=Decimal("999"),
        percentage_change=Decimal("888"),
        percentage_point_change=Decimal("777"),
    )
    bars = comparison_figure(result).data[0]
    assert list(bars.y) == [80.0, 100.0]
    assert list(bars.text) == ["80", "100"]
    assert all(value not in bars.hovertemplate for value in ("999", "888", "777"))


@pytest.mark.parametrize("bad", [1, 1.5, True, "1", None, Decimal("NaN"), Decimal("Infinity")])
@pytest.mark.parametrize("field", ["previous_value", "current_value"])
def test_chart_values_require_finite_decimal_inputs(field, bad):
    result = neutral_result()
    result[field] = bad
    with pytest.raises(ValueError, match="finite Decimal"):
        comparison_figure(result)


@pytest.mark.parametrize("prior", ["0", "-0", "-2"])
def test_a_nonpositive_prior_cannot_be_presented_as_a_calculated_chart(prior):
    with pytest.raises(ValueError, match="positive prior"):
        comparison_figure(neutral_result(prior, "5"))


@pytest.mark.parametrize("current", ["0", "-3"])
def test_zero_or_negative_current_levels_are_not_silently_hidden(current):
    figure = comparison_figure(neutral_result("5", current))
    assert list(figure.data[0].y) == [5.0, float(current)]
    assert figure.data[0].text[1] == current


@pytest.mark.parametrize(
    ("field", "bad"),
    [("currency", "HKD"), ("unit", "billion"), ("metric_code", "UNKNOWN_TEST_METRIC")],
)
def test_metric_currency_and_units_cannot_be_guessed_or_converted(field, bad):
    result = neutral_result()
    result[field] = bad
    with pytest.raises(ValueError, match="metric, currency and unit"):
        comparison_figure(result)


def test_a_percent_metric_cannot_acquire_a_monetary_currency():
    result = neutral_result("12.5", "15", percent=True)
    result["currency"] = "USD"
    with pytest.raises(ValueError, match="metric, currency and unit"):
        comparison_figure(result)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("fiscal_year", True),
        ("source_pdf_page", 0),
        ("source_pdf_page", True),
        ("source_sha256", "not-a-source-hash"),
        ("source_url", "http://example.invalid/neutral.pdf"),
        ("source_url", "https://user:secret@example.invalid/neutral.pdf"),
        ("period_start", "2025-04-01"),
        ("period_end", "2025-06-30"),
        ("source_doc_id", ""),
        ("source_char_start", -1),
        ("source_char_start", True),
        ("source_char_end", 101),
        ("source_snippet", "1,469.6251"),
    ],
)
def test_inconsistent_source_metadata_cannot_enter_hover_or_axis_labels(field, bad):
    result = neutral_result()
    result["current_source"][field] = bad
    with pytest.raises(ValueError):
        comparison_figure(result)


@pytest.mark.parametrize("source", [None, [], "TEST ONLY"])
def test_missing_or_unstructured_source_records_are_rejected(source):
    result = neutral_result()
    result["current_source"] = source
    with pytest.raises(ValueError, match="structured source"):
        comparison_figure(result)


@pytest.mark.parametrize("years", [(2025, 2024), (2024, 2024), (2023, 2025)])
def test_source_year_order_must_be_distinct_and_consecutive(years):
    result = neutral_result()
    for key, year in zip(("previous_source", "current_source"), years, strict=True):
        result[key].update(
            fiscal_year=year,
            period_start=f"{year}-01-01",
            period_end=f"{year}-12-31",
        )
    with pytest.raises(ValueError, match="distinct consecutive"):
        comparison_figure(result)


@pytest.mark.parametrize("field", ["candidate_id", "source_doc_id"])
def test_one_candidate_or_source_document_cannot_be_reused_for_both_bars(field):
    result = neutral_result()
    result["current_source"][field] = result["previous_source"][field]
    with pytest.raises(ValueError, match="distinct consecutive"):
        comparison_figure(result)


@pytest.mark.parametrize("current", ["1E+400", "1E-400"])
def test_finite_decimals_that_overflow_or_underflow_geometry_are_rejected(current):
    with pytest.raises(ValueError, match="plotting range"):
        comparison_figure(neutral_result("1", current))
