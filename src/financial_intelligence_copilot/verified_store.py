"""Persist source-bound fact confirmations without approving financial comparability."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path

from financial_intelligence_copilot.kpi_reviews import load_review_state

NOTICE = (
    "Only explicitly confirmed facts are included. Recorded reviewer names and content hashes "
    "do not authenticate human identity. Fact confirmation does not approve pair comparability. "
    "Revalidate this local snapshot against current sources and reviews before use."
)


def _file_hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _input_fingerprints(root: Path) -> dict:
    """Fingerprint complete input bytes, including an absent review packet."""
    candidate_path = root / "data/kpi_candidates.json"
    if not candidate_path.is_file():
        raise ValueError("No local KPI candidates are registered")
    manifest_path = root / "data/manifest.csv"
    manifest_bytes = manifest_path.read_bytes()
    manifest = list(csv.DictReader(io.StringIO(manifest_bytes.decode("utf-8"))))
    sources = []
    raw_root = (root / "data/raw").resolve()
    for row in manifest:
        source = (raw_root / row["local_filename"]).resolve()
        if not source.is_relative_to(raw_root):
            raise ValueError("Candidate source path leaves the raw-data directory")
        sources.append(
            {
                "doc_id": row["doc_id"],
                "local_filename": row["local_filename"],
                "sha256": _file_hash(source),
            }
        )
    review_path = root / "data/kpi_reviews.json"
    return {
        "candidate_dataset_sha256": _file_hash(candidate_path),
        "review_packet_sha256": _file_hash(review_path) if review_path.is_file() else None,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_pdf_sha256": sorted(sources, key=lambda row: row["doc_id"]),
    }


def _json_ready(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _canonical(payload: dict) -> str:
    """Compare JSON types as well as values; Python equality conflates true and 1."""
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )


def _assert_current(root: Path, payload: dict) -> None:
    if _input_fingerprints(root) != payload["input_fingerprints"]:
        raise ValueError("KPI store inputs changed during validation; retry with stable files")


def build_verified_store(root: Path) -> dict:
    """Recheck actual PDFs and promote only explicit, source-bound fact decisions.

    The candidate dataset stays unverified. This derived snapshot contains only
    recorded fact confirmations, without granting annual-pair comparability.
    Before/after fingerprints detect observed changes; they are not file locks.
    """
    root = Path(root)
    before = _input_fingerprints(root)
    state = load_review_state(root)
    if not state["candidates"]:
        raise ValueError("No local KPI candidates are registered")
    decisions = {item["candidate_id"]: item for item in state["packet"]["candidate_reviews"]}
    records = []
    for candidate in state["candidates"]:
        review = decisions[candidate["candidate_id"]]
        if review["decision"] != "confirmed":
            continue
        record = _json_ready(candidate)
        record.update(
            verified=True,
            review_status="confirmed_fact",
            reviewer=review["reviewer"],
            reviewed_at=review["reviewed_at"],
            candidate_digest=review["candidate_digest"],
            fact_review=_json_ready(review),
        )
        records.append(record)
    payload = {
        "schema_version": 1,
        "kind": "source_bound_verified_kpi_store",
        "notice": NOTICE,
        "input_fingerprints": before,
        "review_packet_present": state["packet_present"],
        "candidate_count": len(state["candidates"]),
        "verified_count": len(records),
        "pending_count": sum(item["decision"] == "pending" for item in decisions.values()),
        "rejected_count": sum(item["decision"] == "rejected" for item in decisions.values()),
        "records": records,
    }
    _canonical(payload)
    _assert_current(root, payload)
    return payload


def write_verified_store(root: Path, output: Path) -> dict:
    """Create a new local snapshot only; preserve every preexisting output."""
    root, output = Path(root), Path(output)
    if output.exists():
        raise FileExistsError("Output already exists; preserve it and choose a new filename")
    resolved_output = output.resolve()
    protected_inputs = {
        (root / relative).resolve()
        for relative in ("data/kpi_candidates.json", "data/kpi_reviews.json", "data/manifest.csv")
    }
    if resolved_output in protected_inputs or resolved_output.is_relative_to(
        (root / "data/raw").resolve()
    ):
        raise ValueError("Output path must not replace KPI inputs or enter the raw-data directory")
    payload = build_verified_store(root)
    serialized = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    _assert_current(root, payload)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(serialized)
    return payload


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("KPI store JSON contains duplicate object keys")
        result[key] = value
    return result


def _reject_constant(value: str):
    raise ValueError(f"KPI store JSON contains a non-finite constant: {value}")


def load_verified_store(root: Path, path: Path) -> dict:
    """Rebuild from live sources/reviews and reject any stale or edited snapshot.

    Callers must use this loader, not trust the stored `verified` flag directly.
    A previously confirmed fact disappears after review revocation. The immutable
    old export is retained for audit but cannot be reused as a current store.
    """
    path = Path(path)
    before = path.read_bytes()
    payload = json.loads(before, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("Invalid verified KPI store schema")
    expected = build_verified_store(root)
    if path.read_bytes() != before:
        raise ValueError("KPI store file changed during validation")
    if _canonical(payload) != _canonical(expected):
        raise ValueError("Verified KPI store is stale or modified; create a fresh snapshot")
    return expected
