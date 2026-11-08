"""Build a shared, temporary runtime from the two pinned official AIA sources.

This module performs no financial or evaluation review. Original reports and
derived files remain outside the source checkout. The process cache survives
browser-session changes, but a server restart requires downloading them again.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http.client import HTTPException
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from financial_intelligence_copilot.session_data import (
    MAX_REPORT_BYTES,
    prepare_session_workspace,
    session_metadata_fingerprint,
)
from financial_intelligence_copilot.ui_state import read_documents, workspace_fingerprint

OFFICIAL_REPORTS = {
    "AIA-2024-EN": {
        "url": (
            "https://www.aia.com/content/dam/group-wise/en/docs/investor-relations/2025/"
            "2024%20Annual%20Report%20%28Eng%29.pdf"
        ),
        "sha256": "0e888a5752d71ac8c841c234212cd3fc0cca9f16991db1f36a774f13b97890e3",
        "filename": "AIA_2024_Annual_Report_EN.pdf",
    },
    "AIA-2025-EN": {
        "url": (
            "https://www.aia.com/content/dam/group-wise/en/docs/investor-relations/2025/"
            "AIA%202025%20annual%20report_EN.pdf"
        ),
        "sha256": "18537f928c3bb4879c35566252f2f8420c6a3a237016af4706b081a77d126977",
        "filename": "AIA_2025_Annual_Report_EN.pdf",
    },
}
DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOAD_DEADLINE_SECONDS = 90
DOWNLOAD_CHUNK_BYTES = 64 * 1024
ReportFetcher = Callable[[str], bytes]


class CloudDataError(ValueError):
    """An official runtime could not be prepared without bypassing source checks."""


def _allowed_url(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.netloc == "www.aia.com"
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and url in {item["url"] for item in OFFICIAL_REPORTS.values()}
    )


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if fp is not None:
            fp.close()
        raise CloudDataError(
            "The registered official source redirected. Review the new source before retrying."
        )


def _download_report(url: str) -> bytes:
    """Download one exact HTTPS source, rejecting every redirect and oversized body."""
    if not _allowed_url(url):
        raise CloudDataError("Only the two registered official AIA report URLs may be fetched.")
    request = Request(
        url,
        headers={
            "User-Agent": "FinancialIntelligenceCopilot/0.1 official-report bootstrap",
            "Accept": "application/pdf",
            "Accept-Encoding": "identity",
        },
    )
    started = time.monotonic()
    try:
        with build_opener(_RejectRedirects()).open(
            request, timeout=DOWNLOAD_TIMEOUT_SECONDS
        ) as response:
            if response.geturl() != url or response.status != 200:
                raise CloudDataError(
                    "The official report response did not match its registered URL."
                )
            encoding = response.headers.get("Content-Encoding", "identity").lower().strip()
            if encoding not in {"", "identity"}:
                raise CloudDataError("The official report used an unsupported content encoding.")
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    expected_length = int(length)
                except ValueError as exc:
                    raise CloudDataError(
                        "The official report has an invalid content length."
                    ) from exc
                if not 0 < expected_length <= MAX_REPORT_BYTES:
                    raise CloudDataError("The official report exceeds the 16 MiB download limit.")
            content = bytearray()
            while True:
                if time.monotonic() - started > DOWNLOAD_DEADLINE_SECONDS:
                    raise CloudDataError("The official report download exceeded its time limit.")
                chunk = response.read(
                    min(DOWNLOAD_CHUNK_BYTES, MAX_REPORT_BYTES + 1 - len(content))
                )
                if time.monotonic() - started > DOWNLOAD_DEADLINE_SECONDS:
                    raise CloudDataError("The official report download exceeded its time limit.")
                if not chunk:
                    break
                content.extend(chunk)
                if len(content) > MAX_REPORT_BYTES:
                    raise CloudDataError("The official report exceeds the 16 MiB download limit.")
            if length is not None and len(content) != expected_length:
                raise CloudDataError("The official report download was incomplete.")
            if not content:
                raise CloudDataError("The official report download was empty.")
            return bytes(content)
    except (HTTPError, URLError, HTTPException, OSError, TimeoutError) as exc:
        raise CloudDataError(
            "The official AIA download was unavailable. Retry initialization or load the two "
            "registered PDFs using the upload controls."
        ) from exc


def _registered_documents(root: Path) -> list[dict]:
    documents = read_documents(root)
    for item in documents:
        pin = OFFICIAL_REPORTS[item["doc_id"]]
        if (
            not _allowed_url(item["source_url"])
            or item["source_url"] != pin["url"]
            or item.get("sha256") != pin["sha256"]
            or item["local_filename"] != pin["filename"]
        ):
            raise CloudDataError(
                "The source manifest differs from the two approved download identities. "
                "Review source changes before enabling automatic initialization."
            )
    return documents


@dataclass
class _WorkspaceOwner:
    """Keep temporary files alive while the cache or a caller still holds this object."""

    temporary: TemporaryDirectory
    project_root: Path
    metadata_fingerprint: str
    source_fingerprint: str
    stats: dict


class CloudWorkspaceCache:
    """Serialize preparation and retain at most one current project/revision."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._current: _WorkspaceOwner | None = None

    def invalidate(self, project_root: Path) -> None:
        """Forget a matching cache entry; callers retain ownership of adopted data."""
        root = Path(project_root).resolve()
        with self._lock:
            if self._current is not None and self._current.project_root == root:
                self._current = None

    def get(self, project_root: Path, *, fetcher: ReportFetcher | None = None) -> dict:
        """Get a checked runtime, downloading only when its metadata revision is absent.

        Keep the returned mapping, including ``_workspace_owner``, while using
        its root. This prevents another revision or explicit cache invalidation
        from deleting files still in use by a browser session. ``fetcher`` is an
        internal test seam; the UI never accepts a URL or downloader from users.
        """
        root = Path(project_root).resolve()
        with self._lock:
            fingerprint = session_metadata_fingerprint(root)
            documents = _registered_documents(root)
            current = self._current
            if current is not None and (
                current.project_root != root or current.metadata_fingerprint != fingerprint
            ):
                self._current = current = None
            if current is not None:
                try:
                    actual = workspace_fingerprint(current.stats["root"], documents)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    self._current = None
                    raise CloudDataError(
                        "The cached report workspace is unavailable. Retry initialization."
                    ) from exc
                if actual != current.source_fingerprint:
                    self._current = None
                    raise CloudDataError(
                        "The cached report workspace changed. Retry initialization."
                    )
                if session_metadata_fingerprint(root) != fingerprint:
                    self._current = None
                    raise CloudDataError(
                        "Source metadata changed during validation. Retry loading."
                    )
                return {**current.stats, "_workspace_owner": current}

            temporary = TemporaryDirectory(prefix="fic-official-runtime-")
            try:
                reports, downloads = {}, []
                download = _download_report if fetcher is None else fetcher
                for item in documents:
                    content = download(item["source_url"])
                    if type(content) is not bytes or not 0 < len(content) <= MAX_REPORT_BYTES:
                        raise CloudDataError("Each downloaded report must be 1 byte to 16 MiB.")
                    if hashlib.sha256(content).hexdigest() != item["sha256"]:
                        raise CloudDataError(
                            f"The official download hash changed for {item['doc_id']}. "
                            "Review the source version; no hash or financial approval was changed."
                        )
                    reports[item["doc_id"]] = content
                    downloads.append(
                        {
                            "doc_id": item["doc_id"],
                            "source_url": item["source_url"],
                            "sha256": item["sha256"],
                            "downloaded_at": datetime.now(UTC).isoformat(),
                        }
                    )
                if session_metadata_fingerprint(root) != fingerprint:
                    raise CloudDataError("Source metadata changed during download. Retry loading.")
                stats = prepare_session_workspace(root, reports, Path(temporary.name) / "workspace")
                if stats["metadata_fingerprint"] != fingerprint:
                    raise CloudDataError(
                        "Source metadata changed during preparation. Retry loading."
                    )
                workspace = stats["root"]
                receipt_path = workspace / "data/processed/session-load-receipt.json"
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                receipt.update(
                    kind="official_runtime_download",
                    downloads=downloads,
                    notice=(
                        "Pinned official sources downloaded into temporary cloud runtime storage. "
                        "Download timestamps do not replace manifest acquisition history. "
                        "Financial and evaluation decisions are unchanged."
                    ),
                )
                receipt_path.write_text(
                    json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
                stats["workspace_fingerprint"] = workspace_fingerprint(
                    workspace, read_documents(workspace)
                )
                if session_metadata_fingerprint(root) != fingerprint:
                    raise CloudDataError("Source metadata changed before runtime adoption. Retry.")
                owner = _WorkspaceOwner(
                    temporary, root, fingerprint, stats["workspace_fingerprint"], stats
                )
                self._current = owner
                return {**stats, "_workspace_owner": owner}
            except BaseException:
                temporary.cleanup()
                raise


_CACHE = CloudWorkspaceCache()


def get_cloud_workspace(project_root: Path, *, fetcher: ReportFetcher | None = None) -> dict:
    """Return the process-shared runtime for the current registered source revision."""
    return _CACHE.get(project_root, fetcher=fetcher)


def invalidate_cloud_workspace(project_root: Path) -> None:
    """Permit explicit retry without deleting workspaces still held by active callers."""
    _CACHE.invalidate(project_root)
