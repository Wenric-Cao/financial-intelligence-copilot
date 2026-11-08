"""Session setup uses generated neutral PDFs, never substitute annual-report data."""

import csv
import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from threading import Event

import pymupdf
import pytest

from financial_intelligence_copilot import session_data
from financial_intelligence_copilot.kpi_reviews import make_review_packet
from financial_intelligence_copilot.retrieval import load_retriever
from financial_intelligence_copilot.ui_state import read_documents, workspace_fingerprint
from financial_intelligence_copilot.verified_store import load_verified_store


@pytest.fixture
def session_project(verified_workspace, tmp_path):
    """Route neutral fixture files through the fixed two-year interface schema."""
    project = tmp_path / "source-project"
    shutil.copytree(verified_workspace["root"] / "data", project / "data")
    manifest = project / "data/manifest.csv"
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row.update(
            doc_id=f"AIA-{row['fiscal_year']}-EN",
            issuer="AIA Group Limited",
            notes="TEST ONLY interface routing; generated neutral PDF, not company evidence.",
        )
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    candidate_path = project / "data/kpi_candidates.json"
    payload = json.loads(candidate_path.read_text())
    for candidate in payload["candidates"]:
        candidate.update(
            issuer="AIA Group Limited",
            source_doc_id=f"AIA-{candidate['fiscal_year']}-EN",
        )
    candidate_path.write_text(json.dumps(payload), encoding="utf-8")
    policy = {
        "schema_version": 1,
        "max_words": 50,
        "overlap_words": 5,
        "min_words": 1,
        "excluded_pdf_pages": {},
    }
    (project / "data/retrieval_policy.json").write_text(json.dumps(policy), encoding="utf-8")
    packet = make_review_packet(payload["candidates"])
    (project / "data/kpi_reviews.json").write_text(json.dumps(packet), encoding="utf-8")
    (project / ".env").write_text("TEST_ONLY_SECRET=not-a-real-credential\n", encoding="utf-8")
    (project / "data/processed").mkdir()
    (project / "data/processed/private-history.json").write_text("{}\n", encoding="utf-8")
    uploads = {
        row["doc_id"]: (project / "data/raw" / row["local_filename"]).read_bytes() for row in rows
    }
    return {"root": project, "uploads": uploads, "destination": tmp_path / "workspace"}


def prepare(project, **kwargs):
    return session_data.prepare_session_workspace(
        project["root"],
        kwargs.get("uploads", project["uploads"]),
        kwargs.get("destination", project["destination"]),
    )


def source_bytes(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def assert_no_partial_runtime(project):
    assert not project["destination"].exists()
    assert not list(project["destination"].parent.glob(".fic-session-*"))
    assert not project["destination"].with_name(".workspace.preparing").exists()


def test_prepare_complete_isolated_runtime_preserves_sources_and_pending_decisions(session_project):
    project = session_project
    before = source_bytes(project["root"])
    result = prepare(project)
    root = result["root"]
    assert root == project["destination"]
    assert result["document_count"] == 2 and result["page_count"] == 2
    assert result["chunk_count"] > 0 and result["verified_fact_count"] == 0
    assert result["metadata_fingerprint"] == session_data.session_metadata_fingerprint(
        project["root"]
    )
    assert source_bytes(project["root"]) == before
    assert not (root / ".env").exists()
    assert not (root / "data/processed/private-history.json").exists()
    assert workspace_fingerprint(root, read_documents(root))
    for doc_id, uploaded in project["uploads"].items():
        pages = json.loads((root / f"data/processed/{doc_id}.pages.json").read_text())
        assert pages["pages"][0]["pdf_page"] == 1
        assert pages["sha256"] == hashlib.sha256(uploaded).hexdigest()
    engine = load_retriever(
        root / "data/processed/retrieval-index.json",
        manifest_path=root / "data/manifest.csv",
        raw_dir=root / "data/raw",
        pages_dir=root / "data/processed",
        policy_path=root / "data/retrieval_policy.json",
    )
    assert engine.search("neutral archive", doc_id="AIA-2025-EN", fiscal_year=2025)
    store = load_verified_store(root, root / "data/processed/verified-kpis.json")
    assert store["records"] == [] and store["verified_count"] == 0
    receipt = json.loads((root / "data/processed/session-load-receipt.json").read_text())
    assert datetime.fromisoformat(receipt["prepared_at"]).tzinfo is not None
    assert receipt["kind"] == "user_supplied_session_reports"
    assert (root / "data/manifest.csv").read_bytes() == before[Path("data/manifest.csv")]


@pytest.mark.parametrize("kind", ["missing", "extra", "not_a_mapping", "wrong_hash"])
def test_only_the_two_pinned_report_uploads_are_accepted(session_project, kind):
    uploads = dict(session_project["uploads"])
    if kind == "missing":
        uploads.pop("AIA-2024-EN")
    elif kind == "extra":
        uploads["UNREGISTERED"] = b"not an annual report"
    elif kind == "not_a_mapping":
        uploads = list(uploads.values())
    else:
        uploads["AIA-2024-EN"] += b"\nchanged fixture bytes\n"
    with pytest.raises(ValueError):
        prepare(session_project, uploads=uploads)
    assert_no_partial_runtime(session_project)


@pytest.mark.parametrize("content", [None, "not bytes", b"", bytearray(b"not accepted")])
def test_nonempty_immutable_pdf_bytes_required(session_project, content):
    uploads = {**session_project["uploads"], "AIA-2024-EN": content}
    with pytest.raises(ValueError, match="nonempty PDF bytes"):
        prepare(session_project, uploads=uploads)
    assert_no_partial_runtime(session_project)


def test_size_limit_is_checked_before_parsing(session_project, monkeypatch):
    monkeypatch.setattr(session_data, "MAX_REPORT_BYTES", 10)

    def never_parse(*args, **kwargs):
        raise AssertionError("Oversize uploads must not reach PDF parsing")

    monkeypatch.setattr(session_data, "parse_pdf", never_parse)
    with pytest.raises(ValueError, match="no larger"):
        prepare(session_project)
    assert_no_partial_runtime(session_project)


def test_existing_destination_is_not_overwritten(session_project):
    destination = session_project["destination"]
    destination.mkdir()
    marker = destination / "preserve.txt"
    marker.write_text("original owner file", encoding="utf-8")
    with pytest.raises(FileExistsError):
        prepare(session_project)
    assert marker.read_text() == "original owner file"


@pytest.mark.parametrize("relative", [".", "data/session-workspace", "data/raw/runtime"])
def test_destination_cannot_enter_source_project(session_project, relative):
    destination = session_project["root"] / relative
    with pytest.raises((ValueError, FileExistsError)):
        prepare(session_project, destination=destination)
    assert not (session_project["root"] / "data/raw/runtime").exists()


def test_destination_symlink_is_not_followed(session_project):
    destination = session_project["destination"]
    destination.symlink_to(session_project["root"] / "missing", target_is_directory=True)
    with pytest.raises(FileExistsError):
        prepare(session_project)
    assert destination.is_symlink()
    assert not (session_project["root"] / "missing").exists()


@pytest.mark.parametrize(
    "field,value", [("sha256", "not-a-pin"), ("local_filename", "../escape.pdf")]
)
def test_malformed_registered_identity_fails_without_publication(session_project, field, value):
    manifest = session_project["root"] / "data/manifest.csv"
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0][field] = value
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):
        prepare(session_project)
    assert_no_partial_runtime(session_project)


def test_public_metadata_symlink_cannot_copy_an_outside_file(session_project):
    path = session_project["root"] / "data/evaluation_cases.json"
    outside = session_project["root"].parent / "private.json"
    outside.write_text('{"TEST_ONLY_PRIVATE":"not a real credential"}', encoding="utf-8")
    path.symlink_to(outside)
    with pytest.raises(ValueError, match="regular files inside"):
        prepare(session_project)
    assert_no_partial_runtime(session_project)


def test_metadata_edits_abort_staged_runtime(session_project, monkeypatch):
    original = session_data.build_index

    def changed_metadata(*args, **kwargs):
        policy = session_project["root"] / "data/retrieval_policy.json"
        policy.write_bytes(policy.read_bytes() + b"\n")
        return original(*args, **kwargs)

    monkeypatch.setattr(session_data, "build_index", changed_metadata)
    with pytest.raises(ValueError, match="metadata changed"):
        prepare(session_project)
    assert_no_partial_runtime(session_project)


def test_publish_does_not_replace_a_destination_created_during_validation(
    session_project, monkeypatch
):
    original = session_data.load_retriever

    def destination_appeared(*args, **kwargs):
        result = original(*args, **kwargs)
        session_project["destination"].mkdir()
        (session_project["destination"] / "owner.txt").write_text("preserve", encoding="utf-8")
        return result

    monkeypatch.setattr(session_data, "load_retriever", destination_appeared)
    with pytest.raises(FileExistsError, match="appeared"):
        prepare(session_project)
    assert (session_project["destination"] / "owner.txt").read_text() == "preserve"
    assert not list(session_project["destination"].parent.glob(".fic-session-*"))


def test_no_ready_destination_is_visible_before_validation(session_project, monkeypatch):
    original = session_data.load_retriever

    def not_published(*args, **kwargs):
        assert not session_project["destination"].exists()
        return original(*args, **kwargs)

    monkeypatch.setattr(session_data, "load_retriever", not_published)
    assert prepare(session_project)["root"].is_dir()


def test_concurrent_calls_cannot_prepare_the_same_destination(session_project, monkeypatch):
    original = session_data.build_index
    entered, proceed = Event(), Event()

    def pause_build(*args, **kwargs):
        entered.set()
        assert proceed.wait(timeout=5), "Test release signal was not received"
        return original(*args, **kwargs)

    monkeypatch.setattr(session_data, "build_index", pause_build)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(prepare, session_project)
        try:
            assert entered.wait(timeout=5)
            with pytest.raises(FileExistsError, match="already being prepared"):
                prepare(session_project)
        finally:
            proceed.set()
        assert first.result(timeout=5)["document_count"] == 2


def test_sessions_do_not_share_raw_files(session_project):
    first = prepare(session_project)["root"]
    second = prepare(
        session_project, destination=session_project["destination"].with_name("second-workspace")
    )["root"]
    filename = read_documents(first)[0]["local_filename"]
    (first / "data/raw" / filename).write_bytes(b"TEST ONLY: one session changed its own file")
    assert (second / "data/raw" / filename).read_bytes() == (
        session_project["root"] / "data/raw" / filename
    ).read_bytes()


def test_metadata_fingerprint_includes_optional_absence_and_exact_bytes(session_project):
    root = session_project["root"]
    before = session_data.session_metadata_fingerprint(root)
    path = root / "pyproject.toml"
    path.write_text("# TEST ONLY optional configuration\n", encoding="utf-8")
    added = session_data.session_metadata_fingerprint(root)
    assert added != before
    path.write_text("# TEST ONLY optional configuration\n\n", encoding="utf-8")
    assert session_data.session_metadata_fingerprint(root) not in {before, added}
    path.unlink()
    assert session_data.session_metadata_fingerprint(root) == before


def test_page_extraction_failure_is_not_published(session_project, monkeypatch):
    original = session_data.parse_pdf

    def failed_page(*args, **kwargs):
        parsed = original(*args, **kwargs)
        page = replace(
            parsed.pages[0], status="extraction_error", text="", error="TEST ONLY failure"
        )
        return replace(parsed, pages=(page,))

    monkeypatch.setattr(session_data, "parse_pdf", failed_page)
    with pytest.raises(ValueError, match="page extraction"):
        prepare(session_project)
    assert_no_partial_runtime(session_project)


def test_blank_report_is_not_published_even_with_matching_pin(session_project):
    root = session_project["root"]
    with pymupdf.open() as document:
        document.new_page()
        blank = document.tobytes()
    manifest = root / "data/manifest.csv"
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["sha256"] = hashlib.sha256(blank).hexdigest()
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    uploads = {**session_project["uploads"], rows[0]["doc_id"]: blank}
    with pytest.raises(ValueError, match="no extractable native text"):
        prepare(session_project, uploads=uploads)
    assert_no_partial_runtime(session_project)


def test_empty_page_keeps_its_physical_number_in_an_otherwise_valid_report(session_project):
    root = session_project["root"]
    manifest = root / "data/manifest.csv"
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    selected = rows[1]
    original = session_project["uploads"][selected["doc_id"]]
    with pymupdf.open(stream=original, filetype="pdf") as document:
        document.new_page()
        content = document.tobytes()
    selected["sha256"] = hashlib.sha256(content).hexdigest()
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    candidates = root / "data/kpi_candidates.json"
    payload = json.loads(candidates.read_text())
    for record in payload["candidates"]:
        if record["source_doc_id"] == selected["doc_id"]:
            record["source_sha256"] = selected["sha256"]
    candidates.write_text(json.dumps(payload), encoding="utf-8")
    (root / "data/kpi_reviews.json").write_text(
        json.dumps(make_review_packet(payload["candidates"])), encoding="utf-8"
    )
    uploads = {**session_project["uploads"], selected["doc_id"]: content}
    result = prepare(session_project, uploads=uploads)
    assert result["page_count"] == 3
    pages = json.loads(
        (result["root"] / f"data/processed/{selected['doc_id']}.pages.json").read_text()
    )["pages"]
    assert [page["pdf_page"] for page in pages] == [1, 2]
    assert pages[1]["status"] == "empty_text" and pages[1]["text"] == ""


def test_actual_recorded_fixture_decisions_are_preserved_without_creating_new_ones(session_project):
    root = session_project["root"]
    review_path = root / "data/kpi_reviews.json"
    packet = json.loads(review_path.read_text())
    for review in packet["candidate_reviews"]:
        review.update(
            decision="confirmed",
            reviewer="TEST ONLY neutral fixture reviewer",
            reviewed_at="2026-11-08T12:00:00+08:00",
            notes="Explicit test-only decision over nonfinancial fixture counts.",
            checks=dict.fromkeys(review["checks"], True),
        )
    review_path.write_text(json.dumps(packet), encoding="utf-8")
    before = source_bytes(root)
    result = prepare(session_project)
    assert result["verified_fact_count"] == 2
    assert source_bytes(root) == before
    copied = json.loads((result["root"] / "data/kpi_reviews.json").read_text())
    assert copied == packet
    assert all(review["decision"] == "pending" for review in copied["comparison_reviews"])
    candidates = json.loads((result["root"] / "data/kpi_candidates.json").read_text())
    assert all(record["verified"] is False for record in candidates["candidates"])
