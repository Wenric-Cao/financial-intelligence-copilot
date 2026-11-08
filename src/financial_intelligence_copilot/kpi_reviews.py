"""Source-bound review decisions and guarded comparisons; never infer owner approval."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from financial_intelligence_copilot.comparison import calculate_change, structural_mismatches
from financial_intelligence_copilot.financial_kpis import load_candidates

FACT_CHECKS = ("value", "unit_currency", "period", "scope", "definition", "source")
PAIR_CHECKS = (
    "definition",
    "unit_currency",
    "period",
    "scope",
    "exchange_rate_basis",
    "tax_basis",
    "restatement",
)


def candidate_digest(record: dict) -> str:
    """Hash the complete raw JSON record, before normalization or derived fields.

    This binds decisions to content, not reviewer identity. An operator must only
    record an actual owner decision; a hash is not an authenticated signature.
    """
    if not isinstance(record, dict):
        raise ValueError("A candidate digest requires a raw structured record")
    try:
        canonical = json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Candidate digest requires finite raw JSON values") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _pairs(records: list[dict]) -> list[tuple[dict, dict]]:
    by_key = {(item["issuer"], item["metric_code"], item["fiscal_year"]): item for item in records}
    return [
        (by_key[(item["issuer"], item["metric_code"], item["fiscal_year"] - 1)], item)
        for item in sorted(
            records, key=lambda row: (row["issuer"], row["metric_code"], row["fiscal_year"])
        )
        if (item["issuer"], item["metric_code"], item["fiscal_year"] - 1) in by_key
    ]


def _pending(checks: tuple[str, ...]) -> dict:
    return {
        "decision": "pending",
        "reviewer": None,
        "reviewed_at": None,
        "notes": "",
        "checks": dict.fromkeys(checks),
    }


def make_review_packet(raw_candidates: list[dict]) -> dict:
    """Prepare pending decisions only. This function cannot approve a candidate."""
    return {
        "schema_version": 1,
        "notice": (
            "All decisions begin pending. Record explicit owner decisions only. "
            "Fact confirmation and pair comparability are separate reviews. "
            "Content hashes do not authenticate reviewer identity."
        ),
        "candidate_reviews": [
            {
                "candidate_id": item["candidate_id"],
                "candidate_digest": candidate_digest(item),
                **_pending(FACT_CHECKS),
            }
            for item in sorted(raw_candidates, key=lambda row: row["candidate_id"])
        ],
        "comparison_reviews": [
            {
                "previous_candidate_id": previous["candidate_id"],
                "current_candidate_id": current["candidate_id"],
                "previous_digest": candidate_digest(previous),
                "current_digest": candidate_digest(current),
                **_pending(PAIR_CHECKS),
            }
            for previous, current in _pairs(raw_candidates)
        ],
    }


def _check_decision(review: dict, decisions: set[str], checks: tuple[str, ...]) -> None:
    if not isinstance(review, dict) or review.get("decision") not in decisions:
        raise ValueError("Invalid owner review decision")
    checked = review.get("checks")
    if (
        not isinstance(checked, dict)
        or set(checked) != set(checks)
        or any(value is not None and type(value) is not bool for value in checked.values())
        or not isinstance(review.get("notes"), str)
    ):
        raise ValueError("Review checklist or notes are malformed")
    if review["decision"] == "pending":
        if (
            review.get("reviewer") is not None
            or review.get("reviewed_at") is not None
            or any(value is True for value in checked.values())
        ):
            raise ValueError("Pending decisions cannot contain review signatures or confirmations")
        return
    if any(
        not isinstance(review.get(key), str) or not review[key].strip()
        for key in ("reviewer", "reviewed_at", "notes")
    ):
        raise ValueError("Decided reviews require reviewer, review time and explanatory notes")
    try:
        reviewed_at = datetime.fromisoformat(review["reviewed_at"])
    except ValueError as exc:
        raise ValueError("Review timestamp must be ISO 8601 with a timezone") from exc
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
        raise ValueError("Review timestamp must be ISO 8601 with a timezone")
    if review["decision"] in {"confirmed", "comparable"} and not all(
        value is True for value in checked.values()
    ):
        raise ValueError("An approving decision requires every review check to be true")


def _checked_candidates(root: Path) -> tuple[list[dict], list[dict]]:
    root = Path(root)
    candidate_path = root / "data/kpi_candidates.json"
    before = candidate_path.read_bytes() if candidate_path.is_file() else None
    candidates = load_candidates(root)
    if (candidate_path.read_bytes() if candidate_path.is_file() else None) != before:
        raise ValueError("Candidate dataset changed during review validation")
    raw = json.loads(before)["candidates"] if before is not None else []
    return candidates, raw


def prepare_review_packet(root: Path) -> dict:
    """Recheck sources and prepare fresh pending decisions, without overwriting reviews."""
    _, raw = _checked_candidates(root)
    return make_review_packet(raw)


def load_review_state(root: Path) -> dict:
    """Recheck source candidates and bind a packet to complete raw candidate content.

    Missing decisions mean pending. Invalid/stale decisions raise rather than
    silently reusing an earlier approval. No verified store is written.
    """
    root = Path(root)
    candidates, raw = _checked_candidates(root)
    expected = make_review_packet(raw)
    review_path = root / "data/kpi_reviews.json"
    present = review_path.is_file()
    packet = json.loads(review_path.read_text(encoding="utf-8")) if present else expected
    if (
        not isinstance(packet, dict)
        or type(packet.get("schema_version")) is not int
        or packet["schema_version"] != 1
    ):
        raise ValueError("Invalid owner review packet schema")
    try:
        expected_facts = {item["candidate_id"]: item for item in expected["candidate_reviews"]}
        facts = packet["candidate_reviews"]
        if not isinstance(facts, list) or len(facts) != len(expected_facts):
            raise ValueError("Review packet must contain each candidate exactly once")
        seen = set()
        for review in facts:
            _check_decision(review, {"pending", "confirmed", "rejected"}, FACT_CHECKS)
            identity = review["candidate_id"]
            if identity not in expected_facts or identity in seen:
                raise ValueError("Unknown or duplicate candidate review")
            seen.add(identity)
            if review["candidate_digest"] != expected_facts[identity]["candidate_digest"]:
                raise ValueError(
                    "Stale candidate review digest; review the changed candidate again"
                )
        expected_pairs = {
            (item["previous_candidate_id"], item["current_candidate_id"]): item
            for item in expected["comparison_reviews"]
        }
        pairs = packet["comparison_reviews"]
        if not isinstance(pairs, list) or len(pairs) != len(expected_pairs):
            raise ValueError("Review packet must contain each annual pair exactly once")
        seen_pairs = set()
        for review in pairs:
            _check_decision(review, {"pending", "comparable", "not_comparable"}, PAIR_CHECKS)
            identity = (review["previous_candidate_id"], review["current_candidate_id"])
            if identity not in expected_pairs or identity in seen_pairs:
                raise ValueError("Unknown, reversed or duplicate comparison review")
            seen_pairs.add(identity)
            if any(
                review[field] != expected_pairs[identity][field]
                for field in ("previous_digest", "current_digest")
            ):
                raise ValueError("Stale comparison review digest; review the changed pair again")
    except (KeyError, TypeError) as exc:
        raise ValueError("Owner review packet has missing or invalid fields") from exc
    return {"candidates": candidates, "packet": packet, "packet_present": present}


def comparison_results(state: dict) -> list[dict]:
    """Release arithmetic only after source, fact and comparability gates pass.

    Input state must come from load_review_state in the same operation. This is
    a local trust boundary, not cryptographic authentication of a human reviewer.
    """
    candidates = {item["candidate_id"]: item for item in state["candidates"]}
    facts = {item["candidate_id"]: item for item in state["packet"]["candidate_reviews"]}
    results = []

    def source(item: dict) -> dict:
        return {
            key: item[key]
            for key in (
                "candidate_id",
                "fiscal_year",
                "period_start",
                "period_end",
                "source_doc_id",
                "source_sha256",
                "source_pdf_page",
                "source_url",
                "source_snippet",
                "source_char_start",
                "source_char_end",
            )
        }

    for review in state["packet"]["comparison_reviews"]:
        previous = candidates[review["previous_candidate_id"]]
        current = candidates[review["current_candidate_id"]]
        reasons = structural_mismatches(previous, current)
        for item in (previous, current):
            decision = facts[item["candidate_id"]]["decision"]
            if decision != "confirmed":
                reason = "fact_review_rejected" if decision == "rejected" else "fact_review_pending"
                if reason not in reasons:
                    reasons.append(reason)
        if review["decision"] != "comparable":
            reasons.append(
                "not_comparable"
                if review["decision"] == "not_comparable"
                else "comparability_pending"
            )
        result = {
            "metric_code": current["metric_code"],
            "previous_source": source(previous),
            "current_source": source(current),
            "status": "needs_review",
            "reasons": reasons,
            "absolute_change": None,
            "percentage_change": None,
            "percentage_point_change": None,
        }
        if not reasons:
            calculation = calculate_change(previous["value"], current["value"], current["unit"])
            result.update({key: value for key, value in calculation.items() if key != "reason"})
            if calculation["reason"]:
                result["reasons"] = [calculation["reason"]]
            if result["status"] == "calculated":
                result.update(
                    previous_value=previous["value"],
                    current_value=current["value"],
                    currency=current["currency"],
                    unit=current["unit"],
                    scope=current["scope"],
                    basis=current["basis"],
                    period_start=current["period_start"],
                    period_end=current["period_end"],
                    comparison_reviewer=review["reviewer"],
                    comparison_reviewed_at=review["reviewed_at"],
                    comparison_notes=review["notes"],
                    review_records={
                        "previous_fact": facts[previous["candidate_id"]],
                        "current_fact": facts[current["candidate_id"]],
                        "pair": review,
                    },
                )
        results.append(result)
    return results
