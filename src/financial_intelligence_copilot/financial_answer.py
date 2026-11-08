"""Narrow annual KPI lookups from revalidated, explicitly reviewed local facts."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from pathlib import Path

from financial_intelligence_copilot.answer import request_limitation
from financial_intelligence_copilot.financial_kpis import METRIC_UNITS
from financial_intelligence_copilot.verified_store import load_verified_store

NOTICE = (
    "Reported annual level from an explicitly recorded fact review, without adjustment or "
    "comparison. Content hashes and recorded reviewer names do not authenticate human identity. "
    "Fact confirmation does not establish comparability. Research demonstration only - "
    "not investment advice."
)
ALIASES = {
    "vonb": "VONB",
    "value of new business": "VONB",
    "anp": "ANP",
    "annualised new premiums": "ANP",
    "annualized new premiums": "ANP",
    "vonb_margin": "VONB_MARGIN",
    "vonb margin": "VONB_MARGIN",
    "value of new business margin": "VONB_MARGIN",
    "opat": "OPAT",
    "operating profit after tax": "OPAT",
    "ufsg": "UFSG",
    "underlying free surplus generation": "UFSG",
}
_METRIC_PATTERN = "|".join(re.escape(alias) for alias in sorted(ALIASES, key=len, reverse=True))
_QUERY = re.compile(
    r"(?:please )?"
    r"(?:(?P<prompt>what (?:is|was)(?: the)?|show(?: me)?(?: the)?|give(?: me)?(?: the)?) )?"
    r"(?:(?P<company>AIA(?: Group Limited)?)(?:'s)? )?"
    r"(?:(?P<annual>(?:reported )?annual|reported) )?"
    rf"(?P<metric>{_METRIC_PATTERN})"
    r"(?: (?P<value>value|annual value|reported value))?"
    r"(?: (?:for|in) (?P<year>(?:FY\s*)?20\d{2}))?"
    r"(?: in (?P<unit>USD million|percent))?"
    r"[?.]?",
    re.IGNORECASE,
)
_YEARS = re.compile(r"(?<![A-Za-z0-9])(?:FY\s*)?(20\d{2})(?!\d)", re.IGNORECASE)


def _manifest_scope(root: Path, doc_id: str, fiscal_year: int) -> tuple[bytes, dict | None]:
    manifest = (root / "data/manifest.csv").read_bytes()
    reader = csv.DictReader(io.StringIO(manifest.decode("utf-8")))
    if not {"doc_id", "issuer", "fiscal_year"}.issubset(reader.fieldnames or []):
        raise ValueError("Source manifest is missing lookup scope fields")
    documents = {}
    for row in reader:
        identity, year, issuer = row["doc_id"], row["fiscal_year"], row["issuer"]
        if (
            not isinstance(identity, str)
            or not identity.strip()
            or identity in documents
            or not isinstance(year, str)
            or re.fullmatch(r"\d{4}", year) is None
            or not isinstance(issuer, str)
            or not issuer.strip()
        ):
            raise ValueError("Source manifest has invalid or duplicate lookup scopes")
        documents[identity] = row
    selected = documents.get(doc_id)
    return manifest, selected if selected and int(selected["fiscal_year"]) == fiscal_year else None


def answer_reviewed_kpi(
    root: Path,
    query: str,
    *,
    doc_id: str,
    fiscal_year: int,
    store_path: Path | None = None,
) -> dict:
    """Look up one reported annual metric only, without generating a financial answer.

    Full-query grammar intentionally rejects interpretation, conversions, interim
    periods and comparisons. Every released fact comes from the source-rechecking
    store loader in this operation, rather than a candidate or cached flag.
    """
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("query must contain 1-2000 characters")
    if not isinstance(doc_id, str) or not doc_id.strip():
        raise ValueError("doc_id must be a nonempty registered document ID")
    if type(fiscal_year) is not int or not 1900 <= fiscal_year <= 9999:
        raise ValueError("fiscal_year must be a four-digit integer")
    root = Path(root).resolve()
    result = {
        "mode": "reviewed_kpi_lookup",
        "status": "abstained",
        "query": query,
        "scope": {"doc_id": doc_id, "fiscal_year": fiscal_year},
        "message": "Use a supported single-metric annual-level query for the selected report.",
        "reason": "unsupported_financial_query",
        "notice": NOTICE,
        "financial_fact": None,
    }

    def abstain(reason: str, message: str) -> dict:
        result.update(reason=reason, message=message)
        return result

    manifest, selected = _manifest_scope(root, doc_id, fiscal_year)
    if selected is None or any(int(year) != fiscal_year for year in _YEARS.findall(query)):
        return abstain(
            "report_scope_conflict",
            "The requested document/year conflicts with the selected report.",
        )
    limitation = request_limitation(query)
    if limitation and limitation[0] != "verified_kpi_unavailable":
        return abstain(*limitation)
    normalized = " ".join(query.replace("\N{RIGHT SINGLE QUOTATION MARK}", "'").split())
    matched = _QUERY.fullmatch(normalized)
    if matched is None:
        return result
    if (
        matched["prompt"]
        and matched["prompt"].casefold().startswith("what")
        and not any(matched[field] for field in ("annual", "value", "year", "unit"))
    ):
        # "What is VONB?" can ask for a definition rather than an annual level.
        return result
    if matched["company"] and selected["issuer"] != "AIA Group Limited":
        return abstain(
            "report_scope_conflict", "The named company differs from the selected source issuer."
        )
    metric = ALIASES[matched["metric"].casefold()]
    requested_unit = matched["unit"]
    if requested_unit:
        requested = (
            ("USD", "million")
            if requested_unit.casefold() == "usd million"
            else (
                None,
                "percent",
            )
        )
        if METRIC_UNITS[metric] != requested:
            return abstain(
                "requested_unit_unavailable",
                "The requested currency/unit differs from the reported metric; "
                "no conversion is made.",
            )
    path = Path(store_path) if store_path is not None else Path("data/processed/verified-kpis.json")
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        return abstain(
            "verified_store_unavailable",
            "No reviewed KPI store is available. "
            "Export a current store after explicit fact review.",
        )
    store = load_verified_store(root, path)
    if (
        hashlib.sha256(manifest).hexdigest() != store["input_fingerprints"]["manifest_sha256"]
        or (root / "data/manifest.csv").read_bytes() != manifest
    ):
        raise ValueError("Source manifest changed during reviewed KPI lookup")
    facts = [
        record
        for record in store["records"]
        if record["source_doc_id"] == doc_id
        and record["fiscal_year"] == fiscal_year
        and record["metric_code"] == metric
    ]
    if not facts:
        return abstain(
            "fact_review_pending" if store["pending_count"] else "reviewed_metric_unavailable",
            "No explicitly confirmed annual fact is available for this metric and report. "
            "Unreviewed or rejected candidate values are not released.",
        )
    if len(facts) != 1 or facts[0]["issuer"] != selected["issuer"]:
        raise ValueError("Reviewed KPI store contains an inconsistent lookup scope")
    if (facts[0]["period_start"], facts[0]["period_end"]) != (
        f"{fiscal_year}-01-01",
        f"{fiscal_year}-12-31",
    ):
        return abstain(
            "unsupported_annual_period",
            "This lookup supports full January-to-December annual facts only; "
            "the reviewed period differs.",
        )
    result.update(
        status="reviewed_kpi",
        reason=None,
        message=(
            "Reported annual value from the selected report; no comparison or basis adjustment."
        ),
        financial_fact=facts[0],
    )
    return result
