"""Persisted fact-store checks use neutral PDFs and explicit TEST ONLY decisions."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from financial_intelligence_copilot import verified_store
from financial_intelligence_copilot.kpi_reviews import make_review_packet


def save_reviews(workspace: dict, confirmed: int = 0, rejected: int = 0) -> Path:
    packet = make_review_packet(workspace["records"])
    for index, review in enumerate(packet["candidate_reviews"]):
        if index >= confirmed + rejected:
            continue
        accepted = index < confirmed
        review.update(
            decision="confirmed" if accepted else "rejected",
            reviewer="TEST ONLY neutral fixture reviewer",
            reviewed_at="2026-11-08T12:30:00+08:00",
            notes="Explicit test decision over nonfinancial archive counts only.",
            checks=dict.fromkeys(review["checks"], accepted),
        )
    path = workspace["root"] / "data/kpi_reviews.json"
    path.write_text(json.dumps(packet), encoding="utf-8")
    return path


def test_missing_and_pending_reviews_export_no_facts(verified_workspace):
    root = verified_workspace["root"]
    original = verified_workspace["candidate_path"].read_bytes()
    missing = verified_store.build_verified_store(root)
    assert missing["records"] == []
    assert missing["candidate_count"] == missing["pending_count"] == 2
    assert missing["verified_count"] == missing["rejected_count"] == 0
    assert missing["review_packet_present"] is False
    assert missing["input_fingerprints"]["review_packet_sha256"] is None
    save_reviews(verified_workspace)
    pending = verified_store.build_verified_store(root)
    assert pending["records"] == []
    assert pending["review_packet_present"] is True
    assert pending["input_fingerprints"]["review_packet_sha256"] is not None
    assert verified_workspace["candidate_path"].read_bytes() == original


def test_explicit_fact_confirmation_preserves_decimal_evidence_and_review(verified_workspace):
    root = verified_workspace["root"]
    original = verified_workspace["candidate_path"].read_bytes()
    review_path = save_reviews(verified_workspace, confirmed=1, rejected=1)
    review_packet = json.loads(review_path.read_text())
    store = verified_store.build_verified_store(root)
    assert store["verified_count"] == store["rejected_count"] == 1
    assert store["pending_count"] == 0
    assert len(store["records"]) == 1
    record = store["records"][0]
    candidate = verified_workspace["records"][0]
    for key, value in candidate.items():
        if key not in {"verified", "review_status", "reviewer", "reviewed_at"}:
            assert record[key] == value
    assert record["value"] == "10.1250"
    assert record["verified"] is True
    assert record["review_status"] == "confirmed_fact"
    assert record["fact_review"] == review_packet["candidate_reviews"][0]
    assert record["candidate_digest"] == record["fact_review"]["candidate_digest"]
    assert record["reviewer"] == record["fact_review"]["reviewer"]
    assert record["reviewed_at"] == record["fact_review"]["reviewed_at"]
    assert record["comparability_status"] == "needs_owner_review"
    assert "comparisons" not in store
    assert "do not authenticate" in store["notice"]
    assert verified_workspace["candidate_path"].read_bytes() == original


def test_roundtrip_revalidates_and_does_not_require_pair_approval(verified_workspace):
    root = verified_workspace["root"]
    save_reviews(verified_workspace, confirmed=2)
    path = root / "data/processed/reviewed.json"
    result = verified_store.write_verified_store(root, path)
    loaded = verified_store.load_verified_store(root, path)
    assert loaded == result == json.loads(path.read_text())
    assert result["verified_count"] == 2
    assert all(item["comparability_status"] == "needs_owner_review" for item in result["records"])
    assert len(result["input_fingerprints"]["source_pdf_sha256"]) == 2
    assert all(
        not Path(item["local_filename"]).is_absolute()
        for item in result["input_fingerprints"]["source_pdf_sha256"]
    )


def test_existing_output_is_never_overwritten(verified_workspace):
    root = verified_workspace["root"]
    path = root / "existing.json"
    path.write_text("Original retained output")
    with pytest.raises(FileExistsError, match="already exists"):
        verified_store.write_verified_store(root, path)
    assert path.read_text() == "Original retained output"


@pytest.mark.parametrize(
    "relative",
    ["data/kpi_reviews.json", "data/../data/kpi_reviews.json", "data/raw/export.json"],
)
def test_output_cannot_create_missing_review_input_or_raw_data(verified_workspace, relative):
    root = verified_workspace["root"]
    output = root / relative
    original = verified_workspace["candidate_path"].read_bytes()
    with pytest.raises(ValueError, match="Output path must not replace KPI inputs"):
        verified_store.write_verified_store(root, output)
    assert not output.exists()
    assert not (root / "data/kpi_reviews.json").exists()
    assert verified_workspace["candidate_path"].read_bytes() == original


def test_output_symlink_cannot_create_missing_review_input(verified_workspace):
    root = verified_workspace["root"]
    review_path = root / "data/kpi_reviews.json"
    output = root / "review-alias.json"
    output.symlink_to(review_path)
    with pytest.raises(ValueError, match="Output path must not replace KPI inputs"):
        verified_store.write_verified_store(root, output)
    assert output.is_symlink()
    assert not review_path.exists()


def test_output_cannot_recreate_missing_pdf_input(verified_workspace):
    root = verified_workspace["root"]
    output = root / "data/raw/neutral_count_2024.pdf"
    output.unlink()
    with pytest.raises(ValueError, match="Output path must not replace KPI inputs"):
        verified_store.write_verified_store(root, output)
    assert not output.exists()


@pytest.mark.parametrize("change", ["pending", "rejected", "removed", "review_notes"])
def test_revoked_removed_or_changed_reviews_invalidate_old_store(verified_workspace, change):
    root = verified_workspace["root"]
    review_path = save_reviews(verified_workspace, confirmed=2)
    path = root / "reviewed.json"
    verified_store.write_verified_store(root, path)
    original = path.read_bytes()
    if change == "removed":
        review_path.unlink()
    elif change == "pending":
        save_reviews(verified_workspace)
    elif change == "rejected":
        save_reviews(verified_workspace, rejected=2)
    else:
        packet = json.loads(review_path.read_text())
        packet["candidate_reviews"][0]["notes"] += " Revised test qualification."
        review_path.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="stale or modified"):
        verified_store.load_verified_store(root, path)
    assert path.read_bytes() == original


def test_new_pending_packet_invalidates_previous_absent_packet_snapshot(verified_workspace):
    root = verified_workspace["root"]
    path = root / "pending.json"
    verified_store.write_verified_store(root, path)
    save_reviews(verified_workspace)
    with pytest.raises(ValueError, match="stale or modified"):
        verified_store.load_verified_store(root, path)


@pytest.mark.parametrize("change", ["candidate", "manifest", "pdf", "missing_pdf"])
def test_source_and_dataset_edits_invalidate_old_store(verified_workspace, change):
    root = verified_workspace["root"]
    save_reviews(verified_workspace, confirmed=2)
    path = root / "reviewed.json"
    verified_store.write_verified_store(root, path)
    if change == "candidate":
        payload = json.loads(verified_workspace["candidate_path"].read_text())
        payload["candidates"][0]["basis"] += " Revised neutral scope."
        verified_workspace["candidate_path"].write_text(json.dumps(payload))
    elif change == "manifest":
        manifest = root / "data/manifest.csv"
        manifest.write_bytes(manifest.read_bytes() + b"\n")
    else:
        pdf = root / "data/raw/neutral_count_2024.pdf"
        if change == "pdf":
            pdf.write_bytes(pdf.read_bytes() + b"\nchanged neutral test bytes\n")
        else:
            pdf.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        verified_store.load_verified_store(root, path)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(schema_version=True),
        lambda payload: payload.update(schema_version=1.0),
        lambda payload: payload.update(candidate_count=2.0),
        lambda payload: payload.update(verified_count=1),
        lambda payload: payload.update(extra="untrusted"),
        lambda payload: payload["records"].pop(),
        lambda payload: payload["records"].append(deepcopy(payload["records"][0])),
        lambda payload: payload["records"][0].update(verified=1),
        lambda payload: payload["records"][0].update(value="99"),
        lambda payload: payload["records"][0].update(source_pdf_page=True),
        lambda payload: payload["records"][0]["fact_review"].update(reviewer="Forged test name"),
    ],
)
def test_stored_payload_tampering_fails_closed(verified_workspace, mutation):
    root = verified_workspace["root"]
    save_reviews(verified_workspace, confirmed=2)
    path = root / "reviewed.json"
    payload = verified_store.write_verified_store(root, path)
    mutation(payload)
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="stale or modified"):
        verified_store.load_verified_store(root, path)


@pytest.mark.parametrize("text", ["[]", "null", "{}", '{"a":1,"a":2}', '{"x":NaN}'])
def test_invalid_stored_json_is_rejected(verified_workspace, text):
    path = verified_workspace["root"] / "invalid.json"
    path.write_text(text)
    with pytest.raises(ValueError):
        verified_store.load_verified_store(verified_workspace["root"], path)


def test_changed_inputs_during_build_fail_closed(verified_workspace, monkeypatch):
    root = verified_workspace["root"]
    review_path = save_reviews(verified_workspace, confirmed=2)
    original_load = verified_store.load_review_state

    def changing_load(project_root):
        result = original_load(project_root)
        review_path.write_bytes(review_path.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(verified_store, "load_review_state", changing_load)
    with pytest.raises(ValueError, match="inputs changed during validation"):
        verified_store.build_verified_store(root)


def test_changed_inputs_before_write_fail_without_output(verified_workspace, monkeypatch):
    root = verified_workspace["root"]
    review_path = save_reviews(verified_workspace, confirmed=2)
    original_snapshot = verified_store._input_fingerprints
    calls = 0

    def changing_snapshot(project_root):
        nonlocal calls
        calls += 1
        if calls == 3:
            review_path.write_bytes(review_path.read_bytes() + b"\n")
        return original_snapshot(project_root)

    monkeypatch.setattr(verified_store, "_input_fingerprints", changing_snapshot)
    output = root / "must-not-exist.json"
    with pytest.raises(ValueError, match="inputs changed during validation"):
        verified_store.write_verified_store(root, output)
    assert not output.exists()


def test_store_changed_during_validation_fails_closed(verified_workspace, monkeypatch):
    root = verified_workspace["root"]
    output = root / "reviewed.json"
    verified_store.write_verified_store(root, output)
    original_build = verified_store.build_verified_store

    def changing_build(project_root):
        result = original_build(project_root)
        output.write_bytes(output.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(verified_store, "build_verified_store", changing_build)
    with pytest.raises(ValueError, match="store file changed during validation"):
        verified_store.load_verified_store(root, output)


@pytest.mark.parametrize("missing", [True, False])
def test_no_registered_candidates_is_an_explicit_error(verified_workspace, missing):
    path = verified_workspace["candidate_path"]
    if missing:
        path.unlink()
    else:
        path.write_text(json.dumps({"schema_version": 1, "candidates": []}))
    output = verified_workspace["root"] / "must-not-exist.json"
    with pytest.raises(ValueError, match="No local KPI candidates"):
        verified_store.write_verified_store(verified_workspace["root"], output)
    assert not output.exists()
