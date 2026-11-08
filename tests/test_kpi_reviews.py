"""Owner-review rules over neutral schema records, never real company evidence."""

import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from financial_intelligence_copilot import kpi_reviews


def neutral_record(year: int, value: str) -> dict:
    """Model the record schema without claiming a downloaded financial source."""
    text = f"Neutral fixture quantity: {value}"
    start = text.index(value)
    return {
        "candidate_id": f"neutral-review-{year}-quantity",
        "issuer": "Neutral Review Fixture",
        "fiscal_year": year,
        "metric_code": "VONB",
        "metric_name": "Neutral schema quantity, not a financial disclosure",
        "value": value,
        "currency": "USD",
        "unit": "million",
        "period_start": f"{year}-01-01",
        "period_end": f"{year}-12-31",
        "period_basis": "Annual calendar-year fixture",
        "scope": "Neutral fixture scope",
        "basis": "Neutral fixture basis, not company evidence",
        "comparability_status": "needs_owner_review",
        "comparability_notes": "Neutral schema test only",
        "source_doc_id": f"TEST-REVIEW-{year}",
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "source_pdf_page": 2,
        "source_char_start": start,
        "source_char_end": start + len(value),
        "source_snippet": value,
        "source_row_start": 0,
        "source_row_end": len(text),
        "source_row_snippet": text,
        "source_header": {"char_start": 0, "char_end": 7, "text": "Neutral"},
        "source_url": f"https://example.invalid/neutral-review-{year}.pdf",
        "verified": False,
        "review_status": "pending_owner_review",
        "reviewer": None,
        "reviewed_at": None,
        "definition_pages": [],
    }


@pytest.fixture
def review_workspace(tmp_path: Path, monkeypatch) -> dict:
    """Isolate review logic; real raw-PDF validation has its own test suite."""
    (tmp_path / "data").mkdir()
    records = [neutral_record(2024, "10"), neutral_record(2025, "12")]
    workspace = {"root": tmp_path, "records": records, "calls": []}

    def checked_candidates(root: Path) -> list[dict]:
        workspace["calls"].append(root)
        return [{**deepcopy(item), "value": Decimal(item["value"])} for item in records]

    monkeypatch.setattr(kpi_reviews, "load_candidates", checked_candidates)
    save_raw(workspace)
    return workspace


def save_raw(workspace: dict) -> None:
    path = workspace["root"] / "data/kpi_candidates.json"
    path.write_text(
        json.dumps({"schema_version": 1, "candidates": workspace["records"]}), encoding="utf-8"
    )


def save_packet(workspace: dict, packet: dict) -> None:
    path = workspace["root"] / "data/kpi_reviews.json"
    path.write_text(json.dumps(packet), encoding="utf-8")


def decided_packet(workspace: dict, *, comparable: bool = True) -> dict:
    """Create explicit test decisions, not product-owner approval of real data."""
    packet = kpi_reviews.make_review_packet(workspace["records"])
    for review in packet["candidate_reviews"]:
        review.update(
            decision="confirmed",
            reviewer="Neutral test reviewer",
            reviewed_at="2026-10-30T12:30:00+08:00",
            notes="Explicit confirmation of this neutral test record only.",
            checks=dict.fromkeys(kpi_reviews.FACT_CHECKS, True),
        )
    if comparable:
        for review in packet["comparison_reviews"]:
            review.update(
                decision="comparable",
                reviewer="Neutral test reviewer",
                reviewed_at="2026-10-30T12:35:00+08:00",
                notes="All named comparison checks passed for neutral fixtures only.",
                checks=dict.fromkeys(kpi_reviews.PAIR_CHECKS, True),
            )
    return packet


def assert_no_calculation(result: dict) -> None:
    assert result["status"] == "needs_review"
    assert isinstance(result["reasons"], list) and result["reasons"]
    for field in (
        "absolute_change",
        "percentage_change",
        "percentage_point_change",
        "percentage_points_change",
        "percent_change",
        "yoy_percent",
        "calculation",
        "previous_value",
        "current_value",
    ):
        assert result.get(field) is None


def test_digest_is_canonical_for_object_key_order_but_preserves_record_content():
    record = neutral_record(2024, "10")
    reordered = dict(reversed(list(record.items())))
    digest = kpi_reviews.candidate_digest(record)
    assert digest == kpi_reviews.candidate_digest(reordered)
    assert len(digest) == 64
    int(digest, 16)
    changed = {**record, "value": "10.0"}
    assert digest != kpi_reviews.candidate_digest(changed)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("scope", "A different neutral scope"),
        ("period_start", "2024-02-01"),
        ("basis", "A different neutral basis"),
        ("source_char_start", 1),
        ("definition_pages", [{"pdf_page": 3, "topic": "Changed neutral definition"}]),
        ("comparability_notes", "Changed caveat"),
    ],
)
def test_digest_binds_interpretation_metadata_and_source_context(field, replacement):
    record = neutral_record(2024, "10")
    assert kpi_reviews.candidate_digest(record) != kpi_reviews.candidate_digest(
        {**record, field: replacement}
    )


def test_missing_packet_generates_pending_state_without_writing_approval(review_workspace):
    root = review_workspace["root"]
    state = kpi_reviews.load_review_state(root)
    assert state["packet_present"] is False
    assert review_workspace["calls"] == [root]
    assert not (root / "data/kpi_reviews.json").exists()
    assert len(state["packet"]["candidate_reviews"]) == 2
    assert len(state["packet"]["comparison_reviews"]) == 1
    for review in state["packet"]["candidate_reviews"] + state["packet"]["comparison_reviews"]:
        assert review["decision"] == "pending"
        assert review["reviewer"] is None and review["reviewed_at"] is None
        assert all(value is None for value in review["checks"].values())
    for record in state["candidates"]:
        assert record["verified"] is False
    assert_no_calculation(kpi_reviews.comparison_results(state)[0])


def test_pending_packet_round_trip_preserves_no_approval_and_accepts_notes(review_workspace):
    packet = kpi_reviews.make_review_packet(review_workspace["records"])
    packet["candidate_reviews"][0]["notes"] = "A question remains for the owner."
    packet["candidate_reviews"][0]["checks"]["definition"] = False
    save_packet(review_workspace, packet)
    state = kpi_reviews.load_review_state(review_workspace["root"])
    assert state["packet_present"] is True
    assert state["packet"] == packet
    assert_no_calculation(kpi_reviews.comparison_results(state)[0])


@pytest.mark.parametrize("field", ["value", "scope", "source_row_snippet", "basis"])
def test_decision_for_a_stale_candidate_record_is_rejected(review_workspace, field):
    save_packet(review_workspace, decided_packet(review_workspace))
    review_workspace["records"][0][field] += "0" if field == "value" else " changed"
    save_raw(review_workspace)
    with pytest.raises(ValueError):
        kpi_reviews.load_review_state(review_workspace["root"])


@pytest.mark.parametrize("kind", ["candidate_reviews", "comparison_reviews"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reviewer", "Forged pending signature"),
        ("reviewed_at", "2026-10-30T12:30:00+08:00"),
    ],
)
def test_pending_decision_cannot_carry_a_signature(review_workspace, kind, field, value):
    packet = kpi_reviews.make_review_packet(review_workspace["records"])
    packet[kind][0][field] = value
    save_packet(review_workspace, packet)
    with pytest.raises(ValueError):
        kpi_reviews.load_review_state(review_workspace["root"])


@pytest.mark.parametrize("kind", ["candidate_reviews", "comparison_reviews"])
def test_pending_decision_cannot_claim_a_completed_check(review_workspace, kind):
    packet = kpi_reviews.make_review_packet(review_workspace["records"])
    checks = packet[kind][0]["checks"]
    checks[next(iter(checks))] = True
    save_packet(review_workspace, packet)
    with pytest.raises(ValueError):
        kpi_reviews.load_review_state(review_workspace["root"])


@pytest.mark.parametrize("kind", ["candidate_reviews", "comparison_reviews"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("decision", "approved_by_next_message"),
        ("reviewer", " "),
        ("notes", ""),
        ("reviewed_at", "not-a-timestamp"),
        ("reviewed_at", "2026-10-30T12:30:00"),
    ],
)
def test_decided_reviews_require_explicit_valid_status_and_signature(
    review_workspace, kind, field, value
):
    packet = decided_packet(review_workspace)
    packet[kind][0][field] = value
    save_packet(review_workspace, packet)
    with pytest.raises(ValueError):
        kpi_reviews.load_review_state(review_workspace["root"])


@pytest.mark.parametrize("kind", ["candidate_reviews", "comparison_reviews"])
@pytest.mark.parametrize("mutation", ["missing", "extra", "false", "integer"])
def test_confirmed_and_comparable_reviews_require_exact_true_checklists(
    review_workspace, kind, mutation
):
    packet = decided_packet(review_workspace)
    checks = packet[kind][0]["checks"]
    first = next(iter(checks))
    if mutation == "missing":
        checks.pop(first)
    elif mutation == "extra":
        checks["undocumented_check"] = True
    else:
        checks[first] = False if mutation == "false" else 1
    save_packet(review_workspace, packet)
    with pytest.raises(ValueError):
        kpi_reviews.load_review_state(review_workspace["root"])


@pytest.mark.parametrize("kind", ["candidate_reviews", "comparison_reviews"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown"])
def test_packet_membership_must_exactly_match_current_candidates_and_pairs(
    review_workspace, kind, mutation
):
    packet = kpi_reviews.make_review_packet(review_workspace["records"])
    if mutation == "missing":
        packet[kind].pop()
    elif mutation == "duplicate":
        packet[kind].append(deepcopy(packet[kind][0]))
    else:
        key = "candidate_id" if kind == "candidate_reviews" else "current_candidate_id"
        packet[kind][0][key] = "unknown-neutral-record"
    save_packet(review_workspace, packet)
    with pytest.raises(ValueError):
        kpi_reviews.load_review_state(review_workspace["root"])


@pytest.mark.parametrize("field", ["previous_digest", "current_digest"])
def test_pair_approval_is_bound_to_both_candidate_digests(review_workspace, field):
    packet = decided_packet(review_workspace)
    packet["comparison_reviews"][0][field] = "0" * 64
    save_packet(review_workspace, packet)
    with pytest.raises(ValueError):
        kpi_reviews.load_review_state(review_workspace["root"])


def test_fact_confirmations_alone_do_not_authorize_comparison(review_workspace):
    packet = decided_packet(review_workspace, comparable=False)
    save_packet(review_workspace, packet)
    state = kpi_reviews.load_review_state(review_workspace["root"])
    assert_no_calculation(kpi_reviews.comparison_results(state)[0])


def test_rejected_fact_remains_unavailable_for_comparison(review_workspace):
    packet = decided_packet(review_workspace, comparable=False)
    packet["candidate_reviews"][0]["decision"] = "rejected"
    packet["candidate_reviews"][0]["checks"]["definition"] = False
    packet["candidate_reviews"][0]["notes"] = "Neutral definition mismatch requires correction."
    save_packet(review_workspace, packet)
    state = kpi_reviews.load_review_state(review_workspace["root"])
    assert_no_calculation(kpi_reviews.comparison_results(state)[0])


def test_explicit_not_comparable_pair_does_not_calculate(review_workspace):
    packet = decided_packet(review_workspace)
    pair = packet["comparison_reviews"][0]
    pair["decision"] = "not_comparable"
    pair["checks"]["tax_basis"] = False
    pair["notes"] = "Neutral test tax basis mismatch prevents comparison."
    save_packet(review_workspace, packet)
    state = kpi_reviews.load_review_state(review_workspace["root"])
    assert_no_calculation(kpi_reviews.comparison_results(state)[0])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("scope", "A different neutral consolidation scope"),
        ("basis", "A different neutral tax basis"),
        ("period_start", "2025-04-01"),
    ],
)
def test_approvals_cannot_override_structural_mismatches(review_workspace, field, value):
    review_workspace["records"][1][field] = value
    save_raw(review_workspace)
    save_packet(review_workspace, decided_packet(review_workspace))
    state = kpi_reviews.load_review_state(review_workspace["root"])
    assert_no_calculation(kpi_reviews.comparison_results(state)[0])


@pytest.mark.parametrize("previous", ["0", "-3"])
def test_completed_reviews_do_not_release_zero_or_negative_base_calculations(
    review_workspace, previous
):
    review_workspace["records"][0] = neutral_record(2024, previous)
    save_raw(review_workspace)
    save_packet(review_workspace, decided_packet(review_workspace))
    state = kpi_reviews.load_review_state(review_workspace["root"])
    assert_no_calculation(kpi_reviews.comparison_results(state)[0])


def test_explicit_fact_and_pair_reviews_allow_neutral_calculation_with_both_sources(
    review_workspace,
):
    packet = decided_packet(review_workspace)
    save_packet(review_workspace, packet)
    state = kpi_reviews.load_review_state(review_workspace["root"])
    result = kpi_reviews.comparison_results(state)[0]
    assert result["status"] == "calculated"
    assert not result["reasons"]
    for output_key, raw in zip(
        ("previous_source", "current_source"), review_workspace["records"], strict=True
    ):
        source = result[output_key]
        assert isinstance(source, dict)
        serialized = json.dumps(source)
        for field in ("source_doc_id", "source_sha256", "source_url"):
            assert raw[field] in serialized
        assert 2 in source.values()
    # Neither a calculation nor a review packet mutates the candidate dataset.
    saved = json.loads((review_workspace["root"] / "data/kpi_candidates.json").read_text())
    assert all(item["verified"] is False for item in saved["candidates"])


def test_source_validation_failure_propagates_without_usable_approval(
    review_workspace, monkeypatch
):
    save_packet(review_workspace, decided_packet(review_workspace))

    def invalid_sources(root):
        raise ValueError("Neutral fixture source hash changed")

    monkeypatch.setattr(kpi_reviews, "load_candidates", invalid_sources)
    with pytest.raises(ValueError, match="source hash"):
        kpi_reviews.load_review_state(review_workspace["root"])


@pytest.mark.parametrize("payload", [{}, [], {"schema_version": True}, {"schema_version": 2}])
def test_malformed_packet_schema_fails_closed(review_workspace, payload):
    save_packet(review_workspace, payload)
    with pytest.raises(ValueError):
        kpi_reviews.load_review_state(review_workspace["root"])
