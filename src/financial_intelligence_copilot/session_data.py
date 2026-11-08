"""Prepare an isolated runtime from the two registered, user-supplied PDF files."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from financial_intelligence_copilot.indexing import build_index
from financial_intelligence_copilot.kpi_reviews import load_review_state
from financial_intelligence_copilot.pdf_parser import DocumentMetadata, parse_pdf
from financial_intelligence_copilot.retrieval import load_retriever
from financial_intelligence_copilot.ui_state import read_documents
from financial_intelligence_copilot.verified_store import write_verified_store

MAX_REPORT_BYTES = 16 * 1024 * 1024
METADATA_FILES = (
    "data/manifest.csv",
    "data/retrieval_policy.json",
    "data/kpi_candidates.json",
    "data/kpi_reviews.json",
    "data/evaluation_cases.json",
    "pyproject.toml",
)
REQUIRED_METADATA = {"data/manifest.csv", "data/retrieval_policy.json"}


def _metadata_snapshot(project_root: Path) -> dict[str, bytes | None]:
    root = project_root.resolve()
    snapshot = {}
    for relative in METADATA_FILES:
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Session metadata must be regular files inside the project")
        if path.is_file():
            snapshot[relative] = path.read_bytes()
        elif relative in REQUIRED_METADATA or path.exists():
            raise ValueError(f"Required session metadata is missing or unreadable: {relative}")
        else:
            snapshot[relative] = None
    return snapshot


def _snapshot_digest(snapshot: dict[str, bytes | None]) -> str:
    values = {
        name: hashlib.sha256(content).hexdigest() if content is not None else None
        for name, content in snapshot.items()
    }
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def session_metadata_fingerprint(project_root: Path) -> str:
    """Identify public metadata bytes, including absent optional review inputs."""
    return _snapshot_digest(_metadata_snapshot(Path(project_root)))


def _json_file(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def prepare_session_workspace(
    project_root: Path, uploaded_reports: dict[str, bytes], destination: Path
) -> dict:
    """Validate fixed report uploads and publish one complete, private session runtime.

    No network is accessed and no file in the source project is written. The
    destination must be a new path outside that project, usually a child of a
    session-owned TemporaryDirectory. A failed preparation removes its staging
    files. Source rights and financial approvals are not established by hashes.
    """
    project_root = Path(project_root).resolve()
    requested = Path(destination)
    if requested.exists() or requested.is_symlink():
        raise FileExistsError("Session destination already exists; choose a new directory")
    destination = requested.resolve()
    if destination.is_relative_to(project_root) or project_root.is_relative_to(destination):
        raise ValueError("Session destination must be outside the source project")
    if not destination.parent.is_dir():
        raise ValueError("Session destination parent directory must already exist")
    if not isinstance(uploaded_reports, dict):
        raise ValueError("Supply the two registered PDFs keyed by document ID")

    snapshot = _metadata_snapshot(project_root)
    fingerprint = _snapshot_digest(snapshot)
    lock = destination.with_name(f".{destination.name}.preparing")
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise FileExistsError("This session destination is already being prepared") from exc
    try:
        with tempfile.TemporaryDirectory(
            prefix=".fic-session-", dir=destination.parent
        ) as temporary:
            staging = Path(temporary)
            for relative, content in snapshot.items():
                if content is not None:
                    path = staging / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)

            documents = read_documents(staging)
            if set(uploaded_reports) != {item["doc_id"] for item in documents}:
                raise ValueError("Upload exactly the registered AIA FY2024 and FY2025 reports")
            for item in documents:
                filename = item["local_filename"]
                if Path(filename).name != filename or filename in {".", ".."}:
                    raise ValueError("Registered PDF filenames must be plain local filenames")
                expected = item.get("sha256", "")
                if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
                    raise ValueError("Each registered report needs its pinned SHA256")
                content = uploaded_reports[item["doc_id"]]
                if type(content) is not bytes or not 0 < len(content) <= MAX_REPORT_BYTES:
                    raise ValueError("Each report must be nonempty PDF bytes no larger than 16 MiB")
                if hashlib.sha256(content).hexdigest() != expected:
                    raise ValueError(
                        f"Uploaded report hash differs from the registered source: {item['doc_id']}"
                    )

            raw, processed = staging / "data/raw", staging / "data/processed"
            raw.mkdir()
            processed.mkdir()
            page_count = 0
            for item in documents:
                source = raw / item["local_filename"]
                source.write_bytes(uploaded_reports[item["doc_id"]])
                metadata = DocumentMetadata(
                    item["doc_id"], item["issuer"], item["fiscal_year"], item["language"]
                )
                parsed = parse_pdf(source, metadata)
                if parsed.sha256 != item["sha256"] or any(
                    page.status == "extraction_error" for page in parsed.pages
                ):
                    raise ValueError("A report failed source-consistent page extraction")
                if not any(page.status == "ok" for page in parsed.pages):
                    raise ValueError("A report has no extractable native text; review it manually")
                page_count += parsed.page_count
                _json_file(processed / f"{item['doc_id']}.pages.json", parsed.to_dict())

            manifest = staging / "data/manifest.csv"
            policy_path = staging / "data/retrieval_policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            index = build_index(manifest, raw, processed, policy)
            index_path = processed / "retrieval-index.json"
            _json_file(index_path, index)
            load_retriever(
                index_path,
                manifest_path=manifest,
                raw_dir=raw,
                pages_dir=processed,
                policy_path=policy_path,
            )
            review_state = load_review_state(staging)
            verified_count = 0
            if review_state["candidates"]:
                store = write_verified_store(staging, processed / "verified-kpis.json")
                verified_count = store["verified_count"]
            receipt = {
                "kind": "user_supplied_session_reports",
                "prepared_at": datetime.now(UTC).isoformat(),
                "metadata_fingerprint": fingerprint,
                "documents": [
                    {"doc_id": item["doc_id"], "sha256": item["sha256"]} for item in documents
                ],
                "document_count": len(documents),
                "page_count": page_count,
                "chunk_count": len(index["chunks"]),
                "verified_fact_count": verified_count,
                "notice": (
                    "User-supplied pinned files processed in isolated session storage. "
                    "Preparation time is not a new download timestamp or source-rights approval. "
                    "Financial and evaluation decisions are unchanged."
                ),
            }
            _json_file(processed / "session-load-receipt.json", receipt)
            if _metadata_snapshot(project_root) != snapshot:
                raise ValueError("Project metadata changed during session preparation; retry")
            if destination.exists() or destination.is_symlink():
                raise FileExistsError("Session destination appeared during preparation")
            os.rename(staging, destination)
        return {
            "root": destination,
            "document_count": len(documents),
            "page_count": page_count,
            "chunk_count": len(index["chunks"]),
            "verified_fact_count": verified_count,
            "metadata_fingerprint": fingerprint,
        }
    finally:
        lock.rmdir()
