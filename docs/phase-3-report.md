# Stage 3: page-preserving chunks and local retrieval

Publication note: machine-specific paths and interpreter commands are generalized
for sharing. Original execution transcripts are retained locally; placeholders
such as `<project-root>` and `<temporary-source-copy>` need local substitution.
Recorded commands, outcomes and limitations retain their original meaning.

Date: 2026-10-25 (Asia/Singapore).
Workspace: `<project-root>`.

## Outcome and scope

Implemented a local lexical retrieval baseline over the two real official AIA
reports. It produces candidate evidence cards with original excerpts and physical
PDF page numbers. It uses the existing Python environment, PyMuPDF, and standard
library; no new dependency, model download, paid API, deployment, or Git push was
used. The original reports and page snapshots were not rewritten.

This completes the retrieval component of milestone 3. Generated answering,
claim-level citation validation, calibrated refusal, verified KPIs, and the full
40-question evaluation remain pending. Product-owner source and case review is
still required; engineering review is not labeled as owner verification.

## 1. Files and implementation decisions

| New file | Responsibility |
| --- | --- |
| `src/financial_intelligence_copilot/chunking.py` | Page-bounded chunks, exact source offsets, stable IDs, separate normalized search text |
| `src/financial_intelligence_copilot/indexing.py` | Manifest/PDF/snapshot validation, reviewed page exclusions, deterministic JSON index |
| `src/financial_intelligence_copilot/retrieval.py` | Source-checked loading, report/year filtering, BM25 scoring, source-card CLI |
| `data/retrieval_policy.json` | Word-window parameters and ten explained page exclusions |
| `data/retrieval_cases.json` | Eight source-inspected engineering probes, all owner-review-pending |
| `scripts/run_retrieval_smoke.py` | Raw results and page-hit counts, separate from answer scoring |
| `tests/test_chunking.py` | Original-span preservation, ID stability, empty-page and window handling |
| `tests/test_retrieval.py` | Document/year boundaries, no-evidence handling, ranking scope, page diversity |
| `tests/test_indexing.py` | Source/cache consistency, tampering rejection, CLI round trip, report-year rules |

`README.md` and `docs/development-plan.md` were updated to reflect actual progress.
`pyproject.toml`, existing parser code, source-manifest rows, PDFs, and original
page JSON files did not require changes.

### Chunk and source representation

- Windows contain up to 180 whitespace-delimited words, overlap by 30, and stay
  within one physical PDF page. Pages with fewer than 8 words are not indexed.
  These are word counts, not LLM token counts.
- Each chunk stores document ID, issuer, report year, language, PDF page, official
  URL, source SHA256, and exact character start/end positions. Offsets use Python
  Unicode string indexes into that page's saved original text.
- `raw_text` is exactly the original substring. `search_text` normalizes Unicode,
  whitespace, replacement-character runs, and long dotted leaders independently.
  Search normalization is never presented as an exact source quote.
- IDs bind the chunking version, source hash, document/page, offsets, and original
  text. Identical builds preserve IDs; duplicate import does not append copies.
- Index creation refuses existing output filenames. A reviewed rebuild creates
  a new artifact instead of silently replacing an existing one.

### Retrieval and provenance boundary

BM25 uses k1=1.5 and b=0.75. Document/year filtering occurs before corpus statistics
or scoring. Stop words remove ordinary question scaffolding and generic issuer/
report labels; no stemming or semantic expansion is performed. Numeric terms
are retained, except the selected report-year label in the query.

The best matching chunk from each distinct physical page is returned, up to k
pages. Scores are ranking values and are not probabilities of factual support.
No lexical overlap gives an empty result; the system does not broaden the report
selection. Explicitly conflicting report years are rejected. A historical FY
mention within the selected report is allowed and does not change source scope.

At index build and load, the implementation freshly parses the current raw PDFs,
checks their manifest hashes, and compares every saved page's text, field types,
metadata, and page sequence. Loading reconstructs the deterministic index using
the current policy and compares canonical JSON with the stored artifact, including
numeric types. Changed PDFs, snapshots, cached excerpts, offsets, or policy cause
rejection. This intentionally favors auditability over startup speed for a
two-document corpus. After loading, the
retriever is an in-memory snapshot; reload it after source changes.

## 2. Actual build and real-data checks

Command actually run:

```bash
.venv/bin/python -m financial_intelligence_copilot.indexing \
  --output data/processed/retrieval-index.json \
  > data/processed/phase-3-build.log 2>&1
```

Actual output:

```text
AIA-2024-EN: 1088 chunks from 371 physical PDF pages
AIA-2025-EN: 1071 chunks from 363 physical PDF pages
Skipped 10 pages; wrote data/processed/retrieval-index.json
```

FY2025 physical page 3 still emits the known no-native-text warning when the PDF
is rechecked. It remains in the page inventory and is excluded from retrieval.

| Document | Chunks | Policy-excluded PDF pages |
| --- | ---: | --- |
| AIA FY2024 | 1,088 | 1, 3, 4 |
| AIA FY2025 | 1,071 | 1, 3, 4, 22, 76, 146, 363 |

Exclusion reasons are public metadata in `data/retrieval_policy.json`: cover,
promotional material, contents navigation/encoding noise, or a publisher address.
All original pages are retained unchanged under `data/processed/`.

A real-data assertion check saved `data/processed/phase-3-checks.json`:

```text
2,159 exact source substrings and source-hash associations checked
40 retrieved evidence-card excerpts checked against page offsets
0 document/year scope leaks
0 duplicate evidence IDs
No-overlap query returned no evidence
Explicit report-year conflict was rejected
```

## 3. Engineering retrieval smoke run

The eight English probes were proposed after inspecting real source pages, before
the initial ranking run. Each has expected physical page IDs and diagnostic
terms, with `engineering_checked_owner_pending` status. They contain no standard
answer or verified KPI. The metric tests whether any expected page appears among
the top k distinct result pages; it does not assess whether a particular chunk
fully supports an answer. Cases and ranking parameters were not changed to remove
the observed top-one miss.

The final source-checked run used:

```bash
.venv/bin/python scripts/run_retrieval_smoke.py \
  --index data/processed/retrieval-index.json \
  --output data/processed/retrieval-smoke.final.json \
  > data/processed/phase-3-smoke-final.log 2>&1
```

| Case | Expected PDF pages | Returned top-five PDF pages | Top-one hit | Top-five hit |
| --- | --- | --- | --- | --- |
| FY2024 Vitality definition | 13 or 359 | 70, 13, 359, 65, 104 | No | Yes |
| FY2024 cybersecurity assurance | 68 | 68, 106, 81, 325, 164 | Yes | Yes |
| FY2024 Three Lines roles | 75 | 75, 76, 293, 144, 118 | Yes | Yes |
| FY2024 compliance policy | 134 | 134, 124, 131, 126, 120 | Yes | Yes |
| FY2025 technology committee | 12 | 12, 91, 93, 280, 128 | Yes | Yes |
| FY2025 Vitality care pathways | 20 | 20, 12, 21, 350, 72 | Yes | Yes |
| FY2025 risk appetite governance | 64 | 64, 63, 65, 119, 131 | Yes | Yes |
| FY2025 Technology Risk | 69 | 69, 12, 54, 19, 107 | Yes | Yes |

Engineering page hits: **7/8 at rank 1; 8/8 within five pages**. This small,
source-inspected set is awaiting owner review and is not a held-out benchmark,
answer accuracy, citation correctness, or the planned 40-question evaluation.

### Observed miss and timing

For the Vitality definition probe, PDF page 70 contains a relevant discussion but
ranks ahead of the definition pages 13 and 359. This illustrates that lexical
relevance alone does not establish that the selected excerpt answers the question.
The miss is preserved for later comparison, rather than hidden by changing cases.

The final local run measured approximately **6.26 seconds** to load and reverify
the index and **1.98-2.87 milliseconds** per in-memory query. This is one local run
over eight cases, not a service latency benchmark. The earlier cache-only load
was faster; it was replaced with source revalidation to close the stale/tampered
cache gap found during review.

## 4. Evidence-card CLI and actual tests

The source-card CLI was exercised with the FY2025 Technology Risk question and
saved five candidate evidence pages to `data/processed/example-evidence.json`:

```bash
.venv/bin/python -m financial_intelligence_copilot.retrieval \
  --index data/processed/retrieval-index.json \
  --doc-id AIA-2025-EN --fiscal-year 2025 \
  --query 'What cybersecurity standards and AI governance arrangements does AIA describe under Technology Risk in its 2025 annual report?' \
  --output data/processed/example-evidence.json
```

Cards use `candidate_evidence_only`, never `verified`, and include the exact
original excerpt and source offsets. The output has no generated answer field.

Final commands actually run:

```bash
.venv/bin/python -m pytest -q > data/processed/phase-3-pytest.log 2>&1
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

Actual final results:

```text
61 passed, 5 warnings in 0.29s
All checks passed!
10 files already formatted
```

The existing PyMuPDF/SWIG deprecation and shutdown warnings remain visible. Tests
cover original spans, stable IDs, empty/failed pages, word windows, source/hash/
page metadata tampering, cached excerpt and policy changes, cross-report
isolation, filtered scoring, no-match behavior, page diversity, year conflicts,
historical-year mentions, CLI round trips, and overwrite refusal.

## 5. Review and next acceptance work

The owner should review the eight candidate cases and their evidence, with at
least five accepted factual cases before the milestone 3 Q&A acceptance claim.
Raw snippets, the index, smoke results, and execution logs stay in the ignored
processed-data directory; public files contain code and concise metadata only.

Next work is a grounded answering/refusal layer that accepts only retrieved
evidence IDs, distinguishes facts from explanation, rejects unsupported claims,
and preserves original source cards. Model/provider selection and any external
API cost must be confirmed before model calls. Semantic retrieval, bilingual
queries, table interpretation, and financial comparability remain separate work.
