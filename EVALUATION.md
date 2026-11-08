# Evaluation: actual development runs and pending human judgments

Recorded on 2026-10-31 (Asia/Singapore). Current mode: local verbatim excerpts,
BM25 retrieval and explicit workflow refusals. No embedding model, reranker,
generative model or external model API is involved.

UI update on 2026-11-08: About & Evaluation now validates and displays the
historical after-fix record below, with its original date and null human scores.
Source-data changes reject it; code/configuration differences are labeled as an
older snapshot. Opening the view does not rerun or update this evaluation.

Stage 12 adds a separate reviewed KPI lookup mode. The forty-case results below
still describe the historical original-excerpt workflow. They were not rerun,
extended to the lookup mode or turned into numerical-answer accuracy. Its
source/review gates have separate neutral-fixture tests and real pending-state
probes; no actual human review or semantic score has been recorded.

## What has actually run

The 40-case development suite completed two real runs against the registered
official AIA FY2024/FY2025 PDFs. Each case's proposed source spans were checked
against freshly extracted PDF text. Index loading separately revalidated the
raw files, saved pages, chunk policy and cached evidence index.

All 40 candidate answers/answerability labels remain **pending owner review**.
There are **0 approved gold answers and 0 human-scored cases**. The runs below
are development results, including a repair made after seeing the first run.
They are not held-out measurements or product-owner acceptance.

| Observation | Initial run | After intent-guard repair |
| --- | ---: | ---: |
| Cases completed | 40/40 | 40/40 |
| Runtime errors | 0 | 0 |
| Extractive responses | 12 | 10 |
| Abstentions | 28 | 30 |
| Engineering behavior matches | 36/40 | 40/40 |
| Exact released source spans | 17/17 | 12/12 |
| Cases with span errors | 0 | 0 |
| Proposed evidence-page hit at 1 | 15/28 | 15/28 |
| Proposed evidence-page hit at 5 | 21/28 | 21/28 |
| Approved gold / human-scored cases | 0 / 0 | 0 / 0 |

**Answer correctness, numerical correctness, citation relevance and abstention
correctness are all unavailable (`null`).** Exact source text can be incomplete
or irrelevant. A current-workflow refusal can match software behavior without
being the desired final product answer. The table must not be relabeled as
answer accuracy, citation accuracy or financial correctness.

## Suite and evidence proposals

The frozen candidate suite is `data/evaluation_cases.json`:

| Category | Cases | Current product behavior being exercised |
| --- | ---: | --- |
| Simple facts | 10 | Selected-report original excerpts; relevance and completeness need human review |
| Financial numbers | 10 | Refuse verified-KPI answers while actual candidate values remain unapproved |
| Table / financial basis | 8 | Preserve the current verified-KPI workflow boundary; definition answers are proposed separately |
| Cross-year comparison | 7 | Refuse while facts/comparability/reviewed-store integration are pending |
| Boundary / trap cases | 5 | Unsupported subject, fabricated page, conflicting report year, prediction and investment advice |

Cases distinguish proposed document answerability from current-mode support.
For example, a number can be present in an annual report while unavailable as an
approved financial answer in this application. Matching that refusal does not
demonstrate numerical correctness or correct abstention in the final MVP.

The suite contains 55 exact short evidence spans. These are source-location
proposals, not exhaustive gold evidence sets. Numeric candidates retain their
existing source hashes/pages; no actual growth calculation was proposed for the
comparison questions. The two reports are already registered in the manifest;
neither raw report nor full extracted text is redistributed by this repository.

Several questions reuse earlier development probes. The additional questions
and all observed failures are also now exposed to development. No subset is
claimed as held out. Later evaluation should report that exposure and collect
new independent acceptance cases if a held-out claim is needed.

## Method and denominators

- **Engineering behavior:** expected response status and reason, explicitly
  authored for the current mode. All 40 cases remain in the denominator,
  including exceptions and mismatches.
- **Source spans:** reconstruct each released quote from evidence IDs and exact
  original offsets; compare text, source document/year/page/hash/URL. No excerpt
  means not applicable, not a passed citation. Case-level format/scope/span errors
  are recorded separately.
- **Proposed page hits:** compare document, fiscal year and physical page against
  the draft evidence locations. Eligible cases are the 28 single-report questions
  with evidence proposals. Seven cross-report questions and five source-free
  boundary probes are excluded. A valid alternative page can be absent from the
  draft list; human review must resolve that before these become gold hit rates.
- **Errors:** keep every case row and raw response/error. Expected report-scope
  rejection is distinguished from unexpected diagnostic retrieval failure.
- **Human judgment:** keep all semantic metrics null until actual gold approval
  and human response scoring are recorded separately.

The CLI's exit status 0 means artifacts were produced without runtime/span or
unexpected diagnostic errors. It does not mean every engineering expectation
matched or that answers were correct. Status 1 retains a completed raw run with
such software errors; status 2 is an input/source/snapshot/publication failure.

## Observed failures and limitations

The initial run exposed four behavior mismatches:

| Case | Initial issue | Repair / remaining limit |
| --- | --- | --- |
| `numeric-05`, `numeric-10` | The `VONB_MARGIN` identifier bypassed the KPI intent rule; regional/context excerpts were released instead of the current unverified-KPI refusal | Intent matching now treats underscores as separators. Original queries and quoted evidence remain unchanged. |
| `compare-06`, `compare-07` | FY-prefixed years missed the comparison rule and fell through to the ordinary KPI refusal | Comparison rules now recognize FY-prefixed years. Both remain abstentions; no real YoY was computed. |

Eight neutral-fixture regressions cover these forms. The same development suite
was then rerun; the first run and its review packet remain unchanged. The second
run is a repair check on observed cases, not independent validation.

The seven proposed evidence-page misses at rank 5 remain:
`numeric-06`, `numeric-07`, `numeric-08`, `numeric-09`, `table-02`, `table-04`,
`table-05`. They concern candidate financial values and table/basis locations.
Retrieval ranking was not tuned in this stage. The single-report BM25 baseline
does not yet provide reliable table-specific retrieval or semantic paraphrases.

Some multi-part factual responses still cover only part of the proposed answer.
For example, the Three Lines excerpt names the functions without their full
responsibilities; the Technology Risk excerpt omits some proposed cybersecurity
standards. Some output pages differ from the proposed evidence pages and may be
valid alternatives. Neither matching status nor an intact quote resolves these
semantic questions.

## Actual timing and provenance

The after-fix run recorded:

- Proposed-suite source validation: **0.262 s**.
- Full index/source verification at startup: **6.200 s**.
- Median per-case total: **0.00465 s**.
- Nearest-rank p95 per-case total: **0.05468 s**.

Per-case totals include a separate diagnostic search plus the answer path and
source-span check. The answer path already searches internally; the diagnostic
time is additional measurement work, not an estimate of ordinary UI latency.
Startup validation is reported separately. These are observed local-machine
timings, without a model/network call, not a production latency guarantee.

Every run records a suite snapshot/digest, all case and response digests,
Python/PyMuPDF versions, source/cache/policy/config/code fingerprints and actual
latencies. Dependency bytes are compared before and after execution; a changing
snapshot is not published. The pending human packet binds run ID/digest, suite,
case and response content. Digests establish content identity, not human identity.

## Reproduce and review

From the installed project environment with the registered local PDFs and index:

```bash
.venv/bin/python scripts/run_evaluation.py \
  --output data/processed/evaluation.rerun.json \
  --review-output data/processed/human-review.rerun.json
```

Choose fresh output filenames. Raw runs/review packets include local report
excerpts and remain Git-ignored. The actual files from this stage are:

```text
data/processed/phase-8-evaluation.json
data/processed/phase-8-human-review.json
data/processed/phase-8-evaluation.after-fix.json
data/processed/phase-8-human-review.after-fix.json
```

Follow `docs/evaluation-review-guide.md` to approve or correct proposed answers
and assess the corresponding frozen responses. Human scores must not be filled
from page-hit, status or string-overlap checks. The separate KPI verification and
comparability gate also remains pending.
