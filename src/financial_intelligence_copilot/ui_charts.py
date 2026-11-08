"""Local figures for freshly guarded comparison results, without review authorization."""

from __future__ import annotations

import math
import re
from decimal import Decimal
from urllib.parse import urlsplit

import plotly.graph_objects as go

from financial_intelligence_copilot.financial_kpis import METRIC_UNITS, parse_reported_value


def _source_metadata(source: dict, value: Decimal, unit: str) -> dict:
    """Check chart-label consistency, not actual PDF identity or owner approval."""
    if not isinstance(source, dict):
        raise ValueError("A comparison chart needs both structured source records")
    for field in ("candidate_id", "source_doc_id", "source_url", "source_sha256", "source_snippet"):
        if not isinstance(source.get(field), str) or not source[field].strip():
            raise ValueError("Comparison chart source metadata is incomplete")
    year = source.get("fiscal_year")
    page = source.get("source_pdf_page")
    if type(year) is not int or not 1 <= year <= 9999 or type(page) is not int or page < 1:
        raise ValueError("Comparison chart source year and physical page must be valid integers")
    if (source.get("period_start"), source.get("period_end")) != (
        f"{year:04d}-01-01",
        f"{year:04d}-12-31",
    ):
        raise ValueError("Comparison charts require full calendar-year source periods")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", source["source_sha256"]):
        raise ValueError("Comparison chart source hash is malformed")
    url = urlsplit(source["source_url"])
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("Comparison chart source URL must be HTTPS without credentials")
    start, end = source.get("source_char_start"), source.get("source_char_end")
    if (
        type(start) is not int
        or type(end) is not int
        or not 0 <= start < end
        or end - start != len(source["source_snippet"])
        or parse_reported_value(source["source_snippet"], unit) != value
    ):
        raise ValueError("Comparison chart value and numeric source token are inconsistent")
    return source


def comparison_figure(result: dict) -> go.Figure:
    """Plot two reported annual levels from a fresh guarded comparison result.

    Only callers loading source-bound review state may authorize a real financial
    chart. This function validates its visual inputs without authenticating an
    owner or reading source files. Floats are used for bar geometry only; exact
    Decimal strings remain in labels and hover text. Growth is not recomputed.
    """
    if not isinstance(result, dict) or result.get("status") != "calculated":
        raise ValueError("Only a calculated guarded comparison may produce a chart")
    metric = result.get("metric_code")
    unit = result.get("unit")
    if (
        not isinstance(metric, str)
        or metric not in METRIC_UNITS
        or "currency" not in result
        or (result["currency"], unit) != METRIC_UNITS[metric]
    ):
        raise ValueError("Comparison chart metric, currency and unit are inconsistent")
    values = [result.get("previous_value"), result.get("current_value")]
    if not all(isinstance(value, Decimal) and value.is_finite() for value in values):
        raise ValueError("Comparison chart levels must be finite Decimal objects")
    if values[0] <= 0:
        raise ValueError("A guarded comparison chart requires a positive prior base")
    sources = [
        _source_metadata(result.get("previous_source"), values[0], unit),
        _source_metadata(result.get("current_source"), values[1], unit),
    ]
    if (
        sources[1]["fiscal_year"] != sources[0]["fiscal_year"] + 1
        or sources[0]["candidate_id"] == sources[1]["candidate_id"]
        or sources[0]["source_doc_id"] == sources[1]["source_doc_id"]
    ):
        raise ValueError(
            "Comparison chart sources must identify distinct consecutive annual reports"
        )

    geometry = []
    for value in values:
        try:
            coordinate = float(value)
        except (ValueError, OverflowError) as exc:
            raise ValueError("Comparison chart level is outside supported plotting range") from exc
        if not math.isfinite(coordinate) or (coordinate == 0 and value != 0):
            raise ValueError("Comparison chart level is outside supported plotting range")
        geometry.append(coordinate)
    years = [f"FY{source['fiscal_year']}" for source in sources]
    labels = [format(value, ",f") + ("%" if unit == "percent" else "") for value in values]
    customdata = [
        [
            label,
            source["fiscal_year"],
            source["source_doc_id"],
            source["source_pdf_page"],
            source["period_start"],
            source["period_end"],
            source["source_url"],
            source["source_sha256"],
        ]
        for label, source in zip(labels, sources, strict=True)
    ]
    unit_label = "percent" if unit == "percent" else f"{result['currency']} million"
    value_suffix = "" if unit == "percent" else f" {unit_label}"
    figure = go.Figure(
        go.Bar(
            x=years,
            y=geometry,
            text=labels,
            textposition="auto",
            customdata=customdata,
            marker_color=["#7C8EA5", "#176B87"],
            hovertemplate=(
                "<b>FY%{customdata[1]}</b><br>"
                "Reported level: %{customdata[0]}" + value_suffix + "<br>"
                "%{customdata[2]} · PDF page %{customdata[3]}<br>"
                "Period: %{customdata[4]} to %{customdata[5]}<extra></extra>"
            ),
            name="Reported annual levels",
        )
    )
    figure.update_layout(
        title=f"{metric.replace('_', ' ')} · reported annual levels",
        xaxis={"type": "category", "categoryorder": "array", "categoryarray": years},
        yaxis={
            "title": unit_label,
            "ticksuffix": "%" if unit == "percent" else "",
            "rangemode": "tozero",
        },
        template="plotly_white",
        showlegend=False,
        height=340,
        margin={"l": 45, "r": 20, "t": 55, "b": 40},
    )
    return figure
