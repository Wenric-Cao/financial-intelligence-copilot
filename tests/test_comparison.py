"""Neutral arithmetic and metadata examples; never real company financial data."""

from copy import deepcopy
from decimal import ROUND_DOWN, Decimal, Inexact, localcontext

import pytest

from financial_intelligence_copilot.comparison import calculate_change, structural_mismatches


def neutral_records():
    records = []
    for year in (2024, 2025):
        records.append(
            {
                "issuer": "Neutral comparison fixture",
                "metric_code": "VONB",
                "currency": "USD",
                "unit": "million",
                "scope": "Neutral schema scope, not a company disclosure",
                "basis": "Neutral arithmetic test basis",
                "candidate_id": f"TEST-{year}-QUANTITY",
                "source_doc_id": f"TEST-{year}-EN",
                "fiscal_year": year,
                "period_start": f"{year}-01-01",
                "period_end": f"{year}-12-31",
            }
        )
    return records


def test_consecutive_full_calendar_years_allow_a_leap_year():
    assert structural_mismatches(*neutral_records()) == []


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("issuer", "Another neutral fixture"),
        ("metric_code", "ANP"),
        ("currency", "HKD"),
        ("unit", "billion"),
        ("scope", "Another neutral scope"),
        ("basis", "Another neutral basis"),
    ],
)
def test_each_comparison_dimension_must_match(field, changed):
    previous, current = neutral_records()
    current[field] = changed
    assert f"{field}_mismatch" in structural_mismatches(previous, current)


@pytest.mark.parametrize("changed", [("HKD", "million"), ("USD", "billion"), (None, "percent")])
def test_equal_but_unsupported_metric_units_are_rejected(changed):
    records = neutral_records()
    for item in records:
        item["currency"], item["unit"] = changed
    reasons = structural_mismatches(*records)
    assert "invalid_previous_metric_units" in reasons
    assert "invalid_current_metric_units" in reasons


def test_percent_metric_has_no_currency_and_percent_units():
    records = neutral_records()
    for item in records:
        item.update(metric_code="VONB_MARGIN", currency=None, unit="percent")
    assert structural_mismatches(*records) == []


@pytest.mark.parametrize("which", [0, 1])
@pytest.mark.parametrize("field", ["issuer", "scope", "basis", "candidate_id", "source_doc_id"])
def test_empty_required_metadata_fails_closed(which, field):
    records = neutral_records()
    records[which][field] = " "
    label = "previous" if which == 0 else "current"
    assert f"invalid_{label}_{field}" in structural_mismatches(*records)


def test_unknown_metric_is_not_treated_as_a_known_financial_definition():
    records = neutral_records()
    for item in records:
        item["metric_code"] = "UNKNOWN_TEST_METRIC"
    assert structural_mismatches(*records) == [
        "unsupported_previous_metric",
        "unsupported_current_metric",
    ]


@pytest.mark.parametrize("bad_year", [True, "2025", 0, 10000, None])
def test_invalid_fiscal_years_fail_closed(bad_year):
    previous, current = neutral_records()
    current["fiscal_year"] = bad_year
    assert "invalid_current_fiscal_year" in structural_mismatches(previous, current)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("period_start", "2025-04-01"),
        ("period_end", "2025-06-30"),
        ("period_start", "20250101"),
        ("period_end", "2025-12-32"),
    ],
)
def test_interim_differently_bounded_or_invalid_periods_are_not_annual_pairs(field, value):
    previous, current = neutral_records()
    current[field] = value
    assert "invalid_current_period" in structural_mismatches(previous, current)


@pytest.mark.parametrize("years", [(2025, 2024), (2024, 2024), (2023, 2025)])
def test_reversed_same_year_or_gapped_pairs_are_rejected(years):
    records = neutral_records()
    for item, year in zip(records, years, strict=True):
        item.update(fiscal_year=year, period_start=f"{year}-01-01", period_end=f"{year}-12-31")
    assert "non_consecutive_fiscal_years" in structural_mismatches(*records)


def test_two_inputs_cannot_reuse_one_candidate_or_source_document():
    previous, current = neutral_records()
    current.update(candidate_id=previous["candidate_id"], source_doc_id=previous["source_doc_id"])
    assert structural_mismatches(previous, current) == ["same_candidate_id", "same_source_document"]


@pytest.mark.parametrize("bad", [None, [], "not a record"])
def test_non_record_input_has_a_stable_failure_reason(bad):
    previous, current = neutral_records()
    assert structural_mismatches(bad, current) == ["invalid_previous_record"]
    assert structural_mismatches(previous, bad) == ["invalid_current_record"]


@pytest.mark.parametrize(
    ("previous", "current", "delta", "growth"),
    [
        ("80", "100", "20", "25"),
        ("80", "60", "-20", "-25"),
        ("80", "80", "0", "0"),
        ("80", "0", "-80", "-100"),
        ("80", "-20", "-100", "-125"),
        ("0.1", "0.3", "0.2", "200"),
    ],
)
def test_positive_prior_amounts_preserve_units_and_exact_decimal_arithmetic(
    previous, current, delta, growth
):
    result = calculate_change(Decimal(previous), Decimal(current), "million")
    assert result == {
        "status": "calculated",
        "reason": None,
        "absolute_change": Decimal(delta),
        "percentage_change": Decimal(growth),
        "percentage_point_change": None,
    }


@pytest.mark.parametrize("prior", ["0", "-0", "-2.5"])
@pytest.mark.parametrize("unit", ["million", "percent"])
def test_non_positive_prior_returns_no_ordinary_change(prior, unit):
    assert calculate_change(Decimal(prior), Decimal("5"), unit) == {
        "status": "needs_review",
        "reason": "non_positive_prior",
        "absolute_change": None,
        "percentage_change": None,
        "percentage_point_change": None,
    }


def test_percentage_level_changes_are_percentage_points_not_percentage_growth():
    result = calculate_change(Decimal("12.5"), Decimal("15.0"), "percent")
    assert result == {
        "status": "calculated",
        "reason": None,
        "absolute_change": None,
        "percentage_change": None,
        "percentage_point_change": Decimal("2.5"),
    }


@pytest.mark.parametrize("bad", [1, 1.5, True, "1", None, Decimal("NaN"), Decimal("Infinity")])
def test_values_must_be_finite_decimals_not_coerced_floats_or_booleans(bad):
    with pytest.raises(ValueError, match="finite Decimal"):
        calculate_change(bad, Decimal("2"), "million")
    with pytest.raises(ValueError, match="finite Decimal"):
        calculate_change(Decimal("1"), bad, "million")


@pytest.mark.parametrize("unit", ["billion", "fraction", "USD", None])
def test_arithmetic_never_infers_or_converts_unsupported_units(unit):
    with pytest.raises(ValueError, match="unit"):
        calculate_change(Decimal("1"), Decimal("2"), unit)


def test_repeating_ratios_have_controlled_precision_independent_of_ambient_context():
    expected = Decimal("33.33333333333333333333333333333333")
    with localcontext() as ambient:
        ambient.prec = 3
        ambient.rounding = ROUND_DOWN
        ambient.traps[Inexact] = True
        ambient.Emax = 9
        result = calculate_change(Decimal("3"), Decimal("4"), "million")
        assert ambient.prec == 3
        assert ambient.rounding == ROUND_DOWN
        assert ambient.traps[Inexact] is True
    assert result["percentage_change"] == expected


def test_large_and_small_decimal_differences_are_not_lost_to_context_rounding():
    previous = Decimal("10000000000000000000000000000000000000000.000001")
    current = Decimal("10000000000000000000000000000000000000000.000003")
    result = calculate_change(previous, current, "million")
    assert result["absolute_change"] == Decimal("0.000002")
    result = calculate_change(Decimal("0.000001"), Decimal("1E+40"), "million")
    assert result["absolute_change"] == Decimal("9999999999999999999999999999999999999999.999999")


def test_structural_checks_do_not_mutate_source_records_or_claim_review_approval():
    records = neutral_records()
    before = deepcopy(records)
    assert structural_mismatches(*records) == []
    assert records == before
    assert all("verified" not in item for item in records)
