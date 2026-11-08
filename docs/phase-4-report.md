# Stage 4: local extractive responses and source-span validation

Publication note: machine-specific paths and interpreter commands are generalized
for sharing. Original execution transcripts are retained locally; placeholders
such as `<project-root>` and `<temporary-source-copy>` need local substitution.
Recorded commands, outcomes and limitations retain their original meaning.

Date: 2026-10-30 (Asia/Singapore).
Workspace: `<project-root>`.

## Outcome and owner decision

The owner explicitly selected local original-text excerpt responses. This stage
implements that mode without a model, API key, model download, or new dependency.
The current environment has no configured model provider/key. No external model
call, deployment, Git commit, or push occurred.

Responses contain exact report excerpts or an explicit abstention. They do not
contain a generated business explanation or claim that a complete answer has
been established. Quote identity is validated; relevance, completeness, financial
facts, and accounting comparability are not automatically verified.

## 1. Files and implementation

| File | Change |
| --- | --- |
| `src/financial_intelligence_copilot/answer.py` | Local excerpt selection, same-page context expansion, policy abstentions, JSON CLI |
| `src/financial_intelligence_copilot/citations.py` | Reconstruct exact quotes from source IDs and page offsets; reject inconsistent selections |
| `src/financial_intelligence_copilot/retrieval.py` | Typed report-scope exception, retaining previous filtering behavior |
| `scripts/run_extractive_smoke.py` | Real-data development probes and explicit boundary cases; raw local results |
| `tests/test_answer.py` | Grounded excerpt behavior, policy boundaries, unknown subjects, scope and CLI checks |
| `tests/test_citations.py` | Valid cross-chunk spans and adversarial citation/offset/source cases |
| `.env.example` | Clarify that current local mode does not load model settings |
| `README.md`, `docs/development-plan.md` | Current status, actual commands, limitations, next acceptance work |

The original reports, page snapshots, manifest, retrieval policy, and index
contents were not changed. Source-file/cache validation from Stage 3 remains in
force when the query CLI loads its retriever.

## 2. Quote contract and response boundary

A quote selection contains only `evidence_ids`, `char_start`, and `char_end`.
Offsets are absolute Python Unicode-character positions within a physical PDF
page's original extracted text. The server reconstructs the text; a caller cannot
supply a fabricated quote or free-form claim in this selection object.

Validation rejects unknown or aliased IDs, mixed document/year/issuer/page/hash/
URL identities, invalid numeric types, unsupported source ranges, coverage gaps,
inconsistent overlapping text, empty quotes, and overlong selections. Multiple
supporting IDs are allowed only when they continuously cover the requested range
on the same source page. No cross-page text concatenation is allowed.

The answering layer can examine other indexed chunks on the initially retrieved
pages to recover sentence context. Primary and expanded evidence IDs are exposed
separately. It selects one evidence page and up to three focused source spans;
it does not silently relabel an expanded passage as the original retrieved chunk.

Search terms, sentence boundaries, glossary-row patterns, unknown-name checks,
and relative relevance cutoffs are deterministic heuristics. They do not prove
semantic support. Known layout noise and instruction-like source sentences are
excluded conservatively, but the native text may still have reading-order issues.
All positive responses use `extractive_evidence`, never a verified-answer label.

## 3. Actual tests and quality checks

Commands actually run:

```bash
.venv/bin/python -m pytest -q > data/processed/phase-4-pytest.log 2>&1
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

Actual results:

```text
106 passed, 5 warnings in 0.44s
All checks passed!
15 files already formatted
```

The existing PyMuPDF/SWIG deprecation warnings and shutdown warning remain visible.
Unit fixtures are explicitly neutral documents, not fictional financial reports.
The citation tests include a complete sentence crossing adjacent/overlapping
chunks, Unicode offsets, incorrect source identities, mapping aliases, gaps,
conflicting overlap, fabricated text fields, and invalid offsets. Response tests
cover scope conflicts, historical-year mentions, missing subjects, financial
workflow boundaries, instruction-like source data, overwrite refusal, and a
nonzero smoke-runner exit when a defined boundary behavior is violated.

## 4. Actual real-report development run

The final reviewed run used the two existing official reports and the same eight
source-inspected questions from Stage 3, plus twelve engineering boundary probes:

```bash
.venv/bin/python scripts/run_extractive_smoke.py \
  --index data/processed/retrieval-index.json \
  --output data/processed/extractive-smoke.reviewed.json \
  > data/processed/phase-4-smoke-reviewed.log 2>&1
```

| Source-inspected probe | Selected physical PDF page | Excerpts |
| --- | ---: | ---: |
| FY2024 Vitality definition | 359 | 1 |
| FY2024 cybersecurity assurance | 106 | 1 |
| FY2024 Three Lines roles | 75 | 2 |
| FY2024 compliance policy | 134 | 1 |
| FY2025 technology committee | 12 | 1 |
| FY2025 Vitality care pathways | 20 | 1 |
| FY2025 risk appetite governance | 64 | 1 |
| FY2025 Technology Risk | 69 | 2 |

Eight questions produced **ten excerpts**. An independent assertion check compared
every quote against its original page substring, checked document/year/page
scope and supporting source hashes, and saved
`data/processed/phase-4-checks.reviewed.json`. All ten spans matched and no source
scope leak was observed. One excerpt used same-page context beyond the primary
retrieved chunk. The final real-data quotes each fit one supporting expanded
chunk; multi-ID reconstruction is exercised by unit tests.

### Explicit refusal probes

| Probe group | Cases | Observed reason |
| --- | ---: | --- |
| Missing unique subject | 1 | `no_matching_evidence` |
| Unknown subject hidden among generic matches, including ordinary title case | 2 | `insufficient_quotable_evidence` |
| Named KPI figures without a verified store | 2 | `verified_kpi_unavailable` |
| YoY and percentage-point calculations | 2 | `comparison_not_available` |
| Future financial prediction | 1 | `prediction_out_of_scope` |
| Buy recommendation | 1 | `investment_advice_out_of_scope` |
| Citation override and fabricated page | 2 | `citation_override_requested` |
| Relabeling another report's year | 1 | `report_scope_conflict` |

All twelve cases matched their defined engineering behavior. This is not a
general abstention-correctness rate: cases are small, explicit, and awaiting
owner review. A KPI refusal explains that verified data is not available yet;
it does not assert that the report lacks those financial figures.

### Known partial coverage and improvements

The development probes informed selection changes; they are not a held-out
benchmark. Initial responses sometimes padded relevant evidence with tangential
sentences. The final mode uses one selected page and suppresses weak additions.
A generic glossary-row rule selects the Vitality definition without hard-coding
its page or wording. Review also found that a title-case missing entity could
be masked by matching words; the name heuristic and a regression test now cover
that concrete case.

Two multi-part questions retain known partial coverage. The Three Lines response
identifies the framework and function roles but does not fully enumerate every
line's detailed responsibilities. The Technology Risk response includes AI
governance and technology-risk text but does not fully cover all cybersecurity
standards requested. The response message and notice preserve this limitation;
producing an excerpt is not counted as a correct or complete answer.

Lowercase, ambiguous, or paraphrased unknown subjects can still evade lexical
checks. Sentence punctuation and layout filters are also imperfect. Injection
patterns cover only some obvious wording. The enforceable boundary here is that
source text remains data, no model or executor is called, and only validated
original source spans are released. No general prompt-injection resistance score
or semantic-answer verification is claimed.

## 5. CLI example and local artifacts

The actual query CLI was exercised with:

```bash
.venv/bin/python -m financial_intelligence_copilot.answer \
  --index data/processed/retrieval-index.json \
  --doc-id AIA-2025-EN --fiscal-year 2025 \
  --query 'What cybersecurity standards and AI governance arrangements does AIA describe under Technology Risk in its 2025 annual report?' \
  --output data/processed/example-extractive-answer.reviewed.json
```

The output is labeled `local_extractive`, contains original excerpts and source
cards, and carries the relevance/completeness and research-use notices. It is not
an LLM response. Output files are never overwritten. Valid abstentions exit 0;
input/source errors exit 2. The smoke runner records results and exits 1 for a
defined boundary mismatch.

Raw excerpts, execution logs, the example response, and all development-run JSON
files remain under the ignored processed-data directory. Earlier initial runs
are retained there for audit. No full report or extracted text was published.

## Next acceptance work

Build the English Streamlit view over this selected local workflow, making the
scope, mode, partial evidence, exact quotes, physical PDF pages, and refusal
reasons easy to inspect. The owner should review at least five factual cases.
Then define and manually verify the first 3-5 comparable KPIs before numerical
answers or YoY calculations. LLM integration remains a separate configured and
authorized phase; the 40-question evaluation has not yet been performed.
