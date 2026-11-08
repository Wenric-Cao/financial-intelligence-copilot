"""Structural comparison checks and Decimal arithmetic, without review approval.

These functions do not establish that financial facts or definitions were
reviewed. Callers must separately validate source evidence and explicit owner
decisions before calculating or publishing a real financial comparison.
"""

from __future__ import annotations

from decimal import MAX_EMAX, MIN_EMIN, ROUND_HALF_EVEN, Context, Decimal, localcontext

from financial_intelligence_copilot.financial_kpis import METRIC_UNITS


def structural_mismatches(previous: dict, current: dict) -> list[str]:
    """Return stable refusal codes for an unadjusted annual comparison.

    The MVP accepts consecutive full calendar years and exactly equal scope and
    basis labels. Equal labels do not independently establish semantic financial
    comparability; that remains an explicit review decision outside this module.
    """
    reasons = []
    for label, record in (("previous", previous), ("current", current)):
        if not isinstance(record, dict):
            reasons.append(f"invalid_{label}_record")
    if reasons:
        return reasons

    for field in ("issuer", "metric_code", "currency", "unit", "scope", "basis"):
        if previous.get(field) != current.get(field):
            reasons.append(f"{field}_mismatch")

    years = []
    for label, record in (("previous", previous), ("current", current)):
        for field in ("issuer", "metric_code", "scope", "basis", "candidate_id", "source_doc_id"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                reasons.append(f"invalid_{label}_{field}")
        code = record.get("metric_code")
        if not isinstance(code, str) or code not in METRIC_UNITS:
            reasons.append(f"unsupported_{label}_metric")
        elif (
            "currency" not in record
            or (record.get("currency"), record.get("unit")) != METRIC_UNITS[code]
        ):
            reasons.append(f"invalid_{label}_metric_units")

        year = record.get("fiscal_year")
        if type(year) is not int or not 1 <= year <= 9999:
            reasons.append(f"invalid_{label}_fiscal_year")
            years.append(None)
        else:
            years.append(year)
            if (record.get("period_start"), record.get("period_end")) != (
                f"{year:04d}-01-01",
                f"{year:04d}-12-31",
            ):
                reasons.append(f"invalid_{label}_period")

    if all(year is not None for year in years) and years[1] != years[0] + 1:
        reasons.append("non_consecutive_fiscal_years")
    if previous.get("candidate_id") and previous.get("candidate_id") == current.get("candidate_id"):
        reasons.append("same_candidate_id")
    if previous.get("source_doc_id") and previous.get("source_doc_id") == current.get(
        "source_doc_id"
    ):
        reasons.append("same_source_document")
    return reasons


def calculate_change(previous: Decimal, current: Decimal, unit: str) -> dict:
    """Calculate a change in neutral or independently authorized inputs.

    This pure arithmetic helper does not check owner review or source identity.
    Monetary percentage change uses at least 34 significant digits, rounding
    half-even where a ratio repeats. Display rounding belongs to the caller.
    Subtraction precision expands to preserve exact finite Decimal differences.
    """
    if not all(isinstance(value, Decimal) and value.is_finite() for value in (previous, current)):
        raise ValueError("Comparison values must be finite Decimal objects")
    if unit not in ("million", "percent"):
        raise ValueError("Comparison unit must be million or percent")
    result = {
        "status": "needs_review",
        "reason": "non_positive_prior",
        "absolute_change": None,
        "percentage_change": None,
        "percentage_point_change": None,
    }
    if previous <= 0:
        return result

    exponents = [value.as_tuple().exponent for value in (previous, current)]
    adjusted = [value.adjusted() for value in (previous, current) if value]
    precision = max(34, max(adjusted) - min(exponents) + 3)
    context = Context(prec=precision, rounding=ROUND_HALF_EVEN, Emin=MIN_EMIN, Emax=MAX_EMAX)
    with localcontext(context):
        difference = current - previous
        result.update(status="calculated", reason=None)
        if unit == "percent":
            result["percentage_point_change"] = difference
        else:
            result["absolute_change"] = difference
            result["percentage_change"] = difference * Decimal(100) / previous
    return result
