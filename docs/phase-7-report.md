# Stage 7: source-bound reviews and guarded comparison backend

Publication note: machine-specific paths and interpreter commands are generalized
for sharing. Original execution transcripts are retained locally; placeholders
such as `<project-root>` and `<temporary-source-copy>` need local substitution.
Recorded commands, outcomes and limitations retain their original meaning.

Date: 2026-10-31 (Asia/Singapore).
Workspace: `<project-root>`.

## Outcome

Implemented the comparison work that does not require inventing owner approval:
separate fact and pair-review records, stale-decision detection, strict annual
comparability checks, Decimal arithmetic, and a source-checked CLI audit.

The actual project audit has **10 candidates, 0 confirmed facts, 5 pending pairs,
and 0 calculated pairs**. All computed-change fields are null. The candidate
dataset remains unverified; no reviewed store, real AIA growth result or chart
was created. The English interface retains its existing pending states. This
iteration does not change the UI or claim a new browser test.

The product owner's generic instruction to continue authorized engineering work;
it did not confirm individual financial facts or tax/currency comparability.
Those decisions remain a separate gate from implementation.

## 1. Changed files

| File | Change |
| --- | --- |
| `src/financial_intelligence_copilot/comparison.py` | Structural checks, amount versus percentage-point arithmetic, nonpositive-base refusal and controlled Decimal context |
| `src/financial_intelligence_copilot/kpi_reviews.py` | Canonical raw-candidate digests, separate fact/pair decisions, source revalidation and guarded calculation orchestration |
| `scripts/check_comparison_readiness.py` | Create fresh pending templates or audit readiness; no output overwrite or verified-store write |
| `data/kpi_reviews.json` | Ten pending fact reviews and five pending pair reviews; null check/signature fields throughout |
| `tests/test_comparison.py` | 65 neutral arithmetic/structure tests |
| `tests/test_kpi_reviews.py` | 59 review-gate tests with an isolated source-loader boundary |
| `tests/test_comparison_cli.py` | Two end-to-end CLI tests using actual generated neutral PDFs and truthful fixture provenance |
| `docs/kpi-review-guide.md` | Review schema, recording process, readiness command, precision and refusal rules |
| `README.md`, `docs/development-plan.md`, this report | Current status, actual results and next acceptance work |

No dependency, original annual report, manifest acquisition record, candidate
value, verified flag, API configuration, or UI module changed. Generated audit
JSON and test logs remain in ignored `data/processed/`.

## 2. Review packet and source validation

The packet distinguishes two decisions:

- One candidate fact: pending, confirmed or rejected. Confirmation requires value,
  unit/currency, period, scope, definition and source checks.
- One annual pair: pending, comparable or not comparable. A comparable decision
  requires definition, unit/currency, period, scope, exchange-rate, tax and
  restatement checks.

Decided records require a nonblank reviewer, timezone-aware ISO 8601 timestamp
and explanatory notes. Approving decisions require every named check to be true.
Pending decisions have no signature or true confirmation checks. There is no
automatic approval from matching headline numbers or identical scope labels.

Each decision binds to the SHA256 of the **complete raw candidate JSON record**,
before Decimal normalization or derived fields. This includes financial values,
metadata, source hash/page/token/row/header, definition references and caveats.
Object-key ordering does not change the digest; changing content does. Unknown,
duplicate, reversed, stale or incomplete records fail validation.

Loading a packet first calls the existing raw-PDF candidate validator and checks
that candidate-file bytes did not change during validation. A missing packet
produces pending state without writing approvals. A malformed or stale packet
raises an error rather than reusing an old decision. Fresh templates always
contain pending decisions and do not transfer earlier approvals.

These are local audit records, not authenticated signatures. A hash detects
changed content; it does not prove who typed a reviewer name. The operator must
record actual product-owner decisions. The API contract is to call
`load_review_state` and then `comparison_results` in the same operation, without
modifying the validated state. The current UI does not load/cache this packet;
future UI integration must fingerprint its bytes and clear stale results.

## 3. Calculation rules and numerical limits

Both candidate facts must be confirmed and the pair explicitly comparable.
The backend then independently requires:

- Same issuer, metric code, supported currency/unit combination, scope and basis.
- Consecutive full January–December fiscal years. FY2024's leap day is valid;
  equal calendar-day counts are not required.
- Distinct candidate identities and source documents, preserving separate source
  citations for each annual input.

Scope/basis labels are compared exactly. This is conservative and may reject
equivalent wording; it cannot detect every semantic difference hidden behind
identical labels. The explicit tax/exchange-rate/definition checks remain
necessary. This stage performs no currency, unit, restatement or tax adjustment.

For a positive prior amount, Python computes the exact finite absolute change
and `(current - previous) / previous * 100` in the original declared units.
For percent-unit metrics, it emits a **percentage-point** difference and leaves
percentage growth and monetary absolute change null. Zero or negative prior
values return `needs_review` with all change fields null. A zero or negative
current value with a positive prior is valid arithmetic, subject to the other
review gates.

Only finite `Decimal` inputs are accepted; floats, booleans and non-finite values
are rejected. A local context uses at least 34 significant digits with half-even
rounding for repeating ratios and expands subtraction precision to preserve exact
finite differences. Ambient Decimal precision, rounding and traps do not alter
the result. Display rounding is separate. JSON serialization uses decimal
strings, without converting to float.

Released results preserve both input periods, fiscal years, source documents,
PDF hashes, physical pages, source tokens and character offsets. Successful
neutral results also retain the recorded fact/pair decisions for audit. Pure
arithmetic helpers do not establish financial authorization; real callers must
use the source/review-gated entry point.

## 4. Commands actually run

The initial template and two readiness runs used:

```bash
.venv/bin/python scripts/check_comparison_readiness.py \
  --init-review data/kpi_reviews.json
.venv/bin/python scripts/check_comparison_readiness.py \
  --output data/processed/phase-7-comparison-readiness.json
.venv/bin/python scripts/check_comparison_readiness.py \
  --output data/processed/phase-7-comparison-readiness.final.json
```

Actual output:

```text
Prepared 10 pending fact reviews and 5 pending pair reviews. No approval recorded.
Source-checked 10 candidates; 0 facts confirmed. Calculated 0/5 annual pairs.
```

The final run adds richer per-input period/token provenance to the first audit.
Both preserve pending status and null calculations. The CLI refuses existing
output files; use a new output name to reproduce a run. Source or packet
validation errors exit with status 2 and do not produce an audit result.

Tests and lint actually run:

```bash
.venv/bin/python -m pytest tests/test_comparison.py -q
.venv/bin/python -m pytest tests/test_kpi_reviews.py -q
.venv/bin/python -m pytest tests/test_comparison_cli.py -q
.venv/bin/python -m pytest -q > data/processed/phase-7-pytest.log 2>&1
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

Final full-suite results:

```text
298 passed, 5 warnings in 2.02s
All checks passed!
29 files already formatted
```

The five warnings are existing PyMuPDF/SWIG import deprecations. All 126 new
tests passed alongside the previous 172. These are software checks, not answer
accuracy, financial owner acceptance or the planned 40-question evaluation.

## 5. Neutral tests and actual-data boundaries

Arithmetic/structure tests cover positive growth, decline, zero/negative current
values, zero/negative prior refusal, percentages versus percentage points, wrong
units/currency/metric/scope/basis, reversed or partial periods, leap years,
source identity and ambient Decimal settings.

Review tests cover full raw-content binding, absent packets, malformed states,
signatures/checklists, stale decisions, facts-only confirmation, rejected facts,
not-comparable pairs, structural mismatch despite apparent review approval,
source-loader failure and source retention after a successful neutral comparison.

The CLI tests generate PDFs explicitly labeled as neutral nonfinancial fixtures,
compute their actual hashes/spans, and invoke the script in subprocesses without
mocking source validation. They exercise all-pending refusal, an explicitly
test-only review and calculation, preservation of both PDF references, overwrite
refusal, PDF-byte tampering and stale candidate metadata. They do not describe
generated counts as real AIA disclosures. An initial fixture helper assumed a
final newline; using the actual end of source text corrected the helper before
the final passing run.

Independent engineering review rechecked the real packet: zero confirmed facts,
zero comparable pairs and zero calculations. A final explicit audit also checked
that candidate verified flags remain false, every review decision is pending,
all three change fields are null and `data/verified_kpis.csv` does not exist.

## Next acceptance work

Use the [KPI review guide](kpi-review-guide.md) and the official PDFs to record
explicit decisions by candidate ID, including qualifications and unresolved
comparability issues. No real-data calculation is needed to review those inputs.

After owner confirmation, build a separate reviewed store, connect only reviewed
and comparable inputs to the calculation/UI pipeline, and add evidence-linked
comparison charts. The planned owner-reviewed 40-question evaluation and final
portfolio materials remain pending. No paid API, public deployment, Git commit
or push occurred in this stage.
