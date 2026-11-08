"""Cloud bootstrap tests use neutral PDFs and never substitute company evidence."""

import csv
import gc
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.client import IncompleteRead
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import URLError

import pytest

from financial_intelligence_copilot import cloud_data
from financial_intelligence_copilot.kpi_reviews import make_review_packet
from financial_intelligence_copilot.ui_state import read_documents, workspace_fingerprint
from financial_intelligence_copilot.verified_store import load_verified_store


@pytest.fixture
def cloud_project(verified_workspace, tmp_path, monkeypatch):
    """Route marked neutral PDFs through the fixed interface; no network is used."""
    source = verified_workspace["root"]
    root = tmp_path / "clean-checkout"
    (root / "data").mkdir(parents=True)
    with (source / "data/manifest.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    pins = {key: dict(value) for key, value in cloud_data.OFFICIAL_REPORTS.items()}
    reports = {}
    for row in rows:
        doc_id = f"AIA-{row['fiscal_year']}-EN"
        pin = pins[doc_id]
        reports[pin["url"]] = (source / "data/raw" / row["local_filename"]).read_bytes()
        pin["sha256"] = row["sha256"]
        row.update(
            doc_id=doc_id,
            issuer="AIA Group Limited",
            source_url=pin["url"],
            local_filename=pin["filename"],
            notes="TEST ONLY interface routing; neutral PDF, not company evidence.",
        )
    with (root / "data/manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    candidates = json.loads((source / "data/kpi_candidates.json").read_text())["candidates"]
    for candidate in candidates:
        doc_id = f"AIA-{candidate['fiscal_year']}-EN"
        candidate.update(
            issuer="AIA Group Limited", source_doc_id=doc_id, source_url=pins[doc_id]["url"]
        )
    (root / "data/kpi_candidates.json").write_text(
        json.dumps({"schema_version": 1, "candidates": candidates}), encoding="utf-8"
    )
    (root / "data/kpi_reviews.json").write_text(
        json.dumps(make_review_packet(candidates)), encoding="utf-8"
    )
    (root / "data/retrieval_policy.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "max_words": 50,
                "overlap_words": 5,
                "min_words": 1,
                "excluded_pdf_pages": {},
            }
        ),
        encoding="utf-8",
    )
    (root / ".env").write_text("TEST_ONLY_SECRET=not-a-real-credential\n", encoding="utf-8")
    runtime_parent = tmp_path / "temporary-runtime"
    runtime_parent.mkdir()
    monkeypatch.setattr(cloud_data, "OFFICIAL_REPORTS", pins)
    monkeypatch.setattr(
        cloud_data,
        "TemporaryDirectory",
        lambda **kwargs: TemporaryDirectory(dir=runtime_parent, **kwargs),
    )
    return {"root": root, "reports": reports, "runtime_parent": runtime_parent}


def all_bytes(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_complete_runtime_is_reused_across_callers_without_source_or_review_edits(cloud_project):
    cache = cloud_data.CloudWorkspaceCache()
    project = cloud_project["root"]
    before = all_bytes(project)
    calls = []

    def fetch(url):
        calls.append(url)
        return cloud_project["reports"][url]

    first = cache.get(project, fetcher=fetch)
    second = cache.get(project, fetcher=fetch)
    assert len(calls) == 2
    assert first["root"] == second["root"]
    assert first["_workspace_owner"] is second["_workspace_owner"]
    assert first["document_count"] == 2 and first["page_count"] == 2
    assert first["chunk_count"] > 0 and first["verified_fact_count"] == 0
    assert not first["root"].is_relative_to(project)
    assert not (first["root"] / ".env").exists()
    assert all_bytes(project) == before
    assert not (project / "data/raw").exists()
    assert not (project / "data/processed").exists()
    assert (
        workspace_fingerprint(first["root"], read_documents(first["root"]))
        == first["workspace_fingerprint"]
    )
    store = load_verified_store(first["root"], first["root"] / "data/processed/verified-kpis.json")
    assert store["records"] == [] and store["verified_count"] == 0
    receipt = json.loads((first["root"] / "data/processed/session-load-receipt.json").read_text())
    assert receipt["kind"] == "official_runtime_download"
    assert len(receipt["downloads"]) == 2
    assert all(
        datetime.fromisoformat(item["downloaded_at"]).tzinfo for item in receipt["downloads"]
    )
    assert (first["root"] / "data/manifest.csv").read_bytes() == before[Path("data/manifest.csv")]


def test_concurrent_visitors_download_and_prepare_only_once(cloud_project):
    cache = cloud_data.CloudWorkspaceCache()
    calls = []

    def fetch(url):
        calls.append(url)
        return cloud_project["reports"][url]

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: cache.get(cloud_project["root"], fetcher=fetch), range(4))
        )
    assert len(calls) == 2
    assert len({item["root"] for item in results}) == 1
    assert len({id(item["_workspace_owner"]) for item in results}) == 1


@pytest.mark.parametrize("mode", ["network", "hash", "empty", "oversize", "wrong_type", "parse"])
def test_failure_leaves_no_partial_workspace_and_can_retry(cloud_project, monkeypatch, mode):
    cache = cloud_data.CloudWorkspaceCache()
    before = all_bytes(cloud_project["root"])

    def broken(url):
        if mode == "network":
            raise cloud_data.CloudDataError("TEST ONLY download unavailable")
        content = cloud_project["reports"][url]
        if mode == "hash":
            return content + b"TEST ONLY changed fixture"
        if mode == "empty":
            return b""
        if mode == "oversize":
            return b"x" * (cloud_data.MAX_REPORT_BYTES + 1)
        if mode == "wrong_type":
            return bytearray(content)
        return content

    original = cloud_data.prepare_session_workspace
    if mode == "parse":

        def fail_prepare(*args, **kwargs):
            raise ValueError("TEST ONLY extraction failed")

        monkeypatch.setattr(cloud_data, "prepare_session_workspace", fail_prepare)
    with pytest.raises((ValueError, OSError)):
        cache.get(cloud_project["root"], fetcher=broken)
    assert not list(cloud_project["runtime_parent"].iterdir())
    assert all_bytes(cloud_project["root"]) == before
    monkeypatch.setattr(cloud_data, "prepare_session_workspace", original)
    assert cache.get(cloud_project["root"], fetcher=cloud_project["reports"].__getitem__)[
        "root"
    ].exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_url", "https://example.invalid/report.pdf"),
        ("source_url", "https://www.aia.com/other.pdf"),
        ("source_url", "https://www.aia.com:443/other.pdf"),
        ("sha256", "0" * 64),
        ("local_filename", "unexpected.pdf"),
        ("issuer", "Unregistered Company"),
        ("fiscal_year", "2026"),
    ],
)
def test_manifest_changes_cannot_expand_network_allowlist(cloud_project, field, value):
    manifest = cloud_project["root"] / "data/manifest.csv"
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0][field] = value
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def never_fetch(url):
        raise AssertionError("An invalid manifest must fail before network access")

    with pytest.raises(ValueError):
        cloud_data.CloudWorkspaceCache().get(cloud_project["root"], fetcher=never_fetch)
    assert not list(cloud_project["runtime_parent"].iterdir())


def test_metadata_revision_rebuild_retains_old_caller_lifetime(cloud_project):
    cache = cloud_data.CloudWorkspaceCache()
    fetch = cloud_project["reports"].__getitem__
    first = cache.get(cloud_project["root"], fetcher=fetch)
    old_root = first["root"]
    policy = cloud_project["root"] / "data/retrieval_policy.json"
    policy.write_bytes(policy.read_bytes() + b"\n")
    second = cache.get(cloud_project["root"], fetcher=fetch)
    assert first["metadata_fingerprint"] != second["metadata_fingerprint"]
    assert old_root.exists() and second["root"].exists()
    del first
    gc.collect()
    assert not old_root.exists()
    assert second["root"].exists()


def test_failed_new_revision_never_returns_previous_cached_data(cloud_project):
    cache = cloud_data.CloudWorkspaceCache()
    first = cache.get(cloud_project["root"], fetcher=cloud_project["reports"].__getitem__)
    path = cloud_project["root"] / "data/kpi_reviews.json"
    path.write_bytes(path.read_bytes() + b"\n")

    def unavailable(url):
        raise cloud_data.CloudDataError("TEST ONLY download unavailable")

    with pytest.raises(cloud_data.CloudDataError, match="unavailable"):
        cache.get(cloud_project["root"], fetcher=unavailable)
    assert first["root"].exists()


def test_metadata_change_during_download_aborts_before_preparation(cloud_project):
    cache = cloud_data.CloudWorkspaceCache()

    def changed(url):
        path = cloud_project["root"] / "data/retrieval_policy.json"
        path.write_bytes(path.read_bytes() + b"\n")
        return cloud_project["reports"][url]

    with pytest.raises(cloud_data.CloudDataError, match="changed during download"):
        cache.get(cloud_project["root"], fetcher=changed)
    assert not list(cloud_project["runtime_parent"].iterdir())


@pytest.mark.parametrize("kind", ["changed", "missing"])
def test_cached_source_tampering_fails_closed_then_retry_rebuilds(cloud_project, kind):
    cache = cloud_data.CloudWorkspaceCache()
    first = cache.get(cloud_project["root"], fetcher=cloud_project["reports"].__getitem__)
    source = next((first["root"] / "data/raw").iterdir())
    if kind == "missing":
        source.unlink()
    else:
        source.write_bytes(source.read_bytes() + b"TEST ONLY changed fixture")
    with pytest.raises(cloud_data.CloudDataError, match="cached report workspace"):
        cache.get(cloud_project["root"], fetcher=cloud_project["reports"].__getitem__)
    second = cache.get(cloud_project["root"], fetcher=cloud_project["reports"].__getitem__)
    assert first["root"] != second["root"]


def test_explicit_retry_keeps_adopted_workspace_alive_but_rebuilds_cache(cloud_project):
    cache = cloud_data.CloudWorkspaceCache()
    first = cache.get(cloud_project["root"], fetcher=cloud_project["reports"].__getitem__)
    cache.invalidate(cloud_project["root"] / "different-project")
    assert cache.get(cloud_project["root"])["root"] == first["root"]
    cache.invalidate(cloud_project["root"])
    assert first["root"].exists()
    second = cache.get(cloud_project["root"], fetcher=cloud_project["reports"].__getitem__)
    assert first["root"] != second["root"]
    old_root = first["root"]
    del first
    gc.collect()
    assert not old_root.exists()


def test_process_restart_simulation_downloads_again(cloud_project):
    calls = []

    def fetch(url):
        calls.append(url)
        return cloud_project["reports"][url]

    first = cloud_data.CloudWorkspaceCache().get(cloud_project["root"], fetcher=fetch)
    second = cloud_data.CloudWorkspaceCache().get(cloud_project["root"], fetcher=fetch)
    assert first["root"] != second["root"] and len(calls) == 4


class Response(io.BytesIO):
    def __init__(self, content, url, *, headers=None, status=200):
        super().__init__(content)
        self.url = url
        self.headers = {} if headers is None else headers
        self.status = status
        self.read_sizes = []

    def geturl(self):
        return self.url

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


def install_response(monkeypatch, response):
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append((request, timeout))
            return response

    def opener(handler):
        assert isinstance(handler, cloud_data._RejectRedirects)
        return Opener()

    monkeypatch.setattr(cloud_data, "build_opener", opener)
    return calls


def test_http_fetch_is_bounded_and_uses_only_exact_registered_url(monkeypatch):
    url = cloud_data.OFFICIAL_REPORTS["AIA-2024-EN"]["url"]
    content = b"TEST ONLY transport fixture"
    response = Response(content, url, headers={"Content-Length": str(len(content))})
    calls = install_response(monkeypatch, response)
    assert cloud_data._download_report(url) == content
    assert len(calls) == 1 and calls[0][0].full_url == url
    assert calls[0][1] == cloud_data.DOWNLOAD_TIMEOUT_SECONDS
    assert all(0 < size <= cloud_data.DOWNLOAD_CHUNK_BYTES for size in response.read_sizes)


@pytest.mark.parametrize(
    "url",
    [
        "http://www.aia.com/report.pdf",
        "https://www.aia.com.evil.invalid/report.pdf",
        "https://www.aia.com@127.0.0.1/report.pdf",
        "https://www.aia.com:443/report.pdf",
        "https://www.aia.com/other.pdf",
        "file:///tmp/report.pdf",
    ],
)
def test_unapproved_transport_urls_never_reach_opener(monkeypatch, url):
    monkeypatch.setattr(
        cloud_data, "build_opener", lambda *args: pytest.fail("Network must not be reached")
    )
    with pytest.raises(cloud_data.CloudDataError, match="registered official"):
        cloud_data._download_report(url)


@pytest.mark.parametrize("target", ["https://www.aia.com/new.pdf", "http://127.0.0.1/private"])
def test_redirect_is_rejected_before_any_followup_request(target):
    response = io.BytesIO(b"TEST ONLY redirect response")
    with pytest.raises(cloud_data.CloudDataError, match="redirected"):
        cloud_data._RejectRedirects().redirect_request(None, response, 302, "Found", {}, target)
    assert response.closed


@pytest.mark.parametrize(
    "content,headers,status,url_suffix,message",
    [
        (b"", {}, 200, "", "empty"),
        (b"abc", {"Content-Length": "invalid"}, 200, "", "invalid content length"),
        (b"abc", {"Content-Length": "4"}, 200, "", "incomplete"),
        (b"abc", {"Content-Length": "0"}, 200, "", "download limit"),
        (b"abc", {"Content-Length": str(17 * 1024 * 1024)}, 200, "", "download limit"),
        (b"abc", {"Content-Encoding": "gzip"}, 200, "", "content encoding"),
        (b"abc", {}, 201, "", "registered URL"),
        (b"abc", {}, 200, "?unexpected", "registered URL"),
    ],
)
def test_bad_transport_response_fails_closed(
    monkeypatch, content, headers, status, url_suffix, message
):
    url = cloud_data.OFFICIAL_REPORTS["AIA-2024-EN"]["url"]
    response = Response(content, url + url_suffix, headers=headers, status=status)
    install_response(monkeypatch, response)
    with pytest.raises(cloud_data.CloudDataError, match=message):
        cloud_data._download_report(url)


def test_stream_limit_does_not_depend_on_content_length(monkeypatch):
    monkeypatch.setattr(cloud_data, "MAX_REPORT_BYTES", 20)
    url = cloud_data.OFFICIAL_REPORTS["AIA-2024-EN"]["url"]
    response = Response(b"x" * 50, url)
    install_response(monkeypatch, response)
    with pytest.raises(cloud_data.CloudDataError, match="download limit"):
        cloud_data._download_report(url)
    assert response.read_sizes == [21]


def test_download_deadline_rejects_a_slow_body(monkeypatch):
    url = cloud_data.OFFICIAL_REPORTS["AIA-2024-EN"]["url"]
    install_response(monkeypatch, Response(b"TEST ONLY transport fixture", url))
    clock = iter([0, 1, cloud_data.DOWNLOAD_DEADLINE_SECONDS + 1])
    monkeypatch.setattr(cloud_data.time, "monotonic", lambda: next(clock))
    with pytest.raises(cloud_data.CloudDataError, match="time limit"):
        cloud_data._download_report(url)


def test_network_error_has_an_actionable_retry_and_upload_message(monkeypatch):
    class Opener:
        def open(self, request, timeout):
            raise URLError("TEST ONLY network unavailable")

    monkeypatch.setattr(cloud_data, "build_opener", lambda *args: Opener())
    with pytest.raises(cloud_data.CloudDataError, match="Retry initialization.*upload controls"):
        cloud_data._download_report(cloud_data.OFFICIAL_REPORTS["AIA-2024-EN"]["url"])


def test_interrupted_body_is_closed_and_reported_as_retryable(monkeypatch):
    url = cloud_data.OFFICIAL_REPORTS["AIA-2024-EN"]["url"]

    class InterruptedResponse(Response):
        def read(self, size=-1):
            raise IncompleteRead(b"TEST ONLY incomplete bytes", 100)

    response = InterruptedResponse(b"", url)
    install_response(monkeypatch, response)
    with pytest.raises(cloud_data.CloudDataError, match="Retry initialization"):
        cloud_data._download_report(url)
    assert response.closed
