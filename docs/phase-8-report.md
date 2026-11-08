# Stage 8: real development evaluation and observed guard repairs

Publication note: machine-specific paths and interpreter commands are generalized
for sharing. Original execution transcripts are retained locally; placeholders
such as `<project-root>` and `<temporary-source-copy>` need local substitution.
Recorded commands, outcomes and limitations retain their original meaning.

Date: 2026-10-31 (Asia/Singapore).
Workspace: `<project-root>`.

## Outcome

Prepared and source-checked 40 development questions with the planned category
mix: 10 simple facts, 10 financial numbers, 8 table/basis questions, 7 cross-year
questions and 5 boundaries. Fifty-five short evidence proposals match actual
registered PDF hashes, physical pages and freshly extracted page offsets.

Implemented a reproducible runner, raw-run preservation, dependency fingerprints
and separate pending human-review packets. Ran the real suite twice: the first
run revealed four engineering-behavior mismatches; a focused repair corrected
two intent-guard defects before the second run. Both runs remain unchanged in
ignored local files.

**Approved gold: 0. Human-scored cases: 0.** All semantic, numerical,
citation-relevance and abstention-correctness metrics remain null. Matching the
current software boundary is not financial or answer accuracy. No KPI fact or
comparability review was approved and no real AIA growth calculation was made.

See [EVALUATION.md](../EVALUATION.md) for actual observations and denominators,
and [the evaluation review guide](evaluation-review-guide.md) for owner review.

## 1. Modified files

| File | Change |
| --- | --- |
| `data/evaluation_cases.json` | Forty pending development cases, proposed answers, current-mode expectations and exact short evidence spans |
| `src/financial_intelligence_copilot/evaluation.py` | Pending-suite/source validation, raw case execution, literal-span checks, honest denominators, digests and review export |
| `scripts/run_evaluation.py` | Actual before/after dependency checks, source/index verification, raw-run and review-packet output, exit/error handling |
| `src/financial_intelligence_copilot/answer.py` | Normalize underscores for intent checks and recognize FY-prefixed comparison years |
| `tests/test_evaluation.py` | 32 neutral source/run/review-integrity tests |
| `tests/test_evaluation_cli.py` | Four actual neutral PDF-to-index CLI checks |
| `tests/test_answer.py` | Eight intent-guard regressions, keeping original queries and evidence intact |
| `EVALUATION.md` | Actual before/after results, limitations, timings and reproduction instructions |
| `docs/evaluation-review-guide.md` | Concrete owner-review materials and separate gold/response judgments |
| `README.md`, `docs/development-plan.md`, this report | Current implementation and remaining acceptance gates |

No new dependency, model service, API key, raw report or financial candidate
value was introduced. The original requirement documents and source acquisition
records were preserved. All new project artifacts are English.

## 2. Source and dataset preparation

Used the already downloaded official English FY2024/FY2025 reports. Read complete
relevant source pages and retained original short quotations, physical page
numbers, source URLs, hashes and character offsets. Table/definition inspection
also used rendered pages to check column scope and footnotes. Parallel source
audits independently checked factual and table/basis drafts. Their intermediate
files stay in ignored `data/processed/`.

The factual set reuses eight earlier subject areas and adds two supported
questions. Several responses may be partial or use valid alternative pages.
The financial-number questions bind to the ten existing unverified candidates.
Comparison proposals cite both original annual sources and propose no growth
value; currency/tax comparability still needs review. Boundary labels are
deliberate engineering proposals, not human-approved document answerability.

`load_suite` was actually called against the raw PDFs and checked all 40 cases /
55 spans. The same source check runs before every CLI execution. The separate
index loader reconstructs and compares the cache against actual sources and
current policy. FY2025 physical page 3 still produces its known empty-native-text
warning; no OCR or substitute data was introduced.

The suite explicitly says development exposure and pending owner review.
Candidate answers are not promoted to gold, and report-answerable questions are
distinguished from unsupported current workflows. No held-out subset is claimed.

## 3. Runner and review safeguards

- Preserve all 40 outcomes, raw responses, retrieved candidates, exceptions and
  scope/span diagnostics. A failed case stays in engineering denominators.
- Source-span validation reconstructs text from evidence IDs and exact offsets.
  Empty excerpt sets are N/A, not successful citations. Scope and source errors
  are recorded separately from the span count.
- Proposed page hits bind document, year and physical page. Their denominator
  is the 28 single-report cases with source proposals; multi-report comparisons
  and source-free boundary cases are not counted.
- Expected report-scope rejection is recorded separately from unexpected
  diagnostic retrieval failure. Unexpected diagnostic errors cause a nonzero
  run status even when the answer path returns.
- Store suite/case/response/run digests, source/cache/policy/code fingerprints,
  Python/PyMuPDF versions and measured loading/query times. If dependency bytes
  change during the run, results are not published.
- Human packets bind frozen run, suite, case and response content. Missing,
  duplicate or edited case/proposal/response records are rejected before export.
  Digests bind content; they do not authenticate a reviewer.
- Keep gold approval, human ratings and signatures pending/null. No automatic
  semantic grader or string-overlap accuracy score is substituted for review.

The current stage exports review packets; it does not ingest modified human
ratings or calculate semantic percentages. That later step needs an agreed
rubric, explicit decisions and validation of those bindings.

## 4. Actual commands and real runs

First run:

```bash
.venv/bin/python scripts/run_evaluation.py \
  --output data/processed/phase-8-evaluation.json \
  --review-output data/processed/phase-8-human-review.json
```

Actual result: 40/40 completed, zero runtime errors, engineering behavior matched
36/40; 17/17 released spans matched source text with zero span-error cases.
The four mismatches were `numeric-05`, `numeric-10`, `compare-06`, `compare-07`.

The underscore in `VONB_MARGIN` prevented the existing acronym boundary check
from recognizing the KPI. Regional/context excerpts were consequently released
instead of the intended pending-verification refusal. Intent normalization now
treats underscores as separators, without changing the original question or any
source text. FY-prefixed comparison years also missed a comparison pattern and
fell through to the ordinary KPI refusal; optional FY prefixes are now accepted.

After eight neutral-fixture regressions passed, ran:

```bash
.venv/bin/python scripts/run_evaluation.py \
  --output data/processed/phase-8-evaluation.after-fix.json \
  --review-output data/processed/phase-8-human-review.after-fix.json
```

Actual final console output:

```text
Completed 40/40 cases; 0 runtime errors.
Engineering behavior matches: 40/40.
Literal source spans: 12/12; 0 cases with span errors.
Semantic scores unavailable (0 approved gold, 0 human-scored cases).
```

Final responses: ten extractive responses and thirty abstentions. One diagnostic
scope rejection is the deliberate report-year boundary case; unexpected
diagnostic errors are zero. Proposed page hits remain 15/28 at rank 1 and 21/28
within five distinct pages. Seven proposed evidence-page misses remain; the
ranking baseline was not changed to fit them.

The first and repaired runs share the same frozen suite digest. Their code/run
digests differ because the guard was repaired. The rerun is development repair
verification, not independent acceptance or an accuracy increase claim. Raw
artifacts include original report excerpts and remain Git-ignored.

## 5. Actual automated tests

Focused source/evaluation and intent tests, followed by the full suite:

```bash
.venv/bin/python -m pytest tests/test_evaluation.py -q
.venv/bin/python -m pytest tests/test_evaluation_cli.py -q
.venv/bin/python -m pytest tests/test_answer.py -q
.venv/bin/python -m pytest -q > data/processed/phase-8-pytest.log 2>&1
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

Actual final results:

```text
342 passed, 5 warnings in 2.39s
All checks passed!
33 files already formatted
```

The 44 additions comprise 32 evaluation tests, four CLI tests and eight answer
regressions. Five warnings remain the existing PyMuPDF/SWIG import deprecations.
Neutral PDFs are explicitly labeled test-only and use actual generated-file
hashes/offsets. No invented AIA amounts, gold answers or evaluation scores were
used in tests.

Tests cover source/evidence tampering, changed dependency snapshots, no-overwrite
behavior, all-null semantic fields, retained runtime/malformed-response errors,
wrong-report same-page hit rejection, whole-run/case/response digest binding,
exact review membership, proposal-copy tampering and the newly found query forms.
One early focused command ran before the new test file existed and collected no
tests; it is not a passing result. Subsequent focused and final full runs are
the actual passing results above.

## 6. Local preview and pending acceptance

Restarted the existing loopback-only Streamlit process so repaired code loads
and old session responses are cleared:

```bash
.venv/bin/python -m streamlit run app.py \
  --server.address 127.0.0.1 --server.port 8501 \
  --server.headless true --browser.gatherUsageStats false
```

It started at `http://127.0.0.1:8501`. No UI layout changed and no new live-browser
walkthrough is claimed; the existing AppTest workflows passed in the full suite.
The About tab's Stage 4 counts remain labeled historical; its planned
owner-reviewed evaluation is still unrun. Current development results are in
`EVALUATION.md` rather than relabeled as formal UI scores.

Next, the owner can review the concrete cases/responses using the evaluation
guide and confirm KPI facts/comparability using the separate KPI guide. Only
explicit decisions can populate reviewed inputs, gold labels or semantic scores.
The reviewed KPI store, actual comparable charts, final human evaluation and
remaining portfolio documents are pending. No paid API, public deployment,
Git commit or push occurred.
