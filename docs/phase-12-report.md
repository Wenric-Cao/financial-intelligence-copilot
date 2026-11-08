# Stage 12: explicit reviewed annual KPI lookup

Executed on 2026-11-08 (Asia/Singapore). This increment connects the reviewed
store to a separate bounded lookup mode and CLI. No real financial fact,
comparability decision, gold answer or human rating was approved.

## Delivered behavior and boundaries

- The default **Original excerpts** mode remains a selected-report evidence
  workflow. **Reviewed KPI lookup** is an explicit separate mode; it does not
  silently replace or reinterpret an excerpt question.
- `financial_answer.py` accepts full-query forms for one of VONB, ANP,
  VONB_MARGIN, OPAT or UFSG and their explicit aliases. Examples include
  `Show VONB for FY2025` and `What is AIA's VONB in USD million?`.
- Successful lookups revalidate the saved store against current local sources
  and decisions. Values remain exact decimal strings with their period, scope,
  basis, source context and actual recorded reviewer/time/notes. A numeric source
  token is labeled separately from a sentence-level quotation. Review metadata
  is not authenticated human identity, and a fact confirmation is not pair
  comparability approval.
- The parser refuses unknown qualifications, regional/interim figures,
  definition/basis interpretation, conversions, derived ratios, multiple metrics
  and comparisons. Ambiguous `What is VONB?` needs an explicit numeric cue such
  as year, unit, annual/reported or value. Direct codes and `Show VONB` are lookup
  commands. No general financial-language understanding is claimed.
- A confirmed input must cover 1 January through 31 December of its fiscal year
  before it can be released as an annual level. Review caught this additional
  boundary because the underlying fact schema can represent other valid periods.
- Missing stores and pending facts abstain without a value. Stale/malformed
  stores, changed sources and invalid records fail visibly. A current query
  cannot select a different report/year or convert the declared currency/unit.
- Mode/year/source/store changes clear old UI responses. Retained lookup answers
  are source-revalidated again before display on each rerun. The optional
  canonical store joins the workspace fingerprint, including creation, edits and
  removal; paths outside the workspace are rejected. These checks do not run
  continuously while a browser sits idle.
- The CLI can use a custom store; relative store paths use `--root`. Response
  output is exclusive and cannot alias canonical inputs, a missing default or
  custom store, or raw data. The UI writes neither reviews nor stores.

The UI still requires the existing local report/page/index inventory. The lookup
itself does not call the retriever; the standalone CLI does not need an index.
Actual financial review and broader numerical QA acceptance remain pending.

## Changed files

| Files | Purpose |
| --- | --- |
| `src/financial_intelligence_copilot/financial_answer.py` | Bounded query parsing, scope/unit/annual-period gates and source-checked fact release |
| `scripts/ask_reviewed_kpi.py` | Standalone lookup, JSON response export and protected output paths |
| `src/financial_intelligence_copilot/ui.py`, `ui_state.py` | Explicit mode, financial response rendering, revalidation and store fingerprinting |
| `tests/test_financial_answer.py`, `test_financial_answer_cli.py` | Real neutral PDFs, conditional positive paths, ambiguity/period/unit/scope guards, source/review changes and CLI integration |
| `tests/test_ui.py`, `test_ui_state.py` | Mode routing, exact/percent presentation, retained-response revalidation, review/store invalidation and optional source references |
| `assets/screenshots/reviewed-kpi-pending.jpg` | Actual English UI showing pending review and no financial value |
| `README.md`, `PRD.md`, `ARCHITECTURE.md`, `EVALUATION.md` | Current behavior, reproduction, architecture and historical evaluation boundaries |
| Review, acceptance, development, demonstration and publication guides under `docs/` | Actual progress, lookup instructions and remaining owner decisions |
| `docs/phase-12-report.md` | This execution record |

All positive financial-answer tests use clearly labeled TEST ONLY nonfinancial
counts and explicit fixture decisions. They do not impersonate AIA disclosures.

## Actual commands and automated results

Commands ran from the project root with the existing environment:

```bash
.venv/bin/python -m pytest -q tests/test_financial_answer.py
.venv/bin/python -m pytest -q tests/test_financial_answer_cli.py
.venv/bin/python -m pytest -q tests/test_ui.py tests/test_ui_state.py
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pip check
git diff --check
```

- Backend: **57 passed**; CLI: **13 passed**; UI/state focused suite: **43 passed**.
- Full suite: **575 passed**, 5 existing PyMuPDF/SWIG deprecation warnings,
  **15.23 s**. This is 85 more test cases than the Stage 11 checkpoint.
- Ruff check passed; all **46 Python files** formatted after formatting the new
  CLI test. The formatted CLI test was rerun successfully. Diff whitespace checks
  passed; dependency checks found no broken requirements. Pip disabled its
  unavailable cache, with no effect on the consistency result.
- No new dependency, external model call, API cost or public deployment.

Software tests do not establish real financial correctness or answer accuracy.

## Actual local AIA checks

Before creating the canonical local store, this command produced an abstention
with `verified_store_unavailable` and `financial_fact=null`:

```bash
.venv/bin/python scripts/ask_reviewed_kpi.py \
  --doc-id AIA-2025-EN --fiscal-year 2025 \
  --query "What is AIA's VONB in USD million?" \
  --output data/processed/phase-12-missing-store.response.json
```

The canonical local store was then created with:

```bash
.venv/bin/python scripts/build_verified_store.py \
  --output data/processed/verified-kpis.json
```

It contains **0/10 reviewed facts**, `records=[]`. Each of the five supported
metrics was queried through the real CLI, plus five boundary cases. All commands
returned valid abstention JSON, exit 0, with no numerical fact:

| Actual query group | Result |
| --- | --- |
| VONB, ANP, VONB_MARGIN, OPAT, UFSG in FY2025 | Five `fact_review_pending` abstentions |
| Hong Kong qualifier | `unsupported_financial_query` |
| VONB in percent | `requested_unit_unavailable` |
| FY2024 requested with FY2025 selected | `report_scope_conflict` |
| Ambiguous `What is VONB?` | `unsupported_financial_query` |
| Year-over-year comparison | `comparison_not_available` |

Before/after SHA256 values for candidates, review decisions, source manifest and
evaluation cases were identical. Local records remain Git-ignored:

```text
data/processed/phase-12-inputs.before.json
data/processed/phase-12-integrity-checks.json
data/processed/phase-12-real-lookups.json
data/processed/phase-12-*.response.json
data/processed/verified-kpis.json
```

## Live browser observations

The local preview used:

```bash
.venv/bin/python -m streamlit run app.py \
  --server.address 127.0.0.1 --server.port 8501 \
  --server.headless true --browser.gatherUsageStats false
```

The initial restricted start could not bind the loopback port. The authorized
local preview then started on `127.0.0.1:8501`; no public hosting was involved.
In the live English interface:

1. Selected **Reviewed KPI lookup** and asked the AIA VONB example. It displayed
   `fact review pending`, no financial value, and a JSON download control.
2. Switched to **Original excerpts**. The prior lookup response cleared after
   the rerun.
3. Asked the Risk Appetite/RMF responsibility question. The original excerpt
   path returned a source-span-checked card for **FY2025 physical PDF page 64**
   with the official PDF link. This is a source/behavior regression observation,
   not new owner acceptance of relevance or completeness.

The public screenshot shows only the actual pending lookup state. No positive
real AIA financial-answer screenshot was created.

## Remaining acceptance

All ten actual KPI fact decisions and five pair decisions remain pending.
No actual financial value or annual change was released. The original forty
evaluation cases remain development-exposed, with zero approved gold answers
and zero human-scored cases. The historical evaluation was not rerun or extended
to measure the new mode.

Next, the owner must review real facts and definitions, separately resolve
comparability, and assess actual responses. Only those explicit decisions can
populate a genuine reviewed store and support real-number/comparison scenarios.
See the [KPI review guide](kpi-review-guide.md) and
[acceptance worksheet](acceptance-checklist.md). The completed code/tests/docs
increment is prepared for the authorized GitHub update; raw PDFs, full text,
local stores, caches, secrets and internal planning documents remain excluded.
