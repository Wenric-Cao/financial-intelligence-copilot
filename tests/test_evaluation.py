"""Development evaluation checks use neutral fixtures, never approved gold answers."""

import csv
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pymupdf
import pytest

from financial_intelligence_copilot import evaluation
from financial_intelligence_copilot.answer import answer_question
from financial_intelligence_copilot.chunking import chunk_page
from financial_intelligence_copilot.evaluation import (
    canonical_digest,
    check_source_spans,
    load_suite,
    make_review_packet,
    run_cases,
    validate_suite,
)
from financial_intelligence_copilot.pdf_parser import DocumentMetadata, parse_pdf
from financial_intelligence_copilot.retrieval import LexicalRetriever, SearchHit

SEMANTIC_FIELDS = {
    "answer_correctness",
    "citation_relevance",
    "numerical_correctness",
    "abstention_correctness",
}
QUESTION = "Who approves the records framework?"
BOARD_QUOTE = "The Archive Board oversees archive stewardship and approves the records framework."


@pytest.fixture
def evaluation_workspace(tmp_path: Path) -> dict:
    """Create tiny source-backed cases clearly labeled as nonfinancial tests."""
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    rows, chunks, proposed_reference = [], [], None
    for year, body in ((2024, "Archive Council"), (2025, "Archive Board")):
        doc_id = f"TEST-{year}-EN"
        source = raw / f"neutral_evaluation_{year}.pdf"
        with pymupdf.open() as document:
            for _ in range(6):
                document.new_page()
            page = document.new_page()
            page.insert_text(
                (72, 72),
                "TEST FIXTURE ONLY - NOT A FINANCIAL REPORT\n\n"
                f"The {body} oversees archive stewardship and approves the records framework.\n"
                "The records framework protects paper folders and reference labels.",
                fontsize=10,
            )
            document.save(source)
        parsed = parse_pdf(source, DocumentMetadata(doc_id, "Neutral Evaluation Fixture", year))
        url = f"https://example.invalid/neutral-evaluation-{year}.pdf"
        chunks.extend(
            chunk_page(
                parsed.to_dict()["pages"][6],
                source_sha256=parsed.sha256,
                source_url=url,
                max_words=16,
                overlap_words=4,
            )
        )
        rows.append(
            {
                "doc_id": doc_id,
                "issuer": "Neutral Evaluation Fixture",
                "ticker": "TEST",
                "fiscal_year": year,
                "period_end": f"{year}-12-31",
                "language": "en",
                "source_url": url,
                "date_downloaded": "",
                "sha256": parsed.sha256,
                "local_filename": source.name,
                "notes": "Generated neutral test fixture; no actual annual-report or gold claims.",
            }
        )
        if year == 2025:
            start = parsed.pages[6].text.index(BOARD_QUOTE)
            proposed_reference = {
                "doc_id": doc_id,
                "fiscal_year": year,
                "pdf_page": 7,
                "source_sha256": parsed.sha256,
                "source_url": url,
                "char_start": start,
                "char_end": start + len(BOARD_QUOTE),
                "quote": BOARD_QUOTE,
            }
    with (tmp_path / "data/manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    fact = {
        "id": "neutral-fact",
        "category": "simple_fact",
        "question": QUESTION,
        "target_docs": ["TEST-2025-EN"],
        "selected_doc_id": "TEST-2025-EN",
        "selected_fiscal_year": 2025,
        "answerable": True,
        "candidate_answer": "The Archive Board (neutral test proposal only).",
        "evidence": [proposed_reference],
        "expected_behavior": {"status": "extractive_evidence", "reason": None},
        "review_status": "pending_owner_review",
        "reviewer": None,
        "reviewed_at": None,
        "review_notes": "Neutral development test only, not approved gold.",
        "exposure": "development",
    }
    boundary = {
        **deepcopy(fact),
        "id": "neutral-missing-subject",
        "category": "boundary",
        "question": "What is ZephyrQuartz?",
        "answerable": False,
        "candidate_answer": None,
        "evidence": [],
        "expected_behavior": {"status": "abstained", "reason": "no_matching_evidence"},
    }
    return {
        "root": tmp_path,
        "suite": {"schema_version": 1, "split": "development", "cases": [fact, boundary]},
        "retriever": LexicalRetriever(chunks),
    }


def test_canonical_digest_is_stable_but_binds_nested_content_and_json_types():
    assert canonical_digest({"a": 1, "b": {"c": "neutral"}}) == canonical_digest(
        {"b": {"c": "neutral"}, "a": 1}
    )
    original = canonical_digest({"value": 1, "proposal": {"text": "neutral"}})
    assert len(original) == 64
    assert original != canonical_digest({"value": 1, "proposal": {"text": "changed"}})
    assert len({canonical_digest({"value": value}) for value in (1, 1.0, True)}) == 3


def test_canonical_digest_rejects_nonfinite_json_values():
    with pytest.raises(ValueError):
        canonical_digest({"invalid": float("nan")})


def test_suite_validation_preserves_pending_proposals_without_inventing_gold(evaluation_workspace):
    cases = validate_suite(evaluation_workspace["suite"])

    assert len(cases) == 2
    assert all(case["review_status"] == "pending_owner_review" for case in cases)
    assert all(case["reviewer"] is None and case["reviewed_at"] is None for case in cases)
    assert cases[0]["candidate_answer"] == "The Archive Board (neutral test proposal only)."
    assert cases[1]["answerable"] is False and cases[1]["evidence"] == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("review_status", "approved"),
        ("reviewer", "An invented reviewer"),
        ("reviewed_at", "2026-01-01T00:00:00Z"),
    ],
)
def test_pending_cases_cannot_contain_approval_or_review_signatures(
    evaluation_workspace, field, value
):
    suite = deepcopy(evaluation_workspace["suite"])
    suite["cases"][0][field] = value

    with pytest.raises(ValueError):
        validate_suite(suite)


def test_duplicate_case_ids_and_false_category_counts_are_rejected(evaluation_workspace):
    suite = deepcopy(evaluation_workspace["suite"])
    suite["cases"][1]["id"] = suite["cases"][0]["id"]
    with pytest.raises(ValueError):
        validate_suite(suite)
    suite = deepcopy(evaluation_workspace["suite"])
    suite["category_counts"] = {"simple_fact": 99, "boundary": 1}
    with pytest.raises(ValueError):
        validate_suite(suite)


@pytest.mark.parametrize("change", ["category", "scope", "answerability", "empty_cases"])
def test_invalid_development_suite_shapes_do_not_run(evaluation_workspace, change):
    suite = deepcopy(evaluation_workspace["suite"])
    if change == "category":
        suite["cases"][0]["category"] = "invented_category"
    elif change == "scope":
        suite["cases"][0]["selected_doc_id"] = "UNLISTED-DOCUMENT"
    elif change == "answerability":
        suite["cases"][0]["answerable"] = 1
    else:
        suite["cases"] = []

    with pytest.raises(ValueError):
        validate_suite(suite)


def test_suite_loading_checks_real_neutral_pdf_bytes_and_source_offsets(evaluation_workspace):
    path = evaluation_workspace["root"] / "neutral-suite.json"
    path.write_text(json.dumps(evaluation_workspace["suite"]), encoding="utf-8")

    loaded = load_suite(path, evaluation_workspace["root"])

    assert loaded["cases"][0]["evidence"][0]["quote"] == BOARD_QUOTE
    source = evaluation_workspace["root"] / "data/raw/neutral_evaluation_2025.pdf"
    with source.open("ab") as handle:
        handle.write(b"\n% deliberate neutral source-byte mutation\n")
    with pytest.raises(ValueError):
        load_suite(path, evaluation_workspace["root"])


def test_suite_loading_rejects_a_proposed_quote_not_present_at_its_source_span(
    evaluation_workspace,
):
    suite = deepcopy(evaluation_workspace["suite"])
    suite["cases"][0]["evidence"][0]["quote"] = "An altered neutral proposal."
    path = evaluation_workspace["root"] / "neutral-suite.json"
    path.write_text(json.dumps(suite), encoding="utf-8")

    with pytest.raises(ValueError):
        load_suite(path, evaluation_workspace["root"])


def test_source_span_check_accepts_an_exact_same_page_cross_chunk_excerpt(evaluation_workspace):
    retriever = evaluation_workspace["retriever"]
    response = answer_question(
        retriever, QUESTION, doc_id="TEST-2025-EN", fiscal_year=2025, max_excerpts=1
    )
    assert len(response["excerpts"][0]["evidence_ids"]) > 1

    check = check_source_spans(response, retriever, "TEST-2025-EN", 2025)

    assert check["total"] == 1
    assert check["checked"] == 1
    assert check["errors"] == []


@pytest.mark.parametrize("change", ["quote", "doc_id", "fiscal_year", "source_sha256"])
def test_forged_quote_or_source_scope_is_not_a_successful_source_check(
    evaluation_workspace, change
):
    retriever = evaluation_workspace["retriever"]
    response = answer_question(
        retriever, QUESTION, doc_id="TEST-2025-EN", fiscal_year=2025, max_excerpts=1
    )
    bad = {
        "quote": "A fabricated neutral sentence.",
        "doc_id": "TEST-2024-EN",
        "fiscal_year": 2024,
        "source_sha256": "f" * 64,
    }
    response["excerpts"][0][change] = bad[change]

    check = check_source_spans(response, retriever, "TEST-2025-EN", 2025)

    assert check["total"] == 1
    assert check["checked"] == 0
    assert check["errors"]


def test_an_abstention_has_no_successful_or_failed_quote_spans(evaluation_workspace):
    response = answer_question(
        evaluation_workspace["retriever"],
        "What is ZephyrQuartz?",
        doc_id="TEST-2025-EN",
        fiscal_year=2025,
    )
    assert response["status"] == "abstained"

    check = check_source_spans(response, evaluation_workspace["retriever"], "TEST-2025-EN", 2025)

    assert check == {"checked": 0, "total": 0, "errors": []}


def test_run_preserves_raw_outputs_and_digests_without_turning_checks_into_accuracy(
    evaluation_workspace,
):
    suite = evaluation_workspace["suite"]

    run = run_cases(evaluation_workspace["retriever"], suite)

    assert run["schema_version"] == 1
    assert len(run["case_results"]) == 2
    for case, result in zip(suite["cases"], run["case_results"], strict=True):
        assert result["case_id"] == case["id"]
        assert result["case_digest"] == canonical_digest(case)
        assert result["response_digest"] == canonical_digest(result["response"])
        assert result["error"] is None
        assert isinstance(result["retrieval_hits"], list)
        assert result["latency"]
        assert result["engineering_behavior_match"] is True
    summary = run["summary"]
    assert summary["case_count"] == 2 and summary["completed_count"] == 2
    assert summary["error_count"] == 0
    assert summary["expected_behavior"] == {"matched": 2, "eligible": 2}
    assert summary["source_spans"]["checked"] == summary["source_spans"]["total"]
    assert summary["source_spans"]["total"] > 0
    assert summary["proposed_page_hit_at_1"] == {"matched": 1, "eligible": 1}
    assert summary["proposed_page_hit_at_5"] == {"matched": 1, "eligible": 1}
    assert summary["approved_gold_count"] == 0 and summary["human_scored_count"] == 0
    assert set(summary["semantic_metrics"]) == SEMANTIC_FIELDS
    assert all(value is None for value in summary["semantic_metrics"].values())
    assert run["run_digest"] == canonical_digest(
        {key: value for key, value in run.items() if key != "run_digest"}
    )


def test_runtime_errors_remain_in_the_run_and_do_not_remove_cases_from_denominators(
    evaluation_workspace,
):
    class SelectiveFailure(LexicalRetriever):
        def search(self, query, **kwargs):
            if "ZephyrQuartz" in query:
                raise RuntimeError("Deliberate neutral fixture retrieval failure")
            return super().search(query, **kwargs)

    suite = deepcopy(evaluation_workspace["suite"])
    suite["cases"].reverse()
    retriever = SelectiveFailure(evaluation_workspace["retriever"].chunks)

    run = run_cases(retriever, suite)

    assert len(run["case_results"]) == 2
    assert [result["case_id"] for result in run["case_results"]] == [
        case["id"] for case in suite["cases"]
    ]
    assert run["case_results"][0]["error"]
    assert "Deliberate" in str(run["case_results"][0]["error"])
    assert run["case_results"][1]["error"] is None
    assert run["summary"]["case_count"] == 2
    assert run["summary"]["completed_count"] == 1
    assert run["summary"]["error_count"] == 1
    assert run["summary"]["expected_behavior"] == {"matched": 1, "eligible": 2}
    assert all(value is None for value in run["summary"]["semantic_metrics"].values())


def test_review_packet_is_bound_to_the_exact_run_case_and_response_without_scores(
    evaluation_workspace,
):
    run = run_cases(evaluation_workspace["retriever"], evaluation_workspace["suite"])

    packet = make_review_packet(run)

    assert packet["schema_version"] == 1
    assert packet["run_id"] == run["run_id"]
    assert packet["run_digest"] == run["run_digest"]
    assert packet["suite_digest"] == run["suite_digest"]
    assert len(packet["reviews"]) == len(run["case_results"])
    for result, review in zip(run["case_results"], packet["reviews"], strict=True):
        assert review["case_id"] == result["case_id"]
        assert review["case_digest"] == result["case_digest"]
        assert review["response_digest"] == result["response_digest"]
        assert review["gold_review"] == {
            "status": "pending",
            "reviewer": None,
            "reviewed_at": None,
            "notes": "",
        }
        assert set(review["ratings"]) == SEMANTIC_FIELDS
        assert all(value is None for value in review["ratings"].values())
        assert review["reviewer"] is None and review["reviewed_at"] is None
        assert review["notes"] == ""


@pytest.mark.parametrize("refresh_run_digest", [False, True])
def test_review_packet_rejects_edited_responses_with_stale_binding_digests(
    evaluation_workspace, refresh_run_digest
):
    run = run_cases(evaluation_workspace["retriever"], evaluation_workspace["suite"])
    run["case_results"][0]["response"]["message"] = "A changed neutral response."
    if refresh_run_digest:
        run["run_digest"] = canonical_digest(
            {key: value for key, value in run.items() if key != "run_digest"}
        )

    with pytest.raises(ValueError):
        make_review_packet(run)


@pytest.mark.parametrize("mutation", ["drop", "duplicate"])
def test_review_packet_requires_exact_frozen_case_membership_even_with_a_new_run_digest(
    evaluation_workspace, mutation
):
    run = run_cases(evaluation_workspace["retriever"], evaluation_workspace["suite"])
    if mutation == "drop":
        run["case_results"].pop()
    else:
        run["case_results"][1] = deepcopy(run["case_results"][0])
    run["run_digest"] = canonical_digest(
        {key: value for key, value in run.items() if key != "run_digest"}
    )

    with pytest.raises(ValueError, match="exactly once"):
        make_review_packet(run)


@pytest.mark.parametrize("field", ["question", "candidate_answer", "proposed_evidence"])
def test_review_packet_rejects_changed_convenience_proposals_after_outer_digest_refresh(
    evaluation_workspace, field
):
    run = run_cases(evaluation_workspace["retriever"], evaluation_workspace["suite"])
    if field == "proposed_evidence":
        run["case_results"][0][field][0]["quote"] = "A changed neutral evidence proposal."
    else:
        run["case_results"][0][field] = "A changed neutral question or answer proposal."
    run["run_digest"] = canonical_digest(
        {key: value for key, value in run.items() if key != "run_digest"}
    )

    with pytest.raises(ValueError, match="proposal fields"):
        make_review_packet(run)


@pytest.mark.parametrize(
    ("field", "wrong_value"), [("doc_id", "TEST-2024-EN"), ("fiscal_year", 2024)]
)
def test_wrong_scope_diagnostic_hit_on_expected_page_does_not_count_as_a_page_hit(
    evaluation_workspace, monkeypatch, field, wrong_value
):
    clean = evaluation_workspace["retriever"]
    valid_hit = clean.search(QUESTION, doc_id="TEST-2025-EN", fiscal_year=2025, top_k=1)[0]
    bad_hit = SearchHit(
        replace(valid_hit.chunk, **{field: wrong_value}),
        valid_hit.score,
        valid_hit.matched_terms,
    )

    class WrongScopeDiagnostics(LexicalRetriever):
        def search(self, query, **kwargs):
            return [bad_hit]

    def answer_using_valid_sources(_retriever, query, **kwargs):
        return answer_question(clean, query, **kwargs)

    monkeypatch.setattr(evaluation, "answer_question", answer_using_valid_sources)
    suite = deepcopy(evaluation_workspace["suite"])
    suite["cases"] = suite["cases"][:1]

    run = run_cases(WrongScopeDiagnostics(clean.chunks), suite)

    result = run["case_results"][0]
    assert result["error"] is None
    assert result["response"]["status"] == "extractive_evidence"
    assert result["retrieval_error"]["kind"] == "unexpected_error"
    assert result["retrieval_hits"][0]["pdf_page"] == 7
    assert result["proposed_page_hit_at_1"] is False
    assert result["proposed_page_hit_at_5"] is False
    assert run["summary"]["proposed_page_hit_at_1"] == {"matched": 0, "eligible": 1}
    assert run["summary"]["proposed_page_hit_at_5"] == {"matched": 0, "eligible": 1}
    assert run["summary"]["unexpected_diagnostic_error_count"] == 1


def test_missing_response_status_is_retained_as_a_case_error_without_losing_later_cases(
    evaluation_workspace, monkeypatch
):
    malformed = {
        "scope": {"doc_id": "TEST-2025-EN", "fiscal_year": 2025},
        "message": "Deliberately incomplete neutral response.",
        "excerpts": [],
    }

    def sometimes_malformed(retriever, query, **kwargs):
        if query == QUESTION:
            return deepcopy(malformed)
        return answer_question(retriever, query, **kwargs)

    monkeypatch.setattr(evaluation, "answer_question", sometimes_malformed)

    run = run_cases(evaluation_workspace["retriever"], evaluation_workspace["suite"])

    assert len(run["case_results"]) == 2
    assert run["case_results"][0]["response"] == malformed
    assert run["case_results"][0]["response_digest"] == canonical_digest(malformed)
    assert run["case_results"][0]["error"]
    assert run["case_results"][1]["error"] is None
    assert run["summary"]["case_count"] == 2
    assert run["summary"]["completed_count"] == 1
    assert run["summary"]["error_count"] == 1
    assert run["summary"]["expected_behavior"] == {"matched": 1, "eligible": 2}
    assert all(value is None for value in run["summary"]["semantic_metrics"].values())
