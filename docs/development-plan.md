# Development plan

## MVP and ownership

Use two official AIA English annual reports, FY2024 and FY2025. Deliver filtered
Q&A with physical PDF-page evidence, 3-5 manually verified common KPIs, comparable
year-over-year calculations in Python, an evaluation of at least 40 reviewed
questions, and an English Streamlit portfolio demonstration.

The product owner confirms business requirements, sources, financial definitions,
KPI values, gold answers, and acceptance. The engineering collaborator implements
and tests the pipeline, preserves provenance, and reports actual results.

## Language policy

Project deliverables default to English, including code, comments, UI, tests,
documentation, evaluation reports, and the demo. Use other languages only when
required, preserve original source evidence, and explain material exceptions in
English. The original product-owner requirement documents remain source records.
Direct collaboration may follow the product owner's language. See `../AGENTS.md`.

## Milestone gates

| Gate | Work | Evidence needed to pass | Status as of 2026-11-08 |
| --- | --- | --- | --- |
| 1 - project foundation | Environment, project skeleton, PDF page parser, source instructions | Actual parser tests and lint; no invented source records | Engineering checks complete |
| 2 - real ingestion | Acquire both official reports; manifest and page checks | Two local PDFs, actual hashes, warning review, physical-page spot checks | Engineering checks complete; owner review pending |
| 3 - retrieval and Q&A | Page-preserving chunks, year filters and selected local extractive mode; model integration is a separate decision | Five owner-reviewed factual questions with traceable page evidence | Local retrieval, excerpt responses and review UI implemented; owner factual acceptance pending |
| 4 - KPIs and comparison | Candidate extraction, owner verification, reviewed store, comparability rules, Plotly | 3-5 common metrics with independent sources and tested Python calculations | Ten candidates, source-bound reviewed-store export/validation, readiness and guarded Plotly UI implemented; owner facts/pairs, populated real-data store and actual comparisons pending |
| 5 - evaluation | At least 40 source-reviewed questions and stored raw runs | Actual correctness, citation, numeric, abstention, retrieval, and latency results | Forty development cases, 55 source-checked evidence proposals, reproducible runner and two raw runs implemented; approved gold and human semantic scores pending |
| 6 - portfolio delivery | Four Streamlit tabs; README, PRD, architecture, evaluation, screenshots, English demo | Reproducible setup and three demonstrable scenarios | English interface, documentation set, recorded screenshots and scripted prototype demo available; isolated-source tests pass; verified-number/comparison demo, final recording and acceptance pending |

Suggested sequence: gates 1-3 in week 1, gates 4-5 in week 2, gate 6 and targeted
repairs in week 3. Timing depends on document availability, manual review, and
approval/configuration of external model use. This is a plan, not completed work.

## Risk controls

- Physical PDF pages are one-based and retained even when extraction fails or
  returns no text. Printed numbering is not inferred.
- Issuer/year metadata is user supplied. Validate report covers and periods;
  filenames and URL year directories cannot establish the fiscal year.
- Native PDF text may scramble tables or multiple columns. Use it as retrieval
  input only after review; KPI extraction needs source-level verification.
- No OCR in the MVP. Flag image-only and empty pages for manual review.
- Later retrieval must filter by document/year before generation. Validate that
  returned citation IDs belong to supplied evidence; evaluate whether the text
  actually supports each claim separately.
- Store candidate KPIs separately from verified records. Preserve reviewer,
  review date, units, currency, period, scope, and basis when that stage begins.
- Identify restated prior-year figures and actual versus constant exchange-rate
  bases before comparison. Zero/negative bases and incompatible definitions need
  review rather than a routine growth percentage.
- Evaluation gold answers require source review. Report counts and denominators;
  reserve some questions for final acceptance rather than tuning on every case.
- Isolate dependencies in a local venv and use `python -m` for checks so commands
  run with the intended interpreter. Add heavy dependencies only when needed.
- Keep raw PDFs, extracted full text, indexes, and secrets out of Git. The owner
  authorizes GitHub updates after each completed, validated increment. External
  paid APIs and deployment still require separate authorization.

## Current iteration and next work

The selected local extractive workflow is now available in an English Streamlit
workspace. It displays scope, exact original excerpts, physical PDF page links,
refusal explanations, and recorded development checks. Source revisions and
fiscal-year changes clear old responses; invalid or missing data fail closed.
The KPI tab now displays ten explicitly unverified candidates with source context
and review CSV export. The comparison tab still states that verified, comparable
inputs are unavailable.

Stage 5 passed 118 automated tests and exercised both real-report years and refusal
paths in a live browser. Stage 6 adds candidate-source, Decimal and pending-review
UI checks; actual final commands and outcomes are in `phase-6-report.md`. These are
software checks, not answer accuracy or owner acceptance. Stage 4's eight
development questions and twelve boundary probes remain historical records;
these historical smoke records do not constitute the owner-reviewed evaluation.

Stage 7 adds source-bound fact and comparability decisions, Decimal calculations,
structural refusal rules and a CLI readiness audit. Tests use neutral quantities;
the actual AIA audit still has zero confirmed facts and zero of five pairs
calculated. The interface retains its pending state. See `phase-7-report.md`.

Stage 8 prepared the planned 10/10/8/7/5 category mix and ran all 40 development
cases. The first run matched 36/40 engineering expectations and exposed two
intent-guard defects; the repaired rerun matched 40/40. Literal span checks were
12/12 and proposed top-five evidence-page hits 21/28. These are development
checks, not correctness scores. Approved gold and human-scored counts remain
zero, and every semantic metric remains unavailable. See `../EVALUATION.md`,
`evaluation-review-guide.md` and `phase-8-report.md`.

Stage 9 adds the English PRD, implemented architecture, two-minute demonstration
script and owner acceptance worksheet. README now gives first-run ordering and
links the delivery set. A temporary source copy excluded original PDFs, processed
artifacts, secrets and the venv; all 342 tests passed using the existing dependency
environment, and missing-report comparison readiness failed without output.
This validates source independence, not a fresh dependency installation. The
demonstration is scripted; no completed recording or owner acceptance is implied.
See `phase-9-report.md` and `acceptance-checklist.md`.

Stage 10 connects source-bound financial review/readiness and conditional Plotly
comparisons to the UI. About validates the historical Stage 8 run, preserves its
original date and denominators, and shows unavailable human scores. Review-file
edits/removal and stale records clear prior outputs. Actual AIA data remains ten
pending facts and five pending pairs; no real growth figure/chart was produced.
All 446 tests passed, including neutral approved/revoked UI paths; no candidate
or human review decision changed. See `phase-10-report.md`.

Stage 11 adds a separate reviewed-fact JSON store and export/check command. Only
explicitly confirmed facts enter the projection. Full input-byte fingerprints,
source rechecks and strict payload comparison reject stale, revoked or tampered
stores. Current AIA facts remain pending and the real-data projection is empty.
The candidate and review datasets stay unchanged. Numerical Q&A and populated
financial acceptance remain pending. Actual commands/results are recorded in
`phase-11-report.md`.

Stage 12 connects the reviewed store to an explicit annual KPI lookup mode in
the Ask tab and a standalone CLI. Each released value must be a current,
source-revalidated confirmed fact for the selected report, metric and full
annual period. Unsupported definitions/qualifiers, conversions and comparisons
are refused. UI mode/year/source/store changes clear old responses; retained
lookup answers revalidate on rerun. The original excerpt path stays separate.
All 575 tests passed; actual pending AIA queries released no financial values.
No real approvals, comparisons or human scores changed. See `phase-12-report.md`.

Next, the owner can review at least five factual cases in the interface and the
ten KPI candidates using `kpi-review-guide.md`. VONB, ANP, VONB margin, OPAT and
UFSG have independently sourced annual values. OPAT's shareholder scope, margin's
gross-NCI definition, reported-level versus CER presentation, and FY2025 tax
changes require explicit decisions. Five prior-year value matches do not establish
comparability. Record explicit decisions in the separate review packet; it binds
to the complete raw candidate content and invalidates stale approvals. Promote
candidates to a separate verified store only after owner confirmation; then
exercise the integrated calculations/charts with actual reviewed inputs.
Keep Python calculations separate from verbatim report quotations.

Review proposed answers/source alternatives and actual frozen responses before
aggregating semantic scores. All 40 questions are now exposed to development;
collect new independent acceptance questions before making held-out claims.

Generative answering requires separate model/provider configuration and approval
of any external API cost. It must retain strict evidence IDs and add semantic
claim-support evaluation; quote-span validation alone cannot supply that guarantee.
No verified financial dataset, LLM result, or full RAG evaluation is implied by
the local UI tests. Do not add empty placeholder implementations for later work.
