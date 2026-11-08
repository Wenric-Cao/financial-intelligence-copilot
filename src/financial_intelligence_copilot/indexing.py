"""Build a local evidence index from source-checked PDF page snapshots."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from financial_intelligence_copilot.chunking import CHUNKING_VERSION, chunk_page
from financial_intelligence_copilot.pdf_parser import DocumentMetadata, parse_pdf


def build_index(
    manifest_path: str | Path,
    raw_dir: str | Path,
    pages_dir: str | Path,
    policy: dict,
) -> dict:
    """Validate provenance and build a deterministic index without network access.

    Fresh native extraction is compared with saved page text before chunking.
    A SHA256 field in a sidecar JSON alone does not prove its text is authentic.
    This verifies local source consistency, not financial facts or source rights.
    """
    if policy.get("schema_version") != 1:
        raise ValueError("Unsupported retrieval policy schema")
    options = {key: policy[key] for key in ("max_words", "overlap_words", "min_words")}
    # Validate window settings even when no pages can be indexed.
    chunk_page(
        {"status": "empty_text", "text": ""},
        source_sha256="",
        source_url="",
        **options,
    )
    with Path(manifest_path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "doc_id",
            "issuer",
            "fiscal_year",
            "language",
            "source_url",
            "sha256",
            "local_filename",
        }
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Manifest is missing required source fields")
        rows = list(reader)
    if not rows:
        raise ValueError("Manifest has no actual source records")
    doc_ids = [row["doc_id"] for row in rows]
    if len(set(doc_ids)) != len(doc_ids):
        raise ValueError("Manifest contains duplicate document IDs")
    exclusions = policy.get("excluded_pdf_pages", {})
    if not isinstance(exclusions, dict) or set(exclusions) - set(doc_ids):
        raise ValueError("Page exclusions reference unknown documents")

    records, documents, skipped = [], [], []
    for row in sorted(rows, key=lambda item: item["doc_id"]):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", row["doc_id"]):
            raise ValueError("Document ID must be a safe, non-empty identifier")
        metadata = DocumentMetadata(
            row["doc_id"], row["issuer"], int(row["fiscal_year"]), row["language"]
        )
        url = urlparse(row["source_url"])
        if url.scheme != "https" or not url.netloc or url.username or url.password:
            raise ValueError("Source URL must be HTTPS and contain no credentials")
        raw_root = Path(raw_dir).resolve()
        source = (raw_root / row["local_filename"]).resolve()
        if not source.is_relative_to(raw_root) or not row["local_filename"]:
            raise ValueError("Source filename must stay inside the raw-data directory")
        saved = json.loads(
            (Path(pages_dir) / f"{metadata.doc_id}.pages.json").read_text(encoding="utf-8")
        )
        if not isinstance(saved, dict) or not isinstance(saved.get("pages"), list):
            raise ValueError(f"Invalid page inventory for {metadata.doc_id}")
        fresh = parse_pdf(source, metadata)
        if fresh.sha256 != row["sha256"] or saved.get("sha256") != fresh.sha256:
            raise ValueError(f"Source hash mismatch for {metadata.doc_id}; review the manifest")
        if (
            saved.get("schema_version") != 1
            or saved.get("source_filename") != source.name
            or type(saved.get("page_count")) is not int
            or saved["page_count"] != fresh.page_count
            or len(saved.get("pages", [])) != fresh.page_count
        ):
            raise ValueError(f"Invalid page inventory for {metadata.doc_id}")

        excluded = exclusions.get(metadata.doc_id, {})
        if not isinstance(excluded, dict):
            raise ValueError("Each document's page exclusions must map page numbers to reasons")
        for number, reason in excluded.items():
            if (
                not str(number).isdigit()
                or not 1 <= int(number) <= fresh.page_count
                or not isinstance(reason, str)
                or not reason.strip()
            ):
                raise ValueError(f"Invalid page exclusion for {metadata.doc_id}")

        before = len(records)
        for saved_page, fresh_page in zip(saved["pages"], fresh.pages, strict=True):
            expected = asdict(fresh_page)
            if not isinstance(saved_page, dict) or any(
                type(saved_page.get(key)) is not type(value) or saved_page.get(key) != value
                for key, value in expected.items()
            ):
                raise ValueError(
                    f"Saved text/metadata does not match PDF page {fresh_page.pdf_page} "
                    f"of {metadata.doc_id}; regenerate and review the page snapshot"
                )
            page_number = fresh_page.pdf_page
            reason = excluded.get(str(page_number))
            if reason:
                chunks = []
            else:
                chunks = chunk_page(
                    saved_page,
                    source_sha256=fresh.sha256,
                    source_url=row["source_url"],
                    **options,
                )
                if not chunks:
                    reason = (
                        f"Page status: {fresh_page.status}"
                        if fresh_page.status != "ok"
                        else "Fewer words than the configured minimum"
                    )
            records.extend(asdict(chunk) for chunk in chunks)
            if reason:
                skipped.append(
                    {"doc_id": metadata.doc_id, "pdf_page": page_number, "reason": reason}
                )
        if len(records) == before:
            raise ValueError(f"No indexable text in {metadata.doc_id}; review page exclusions")
        documents.append(
            {
                **asdict(metadata),
                "source_url": row["source_url"],
                "source_sha256": fresh.sha256,
                "page_count": fresh.page_count,
                "chunk_count": len(records) - before,
            }
        )

    policy_bytes = json.dumps(policy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema_version": 1,
        "index_kind": "local-bm25",
        "chunking_version": CHUNKING_VERSION,
        "policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "policy": json.loads(policy_bytes),
        "documents": documents,
        "skipped_pages": skipped,
        "chunks": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--pages-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--policy", type=Path, default=Path("data/retrieval_policy.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("Output already exists; choose another path")
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        index = build_index(args.manifest, args.raw_dir, args.pages_dir, policy)
        serialized = json.dumps(index, ensure_ascii=False, indent=2) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    for document in index["documents"]:
        print(
            f"{document['doc_id']}: {document['chunk_count']} chunks from "
            f"{document['page_count']} physical PDF pages"
        )
    print(f"Skipped {len(index['skipped_pages'])} pages; wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
