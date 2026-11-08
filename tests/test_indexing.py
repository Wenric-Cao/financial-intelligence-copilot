"""Provenance and command-line checks using neutral local PDF fixtures."""

import csv
import json
from dataclasses import asdict
from pathlib import Path

import pymupdf
import pytest

from financial_intelligence_copilot.indexing import build_index
from financial_intelligence_copilot.indexing import main as build_main
from financial_intelligence_copilot.pdf_parser import DocumentMetadata, parse_pdf
from financial_intelligence_copilot.retrieval import load_retriever
from financial_intelligence_copilot.retrieval import main as search_main


@pytest.fixture
def local_source(tmp_path: Path):
    raw, processed = tmp_path / "raw", tmp_path / "processed"
    raw.mkdir()
    processed.mkdir()
    source = raw / "neutral_fixture.pdf"
    with pymupdf.open() as document:
        for text in (
            "TEST FIXTURE ONLY\nCedar habitats are described in the first section.",
            "",
            "TEST FIXTURE ONLY\nMarble sculpture is described in the final section.",
        ):
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        document.save(source)
    parsed = parse_pdf(source, DocumentMetadata("TEST-2024-EN", "Test Fixture Issuer", 2024))
    snapshot = processed / "TEST-2024-EN.pages.json"
    snapshot.write_text(json.dumps(parsed.to_dict()), encoding="utf-8")
    row = {
        "doc_id": "TEST-2024-EN",
        "issuer": "Test Fixture Issuer",
        "fiscal_year": "2024",
        "language": "en",
        "source_url": "https://example.invalid/neutral_fixture.pdf",
        "sha256": parsed.sha256,
        "local_filename": source.name,
    }
    manifest = tmp_path / "manifest.csv"
    write_manifest(manifest, row)
    policy = {
        "schema_version": 1,
        "max_words": 10,
        "overlap_words": 2,
        "min_words": 2,
        "excluded_pdf_pages": {"TEST-2024-EN": {"1": "Deliberate test navigation exclusion"}},
    }
    return manifest, raw, processed, policy


def write_manifest(path: Path, row: dict):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


def test_build_is_deterministic_and_source_spans_are_exact(local_source):
    index = build_index(*local_source)
    assert index == build_index(*local_source)
    assert len(index["documents"]) == 1
    assert {chunk["pdf_page"] for chunk in index["chunks"]} == {3}
    assert {page["pdf_page"] for page in index["skipped_pages"]} == {1, 2}
    snapshot = json.loads((local_source[2] / "TEST-2024-EN.pages.json").read_text())
    for chunk in index["chunks"]:
        source_text = snapshot["pages"][chunk["pdf_page"] - 1]["text"]
        assert source_text[chunk["char_start"] : chunk["char_end"]] == chunk["raw_text"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("text", "Altered test content"),
        ("fiscal_year", 9999),
        ("pdf_page", 9999),
        ("pdf_page", 3.0),
        ("fiscal_year", 2024.0),
    ],
)
def test_saved_text_or_metadata_tampering_is_rejected(local_source, field, value):
    snapshot = local_source[2] / "TEST-2024-EN.pages.json"
    data = json.loads(snapshot.read_text())
    data["pages"][2][field] = value
    snapshot.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match PDF page"):
        build_index(*local_source)


def test_changed_raw_bytes_invalidate_source_hash(local_source):
    source = local_source[1] / "neutral_fixture.pdf"
    with source.open("ab") as handle:
        handle.write(b"\n% changed neutral fixture bytes\n")
    with pytest.raises(ValueError, match="Source hash mismatch"):
        build_index(*local_source)


def test_source_path_must_remain_inside_raw_directory(local_source):
    manifest = local_source[0]
    with manifest.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    row["local_filename"] = "../outside.pdf"
    write_manifest(manifest, row)
    with pytest.raises(ValueError, match="inside the raw-data directory"):
        build_index(*local_source)


def test_duplicate_manifest_documents_are_rejected(local_source):
    manifest = local_source[0]
    with manifest.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    with manifest.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=list(row)).writerow(row)
    with pytest.raises(ValueError, match="duplicate document IDs"):
        build_index(*local_source)


def test_unknown_page_policy_document_is_rejected(local_source):
    local_source[3]["excluded_pdf_pages"]["UNKNOWN-DOC"] = {"1": "Unknown test document"}
    with pytest.raises(ValueError, match="unknown documents"):
        build_index(*local_source)


def test_cli_build_search_roundtrip(local_source, tmp_path: Path, capsys):
    manifest, raw, processed, policy = local_source
    policy_path, index_path = tmp_path / "policy.json", tmp_path / "index.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    args = [
        "--manifest",
        str(manifest),
        "--raw-dir",
        str(raw),
        "--pages-dir",
        str(processed),
        "--policy",
        str(policy_path),
        "--output",
        str(index_path),
    ]
    assert build_main(args) == 0
    capsys.readouterr()
    assert (
        search_main(
            [
                "--index",
                str(index_path),
                "--manifest",
                str(manifest),
                "--raw-dir",
                str(raw),
                "--pages-dir",
                str(processed),
                "--policy",
                str(policy_path),
                "--doc-id",
                "TEST-2024-EN",
                "--fiscal-year",
                "2024",
                "--query",
                "Where is marble sculpture described?",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "candidate_evidence"
    assert len(result["hits"]) == 1
    hit = result["hits"][0]
    assert hit["pdf_page"] == 3
    assert hit["fiscal_year"] == 2024
    assert hit["source_url"] == "https://example.invalid/neutral_fixture.pdf"
    assert hit["verification_status"] == "candidate_evidence_only"
    assert "Marble sculpture" in hit["source_excerpt"]
    assert "answer" not in result
    loaded = load_retriever(
        index_path,
        manifest_path=manifest,
        raw_dir=raw,
        pages_dir=processed,
        policy_path=policy_path,
    )
    assert all(asdict(chunk)["pdf_page"] == 3 for chunk in loaded.chunks)
    with pytest.raises(SystemExit) as error:
        build_main(args)
    assert error.value.code == 2


def test_query_report_year_conflict_is_rejected(local_source):
    from financial_intelligence_copilot.chunking import EvidenceChunk
    from financial_intelligence_copilot.retrieval import LexicalRetriever

    retriever = LexicalRetriever(
        EvidenceChunk(**chunk) for chunk in build_index(*local_source)["chunks"]
    )
    with pytest.raises(ValueError, match="different report year"):
        retriever.search(
            "What does the 2025 annual report say?", doc_id="TEST-2024-EN", fiscal_year=2024
        )


def test_historical_fiscal_year_mention_does_not_change_report_scope(local_source):
    from financial_intelligence_copilot.chunking import EvidenceChunk
    from financial_intelligence_copilot.retrieval import LexicalRetriever

    retriever = LexicalRetriever(
        EvidenceChunk(**chunk) for chunk in build_index(*local_source)["chunks"]
    )
    hits = retriever.search(
        "According to the 2024 annual report, what does it say about marble in FY2023?",
        doc_id="TEST-2024-EN",
        fiscal_year=2024,
    )
    assert hits and all(hit.chunk.fiscal_year == 2024 for hit in hits)


@pytest.mark.parametrize(
    "change", ["cached_excerpt", "cached_page_type", "cached_offset_type", "raw_pdf", "policy"]
)
def test_loading_rejects_changed_cache_source_or_policy(local_source, tmp_path, change):
    manifest, raw, processed, policy = local_source
    index = build_index(*local_source)
    if change == "cached_excerpt":
        index["chunks"][0]["raw_text"] = "Altered neutral test excerpt"
    elif change == "cached_page_type":
        index["chunks"][0]["pdf_page"] = float(index["chunks"][0]["pdf_page"])
    elif change == "cached_offset_type":
        assert index["chunks"][0]["char_start"] == 0
        index["chunks"][0]["char_start"] = False
    elif change == "raw_pdf":
        with (raw / "neutral_fixture.pdf").open("ab") as handle:
            handle.write(b"\n% changed after index build\n")
    else:
        policy["max_words"] += 1
    index_path, policy_path = tmp_path / "index.json", tmp_path / "policy.json"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(ValueError, match="mismatch|does not match"):
        load_retriever(
            index_path,
            manifest_path=manifest,
            raw_dir=raw,
            pages_dir=processed,
            policy_path=policy_path,
        )
