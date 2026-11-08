"""Development evaluation with source checks and pending human judgments kept separate."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import pymupdf

from financial_intelligence_copilot.answer import answer_question
from financial_intelligence_copilot.citations import validate_excerpt
from financial_intelligence_copilot.retrieval import ReportScopeError

CATEGORIES = {"simple_fact", "financial_numeric", "table_basis", "cross_year", "boundary"}
SEMANTIC_FIELDS = (
    "answer_correctness",
    "citation_relevance",
    "numerical_correctness",
    "abstention_correctness",
)


def canonical_digest(payload: dict) -> str:
    """Bind JSON content, without claiming human identity authentication."""
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_suite(payload: dict) -> list[dict]:
    """Accept development drafts only; no proposed answer becomes approved gold."""
    if (
        not isinstance(payload, dict)
        or type(payload.get("schema_version")) is not int
        or payload["schema_version"] != 1
        or payload.get("split") != "development"
        or not isinstance(payload.get("cases"), list)
        or not payload["cases"]
    ):
        raise ValueError("Invalid development evaluation suite")
    seen = set()
    try:
        for case in payload["cases"]:
            if not isinstance(case, dict):
                raise ValueError("Each evaluation case must be a structured record")
            for key in ("id", "question", "selected_doc_id", "review_notes"):
                if not isinstance(case[key], str) or not case[key].strip():
                    raise ValueError("Case identity, question, scope and review notes are required")
            if case["id"] in seen:
                raise ValueError("Duplicate evaluation case ID")
            seen.add(case["id"])
            if case["category"] not in CATEGORIES or len(case["question"]) > 2000:
                raise ValueError("Unsupported evaluation category or question length")
            if (
                case["review_status"] != "pending_owner_review"
                or case["reviewer"] is not None
                or case["reviewed_at"] is not None
                or case.get("owner_gold") is not None
                or case.get("exposure") != "development"
            ):
                raise ValueError("Draft cases must remain pending and development-exposed")
            docs = case["target_docs"]
            if (
                not isinstance(docs, list)
                or not docs
                or any(not isinstance(doc, str) or not doc for doc in docs)
                or len(docs) != len(set(docs))
                or case["selected_doc_id"] not in docs
                or type(case["selected_fiscal_year"]) is not int
                or type(case["answerable"]) is not bool
            ):
                raise ValueError("Invalid proposed answerability or selected report scope")
            evidence = case["evidence"]
            if not isinstance(evidence, list) or (case["answerable"] and not evidence):
                raise ValueError("Answerable proposals need actual source evidence")
            if case["answerable"] and (
                not isinstance(case.get("candidate_answer"), str)
                or not case["candidate_answer"].strip()
            ):
                raise ValueError("An answerable proposal needs a pending candidate answer")
            for reference in evidence:
                if (
                    not isinstance(reference, dict)
                    or reference["doc_id"] not in docs
                    or type(reference["fiscal_year"]) is not int
                    or type(reference["pdf_page"]) is not int
                    or reference["pdf_page"] < 1
                    or type(reference["char_start"]) is not int
                    or type(reference["char_end"]) is not int
                    or not 0 <= reference["char_start"] < reference["char_end"]
                    or not isinstance(reference["quote"], str)
                    or not reference["quote"].strip()
                    or len(reference["quote"]) > 600
                    or len(reference["quote"]) != reference["char_end"] - reference["char_start"]
                ):
                    raise ValueError("Invalid proposed source span")
                for key in ("source_sha256", "source_url"):
                    if not isinstance(reference[key], str) or not reference[key]:
                        raise ValueError("Source hash and URL are required")
            behavior = case["expected_behavior"]
            if not isinstance(behavior, dict) or behavior.get("status") not in {
                "extractive_evidence",
                "abstained",
            }:
                raise ValueError("Invalid engineering behavior expectation")
            reason = behavior.get("reason")
            if (behavior["status"] == "extractive_evidence" and reason is not None) or (
                behavior["status"] == "abstained" and (not isinstance(reason, str) or not reason)
            ):
                raise ValueError("Expected response reason is inconsistent with status")
    except (KeyError, TypeError) as exc:
        raise ValueError("Evaluation case is missing or has invalid fields") from exc
    counts = dict(Counter(case["category"] for case in payload["cases"]))
    if "category_counts" in payload and payload["category_counts"] != counts:
        raise ValueError("Declared category counts do not match the cases")
    return payload["cases"]


def load_suite(path: Path, root: Path) -> dict:
    """Validate every proposed quote against freshly extracted registered raw PDFs."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = validate_suite(payload)
    with (Path(root) / "data/manifest.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    registry = {row["doc_id"]: row for row in rows}
    if len(registry) != len(rows):
        raise ValueError("Duplicate source document in evaluation manifest")
    documents, page_text = {}, {}
    try:
        for case in cases:
            if any(doc not in registry for doc in case["target_docs"]):
                raise ValueError("Unknown evaluation target document")
            if (
                int(registry[case["selected_doc_id"]]["fiscal_year"])
                != case["selected_fiscal_year"]
            ):
                raise ValueError("Evaluation selected year differs from its registered document")
            for reference in case["evidence"]:
                doc_id = reference["doc_id"]
                row = registry[doc_id]
                if (
                    reference["fiscal_year"] != int(row["fiscal_year"])
                    or reference["source_sha256"] != row["sha256"]
                    or reference["source_url"] != row["source_url"]
                ):
                    raise ValueError("Evaluation source metadata differs from the manifest")
                if doc_id not in documents:
                    raw = (Path(root) / "data/raw").resolve()
                    source = (raw / row["local_filename"]).resolve()
                    if not source.is_relative_to(raw):
                        raise ValueError("Evaluation source path leaves the raw directory")
                    with source.open("rb") as handle:
                        digest = hashlib.file_digest(handle, "sha256").hexdigest()
                    if digest != row["sha256"]:
                        raise ValueError("Evaluation raw PDF hash mismatch")
                    documents[doc_id] = pymupdf.open(source)
                    if documents[doc_id].needs_pass or not documents[doc_id].is_pdf:
                        raise ValueError("Evaluation source must be an unlocked PDF")
                page = reference["pdf_page"]
                if page > documents[doc_id].page_count:
                    raise ValueError("Evaluation source PDF page is outside the document")
                key = (doc_id, page)
                if key not in page_text:
                    page_text[key] = (
                        documents[doc_id].load_page(page - 1).get_text("text", sort=True)
                    )
                if (
                    page_text[key][reference["char_start"] : reference["char_end"]]
                    != reference["quote"]
                ):
                    raise ValueError("Evaluation quote does not match its actual PDF source span")
    except (KeyError, TypeError, RuntimeError) as exc:
        raise ValueError("Evaluation source validation failed") from exc
    finally:
        for document in documents.values():
            document.close()
    return payload


def check_source_spans(response: dict, retriever, doc_id: str, fiscal_year: int) -> dict:
    """Reconstruct released excerpts; this does not judge answer relevance."""
    result = {"checked": 0, "total": 0, "errors": []}
    if not isinstance(response, dict):
        result["errors"].append("Response is not a structured object")
        return result
    excerpts = response.get("excerpts")
    if not isinstance(excerpts, list):
        result["errors"].append("Response excerpts must be a list")
        return result
    result["total"] = len(excerpts)
    if response.get("scope") != {"doc_id": doc_id, "fiscal_year": fiscal_year}:
        result["errors"].append("Response scope differs from the selected document/year")
    if response.get("status") == "abstained" and excerpts:
        result["errors"].append("Abstained response contains excerpts")
    if response.get("status") == "extractive_evidence" and not excerpts:
        result["errors"].append("Extractive response contains no excerpts")
    evidence = {chunk.chunk_id: chunk for chunk in retriever.chunks}
    for number, excerpt in enumerate(excerpts):
        try:
            selection = {
                "evidence_ids": list(excerpt["evidence_ids"]),
                "char_start": excerpt["char_start"],
                "char_end": excerpt["char_end"],
            }
            reconstructed = validate_excerpt(
                selection, evidence=evidence, doc_id=doc_id, fiscal_year=fiscal_year
            ).to_dict()
            for key in (
                "issuer",
                "doc_id",
                "fiscal_year",
                "pdf_page",
                "source_url",
                "source_sha256",
                "char_start",
                "char_end",
                "quote",
            ):
                if excerpt[key] != reconstructed[key]:
                    raise ValueError("Released excerpt differs from the reconstructed source")
            result["checked"] += 1
        except (KeyError, ValueError, TypeError) as exc:
            result["errors"].append(f"Excerpt {number + 1}: {exc}")
    return result


def run_cases(retriever, suite: dict) -> dict:
    """Run an already source-checked suite; preserve errors and unscored judgments."""
    cases = validate_suite(suite)
    started = datetime.now(UTC).isoformat()
    rows = []
    for case in cases:
        start = perf_counter()
        row = {
            "case_id": case["id"],
            "case_digest": canonical_digest(case),
            "category": case["category"],
            "question": case["question"],
            "candidate_answer": case.get("candidate_answer"),
            "proposed_evidence": case["evidence"],
            "document_answerability_proposal": case["answerable"],
            "current_mode_support": case.get("current_mode_support"),
            "response": None,
            "response_digest": None,
            "retrieval_hits": [],
            "retrieval_error": None,
            "error": None,
            "engineering_behavior_match": False,
            "source_span_check": {"checked": 0, "total": 0, "errors": []},
        }
        retrieval_start = perf_counter()
        try:
            hits = retriever.search(
                case["question"],
                doc_id=case["selected_doc_id"],
                fiscal_year=case["selected_fiscal_year"],
                top_k=5,
            )
            row["retrieval_hits"] = [hit.to_dict() for hit in hits]
            if any(
                hit["doc_id"] != case["selected_doc_id"]
                or type(hit["fiscal_year"]) is not int
                or hit["fiscal_year"] != case["selected_fiscal_year"]
                for hit in row["retrieval_hits"]
            ):
                raise ValueError("Diagnostic retrieval returned a different report scope")
        except ReportScopeError as exc:
            row["retrieval_error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "kind": "expected_scope_rejection"
                if case["expected_behavior"]["reason"] == "report_scope_conflict"
                else "unexpected_error",
            }
        except Exception as exc:
            row["retrieval_error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "kind": "unexpected_error",
            }
        retrieval_seconds = perf_counter() - retrieval_start
        answer_start = perf_counter()
        try:
            response = answer_question(
                retriever,
                case["question"],
                doc_id=case["selected_doc_id"],
                fiscal_year=case["selected_fiscal_year"],
                top_k=5,
            )
            if not isinstance(response, dict):
                raise ValueError("Answer response must be a structured JSON object")
            digest = canonical_digest(response)
            row["response"] = response
            row["response_digest"] = digest
            if response.get("status") not in {"abstained", "extractive_evidence"}:
                raise ValueError("Invalid answer response status")
            expected = case["expected_behavior"]
            row["engineering_behavior_match"] = (
                response.get("status") == expected["status"]
                and response.get("reason") == expected["reason"]
            )
            row["source_span_check"] = check_source_spans(
                response, retriever, case["selected_doc_id"], case["selected_fiscal_year"]
            )
        except Exception as exc:
            row["error"] = {"type": type(exc).__name__, "message": str(exc)}
        row["latency"] = {
            "diagnostic_retrieval_seconds": retrieval_seconds,
            "answer_and_span_check_seconds": perf_counter() - answer_start,
            "total_case_seconds": perf_counter() - start,
        }
        expected_pages = {
            (item["doc_id"], item["fiscal_year"], item["pdf_page"])
            for item in case["evidence"]
            if item["doc_id"] == case["selected_doc_id"]
        }
        eligible = len(case["target_docs"]) == 1 and bool(expected_pages)
        pages = [
            (hit["doc_id"], hit["fiscal_year"], hit["pdf_page"]) for hit in row["retrieval_hits"]
        ]
        row["proposed_page_hit_at_1"] = bool(set(pages[:1]) & expected_pages) if eligible else None
        row["proposed_page_hit_at_5"] = bool(set(pages[:5]) & expected_pages) if eligible else None
        rows.append(row)
    times = sorted(row["latency"]["total_case_seconds"] for row in rows)
    summary = {
        "case_count": len(rows),
        "completed_count": sum(row["error"] is None for row in rows),
        "error_count": sum(row["error"] is not None for row in rows),
        "diagnostic_retrieval_error_count": sum(row["retrieval_error"] is not None for row in rows),
        "unexpected_diagnostic_error_count": sum(
            row["retrieval_error"] is not None
            and row["retrieval_error"]["kind"] == "unexpected_error"
            for row in rows
        ),
        "category_counts": dict(Counter(case["category"] for case in cases)),
        "response_status_counts": dict(
            Counter(
                row["response"].get("status", "invalid_response")
                for row in rows
                if row["response"] is not None
            )
        ),
        "expected_behavior": {
            "matched": sum(row["engineering_behavior_match"] for row in rows),
            "eligible": len(rows),
        },
        "source_spans": {
            "checked": sum(row["source_span_check"]["checked"] for row in rows),
            "total": sum(row["source_span_check"]["total"] for row in rows),
            "case_errors": sum(bool(row["source_span_check"]["errors"]) for row in rows),
        },
        "approved_gold_count": 0,
        "human_scored_count": 0,
        "semantic_metrics": dict.fromkeys(SEMANTIC_FIELDS),
        "latency_seconds": {
            "median_case": (times[(len(times) - 1) // 2] + times[len(times) // 2]) / 2,
            "p95_case_nearest_rank": times[math.ceil(0.95 * len(times)) - 1],
        },
    }
    for rank in (1, 5):
        key = f"proposed_page_hit_at_{rank}"
        summary[key] = {
            "matched": sum(row[key] is True for row in rows),
            "eligible": sum(row[key] is not None for row in rows),
        }
    run = {
        "schema_version": 1,
        "kind": "local_extractive_development_evaluation",
        "started_at": started,
        "run_id": "dev-" + canonical_digest({"started_at": started, "suite": suite})[:20],
        "suite_digest": canonical_digest(suite),
        "suite_snapshot": json.loads(json.dumps(suite)),
        "mode": "local_extractive",
        "top_k": 5,
        "model_api_calls": 0,
        "provider_cost": None,
        "environment": {"python": platform.python_version(), "PyMuPDF": version("PyMuPDF")},
        "case_results": rows,
        "summary": summary,
        "notice": (
            "Development-exposed cases and unapproved source/answer proposals. Engineering "
            "behavior matches, literal source spans and proposed page hits are not semantic, "
            "numerical, citation-relevance or abstention correctness. No held-out claim."
        ),
    }
    run["run_digest"] = canonical_digest(run)
    return run


def make_review_packet(run: dict) -> dict:
    """Bind pending human judgments to the frozen run, cases and responses."""
    if canonical_digest(
        {key: value for key, value in run.items() if key != "run_digest"}
    ) != run.get("run_digest"):
        raise ValueError("Run content differs from its recorded digest")
    if canonical_digest(run["suite_snapshot"]) != run["suite_digest"]:
        raise ValueError("Suite snapshot differs from its recorded digest")
    cases = {case["id"]: case for case in run["suite_snapshot"]["cases"]}
    validate_suite(run["suite_snapshot"])
    identities = [row["case_id"] for row in run["case_results"]]
    if len(identities) != len(cases) or set(identities) != set(cases):
        raise ValueError("Review packet requires each frozen suite case exactly once")
    for row in run["case_results"]:
        case = cases[row["case_id"]]
        if canonical_digest(case) != row["case_digest"]:
            raise ValueError("Run case differs from its recorded digest")
        if (
            row["question"] != case["question"]
            or row["candidate_answer"] != case.get("candidate_answer")
            or row["proposed_evidence"] != case["evidence"]
        ):
            raise ValueError("Run proposal fields differ from the frozen suite case")
        expected_response_digest = (
            canonical_digest(row["response"]) if row["response"] is not None else None
        )
        if expected_response_digest != row["response_digest"]:
            raise ValueError("Run response differs from its recorded digest")
    return {
        "schema_version": 1,
        "run_id": run["run_id"],
        "run_digest": run["run_digest"],
        "suite_digest": run["suite_digest"],
        "notice": "Pending human review only. Digests bind content, not reviewer identity.",
        "reviews": [
            {
                "case_id": row["case_id"],
                "case_digest": row["case_digest"],
                "response_digest": row["response_digest"],
                "question": row["question"],
                "candidate_answer": row["candidate_answer"],
                "proposed_evidence": row["proposed_evidence"],
                "response": row["response"],
                "gold_review": {
                    "status": "pending",
                    "reviewer": None,
                    "reviewed_at": None,
                    "notes": "",
                },
                "ratings": dict.fromkeys(SEMANTIC_FIELDS),
                "reviewer": None,
                "reviewed_at": None,
                "notes": "",
            }
            for row in run["case_results"]
        ],
    }
