"""English local Streamlit workspace for inspecting report evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st

from financial_intelligence_copilot.answer import answer_question
from financial_intelligence_copilot.cloud_data import get_cloud_workspace
from financial_intelligence_copilot.evaluation_records import load_development_record
from financial_intelligence_copilot.financial_answer import answer_reviewed_kpi
from financial_intelligence_copilot.financial_kpis import candidate_csv
from financial_intelligence_copilot.kpi_reviews import comparison_results, load_review_state
from financial_intelligence_copilot.retrieval import load_retriever
from financial_intelligence_copilot.session_data import (
    prepare_session_workspace,
    session_metadata_fingerprint,
)
from financial_intelligence_copilot.ui_charts import comparison_figure
from financial_intelligence_copilot.ui_state import (
    official_pdf_link,
    read_documents,
    workspace_fingerprint,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = {
    "Risk governance": (
        "Which body sets AIA's Risk Appetite and approves its Risk Management Framework?"
    ),
    "Wellness programme": "What is AIA Vitality?",
    "Missing evidence": "What is ZephyrQuartz?",
    "Financial metric boundary": "What is AIA's VONB in USD million?",
}
DATA_ERRORS = (OSError, ValueError, KeyError, TypeError)


def _empty_runtime_checkout(project_root: Path) -> bool:
    """Initialize a clean checkout, without concealing partial or damaged local data."""
    documents = read_documents(project_root)
    paths = [project_root / "data/processed/retrieval-index.json"]
    for item in documents:
        paths.extend(
            [
                project_root / "data/raw" / item["local_filename"],
                project_root / "data/processed" / f"{item['doc_id']}.pages.json",
            ]
        )
    return not any(path.exists() or path.is_symlink() for path in paths)


def _automatic_workspace(project_root: Path) -> tuple[Path, dict | None, str | None]:
    """Adopt only the official runtime cache; a failed attempt needs an explicit retry."""
    revision = None
    try:
        if not _empty_runtime_checkout(project_root):
            st.session_state.pop("_cloud_workspace_handle", None)
            return project_root, None, None
        revision = session_metadata_fingerprint(project_root)
        failure = st.session_state.get("_cloud_setup_failure")
        if (
            failure
            and failure["project_root"] == str(project_root)
            and failure["revision"] == revision
        ):
            return project_root, None, failure["message"]
        with st.spinner("Preparing official AIA reports and checking source evidence..."):
            stats = get_cloud_workspace(project_root)
        if (
            stats["metadata_fingerprint"] != revision
            or session_metadata_fingerprint(project_root) != revision
        ):
            raise ValueError("Registered source configuration changed during initialization")
        st.session_state["_cloud_workspace_handle"] = stats
        st.session_state.pop("_cloud_setup_failure", None)
        return Path(stats["root"]), stats, None
    except DATA_ERRORS as exc:
        st.session_state.pop("_cloud_workspace_handle", None)
        message = str(exc)
        st.session_state["_cloud_setup_failure"] = {
            "project_root": str(project_root),
            "revision": revision,
            "message": message,
        }
        return project_root, None, message


def _clear_session_workspace() -> None:
    """Discard only the temporary workspace owned by this Streamlit session."""
    _clear_response_and_engine()
    temporary = st.session_state.pop("_session_tempdir", None)
    for key in (
        "_session_workspace",
        "_session_project_root",
        "_session_metadata_fingerprint",
        "_session_report_stats",
    ):
        st.session_state.pop(key, None)
    st.session_state["_session_upload_generation"] = (
        st.session_state.get("_session_upload_generation", 0) + 1
    )
    if temporary is not None:
        temporary.cleanup()


def _current_workspace(project_root: Path) -> tuple[Path, str | None]:
    """Use session data only while its original public source configuration matches."""
    owner_root = st.session_state.get("_session_project_root")
    if owner_root is not None and owner_root != str(project_root):
        _clear_session_workspace()
    active = st.session_state.get("_session_workspace")
    if active is None:
        return project_root, None
    try:
        current = session_metadata_fingerprint(project_root)
    except DATA_ERRORS:
        current = None
    if current != st.session_state.get("_session_metadata_fingerprint"):
        _clear_session_workspace()
        return (
            project_root,
            "The registered source or review configuration changed. Load reports again.",
        )
    return Path(active), None


def _load_session_reports(project_root: Path, reports: dict[str, bytes]) -> dict:
    """Adopt a fully checked new workspace; failed uploads preserve the previous one."""
    temporary = TemporaryDirectory(prefix="fic-report-session-")
    try:
        stats = prepare_session_workspace(project_root, reports, Path(temporary.name) / "workspace")
        workspace = Path(stats["root"])
        workspace_fingerprint(workspace, read_documents(workspace))
        if stats["metadata_fingerprint"] != session_metadata_fingerprint(project_root):
            raise ValueError("Registered source configuration changed while reports were loading")
        _clear_session_workspace()
    except Exception:
        temporary.cleanup()
        raise
    st.session_state["_session_tempdir"] = temporary
    st.session_state["_session_workspace"] = str(workspace)
    st.session_state["_session_project_root"] = str(project_root)
    st.session_state["_session_metadata_fingerprint"] = stats["metadata_fingerprint"]
    st.session_state["_session_report_stats"] = stats
    return stats


def _render_session_setup(project_root: Path, data_error: str | None, notice: str | None) -> None:
    """Load only the two registered reports into isolated temporary server storage."""
    active = st.session_state.get("_session_workspace") is not None
    if notice:
        st.warning(notice)
    if active:
        stats = st.session_state["_session_report_stats"]
        st.success(
            f"Session reports loaded: {stats['document_count']} reports, "
            f"{stats['page_count']} physical pages and {stats['chunk_count']} evidence chunks."
        )
        st.caption("Report bytes matched the registered sources. Financial review is separate.")
        if st.button("Clear loaded reports", key="clear_session_reports"):
            try:
                _clear_session_workspace()
            except DATA_ERRORS as exc:
                st.error("Could not completely clear temporary report files. " + str(exc))
            else:
                st.rerun()
    elif data_error:
        st.warning("Report data has not been loaded in this session.")
    with st.expander("Load official AIA reports for this session", expanded=bool(data_error)):
        st.write(
            "Load the registered AIA FY2024 and FY2025 English annual reports. "
            "Only the two registered PDF versions are accepted; other documents are rejected."
        )
        st.caption(
            "Use reports you are authorized to process. Files are uploaded to temporary server "
            "storage for this session, not to GitHub. Full reports and extracted text are not "
            "offered for download. No model API is called or financial approval recorded. "
            "You may need to load reports again after a restart or a new session."
        )
        try:
            documents = read_documents(project_root)
        except DATA_ERRORS as exc:
            st.error("The registered source inventory is unavailable. " + str(exc))
            return
        uploads = {}
        generation = st.session_state.get("_session_upload_generation", 0)
        for document in sorted(documents, key=lambda item: item["fiscal_year"]):
            year = document["fiscal_year"]
            st.link_button(f"Get the official FY{year} English report", document["source_url"])
            uploaded = st.file_uploader(
                f"AIA FY{year} official annual report (PDF)",
                type=["pdf"],
                accept_multiple_files=False,
                max_upload_size=16,
                key=f"session_report_{generation}_{document['doc_id']}",
            )
            if uploaded is not None:
                uploads[document["doc_id"]] = uploaded.getvalue()
        if st.button(
            "Load official reports",
            key="load_session_reports",
            disabled=len(uploads) != len(documents),
        ):
            try:
                with st.spinner("Checking report hashes, physical pages and evidence index..."):
                    _load_session_reports(project_root, uploads)
            except DATA_ERRORS as exc:
                st.error("Could not load the registered reports. " + str(exc))
                st.caption(
                    "Check that each file is the full English report for its labeled year. "
                    "A changed official version needs source review; its hash is not updated here."
                )
            else:
                st.rerun()


def _clear_response_and_engine() -> None:
    for key in (
        "_response",
        "_response_question",
        "_retriever",
        "_engine_revision",
        "_load_error",
        "_kpi_candidates",
        "_kpi_revision",
        "_review_state",
        "_review_revision",
        "_comparison_results",
        "_comparison_revision",
        "comparison_metric",
    ):
        st.session_state.pop(key, None)


def _set_example() -> None:
    label = st.session_state["example"]
    if label in EXAMPLES:
        st.session_state["question"] = EXAMPLES[label]
    st.session_state.pop("_response", None)


def _verified_engine(root: Path, revision: str):
    if st.session_state.get("_engine_revision") != revision:
        engine = load_retriever(
            root / "data/processed/retrieval-index.json",
            manifest_path=root / "data/manifest.csv",
            raw_dir=root / "data/raw",
            pages_dir=root / "data/processed",
            policy_path=root / "data/retrieval_policy.json",
        )
        if workspace_fingerprint(root, read_documents(root)) != revision:
            raise ValueError("Local sources changed during verification. Recheck and try again.")
        st.session_state["_retriever"] = engine
        st.session_state["_engine_revision"] = revision
    return st.session_state["_retriever"]


def _verified_reviews(root: Path, revision: str) -> dict:
    if st.session_state.get("_review_revision") != revision:
        state = load_review_state(root)
        results = comparison_results(state)
        if workspace_fingerprint(root, read_documents(root)) != revision:
            raise ValueError("Review sources changed during validation. Recheck and try again.")
        st.session_state["_review_state"] = state
        st.session_state["_review_revision"] = revision
        st.session_state["_comparison_results"] = results
        st.session_state["_comparison_revision"] = revision
        st.session_state["_kpi_candidates"] = state["candidates"]
        st.session_state["_kpi_revision"] = revision
    if workspace_fingerprint(root, read_documents(root)) != revision:
        raise ValueError("Review sources changed before display. Recheck and try again.")
    return st.session_state["_review_state"]


def _clear_reviews() -> None:
    for key in (
        "_review_state",
        "_review_revision",
        "_comparison_results",
        "_comparison_revision",
        "_kpi_candidates",
        "_kpi_revision",
        "comparison_metric",
    ):
        st.session_state.pop(key, None)


def _render_response(response: dict) -> None:
    st.divider()
    financial_lookup = response.get("mode") == "reviewed_kpi_lookup"
    st.subheader("Reviewed financial fact" if financial_lookup else "Report evidence")
    st.caption(f"Response to: {response['query']}")
    if response["status"] == "abstained":
        st.warning(response["message"])
        st.caption(f"Reason: {response['reason'].replace('_', ' ')}")
    elif financial_lookup:
        item = response["financial_fact"]
        st.info(
            "Reported annual level from a recorded fact confirmation. No comparison is implied."
        )
        st.write(item["metric_name"])
        units = " ".join(part for part in (item["currency"], item["unit"]) if part)
        st.metric("Reported annual level", f"{item['value']} {units}")
        st.caption(f"FY{item['fiscal_year']} · Physical PDF page {item['source_pdf_page']}")
        st.write(f"Annual period: {item['period_start']} to {item['period_end']}")
        st.write("Scope: " + item["scope"])
        st.write("Basis: " + item["basis"])
        st.caption("Original numeric source token (not a complete answer quotation)")
        st.code(item["source_snippet"], language=None, wrap_lines=True)
        st.link_button(
            f"Open official report · PDF page {item['source_pdf_page']}",
            official_pdf_link(item["source_url"], item["source_pdf_page"]),
        )
        with st.expander("Source context and recorded review"):
            st.code(item["source_row_snippet"], language=None, wrap_lines=True)
            if item.get("source_header"):
                st.code(item["source_header"]["text"], language=None, wrap_lines=True)
            st.write("Recorded reviewer: " + item["reviewer"])
            st.write("Recorded review time: " + item["reviewed_at"])
            st.write("Review notes: " + item["fact_review"]["notes"])
            st.write("Comparability caveats: " + item["comparability_notes"])
            st.caption(
                "Recorded metadata and content hashes do not authenticate reviewer identity."
            )
            st.code(
                json.dumps(
                    {
                        "candidate_id": item["candidate_id"],
                        "source_doc_id": item["source_doc_id"],
                        "source_sha256": item["source_sha256"],
                        "page_character_range": [
                            item["source_char_start"],
                            item["source_char_end"],
                        ],
                        "definition_pages": item.get("definition_pages", []),
                    },
                    indent=2,
                ),
                language="json",
            )
        st.caption(response["notice"])
    else:
        st.info(
            "Original-text excerpts. Evidence may be partial; review the report for full context."
        )
        for number, item in enumerate(response["excerpts"], start=1):
            with st.container(border=True):
                st.markdown(
                    f"**Excerpt {number} · FY{item['fiscal_year']} · PDF page {item['pdf_page']}**"
                )
                st.caption(item["issuer"] + " · Source-span checked")
                st.code(item["quote"], language=None, wrap_lines=True)
                st.link_button(
                    f"Open official report · PDF page {item['pdf_page']}",
                    official_pdf_link(item["source_url"], item["pdf_page"]),
                )
                with st.expander("Citation details"):
                    st.code(
                        json.dumps(
                            {
                                "evidence_ids": item["evidence_ids"],
                                "doc_id": item["doc_id"],
                                "source_sha256": item["source_sha256"],
                                "page_character_range": [item["char_start"], item["char_end"]],
                            },
                            indent=2,
                        ),
                        language="json",
                    )
    st.caption("Research demonstration only - not investment advice.")
    st.download_button(
        "Download response JSON",
        json.dumps(response, ensure_ascii=False, indent=2),
        file_name=f"{response['scope']['doc_id']}.response.json",
        mime="application/json",
    )


def _render_about(root: Path, documents: list[dict]) -> None:
    st.subheader("Evidence you can inspect")
    st.write(
        "This prototype helps researchers inspect AIA annual-report evidence with traceable "
        "physical PDF page references. Original excerpts and a separate reviewed annual KPI "
        "lookup retain their distinct evidence and review requirements."
    )
    st.caption("Official PDF → Page-preserving text → Local retrieval → Source-span validation")
    st.markdown("**Official report sources**")
    for item in documents:
        st.link_button(f"AIA FY{item['fiscal_year']} · English annual report", item["source_url"])
    st.subheader("Recorded development evaluation")
    try:
        record = load_development_record(root)
    except DATA_ERRORS as exc:
        record = None
        st.error("Evaluation record validation failed. " + str(exc))
    if record:
        recorded_at = datetime.fromisoformat(record["started_at"]).astimezone(UTC)
        st.caption("Recorded on " + recorded_at.strftime("%Y-%m-%d %H:%M UTC"))
        st.dataframe(
            [
                {
                    "Recorded check": "Cases completed",
                    "Result": f"{record['completed_count']}/{record['case_count']}",
                },
                {
                    "Recorded check": "Current-mode engineering behavior matches",
                    "Result": f"{record['behavior_matched']}/{record['behavior_eligible']}",
                },
                {
                    "Recorded check": "Literal source spans",
                    "Result": f"{record['spans_checked']}/{record['spans_total']}"
                    if record["spans_total"]
                    else "N/A (no excerpts)",
                },
                {
                    "Recorded check": "Proposed evidence-page hits within five results",
                    "Result": (
                        f"{record['page_hits_5']}/{record['page_hit_eligible']}"
                        if record["page_hit_eligible"]
                        else "N/A (no eligible questions)"
                    ),
                },
                {
                    "Recorded check": "Runtime errors / cases with span errors",
                    "Result": f"{record['error_count']} / {record['span_case_errors']}",
                },
            ],
            hide_index=True,
            width="stretch",
        )
        st.info(
            "Human correctness scores are unavailable: 0 approved gold answers "
            "and 0 human-scored cases."
        )
        st.caption(
            "These are development-exposed behavior, source-span and proposed-page observations. "
            "They do not measure answer correctness, citation relevance, numerical correctness "
            "or appropriate final-product abstention."
        )
        if not record["code_snapshot_current"]:
            st.warning(
                "This run was produced by an earlier code/configuration snapshot. "
                "Its observations describe the recorded run."
            )
        with st.expander("Recorded evaluation details"):
            st.caption("Run ID: " + record["run_id"])
            st.caption("Run digest: " + record["run_digest"])
            if record["page_hit_eligible"]:
                st.write(
                    f"Proposed page hits at rank 1: {record['page_hits_1']}/"
                    f"{record['page_hit_eligible']}"
                )
            else:
                st.write("Proposed page hits at rank 1: N/A (no eligible questions)")
            st.write(
                "The source inputs still match this record. "
                "Current UI behavior is not a fresh evaluation run."
            )
    else:
        st.info("No validated local development evaluation record is available.")
        st.caption(
            "Obtain the local sources and reproduce the recorded development run using the README. "
            "Human correctness scores remain unavailable."
        )
    with st.expander("Scope and limitations", expanded=True):
        st.write(
            "Product-owner source and case review is pending. "
            "Quotes are checked against source IDs and offsets; this does not establish "
            "relevance, completeness, or financial correctness. "
            "Some multi-part questions have partial coverage. "
            "Multicolumn reading order and lexical "
            "matching can still fail. Page labels use physical PDF positions, starting at 1."
        )
        st.write(
            "Financial tabs read recorded fact and comparability decisions. Formal semantic "
            "evaluation needs separate owner review. Generative answering is a separate product "
            "decision. This mode makes no model API calls."
        )
        st.write(
            "Reviewed KPI lookup revalidates a separate local fact store before display. "
            "It supports one reported annual level; it does not interpret definitions, "
            "convert currencies or calculate comparisons. A fact confirmation does not "
            "establish comparability or authenticate the recorded reviewer."
        )


def _render_kpi_review(root: Path, fiscal_year: int, revision: str | None, data_error) -> None:
    st.subheader("Financial KPIs")
    if not (root / "data/kpi_candidates.json").is_file():
        st.info("Verified financial KPIs are not available yet.")
        st.write(
            "Values require source, currency, unit, period, scope, and basis review before display."
        )
        return
    if data_error:
        st.warning("Restore the registered local sources before reviewing candidate values.")
        return
    try:
        with st.spinner("Checking report inputs and review records..."):
            state = _verified_reviews(root, revision)
        records = state["candidates"]
    except DATA_ERRORS as exc:
        _clear_reviews()
        st.error("KPI candidate validation failed. " + str(exc))
        return
    if not records:
        st.info("No local review candidates are registered.")
        return
    facts = {item["candidate_id"]: item for item in state["packet"]["candidate_reviews"]}
    confirmed = [item for item in records if facts[item["candidate_id"]]["decision"] == "confirmed"]
    if confirmed:
        st.success(f"Fact confirmations recorded: {len(confirmed)}")
        with st.expander("Confirmed report inputs"):
            st.dataframe(
                [
                    {
                        "Metric": item["metric_code"],
                        "Fiscal year": item["fiscal_year"],
                        "Confirmed value": f"{item['value']:,}",
                        "Unit": "%" if item["unit"] == "percent" else "USD million",
                        "Reviewer": facts[item["candidate_id"]]["reviewer"],
                        "Reviewed at": facts[item["candidate_id"]]["reviewed_at"],
                        "PDF page": item["source_pdf_page"],
                    }
                    for item in confirmed
                ],
                hide_index=True,
                width="stretch",
            )
        st.caption("Recorded fact confirmations do not independently approve a comparison.")
    else:
        st.info("Verified financial KPIs are not available yet.")
    st.caption("Candidate source records and recorded fact decisions are kept separately.")
    st.subheader("Candidate review")
    if not confirmed:
        st.warning("Pending owner review - these values are not verified financial data.")
    else:
        st.info(
            "Candidate records retain their original status; recorded fact decisions appear below."
        )
    view = st.radio("Review scope", ["Selected fiscal year", "Both fiscal years"], horizontal=True)
    selected = (
        records
        if view == "Both fiscal years"
        else [item for item in records if item["fiscal_year"] == fiscal_year]
    )
    st.dataframe(
        [
            {
                "Metric": item["metric_code"],
                "Fiscal year": item["fiscal_year"],
                "Candidate value": f"{item['value']:,}",
                "Currency": item["currency"] or "N/A",
                "Unit": item["unit"],
                "Fact review": facts[item["candidate_id"]]["decision"].replace("_", " ").title(),
                "PDF page": item["source_pdf_page"],
            }
            for item in selected
        ],
        hide_index=True,
        width="stretch",
    )
    if not selected:
        return
    by_id = {item["candidate_id"]: item for item in selected}
    chosen = st.selectbox(
        "Review candidate",
        list(by_id),
        key="kpi_candidate",
        format_func=lambda key: f"{by_id[key]['metric_code']} · FY{by_id[key]['fiscal_year']}",
    )
    item = by_id[chosen]
    with st.container(border=True):
        st.markdown("**" + item["metric_name"] + "**")
        unit = "%" if item["unit"] == "percent" else "USD million"
        st.write(f"Candidate value: {item['value']:,} {unit}")
        decision = facts[item["candidate_id"]]
        st.caption(f"{item['candidate_id']} · Fact review: {decision['decision']}")
        if decision["decision"] != "pending":
            st.caption(f"Reviewer: {decision['reviewer']} · Reviewed at: {decision['reviewed_at']}")
            st.write("Review notes: " + decision["notes"])
        st.caption("Comparison availability is determined separately in Year-over-Year.")
        st.write(f"Period: {item['period_start']} to {item['period_end']}")
        st.write("Scope: " + item["scope"])
        st.write("Basis: " + item["basis"])
        st.warning(item["comparability_notes"])
        st.link_button(
            f"Open candidate source · PDF page {item['source_pdf_page']}",
            official_pdf_link(item["source_url"], item["source_pdf_page"]),
        )
        st.caption(
            "Original header context and table row. Check the fiscal-year column and total-row "
            "definition; native text may include adjacent rows or sidebar noise."
        )
        if item.get("source_header"):
            st.code(item["source_header"]["text"], language=None, wrap_lines=False)
        st.code(item["source_row_snippet"], language=None, wrap_lines=True)
        if prior := item.get("prior_year_comparative"):
            st.write(
                f"FY{item['fiscal_year']} report's FY{prior['reported_fiscal_year']} comparative: "
                f"{prior['value']:,} {unit}."
            )
            state = "matches" if item["comparative_matches_original"] else "differs from"
            st.caption(
                "This headline value " + state + " the original prior-year candidate. "
                "A match does not approve financial comparability."
            )
        with st.expander("Definition, scope and tax references"):
            for reference in item.get("definition_pages", []):
                st.link_button(
                    f"{reference['topic']} · PDF page {reference['pdf_page']}",
                    official_pdf_link(item["source_url"], reference["pdf_page"]),
                )
            st.caption(f"Source SHA256: {item['source_sha256']}")
            st.caption(
                f"Numeric token: {item['source_snippet']} · page characters "
                f"[{item['source_char_start']}, {item['source_char_end']})"
            )
    st.download_button(
        "Download all candidates (CSV)",
        candidate_csv(records),
        file_name="kpi-candidates-pending-review.csv",
        mime="text/csv",
    )
    st.caption(
        "Confirm the row, column, units, period, scope, definition and tax basis. "
        "No approval or growth calculation is performed by this review page."
    )


def _review_reason(reason: str) -> str:
    labels = {
        "fact_review_pending": "Fact confirmation pending",
        "fact_review_rejected": "An input fact was rejected",
        "comparability_pending": "Comparability review pending",
        "not_comparable": "Pair recorded as not comparable",
        "non_positive_prior": "Prior value is zero or negative; manual review required",
    }
    return labels.get(reason, reason.replace("_", " ").capitalize())


def _decimal_json(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError("Unsupported comparison export value")


def _render_comparisons(root: Path, revision: str | None, data_error) -> None:
    st.subheader("Year-over-Year")
    st.caption(
        "This view reviews FY2024 and FY2025 together, "
        "independently of the question's selected year."
    )
    if data_error:
        st.warning("Restore the registered local sources before reviewing comparisons.")
        return
    if not (root / "data/kpi_candidates.json").is_file():
        st.info("Year-over-year analysis is pending verified, comparable KPI inputs.")
        return
    try:
        state = _verified_reviews(root, revision)
        results = st.session_state["_comparison_results"]
        if workspace_fingerprint(root, read_documents(root)) != revision:
            raise ValueError("Review sources changed before display. Recheck and try again.")
    except DATA_ERRORS as exc:
        _clear_reviews()
        st.error("Comparison validation failed. " + str(exc))
        return
    if not results:
        st.info("Year-over-year analysis is pending verified, comparable KPI inputs.")
        st.caption("Register independently sourced annual inputs for both years.")
        return
    calculated = [item for item in results if item["status"] == "calculated"]
    if not calculated:
        st.info("Year-over-year analysis is pending verified, comparable KPI inputs.")
    st.subheader("Comparison readiness")
    fact_count = sum(
        item["decision"] == "confirmed" for item in state["packet"]["candidate_reviews"]
    )
    st.caption(
        f"Confirmed facts: {fact_count}/{len(state['candidates'])} · "
        f"Calculated pairs: {len(calculated)}/{len(results)}"
    )
    if not state["packet_present"]:
        st.warning("No local review packet is present. Every decision remains pending.")
    st.dataframe(
        [
            {
                "Metric": item["metric_code"],
                "Previous year": item["previous_source"]["fiscal_year"],
                "Current year": item["current_source"]["fiscal_year"],
                "Status": "Available" if item["status"] == "calculated" else "Needs review",
                "Reason": "; ".join(_review_reason(reason) for reason in item["reasons"])
                or "Recorded reviews passed",
            }
            for item in results
        ],
        hide_index=True,
        width="stretch",
    )
    by_key = {
        item["previous_source"]["candidate_id"] + ":" + item["current_source"]["candidate_id"]: item
        for item in results
    }
    chosen = st.selectbox(
        "Comparison metric",
        list(by_key),
        key="comparison_metric",
        format_func=lambda key: (
            f"{by_key[key]['metric_code']} · FY{by_key[key]['previous_source']['fiscal_year']} "
            f"→ FY{by_key[key]['current_source']['fiscal_year']}"
        ),
    )
    item = by_key[chosen]
    with st.container(border=True):
        st.markdown("**" + item["metric_code"] + "**")
        if item["status"] != "calculated":
            st.warning("; ".join(_review_reason(reason) for reason in item["reasons"]))
        else:
            st.subheader("Reviewed comparison")
            unit = "%" if item["unit"] == "percent" else "USD million"
            st.write(
                f"FY{item['previous_source']['fiscal_year']}: {item['previous_value']:,} {unit} · "
                f"FY{item['current_source']['fiscal_year']}: {item['current_value']:,} {unit}"
            )
            st.caption("Scope: " + item["scope"] + " · Basis: " + item["basis"])
            if item["unit"] == "percent":
                st.metric("Percentage-point change", f"{item['percentage_point_change']:,} pp")
            else:
                left, right = st.columns(2)
                left.metric("Absolute change", f"{item['absolute_change']:,} {unit}")
                right.metric("Percentage change", f"{item['percentage_change']:.2f}%")
                st.caption(
                    "Percentage change is rounded to two decimal places for display; "
                    "the JSON export retains the full calculated result."
                )
            st.caption("Changes use reported annual levels and are not labeled CER growth.")
            try:
                figure = comparison_figure(item)
                st.plotly_chart(
                    figure,
                    width="stretch",
                    key="reviewed-comparison-chart",
                    config={"displaylogo": False},
                )
            except ValueError as exc:
                st.error("Comparison chart could not be prepared. " + str(exc))
            with st.expander("Recorded review decisions"):
                st.write("Pair reviewer: " + item["comparison_reviewer"])
                st.write("Reviewed at: " + item["comparison_reviewed_at"])
                st.write(item["comparison_notes"])
                st.code(json.dumps(item["review_records"], indent=2), language="json")
        for label in ("previous_source", "current_source"):
            source = item[label]
            st.link_button(
                f"FY{source['fiscal_year']} source · PDF page {source['source_pdf_page']}",
                official_pdf_link(source["source_url"], source["source_pdf_page"]),
            )
            st.caption(
                f"{source['candidate_id']} · Period: "
                f"{source['period_start']} to {source['period_end']}"
            )
    st.download_button(
        "Download comparison audit JSON",
        json.dumps(results, default=_decimal_json, indent=2),
        file_name="comparison-readiness.json",
        mime="application/json",
    )
    st.caption(
        "This view reads recorded decisions and does not write approvals. "
        "Pending pairs have no calculated change or chart."
    )


def run_app(root: Path | None = None, *, auto_load_reports: bool = False) -> None:
    project_root = Path(root).resolve() if root is not None else PROJECT_ROOT
    st.set_page_config(page_title="Financial Intelligence Copilot", page_icon="📖", layout="wide")
    st.caption("FINANCIAL RESEARCH WORKSPACE")
    st.title("Financial Intelligence Copilot")
    st.write("Annual-report research, with evidence you can inspect.")
    st.caption("Local research modes · Research demonstration only - not investment advice.")

    root, session_notice = _current_workspace(project_root)
    cloud_stats, cloud_error = None, None
    if auto_load_reports and root == project_root:
        root, cloud_stats, cloud_error = _automatic_workspace(project_root)

    documents, revision, data_error = [], None, None
    try:
        documents = read_documents(root)
        revision = workspace_fingerprint(root, documents)
    except DATA_ERRORS as exc:
        data_error = str(exc)
        _clear_response_and_engine()

    with st.sidebar:
        st.header("Research scope")
        st.selectbox("Company", ["AIA Group Limited"], disabled=True)
        years = [item["fiscal_year"] for item in documents] or [2025, 2024]
        fiscal_year = st.selectbox(
            "Fiscal year", years, key="fiscal_year", format_func=lambda year: f"FY{year}"
        )
        st.caption("English official annual reports. One selected report per question.")
        answer_mode = st.selectbox(
            "Answer mode", ["Original excerpts", "Reviewed KPI lookup"], key="answer_mode"
        )
        st.divider()
        st.markdown("**Local research modes**")
        st.caption(
            "Original excerpts or a single reviewed annual KPI level. "
            "No generated summaries or model API calls."
        )
        recheck = st.button("Recheck local sources", disabled=bool(data_error))

    document = next((item for item in documents if item["fiscal_year"] == fiscal_year), None)
    doc_id = document["doc_id"] if document else f"AIA-{fiscal_year}-EN"
    active_scope = (str(root), doc_id, fiscal_year, revision, answer_mode)
    if st.session_state.get("_active_scope") != active_scope:
        _clear_response_and_engine()
        st.session_state["_active_scope"] = active_scope
    if recheck:
        _clear_response_and_engine()
        try:
            with st.spinner("Checking local sources and index..."):
                _verified_engine(root, revision)
        except DATA_ERRORS as exc:
            st.session_state["_load_error"] = str(exc)
    source_status = st.sidebar.empty()

    left, middle, right = st.columns(3)
    left.metric("Registered reports", len(documents))
    middle.metric("Selected report", f"FY{fiscal_year}")
    right.metric(
        "Response mode", "Reviewed KPI" if answer_mode == "Reviewed KPI lookup" else "Excerpts"
    )
    tabs = st.tabs(
        ["Ask the Annual Report", "Financial KPIs", "Year-over-Year", "About & Evaluation"]
    )
    with tabs[0]:
        st.subheader("Ask the selected annual report")
        st.caption(
            "Choose an example or ask an English question. Every released quote retains its source."
        )
        if answer_mode == "Reviewed KPI lookup":
            st.info(
                "Look up one reported annual metric: VONB, ANP, VONB_MARGIN, OPAT or UFSG. "
                "For example: What is AIA's VONB in USD million? "
                "Only explicitly confirmed facts in the current local reviewed store can be shown. "
                "Definitions, multiple metrics and comparisons are outside this lookup mode."
            )
        if cloud_stats:
            st.success(
                f"Official reports ready: {cloud_stats['document_count']} reports, "
                f"{cloud_stats['page_count']} physical pages and "
                f"{cloud_stats['chunk_count']:,} evidence chunks."
            )
            st.caption(
                "Automatically loaded from AIA and checked against the registered hashes. "
                "You can refresh or open a new tab without uploading reports. "
                "Financial fact confirmation remains separate."
            )
        elif cloud_error:
            st.error("Automatic report loading could not finish. Retry or use the upload fallback.")
            if st.button("Retry official report loading", key="retry_cloud_reports"):
                st.session_state.pop("_cloud_setup_failure", None)
                st.rerun()
            with st.expander("Source diagnostic details"):
                st.code(cloud_error, language=None)
        elif data_error:
            with st.expander("Source diagnostic details"):
                st.error(f"Local data is unavailable. {data_error}")
                st.caption(
                    "Load the registered reports for this session, or restore local files "
                    "and rebuild the index using the README."
                )
        if not cloud_stats:
            _render_session_setup(project_root, data_error, session_notice)
        st.session_state.setdefault("question", EXAMPLES["Risk governance"])
        st.selectbox(
            "Start with an example",
            list(EXAMPLES) + ["Custom question"],
            key="example",
            on_change=_set_example,
        )
        with st.form("annual_report_question"):
            question = st.text_area("Your question", key="question", max_chars=2000, height=110)
            submitted = st.form_submit_button(
                "Find evidence", type="primary", disabled=bool(data_error)
            )
        if submitted and not question.strip():
            st.session_state.pop("_response", None)
            st.warning("Enter an English question to inspect report evidence.")
        elif submitted:
            st.session_state.pop("_response", None)
            st.session_state.pop("_load_error", None)
            try:
                with st.spinner("Checking sources and finding report evidence..."):
                    if answer_mode == "Reviewed KPI lookup":
                        response = answer_reviewed_kpi(
                            root, question, doc_id=doc_id, fiscal_year=fiscal_year
                        )
                    else:
                        engine = _verified_engine(root, revision)
                        response = answer_question(
                            engine, question, doc_id=doc_id, fiscal_year=fiscal_year
                        )
                    if workspace_fingerprint(root, read_documents(root)) != revision:
                        raise ValueError(
                            "Local sources changed during the query. Recheck and try again."
                        )
                st.session_state["_response"] = response
            except DATA_ERRORS as exc:
                _clear_response_and_engine()
                st.session_state["_load_error"] = str(exc)
        if st.session_state.get("_load_error"):
            st.error("Could not verify local sources. " + st.session_state["_load_error"])
        response = st.session_state.get("_response")
        if response and response.get("mode") == "reviewed_kpi_lookup" and not submitted:
            try:
                response = answer_reviewed_kpi(
                    root, response["query"], doc_id=doc_id, fiscal_year=fiscal_year
                )
                if workspace_fingerprint(root, read_documents(root)) != revision:
                    raise ValueError(
                        "Local sources changed before the financial response display. "
                        "Recheck and try again."
                    )
                st.session_state["_response"] = response
            except DATA_ERRORS as exc:
                _clear_response_and_engine()
                st.session_state["_load_error"] = str(exc)
                st.error("Could not verify the reviewed KPI response. " + str(exc))
                response = None
        if response:
            _render_response(response)
        else:
            st.caption("Evidence will appear here after you submit a question.")

    with tabs[1]:
        _render_kpi_review(root, fiscal_year, revision, data_error)
    with tabs[2]:
        _render_comparisons(root, revision, data_error)
    with tabs[3]:
        _render_about(root, documents)
    current_response = st.session_state.get("_response")
    if (
        current_response
        and current_response.get("mode") == "reviewed_kpi_lookup"
        and current_response["status"] == "reviewed_kpi"
    ):
        source_status.success("Reviewed KPI sources checked")
    elif st.session_state.get("_engine_revision") == revision and revision is not None:
        source_status.success("Local sources checked")
    else:
        source_status.caption("Source verification runs before the first response.")


if __name__ == "__main__":
    run_app()
