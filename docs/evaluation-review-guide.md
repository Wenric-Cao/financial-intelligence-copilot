# Evaluation review guide

The current suite has 40 development cases with 55 proposed short source spans.
Every answer/answerability proposal is pending owner review. The actual raw run
exists; no human acceptance or semantic accuracy score has been recorded.

## Review materials

| Artifact | Purpose |
| --- | --- |
| `data/evaluation_cases.json` | Frozen draft questions, proposed answers/source spans, scope and current-mode expectations |
| `data/processed/phase-8-evaluation.after-fix.json` | Latest actual responses, retrieved evidence, errors, timings and snapshot fingerprints |
| `data/processed/phase-8-human-review.after-fix.json` | Pending review packet with questions, proposals and actual responses together |
| `EVALUATION.md` | Actual results, observed failures, definitions and limitations |

The first-run files without `.after-fix` remain available for inspecting the four
original behavior mismatches. The latest packet binds the after-fix run ID,
run digest, suite digest, each case digest and each response digest. Preserve the
frozen cases/run files while adding decisions to a separate working copy of the
review packet. The current export has null ratings and reviewer signatures.

## Product-owner workflow

1. Choose a case ID. Read its question and selected document/year. For a
   cross-year case, check both source documents and the financial-basis issue.
2. Open the official source PDF URL in `proposed_evidence`, using physical PDF
   page numbers rather than printed labels. Check the complete relevant page,
   including headings, units, column labels and footnotes.
3. Confirm or correct the proposed answer and its evidence. A literal span match
   proves only that the text exists. Note valid alternative pages and missing
   parts of a multi-part answer.
4. Separately inspect the actual response. Judge relevance, completeness, scope,
   numerical meaning and the appropriateness of a refusal. Keep those judgments
   distinct from the source proposal itself.
5. Record the actual reviewer, timezone-aware review time, decision/ratings and
   explanatory notes in the working packet. Leave unresolved fields null. Send
   corrections by case ID so the engineering collaborator can preserve the
   qualifications and verify artifact bindings before computing any score.

The exported `gold_review.status` begins `pending`. A future accepted or rejected
decision requires actual owner review; filling its name/time does not itself
authenticate identity. The current stage exports pending review material and
does not ingest or automatically grade modified packets. A later scoring step
must validate those decisions and digest bindings before aggregation.

## Judgments to record

| Judgment | Review question |
| --- | --- |
| Gold proposal | Is the proposed answer/answerability label correct and sufficiently supported, including any alternative source pages? |
| Answer correctness | Does the actual response answer this question faithfully? State missing or contradictory parts. |
| Citation relevance | Does each released page/span support the associated answer, rather than merely match the source literally? |
| Numerical correctness | Where a numeric answer is actually provided, are number/sign/unit/currency/period/scope/basis correct? Otherwise leave not applicable. |
| Abstention correctness | Where the response refuses, is that refusal appropriate for the document and the evaluated product mode? Record both aspects if they differ. |

There is no automatic numeric scoring convention in the export yet. Use notes
and leave ratings null where a rubric or answer is unresolved. The engineering
collaborator will formalize the rubric with the owner before calculating semantic
percentages. A missing or not-applicable rating must not become a zero or a pass.

## Important mode distinction

Ten numeric and eight table/basis questions are currently blocked by the
unverified-KPI workflow; seven cross-year questions are blocked by unapproved
comparability and pending product integration. Their sources can still contain
the requested facts. Matching the present software refusal is not proof of
correct final-product abstention, financial correctness or completed MVP work.

The five boundary cases concern an artificial absent marker, fabricated physical
page, report-year conflict, future prediction and investment advice. Their
current-mode expectations are engineering proposals and do not substitute for
human review.

Suggested starting points: `fact-01` and `fact-08` for simple evidence;
`fact-03` and `fact-09` for partial-coverage review; `numeric-05` for the repaired
identifier boundary; `table-07` for tax-basis interpretation; `compare-06` for
currency-basis comparability; `boundary-03` for report-scope conflict. Actual KPI
fact approval remains in the separate [KPI review guide](kpi-review-guide.md).

All 40 cases have been exposed to development, and several were used in earlier
smoke runs. New independent acceptance questions are needed before making any
held-out performance claim. A general instruction to continue development does
not approve gold answers or score responses.
