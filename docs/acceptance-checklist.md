# Product-owner acceptance worksheet

Status updated on 2026-11-08. Engineering records are available; the full MVP is
not accepted. This worksheet is a starting point for actual review, not a record
of completed owner checks. Leave each owner item open until an explicit decision
is recorded with its qualifications.

## Current evidence and open decisions

| Area | Current engineering evidence | Owner acceptance / remaining work |
| --- | --- | --- |
| Sources and pages | Two registered local official reports; page parsing and physical-page provenance recorded | Report/source and context acceptance pending |
| Factual excerpts | Local report-scoped retrieval, exact-span cards, original-text answers and explicit refusals | At least five factual cases must be reviewed for relevance and completeness |
| KPI facts | Ten source-backed candidates, separate reviewed store and bounded source-checked lookup mode/CLI | 0/10 fact confirmations; real-data store is empty and actual lookups abstain |
| Comparisons | Separate pair decisions, readiness/source UI and conditional Plotly charts, tested with neutral fixtures | 0/5 actual pairs approved or calculated; real inputs need owner review |
| Evaluation | Forty development cases, two actual runs, frozen source/run/response digests | 0/40 approved gold answers and 0 human-scored responses; semantic scores unavailable |
| Portfolio | English README, PRD, architecture, evaluation record and scripted demonstration | Final demonstration/recording and product acceptance pending |

Read [PRD](../PRD.md) for the product criteria,
[architecture](../ARCHITECTURE.md) for implemented boundaries, and
[evaluation](../EVALUATION.md) for actual measurements and limitations.

## 1. Review five factual cases first

Start the [local preview](http://127.0.0.1:8501) with the README command. Select
the indicated year and use the exact question from `data/evaluation_cases.json`.
Inspect the actual source card and the complete relevant PDF page. A page match
alone is insufficient: the excerpt must address the question and retain needed
context.

| Case | Selected report | Topic | Proposed physical PDF page |
| --- | --- | --- | ---: |
| `fact-01` | FY2024 | AIA Vitality definition | 359 |
| `fact-04` | FY2024 | Compliance Policy coverage | 134 |
| `fact-07` | FY2025 | Vitality care pathways | 20 |
| `fact-08` | FY2025 | Risk Appetite / Risk Management Framework responsibility | 64 |
| `fact-10` | FY2025 | Employee-engagement survey and frequency | 20 |

The actual response can cite a valid alternative page; for example, the recorded
`fact-10` response uses physical page 68. Record whether that alternative supports
the complete answer rather than automatically failing a different page. Coverage
may also be partial. Use the [evaluation review guide](evaluation-review-guide.md)
and the frozen after-fix packet for your notes.

- [ ] Verify selected report year and source identity.
- [ ] Verify physical page and original wording.
- [ ] Judge relevance, completeness and any omitted qualification for each case.
- [ ] Record confirmed/corrected case IDs and actual reviewer/time separately.

## 2. Review facts and comparability separately

Use [the KPI guide](kpi-review-guide.md). Candidate IDs are
`AIA-{2024|2025}-{VONB|ANP|VONB_MARGIN|OPAT|UFSG}`. The interface exposes these
as pending candidates and links their source context; it has no approval button.

- [ ] Confirm each selected numeric cell, sign, currency/unit and annual period.
- [ ] Confirm metric definition, consolidated/shareholder/NCI scope and exclusions.
- [ ] Review exchange-rate, tax and restatement issues for each annual pair.
- [ ] State fact approval independently from pair comparability.
- [ ] Record explicit decisions in the source-bound review packet; retain open issues.

Matching prior-year headline cells does not approve comparability. Review records
have content hashes, not authenticated human signatures. The engineering
collaborator can record actual decisions returned by the owner; it cannot infer
approval from an instruction to continue development.

## 3. Approve proposed answers, then assess actual responses

Use the forty-case working packet described in the evaluation guide. Keep the
original suite and raw runs unchanged. Confirm or correct proposed source/answer
labels before assigning semantic judgments to the matching frozen responses.

- [ ] Review gold proposals and alternative evidence pages.
- [ ] Agree a scoring rubric and not-applicable rules before aggregating scores.
- [ ] Assess answer correctness/completeness, citation relevance and numeric meaning.
- [ ] Distinguish an appropriate product-boundary refusal from final document answerability.
- [ ] Keep unresolved/not-applicable judgments null; record actual reviewer/time.
- [ ] Disclose development exposure; add new independent cases for held-out claims.

## Decision format

An owner response can identify only the records actually reviewed, for example:

```text
fact-08: source and answer confirmed; no missing qualification identified.
AIA-2025-OPAT: value/unit/period confirmed; tax comparability remains pending.
table-07: proposed answer needs a qualification; see my correction below.
```

These lines illustrate a response format; they are not actual approvals. The
next engineering step depends on the decisions received: correct proposals,
build reviewed inputs, exercise comparable real-data charts, or compute an agreed human
evaluation. Finished, validated source increments are now authorized for
publication to the existing public GitHub repository. Deployment and paid APIs
remain separately authorized actions; publication never records a financial or
evaluation approval.
